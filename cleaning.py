"""CONVIVE - data cleaning and transformation (WBS 3.1.3).

Reads data/processed/parquet/ and writes data/processed/clean/<KEY>/<YYYYMM>.parquet (git-ignored).
Rows are never imputed. NA stays NA and a published 0 stays 0, with a flag. Every action is logged.
"""

import pandas as pd

import levels as lv
import loaders as L
import quality as q

WEEKDAY_CASE = " ".join(f"WHEN '{d}' THEN {i}" for i, d in enumerate(lv.WEEKDAY_ORDER))
AGE_SQL = """CASE WHEN edad = 'NA' THEN 'NA'
                  WHEN length(edad) = 4 THEN substr(edad, 1, 2) || '-' || substr(edad, 3, 2) ELSE edad END"""


def _register_lookups(con, incomplete):
    con.register("barrio_lookup_df", lv.barrio_lookup())
    con.execute("CREATE OR REPLACE TEMP TABLE barrio_lookup AS SELECT * FROM barrio_lookup_df")
    gaps = pd.DataFrame({"mes": list(incomplete), "missing_days": list(incomplete.values())},
                        columns=["mes", "missing_days"]).astype({"mes": str, "missing_days": int})
    con.register("gaps_df", gaps)
    con.execute("CREATE OR REPLACE TEMP TABLE month_gaps AS SELECT * FROM gaps_df")
    # T3 flags look across months, so they cannot be computed inside one monthly file.
    t3 = L.parquet_glob("T3")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE t3_partial AS SELECT periodo, origen FROM {t3}
                    GROUP BY 1, 2 HAVING count(DISTINCT pernoctaciones) < 7""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE t3_two_months AS SELECT periodo FROM {t3}
                    GROUP BY 1 HAVING count(DISTINCT mes) > 1""")


def _temporal_sql(column):
    """Parsed date plus normalised weekday columns. Grouped rows ('NA' date) keep NULL."""
    d = f'TRY_CAST("{column}" AS DATE)'
    return f"""{d} AS date,
        CASE isodow({d}) WHEN 1 THEN 'Lunes' WHEN 2 THEN 'Martes' WHEN 3 THEN 'Miércoles' WHEN 4 THEN 'Jueves'
             WHEN 5 THEN 'Viernes' WHEN 6 THEN 'Sábado' WHEN 7 THEN 'Domingo' END AS weekday,
        isodow({d}) - 1 AS weekday_idx, isodow({d}) >= 6 AS is_weekend, isoyear({d}) AS iso_year, week({d}) AS iso_week"""


def _clean_month(con, key, path, destination):
    """Write one clean month. Returns (rows in, rows out)."""
    src = q._read(path)
    dims = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()]
    n_in = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    quoted = ", ".join(f'"{c}"' for c in dims)
    month = path.stem
    extra = [f"CAST(substr(source_month, 1, 4) AS INTEGER) AS year",
             f"CAST(substr(source_month, 5, 2) AS INTEGER) AS month_num",
             "coalesce(g.missing_days, 0) AS missing_days_in_month",
             "coalesce(g.missing_days, 0) > 0 AS incomplete_month"]
    joins = "LEFT JOIN month_gaps g ON g.mes = s.source_month"

    if key == "M3":
        # Not simple copies (see 3.1.2): keep every row and flag them. Consumers decide once the mentor answers.
        keys = "day, origen, municipio_origen, barrio_origen, municipio_destino, barrio_destino"
        base = f"""SELECT *, count(*) OVER (PARTITION BY {keys}) AS key_rows,
                          row_number() OVER (PARTITION BY {keys}, viajes) > 1 AS is_exact_repeat FROM {src}"""
    else:
        base = f"SELECT DISTINCT {quoted} FROM {src}"

    if key in L.MOBILITY_KEYS:
        extra.append(_temporal_sql("day"))
        extra.append("viajes = 0 AS is_censored_zero")
    if key in ("M1", "M3"):
        for side, alias in (("origen", "lo"), ("destino", "ld")):
            joins += f" LEFT JOIN barrio_lookup {alias} ON {alias}.cod_barrio = s.barrio_{side}"
            extra += [f"{alias}.cod_barrio_map AS barrio_{side}_map", f"{alias}.distrito AS distrito_{side}",
                      f"{alias}.distrito_name AS distrito_{side}_name"]
    if key in ("T2", "T5"):
        extra.append(_temporal_sql("date_dt"))
    if key in ("T4", "T5", "T6", "T7", "T8", "T9"):
        joins += " LEFT JOIN barrio_lookup b ON b.cod_barrio = s.cod_barrio"
        extra += ["b.cod_barrio_map", "b.barrio_name", "b.distrito", "b.distrito_name"]
    if key == "T9":
        extra.append(f"{AGE_SQL} AS edad_group")
    if key == "T3":
        extra += ["split_part(periodo, ' | ', 1)::DATE AS week_start", "split_part(periodo, ' | ', 2)::DATE AS week_end",
                  "(s.periodo, s.origen) IN (SELECT periodo, origen FROM t3_partial) AS partial_week",
                  "s.periodo IN (SELECT periodo FROM t3_two_months) AS week_in_two_months"]
    if key.startswith("T"):
        text = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {src}").fetchall()
                if r[1] == "VARCHAR" and r[0] != "source_month"]
        extra.append("(" + " OR ".join(f"s.\"{c}\" = 'NA'" for c in text) + ") AS is_grouped_na")

    tmp = destination.with_suffix(".tmp")
    con.execute(f"""COPY (SELECT s.*, {', '.join(extra)} FROM ({base}) s {joins})
                    TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 500000)""")
    tmp.replace(destination)
    return n_in, con.execute(f"SELECT count(*) FROM {q._read(destination)}").fetchone()[0], month


def clean_all(con, incomplete, keys=None, force=False, verbose=True):
    """Clean every dataset. Idempotent: skips a month if its clean file is newer than its Parquet."""
    _register_lookups(con, incomplete)
    totals = {}
    for key in keys or L.ALL_KEYS:
        out_dir = L.CLEAN_DIR / key
        out_dir.mkdir(parents=True, exist_ok=True)
        rows_in = rows_out = 0
        for path in q._files(key):
            destination = out_dir / path.name
            if destination.exists() and destination.stat().st_mtime > path.stat().st_mtime and not force:
                rows_in += con.execute(f"SELECT count(*) FROM {q._read(path)}").fetchone()[0]
                rows_out += con.execute(f"SELECT count(*) FROM {q._read(destination)}").fetchone()[0]
                continue
            a, b, _ = _clean_month(con, key, path, destination)
            rows_in += a
            rows_out += b
        totals[key] = (rows_in, rows_out)
        if verbose:
            print(f"{key}: {rows_in:,} rows in, {rows_out:,} rows out", flush=True)
    return totals


def cleaning_log(con, totals):
    """Every action with dataset, rule, rows affected and reason. Counted on the clean files."""
    rows = []

    def add(dataset, rule, affected, reason):
        rows.append({"dataset": dataset, "rule": rule, "rows affected": f"{affected:,}", "reason": reason})

    for key, (a, b) in totals.items():
        if key == "M3":
            n_rep, n_key = con.execute(f"""SELECT sum(is_exact_repeat::BIGINT), sum((key_rows > 1)::BIGINT)
                                           FROM {L.parquet_glob(key, 'clean')}""").fetchone()
            add(key, "Exact duplicates NOT dropped; flagged `is_exact_repeat`", int(n_rep),
                "Deviation from the plan. Rows sharing a key usually have different values, so an identical pair can be two real segments. "
                "M3 is not used in Q1 to Q6. Decision pending the mentor")
            add(key, "Rows sharing a key flagged with `key_rows`", int(n_key), "The file seems to have a dimension that is not in the description")
        else:
            add(key, "Drop exact duplicates", a - b, "Double counting (C1)" if a - b else "Checked: none found")
    for key in ("M1", "M3"):
        n = con.execute(f"SELECT count(*) FROM {L.parquet_glob(key, 'clean')}").fetchone()[0]
        unmatched = con.execute(f"""SELECT sum((distrito_origen IS NULL AND barrio_origen <> '-')::BIGINT),
                                           sum((distrito_destino IS NULL AND barrio_destino <> '-')::BIGINT)
                                    FROM {L.parquet_glob(key, 'clean')}""").fetchone()
        add(key, "Apply neighbourhood correspondence (district and map code added)", n,
            f"Iteration 1 code rule matched only part of the map (2.1.1). Unmatched real codes: origin {unmatched[0] or 0}, destination {unmatched[1] or 0}")
    for key in ("T4", "T5", "T6", "T7", "T8", "T9"):
        n, grouped, unmatched = con.execute(f"""SELECT count(*), sum((cod_barrio = 'NA')::BIGINT),
            sum((barrio_name IS NULL AND cod_barrio <> 'NA')::BIGINT) FROM {L.parquet_glob(key, 'clean')}""").fetchone()
        add(key, "Apply neighbourhood correspondence (name and district added)", n,
            f"{grouped or 0:,} rows have the grouped code NA and stay unassigned. Unmatched real codes: {unmatched or 0}")
    for key in L.MOBILITY_KEYS + ["T2", "T5"]:
        n = con.execute(f"SELECT count(*) FROM {L.parquet_glob(key, 'clean')} WHERE weekday IS NOT NULL").fetchone()[0]
        add(key, "Harmonise weekday (name, index, weekend flag, ISO week) from the calendar date", n,
            "One spelling with accents, verified against the calendar (2.1.2)")
    for key in L.MOBILITY_KEYS:
        n = con.execute(f"SELECT sum(is_censored_zero::BIGINT) FROM {L.parquet_glob(key, 'clean')}").fetchone()[0]
        add(key, "Flag published zeros `is_censored_zero`; value stays 0", int(n or 0), "A 0 means fewer than 15 trips, not no trips")
    n = con.execute(f"SELECT sum((edad <> 'NA')::BIGINT) FROM {L.parquet_glob('T9', 'clean')}").fetchone()[0]
    add("T9", "Harmonise age group (`1829` becomes `18-29` in `edad_group`)", int(n), "The files use another format than the description")
    for key in L.TOURISM_KEYS:
        n = con.execute(f"SELECT sum(is_grouped_na::BIGINT) FROM {L.parquet_glob(key, 'clean')}").fetchone()[0]
        add(key, "Keep NA as NA; flag `is_grouped_na`", int(n or 0), "Segments below 15 people. Never read as 0 visitors")
    for key in L.ALL_KEYS:
        n = con.execute(f"SELECT sum(incomplete_month::BIGINT) FROM {L.parquet_glob(key, 'clean')}").fetchone()[0]
        add(key, "Flag `incomplete_month` (month with missing days)", int(n or 0), "Monthly values of those months may be lower than the full month")
    n = con.execute(f"SELECT sum(partial_week::BIGINT) FROM {L.parquet_glob('T3', 'clean')}").fetchone()[0]
    add("T3", "Flag `partial_week` (fewer than 7 night values)", int(n or 0), "Weeks that contain a missing day")
    n = con.execute(f"SELECT sum(week_in_two_months::BIGINT) FROM {L.parquet_glob('T3', 'clean')}").fetchone()[0]
    add("T3", "Flag `week_in_two_months`", int(n or 0), "The same week appears under two months; excluded from the T3 distribution")
    for key in L.TOURISM_KEYS:
        add(key, "Rename to the official column names", 0 if key != "T8" else totals[key][1],
            "`pais_residencia` becomes `pais_Residencia`" if key == "T8" else "No change needed")
    for key in L.MOBILITY_KEYS:
        add(key, "Rename to the official column names", totals[key][1], "`day_of_week` becomes `day_of_the_week`")
    return pd.DataFrame(rows)


def write_log(log, totals):
    rows = pd.DataFrame([{"dataset": k, "rows in": f"{a:,}", "rows out": f"{b:,}"} for k, (a, b) in totals.items()])
    return q.write_md("3.1.3_cleaning_log.md", f"""
# 3.1.3 Data cleaning and transformation: cleaning log

CONVIVE · Team 102_A · Iteration 2. Generated by `cleaning.py`. The clean data are in `data/processed/clean/` (git-ignored) and are **not** a deliverable (NDA).

Principles: no imputation, NA stays NA, a published 0 stays 0 with a flag, and no value is changed.

## Rows in and out

{q.md_table(rows)}

## Actions

{q.md_table(log)}
""")
