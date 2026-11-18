"""CONVIVE - aggregated data validation (WBS 2.2.2, Iteration 3).

Checks the aggregated tables of 2.2.1 (and the 3.1.6 tables they extend) before any analysis uses them:
totals against an independent path, unique visitors never summed into people, coverage, zeros and the privacy rule.

    python validation.py        writes deliverables/iteration3/2.2.2_validation_log.md and .csv

Exit code 1 if a blocking check fails.
"""

import sys
from datetime import date

import numpy as np
import pandas as pd

import research as R

OUT_MD = R.OUT / "2.2.2_validation_log.md"
OUT_CSV = R.OUT / "2.2.2_validation_log.csv"
COUNT_COLUMNS = {"n_flows", "n_zero", "n_flows_zero", "rows", "rows_grouped_na", "periods_with_data", "days", "n_days", "months",
                 "months_present", "months_in_year", "n_barrios", "n_segments", "rows_below_100", "n_weeks", "pernoctaciones"}


class Log:
    def __init__(self):
        self.rows = []

    def add(self, area, check, passed, evidence, blocking=True, action="None needed"):
        self.rows.append({"#": len(self.rows) + 1, "area": area, "check": check,
                          "result": "PASS" if passed else ("FAIL" if blocking else "WARN"), "evidence": evidence, "action": action})
        return passed


def raw_csv(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def check_privacy(log):
    """No exported number below 15 in any aggregated table (counts of rows/days are not people or trips)."""
    bad = []
    files = sorted(R.AGG.glob("*.csv")) + sorted(R.STATS.glob("*.csv"))
    for path in files:
        df = raw_csv(path)
        for col in df.columns:
            if col in COUNT_COLUMNS or col.startswith(("share", "change", "n_months", "visitor_share", "gini", "top10", "is_", "vs_", "rows_vs")):
                continue
            values = pd.to_numeric(df[col], errors="coerce")
            if values.notna().mean() < 0.5:          # text column
                continue
            if col in ("year", "month", "weekday_idx", "mes", "cod_barrio", "barrio_origen", "barrio_destino", "distrito",
                       "cod_municipio_residencia"):
                continue
            n = int(((values > 0) & (values < 15)).sum())
            if n:
                bad.append(f"{path.name}:{col} ({n})")
    log.add("Privacy", "No exported count of people or trips between 1 and 14 (written as <15)", not bad,
            f"{len(files)} tables scanned; " + ("violations: " + ", ".join(bad) if bad else "0 violations"),
            action="Apply the threshold in the generating function" if bad else "None needed")


def check_trips_two_paths(log, t):
    """M1 trips: the 2.2.1 path (raw CSV, pandas) must equal the 3.1.6 path (clean Parquet, DuckDB)."""
    od = t["od"].dropna(subset=["viajes"])
    a = od.groupby(["year", "origen"])["viajes"].sum()
    b = t["trips"].groupby(["year", "origen"])["viajes"].sum()
    joined = pd.concat([a.rename("aggregates_2_2_1"), b.rename("stats_3_1_6")], axis=1)
    diff = (joined["aggregates_2_2_1"] - joined["stats_3_1_6"]).abs().max()
    total = joined["stats_3_1_6"].sum()
    log.add("Totals", "M1 trips per year and origin are identical through two independent paths (raw CSV with pandas vs clean "
            "Parquet with DuckDB)", diff == 0, f"{len(joined)} year x origin totals, {total:,.0f} trips; largest difference {diff:,.0f}")
    zero_a = t["od"]["n_zero"].sum() / t["od"]["n_flows"].sum()
    zero_b = t["trips"]["n_flows_zero"].sum() / t["trips"]["n_flows"].sum()
    log.add("Zeros", "Share of published zero flows (<15 trips) is the same in both paths", abs(zero_a - zero_b) < 1e-9,
            f"{zero_a:.4%} vs {zero_b:.4%}. Zeros stay 0 with a flag; they are never read as 'no trips'")


def check_not_summed(log, t):
    """Unique visitors: no neighbourhood value above the city value; presences above people (proves they are not people)."""
    city = t["city_monthly"].groupby(["mes", "origen", "tipo_visitante"])["visitantes"].sum()
    barrio = t["barrio_monthly"].dropna(subset=["visitantes"]).groupby(["mes", "origen", "tipo_visitante"])["visitantes"]
    joined = pd.concat([city.rename("city"), barrio.max().rename("max_barrio"), barrio.sum().rename("sum_barrios")], axis=1).dropna()
    ok = (joined["max_barrio"] <= joined["city"]).all()
    log.add("Not additive", "T4: the largest neighbourhood never exceeds the city value of T1 (same month, origin and type)", ok,
            f"{len(joined)} month x segment cells; max ratio {joined['max_barrio'].div(joined['city']).max():.3f}")
    ratio = joined["sum_barrios"] / joined["city"]
    log.add("Not additive", "T4: summing neighbourhoods gives MORE than the city people (so sums are labelled presences, never people)",
            (ratio > 1).all(), f"sum of neighbourhoods / city people: median {ratio.median():.2f}, range {ratio.min():.2f}-{ratio.max():.2f}")

    t1i = t["city_monthly"][t["city_monthly"]["origen"] == "Internacional"].groupby(["mes", "tipo_visitante"])["visitantes"].sum()
    t8 = t["t8_city"].groupby(["mes", "tipo_visitante"]).agg(presences=("presences", "sum"))
    t8_max = t["t8_city"].groupby(["mes", "tipo_visitante"])["max_barrio"].max()
    joined = pd.concat([t1i.rename("t1"), t8["presences"], t8_max.rename("max")], axis=1).dropna()
    log.add("Not additive", "T8: country presences >= T1 international people, and the largest single neighbourhood-country cell <= T1",
            bool((joined["presences"] >= joined["t1"]).all() and (joined["max"] <= joined["t1"]).all()),
            f"{len(joined)} month x type cells; presences / people median {(joined['presences'] / joined['t1']).median():.2f}")

    t2 = t["city_daily"].groupby(["date", "origen"])["visitantes"].sum()
    t5 = t["t5"].dropna(subset=["visitantes"]).groupby(["date", "origen"])["visitantes"].max()
    t2.index = t2.index.set_levels([t2.index.levels[0].astype(str), t2.index.levels[1]])
    joined = pd.concat([t2.rename("city"), t5.rename("max_barrio")], axis=1).dropna()
    log.add("Not additive", "T5: the largest neighbourhood of each day never exceeds the city value of T2", bool((joined["max_barrio"] <= joined["city"]).all()),
            f"{len(joined)} day x origin cells; max ratio {joined['max_barrio'].div(joined['city']).max():.3f}")


def check_coverage(log, t):
    months = {"T6": t["t6_city"], "T7": t["t7_city"], "T8": t["t8_city"], "T9": t["t9_city"]}
    for key, df in months.items():
        n = df["mes"].nunique()
        log.add("Coverage", f"{key}: 32 months present (Jan 2023 to Aug 2025)", n == 32, f"{n} months")
    days = t["t5"]["date"].nunique()
    log.add("Coverage", "T5: 971 days present (974 calendar days minus the 3 days missing in every daily file, I-3.1.2)", days == 971,
            f"{days} days")
    barris = {"T5": t["t5"]["cod_barrio"].nunique(), "M1 destination": t["od"]["barrio_destino"].nunique(),
              "M1 origin": t["od"]["barrio_origen"].nunique(), "coverage table": t["coverage"]["cod_barrio"].nunique()}
    log.add("Coverage", "73 neighbourhoods in every neighbourhood table", all(v == 73 for v in barris.values()),
            ", ".join(f"{k} {v}" for k, v in barris.items()))
    names = R.read(R.AGG / "m1_name_check.csv")
    ok = names["matches"].str.lower().eq("true").all()
    log.add("Coverage", "M1 names equal the 2.1.1 code-to-name correspondence in every month (73 of 73)", ok,
            f"{int(names['matches'].str.lower().eq('true').sum())} of {len(names)} codes match")


def check_na(log, t):
    na = {k: float((t[k][c] == "NA").mean()) for k, c in [("t8_city", "country"), ("t7_city", "province"), ("t6_city", "municipality")]}
    log.add("Grouped NA", "Grouped NA segments are kept as their own category, never dropped or read as 0", all(v > 0 for v in na.values()),
            "share of rows that are the NA group: " + ", ".join(f"{k[:2].upper()} {v:.2%}" for k, v in na.items()))
    t9 = t["t9_city"]
    intl = int((t9["origen"] == "Internacional").sum())
    log.add("Known issue", "T9 contains international visitors, as the data description says (issue I9 if not)", intl > 0,
            f"{intl} international rows in T9", blocking=False, action="Q14 answered for national and regional only; ask the BM")


def check_t3(log, t):
    df = t["overnight"]
    sums = df.groupby(["year", "origen"])["share_of_year_origin"].sum()
    log.add("Consistency", "T3: the distribution of nights adds up to 100% for each year and origin", bool(np.allclose(sums, 1, atol=0.002)),
            f"{len(sums)} year x origin groups; min {sums.min():.4f}, max {sums.max():.4f}")


def main():
    t = R.load_all()
    log = Log()
    check_privacy(log)
    check_trips_two_paths(log, t)
    check_not_summed(log, t)
    check_coverage(log, t)
    check_na(log, t)
    check_t3(log, t)
    table = pd.DataFrame(log.rows)
    R.OUT.mkdir(parents=True, exist_ok=True)
    table.to_csv(OUT_CSV, index=False)
    passed = (table["result"] == "PASS").sum()
    failed = (table["result"] == "FAIL").sum()
    lines = ["# 2.2.2 Aggregated data validation log", "",
             f"CONVIVE · Team 102_A · Iteration 3 · generated by `validation.py` on {date.today():%d %b %Y}. "
             "Input: the 2.2.1 aggregated tables and the 3.1.6 statistics. No raw data are read here.", "",
             f"**Result: {passed} of {len(table)} checks passed, {failed} failed, {len(table) - passed - failed} warnings.**", "",
             "| # | Area | Check | Result | Evidence | Action |", "|---|---|---|---|---|---|"]
    for r in log.rows:
        lines.append(f"| {r['#']} | {r['area']} | {r['check']} | **{r['result']}** | {r['evidence']} | {r['action']} |")
    lines += ["", "## What the checks prove", "",
              "- The aggregation of 2.2.1 reads the raw CSV files with pandas; the statistics of 3.1.6 read the cleaned Parquet with DuckDB. "
              "Identical trip totals through both paths show that neither the conversion nor the cleaning lost or duplicated rows.",
              "- Sums of unique visitors across neighbourhoods are always larger than the city figure, so they cannot be people. "
              "Every such sum is named `presences` (person x neighbourhood) in the tables and in the dashboard.",
              "- No table contains a count of people or trips from 1 to 14: the privacy threshold of the NDA holds in every exported file."]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Validation: {passed}/{len(table)} passed, {failed} failed")
    print(table[["#", "check", "result", "evidence"]].to_string(index=False))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
