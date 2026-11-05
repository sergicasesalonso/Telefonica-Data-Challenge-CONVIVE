"""Builds CONVIVE_Iteration2.ipynb (WBS 3.1.7). Execute it with:

    python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=-1 CONVIVE_Iteration2.ipynb

Cell outputs show only counts, ranges, category names and aggregated tables. They never show data rows.
"""

import nbformat as nbf

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

CELLS = [
    md("""# CONVIVE · Iteration 2 (real data)

Team 102_A (Convive Lab) · Mobile Data Challenge 2026 · WBS 3.1.7, switch from synthetic to real data.

This notebook runs the whole Iteration 2 pipeline on the real Smart Steps data, from the monthly CSVs to the aggregated tables the dashboard reads.

**Rules.** The data are under NDA. Outputs show only counts, ranges, category names and aggregated tables. Trips and unique visitors are never combined, unique visitors are never summed across days, months or neighbourhoods, and a 0 or NA never means "nobody". The results describe patterns, not causes."""),
    code("""import pandas as pd
import matplotlib.pyplot as plt

import analysis as an
import cleaning
import convive as cv
import descriptives as ds
import levels as lv
import loaders as L
import quality as q
import run_iteration2 as run

pd.set_option("display.max_colwidth", 110, "display.width", 180, "display.max_rows", 80)
con = L.connect()
print("Geometry file:", cv.GEO_FILE.relative_to(cv.HERE))"""),

    md("""## 1. Parquet build (3.1.1)

16 GB of CSV do not fit in pandas. Each monthly CSV is converted once to Parquet with DuckDB. The step is idempotent: already converted files are skipped."""),
    code("""manifest = L.build_parquet(verbose=False)
found = [e for e in manifest.values() if e.get("found")]
print(f"{len(found)} files, {sum(e['bytes'] for e in found) / 1024 ** 3:.1f} GB of CSV, {sum(e['rows'] for e in found):,} rows")"""),

    md("## 2. Data inventory (3.1.0)"),
    code("""inventory = run.step_inventory(con)
inventory[["dataset", "monthly files found", "missing months", "total size", "total rows", "columns found / expected", "separator", "encoding", "date range"]]"""),

    md("## 3. Inspection (3.1.1)\n\nColumn types, distinct values and shares of NA and zeros. The full version is in `3.1.1_inspection_summary.md`."),
    code("""inspection = run.step_inspect(con)
pd.DataFrame([{"dataset": k, "rows": f"{v['rows']:,}", "columns": len(v["table"])} for k, v in inspection.items()])"""),
    code("""inspection["M1"]["table"]"""),
    code("""inspection["T4"]["table"]"""),

    md("""## 4. Switch from synthetic to real data (3.1.7)

`convive.load(key, mode="real")` now reads the monthly layout through `loaders.py`. `mode="synthetic"` keeps the Iteration 1 behaviour. M2 and M3 need a list of months, because the full period does not fit in pandas."""),
    code("""real_t1, source = cv.load("T1", "real")
print("T1:", source, f"{len(real_t1):,} rows,", real_t1["mes"].nunique(), "months")
real_m1, source = cv.load("M1", "real", months=["2024-07"])
print("M1, one month:", source, f"{len(real_m1):,} rows; columns match the official description:", set(cv.SCHEMAS["M1"]["columns"]) <= set(real_m1.columns))
del real_m1
try:
    cv.load("M3", "real")
except ValueError as error:
    print("M3 without months is refused:", error)

synthetic_t1, source = cv.load("T1", "synthetic")
if synthetic_t1 is None:
    cv.make_synthetic_data()
    synthetic_t1, source = cv.load("T1", "synthetic")
print("Synthetic mode still works:", source, f"{len(synthetic_t1):,} rows")"""),

    md("## 5. Geographic levels (2.1.1) and temporal levels (2.1.2)"),
    code("""levels_table, geo_report, temporal = run.step_levels(con)
print(f"Iteration 1 code rule matches {geo_report['legacy_matches']} of {geo_report['n_map']} neighbourhoods")
print(f"Correspondence by name matches {geo_report['name_matches']} of {geo_report['n_map']}")
geo_report["coverage"]"""),
    code("""print("Missing days:", [str(d) for d in temporal["missing"]])
print("Incomplete months:", temporal["incomplete"])
temporal["periods"]"""),
    code("""geo, barris = cv.load_barris()
fig, ax = plt.subplots(figsize=(6, 6))
cv.plot_map(geo, ax=ax, title="The 73 neighbourhoods by district")
plt.show()"""),

    md("""## 6. Data quality on the real data (3.1.2)

Checks S1 to S4, C1 to C4 and X1 to X3 of `data_review_plan.md`, in SQL so that they also run on M2 and M3. The R1 trigger is evaluated per dataset. The full report is `3.1.2_data_quality_report.md`."""),
    code("""quality_results = run.step_quality(con)
q.r1_assessment(quality_results)"""),
    code("""quality_results["tables"]["M1"]"""),
    code("""quality_results["tables"]["M3"]"""),
    code("""quality_results["tables"]["T4"]"""),
    code("""cross, details = quality_results["cross"]
cross"""),
    md("""Cross-check with the Iteration 1 function: `convive.review()` runs unchanged on the tourism files, which fit in pandas, and on one month of M1."""),
    code("""for key in ["T1", "T4"]:
    frame, _ = cv.load(key, "real")
    print(key)
    display(cv.review_table(cv.review(frame, key, barris)))
frame, _ = cv.load("M1", "real", months=["2024-07"])
print("M1, July 2024")
display(cv.review_table(cv.review(frame, "M1", barris)))
del frame"""),

    md("## 7. Cleaning (3.1.3)\n\nWrites clean Parquet to `data/processed/clean/` (git-ignored). Nothing is imputed, NA stays NA and a published 0 stays 0 with a flag."),
    code("""totals, cleaning_log = run.step_clean(con)
cleaning_log.head(20)"""),

    md("## 8. Aggregated statistics (3.1.6)\n\nThese tables are the dashboard's only input. Values below 15 are written as `<15`."),
    code("""tables, headlines = run.step_stats(con)
for path in sorted(ds.STATS_DIR.glob("*.csv")):
    print(f"{path.name:45s} {path.stat().st_size / 1024:8,.0f} KB")"""),
    code("""paragraphs = ds.question_paragraphs(headlines)
for qid, p in paragraphs.items():
    print(f"{qid}. {p['title']}\\n   {p['text']}\\n   Limitation: {p['limit']}\\n")"""),

    md("## 9. First look at the aggregated tables\n\nThe dashboard shows these with filters. Colours per origin are the same in both."),
    code("""COLORS = {"Internacional": "#0072B2", "Nacional": "#E69F00", "Regional": "#009E73"}
MARKERS = {"Internacional": "o", "Nacional": "s", "Regional": "D"}
city = pd.read_csv(ds.STATS_DIR / "city_monthly_by_origin_type.csv", dtype={"mes": str})
city["visitantes"] = pd.to_numeric(city["visitantes"], errors="coerce")
series = city.groupby(["mes", "origen"])["visitantes"].sum().unstack()
series.index = pd.to_datetime(series.index, format="%Y%m")
fig, ax = plt.subplots(figsize=(10, 4))
for origin in series.columns:
    ax.plot(series.index, series[origin] / 1e6, color=COLORS[origin], marker=MARKERS[origin], markersize=4, lw=2, label=origin)
ax.set_ylabel("Unique visitors per month (millions)")
ax.set_title("Q2 · Monthly unique visitors by origin (T1)")
ax.spines[["top", "right"]].set_visible(False)
ax.grid(axis="y", color="#e6e6e6")
ax.set_ylim(bottom=0)
ax.legend(frameon=False, ncol=3)
plt.show()"""),
    code("""trips = pd.read_csv(ds.STATS_DIR / "barrio_incoming_trips_by_origen.csv", dtype={"cod_barrio": str, "mes": str})
trips["viajes"] = pd.to_numeric(trips["viajes"], errors="coerce").fillna(0)
total = trips.groupby("cod_barrio")["viajes"].sum()
share = trips[trips["origen"] != "Residente"].groupby("cod_barrio")["viajes"].sum() / total
values = dict(zip(barris["cod_barrio"], barris["cod_barrio_ss"].map(share)))
fig, ax = plt.subplots(figsize=(7, 7))
cv.plot_map(geo, values=values, ax=ax, cmap="Purples", legend_label="Visitor share of incoming trips",
            title="Q6 · Visitor share of incoming trips (trips, not people)")
plt.show()"""),

    md("## 10. Standalone maps (4.2.1) and deliverables"),
    code("""run.step_maps(con)
con.close()
for path in sorted(q.DELIVERABLES.iterdir()):
    print(path.name)"""),
    md("""## 11. Limits

- Trips are not visitors, and the two are never mixed.
- Published zeros in mobility mean fewer than 15 trips, so totals of trips are lower estimates.
- M3 has repeated keys with different values. It is not used here, and the question goes to the mentor before Iteration 3.
- The dashboard is started with `streamlit run app/dashboard.py`."""),
]


def main():
    nb = nbf.v4.new_notebook(cells=CELLS, metadata={"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}})
    nbf.write(nb, "CONVIVE_Iteration2.ipynb")
    print("CONVIVE_Iteration2.ipynb written")


if __name__ == "__main__":
    main()
