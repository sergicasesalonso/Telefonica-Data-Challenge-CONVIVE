"""CONVIVE - loaders for the real Smart Steps data (WBS 3.1.1 / 3.1.7).

The real data are delivered as monthly folders:

    data/output_limite_legal_mobilidad/YYYY-MM/movilidad_<kind>_YYYY-MM_origen.csv   (M1, M2, M3)
    data/output_limite_legal_turismo/YYYYMM/<dataset>.csv                            (T1 ... T9)

16 GB of CSV do not fit in pandas, so each CSV is converted once to Parquet with DuckDB, and every later
step reads Parquet. The conversion is idempotent: a file is skipped when its Parquet exists and is newer.

    python -m loaders build            convert everything
    python -m loaders build --force    convert everything again

Everything under data/ is git-ignored.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

import convive as cv

HERE = Path(__file__).parent
MOBILITY_DIR = HERE / "data" / "output_limite_legal_mobilidad"
TOURISM_DIR = HERE / "data" / "output_limite_legal_turismo"
PROCESSED_DIR = HERE / "data" / "processed"
PARQUET_DIR = PROCESSED_DIR / "parquet"
CLEAN_DIR = PROCESSED_DIR / "clean"
MANIFEST = PARQUET_DIR / "_manifest.json"

MOBILITY_KEYS = ["M1", "M2", "M3"]
TOURISM_KEYS = ["T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9"]
ALL_KEYS = MOBILITY_KEYS + TOURISM_KEYS

# Column names in the real files that differ from the official description (convive.SCHEMAS).
# The Parquet files use the official names, so all later code has a single vocabulary.
COLUMN_RENAMES = {"day_of_week": "day_of_the_week", "pais_residencia": "pais_Residencia"}

# Stored as numbers. Every other column stays text, so leading zeros are kept ("08019", "080190101").
INTEGER_COLUMNS = {"viajes", "visitantes", "pernoctaciones"}


def expected_months():
    """The 32 months of the challenge as 'YYYYMM'."""
    return [p.strftime("%Y%m") for p in pd.period_range(cv.PERIOD_START, cv.PERIOD_END, freq="M")]


def _month_id(month):
    """Accept 202301, '202301' or '2023-01' and return 'YYYYMM'."""
    text = str(month).replace("-", "")
    if len(text) != 6 or not text.isdigit():
        raise ValueError(f"Month must look like 202301 or 2023-01, got {month!r}")
    return text


def csv_path(key, month):
    """Path of the CSV of one dataset and month (it may not exist)."""
    month = _month_id(month)
    name = cv.SCHEMAS[key]["file"]
    if key in MOBILITY_KEYS:
        dashed = f"{month[:4]}-{month[4:]}"
        return MOBILITY_DIR / dashed / f"{name}_{dashed}_origen.csv"
    return TOURISM_DIR / month / f"{name}.csv"


def parquet_path(key, month, root=None):
    return (root or PARQUET_DIR) / key / f"{_month_id(month)}.parquet"


def connect(memory_limit="8GB", threads=None):
    """DuckDB connection that spills to data/processed/tmp instead of the system temp folder."""
    tmp = PROCESSED_DIR / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{memory_limit}'")
    con.execute(f"SET temp_directory='{tmp.as_posix()}'")
    con.execute("SET preserve_insertion_order=false")
    if threads:
        con.execute(f"SET threads={int(threads)}")
    return con


def _sql_str(value):
    return "'" + str(value).replace("'", "''") + "'"


def detect_format(path, sample_bytes=2_000_000):
    """Detect separator, encoding, header, BOM and line ending of one CSV. No assumptions."""
    with open(path, "rb") as fh:
        raw = fh.read(sample_bytes)
    bom = raw.startswith(b"\xef\xbb\xbf")
    if bom:
        raw = raw[3:]
    if len(raw) == sample_bytes:          # do not judge a character cut at the end of the sample
        raw = raw[: raw.rfind(b"\n") + 1]
    try:
        text, encoding = raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        text, encoding = raw.decode("latin-1"), "latin-1"
    lines = text.splitlines()
    header = lines[0] if lines else ""
    counts = {sep: header.count(sep) for sep in (";", ",", "\t", "|")}
    sep = max(counts, key=counts.get)
    columns = [c.strip().strip('"') for c in header.split(sep)]
    return {"sep": sep, "encoding": encoding + ("-bom" if bom else ""),
            "newline": "CRLF" if b"\r\n" in raw else "LF",
            "has_header": all(not c.isdigit() for c in columns), "columns": columns}


def _convert_one(con, key, month, fmt):
    """Convert one monthly CSV. Text columns stay text; measures go through TRY_CAST so that any
    non-numeric value becomes NULL and is counted, never silently turned into a number."""
    src = csv_path(key, month)
    dst = parquet_path(key, month)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    select = []
    for col in fmt["columns"]:
        out = COLUMN_RENAMES.get(col, col)
        if out in INTEGER_COLUMNS:
            select.append(f'TRY_CAST("{col}" AS BIGINT) AS "{out}"')
        else:
            select.append(f'"{col}" AS "{out}"')
    select.append(f"'{_month_id(month)}' AS source_month")
    encoding = "latin-1" if fmt["encoding"].startswith("latin") else "utf-8"
    reader = (f"read_csv({_sql_str(src.as_posix())}, delim={_sql_str(fmt['sep'])}, header=true, "
              f"all_varchar=true, quote='\"', encoding='{encoding}', auto_detect=true, sample_size=1000)")
    con.execute(f"COPY (SELECT {', '.join(select)} FROM {reader}) TO {_sql_str(tmp.as_posix())} "
                "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 500000)")
    tmp.replace(dst)
    rows = con.execute(f"SELECT count(*) FROM read_parquet({_sql_str(dst.as_posix())})").fetchone()[0]
    return rows


def build_parquet(keys=None, force=False, verbose=True):
    """Convert every CSV to data/processed/parquet/<KEY>/<YYYYMM>.parquet. Returns the manifest.

    Idempotent: a file is skipped if its Parquet exists and is newer than the CSV (unless force=True).
    The manifest stores what was detected per file; it holds only sizes, counts and formats.
    """
    keys = keys or ALL_KEYS
    PARQUET_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    con = connect()
    converted = skipped = 0
    started = time.time()
    # Tourism first: small, so problems surface early.
    for key in sorted(keys, key=lambda k: (k.startswith("M"), k)):
        for month in expected_months():
            src, dst = csv_path(key, month), parquet_path(key, month)
            entry_id = f"{key}/{month}"
            if not src.exists():
                manifest[entry_id] = {"key": key, "month": month, "found": False}
                continue
            up_to_date = dst.exists() and dst.stat().st_mtime > src.stat().st_mtime
            if up_to_date and not force and manifest.get(entry_id, {}).get("rows") is not None:
                skipped += 1
                continue
            fmt = detect_format(src)
            rows = _convert_one(con, key, month, fmt)
            manifest[entry_id] = {"key": key, "month": month, "found": True, "bytes": src.stat().st_size,
                                  "rows": rows, "sep": fmt["sep"], "encoding": fmt["encoding"],
                                  "newline": fmt["newline"], "has_header": fmt["has_header"],
                                  "columns": fmt["columns"]}
            converted += 1
            if verbose:
                print(f"[{time.time() - started:7.0f}s] {entry_id}: {rows:,} rows", flush=True)
            MANIFEST.write_text(json.dumps(manifest, indent=0), encoding="utf-8")
    MANIFEST.write_text(json.dumps(manifest, indent=0), encoding="utf-8")
    con.close()
    if verbose:
        print(f"Done: {converted} converted, {skipped} already up to date, {time.time() - started:.0f}s", flush=True)
    return manifest


def read_manifest():
    return json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}


def parquet_glob(key, stage="raw"):
    """SQL fragment that reads a whole dataset: read_parquet('.../<KEY>/*.parquet')."""
    root = CLEAN_DIR if stage == "clean" else PARQUET_DIR
    return f"read_parquet({_sql_str((root / key / '*.parquet').as_posix())}, union_by_name=true)"


def _load(key, months, columns, where, stage, lazy, con):
    root = CLEAN_DIR if stage == "clean" else PARQUET_DIR
    if not (root / key).exists():
        raise FileNotFoundError(f"No Parquet for {key} in {root}. Run: python -m loaders build")
    con = con or connect()
    if months is None:
        source = parquet_glob(key, stage)
    else:
        paths = [parquet_path(key, m, root) for m in ([months] if isinstance(months, (str, int)) else months)]
        paths = [p.as_posix() for p in paths if p.exists()]
        if not paths:
            raise FileNotFoundError(f"None of the requested months exist for {key}")
        source = f"read_parquet({paths!r}, union_by_name=true)"
    cols = ", ".join(f'"{c}"' for c in columns) if columns else "*"
    sql = f"SELECT {cols} FROM {source}" + (f" WHERE {where}" if where else "")
    return con.sql(sql) if lazy else con.execute(sql).df()


def load_mobility(kind, months=None, columns=None, where=None, stage="raw", lazy=False, con=None):
    """Load mobility data. `kind` is M1/M2/M3 or barrios/municipios/mun_barrios.

    months:  None (all) or a list of months (202301 or '2023-01').
    lazy:    True returns a DuckDB relation instead of a DataFrame. Use it for full-period M2 and M3,
             which do not fit in pandas.
    stage:   'raw' (converted CSV) or 'clean' (output of WBS 3.1.3).
    """
    aliases = {"barrios": "M1", "municipios": "M2", "mun_barrios": "M3"}
    key = aliases.get(kind, kind)
    if key not in MOBILITY_KEYS:
        raise ValueError(f"Unknown mobility dataset: {kind!r}")
    return _load(key, months, columns, where, stage, lazy, con)


def load_tourism(key, months=None, columns=None, where=None, stage="raw", lazy=False, con=None):
    """Load tourism data (T1 ... T9). Same options as load_mobility."""
    if key not in TOURISM_KEYS:
        raise ValueError(f"Unknown tourism dataset: {key!r}")
    return _load(key, months, columns, where, stage, lazy, con)


def _main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="CONVIVE: convert the monthly CSVs to Parquet")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--force", action="store_true", help="convert again even if the Parquet is newer")
    parser.add_argument("--keys", nargs="*", help="only these datasets, e.g. T1 M1")
    args = parser.parse_args(argv)
    build_parquet(keys=args.keys, force=args.force)


if __name__ == "__main__":
    _main()
