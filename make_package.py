"""CONVIVE - builds the hand-over package of the final product (WBS 4.3.2, 3.3.2).

    python make_package.py                code, notebooks, reports and guide
    python make_package.py --with-tables  adds the aggregated tables, figures and screenshots, so the dashboard opens at once.
                                          ONLY for people covered by the NDA (RQ-12).

Raw data and Parquet files (data/, except the open neighbourhood map) are never included. Before writing, every table is
scanned: the package is refused if it holds a count of people or trips from 1 to 14.
"""

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd

import research as R
import validation as V

HERE = Path(__file__).resolve().parent
OUT = HERE / "deliverables" / "final"
GEO = HERE / "data" / "geo" / "barris_bcn.geojson"        # open data (Ajuntament de Barcelona, CC BY 4.0)
TABLE_TYPES = {".csv", ".json", ".png"}


def tracked():
    names = subprocess.run(["git", "ls-files", "-z"], cwd=HERE, capture_output=True, check=True).stdout.decode("utf-8").split("\0")
    return [HERE / n for n in names if n and (HERE / n).is_file()]


def privacy_ok():
    log = V.Log()
    V.check_privacy(log)
    return log.rows[0]["result"] == "PASS", log.rows[0]["evidence"]


def safe(path):
    """Nothing from data/ except the open map."""
    return path == GEO or "data" not in path.relative_to(HERE).parts[:1]


def collect(with_tables):
    files = set(tracked()) | ({GEO} if GEO.exists() else set())
    if with_tables:
        files |= {p for p in (HERE / "deliverables").rglob("*") if p.is_file() and p.suffix.lower() in TABLE_TYPES}
    return sorted(p for p in files if safe(p) and "__pycache__" not in p.parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--with-tables", action="store_true")
    args = parser.parse_args()
    if args.with_tables:
        ok, evidence = privacy_ok()
        print("Privacy scan:", evidence)
        if not ok:
            return 1
    files = collect(args.with_tables)
    name = OUT / ("CONVIVE_FinalProduct_NDA.zip" if args.with_tables else "CONVIVE_FinalProduct_Code.zip")
    with zipfile.ZipFile(name, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, Path("CONVIVE") / path.relative_to(HERE))
    raw = [p for p in files if p.suffix == ".parquet" or "output_limite_legal" in str(p)]
    assert not raw, "raw data in the package"
    groups = pd.Series([p.suffix or "other" for p in files]).value_counts().to_dict()
    print(f"{name.name}: {len(files)} files, {name.stat().st_size / 1e6:.1f} MB, {groups}")
    print("Aggregated tables come from", R.AGG.relative_to(HERE))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
