"""Builds CONVIVE_Iteration3.ipynb (WBS 3.2.1-3.2.4: analysis notebook of Iteration 3). Execute it with:

    python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=-1 CONVIVE_Iteration3.ipynb

The notebook reads only aggregated tables (threshold 15 applied). The aggregation step (2.2.1) runs only where the
raw data exist (data/, NDA); elsewhere the notebook uses the aggregated tables already built.
"""

import nbformat as nbf

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell


def question(qid, figure=None, extra=None):
    cells = [code(f"""show("{qid}")""")]
    if extra:
        cells.append(code(extra))
    if figure:
        cells.append(code(f"""Image(filename=str(R.OUT / "figures" / "{figure}"))"""))
    return cells


CELLS = [
    md("""# CONVIVE · Iteration 3 · Quantified research questions

Team 102_A (Convive Lab) · Mobile Data Challenge 2026 · Iteration 3 (10-23 Nov 2026) · WBS 2.2.1, 2.2.2, 3.2.0-3.2.4

The Business Manager asked on 9 Nov for research questions that are **precise and quantified**, with an explicit threshold that tells us how to answer each one with the data, more concrete questions about tourists, and an explanation of the neighbourhoods with very few data. This notebook does exactly that:

1. **2.2.1** builds the aggregated tables (countries, provinces, municipalities, profile, daily neighbourhood visitors, trips between neighbourhoods, coverage).
2. **2.2.2** validates them (totals through two independent paths, unique visitors never summed, coverage, privacy threshold).
3. **3.2.4 / 3.2.1-3.2.3** answer Q1-Q20. For every question: belief → question → metric → **decision rule fixed in advance** → answer → verdict → limitation.
4. **I8** explains the low-data neighbourhoods.

**Rules (NDA).** Outputs show only aggregated values; any count below 15 reads `<15`. Trips and unique visitors are never combined; unique visitors are never summed into people (sums across neighbourhoods are called *presences*). The results describe patterns, not causes."""),
    code("""from pathlib import Path
import pandas as pd
from IPython.display import Image, Markdown, display

import aggregates as A
import research as R
import research_report as RR
import validation as V

pd.set_option("display.max_colwidth", 120, "display.width", 200, "display.max_rows", 80)
RAW_AVAILABLE = A.TOURISM_DIR.exists() and A.MOBILITY_DIR.exists()
print("Raw data on this computer:", RAW_AVAILABLE)"""),
    md("""## 1. Aggregation data generation (2.2.1)

Reads the monthly CSV files with pandas only (no DuckDB needed), one month at a time, and writes NDA-safe aggregated tables. Mobility is cached per month, so the step can resume."""),
    code("""if RAW_AVAILABLE:
    A.run_tourism()
    A.run_mobility()
else:
    print("No raw data here: using the aggregated tables in", A.OUT_DIR.relative_to(A.HERE))
sorted(p.name for p in A.OUT_DIR.glob("*.csv"))"""),
    md("""## 2. Aggregated data validation (2.2.2)"""),
    code("""V.main()
pd.read_csv(V.OUT_CSV)[["#", "area", "check", "result", "evidence"]]"""),
    md("""## 3. Answers

`R.THRESHOLDS` holds every decision rule. They were written before the answers were computed: a rule decides the verdict, not the number."""),
    code("""t, r = R.run_all()
answers = RR.answers_table(r)


def show(qid):
    row = answers.set_index("id").loc[qid]
    display(Markdown(f"### {qid} · {row.question}\\n\\n*Belief:* “{row.belief}”  \\n*Metric:* {row.metric}  \\n"
                     f"*Decision rule:* {row.decision_rule}\\n\\n**Answer.** {row.answer}\\n\\n**Verdict: {row.verdict}.**  \\n"
                     f"*Limitation:* {row.limitation}"))


answers[["id", "belief", "verdict"]]"""),
    md("""### 3.1 Quantified Q1-Q6 (3.2.4)"""),
    *question("Q1", "q1_concentration.png", "r['Q1']['table'].round(3)"),
    *question("Q2", "q2_seasonality.png", "r['Q2']['table'].round(3)"),
    *question("Q3", "q3_origin_countries.png"),
    *question("Q4", "q4_weekend_barrios.png", "r['Q4']['table'].round(3)"),
    *question("Q5", "q5_growth.png"),
    *question("Q6", "q6_tourist_barris.png", "r['Q6']['table'].round(3)"),
    md("""### 3.2 Who visits (3.2.1 exploratory analysis)"""),
    *question("Q11"),
    *question("Q12", "q12_q13_residence.png"),
    *question("Q13"),
    *question("Q14", "q14_profile.png"),
    *question("Q17", "q17_country_growth.png"),
    md("""### 3.2b Nationalities of international visitors (3.2.1, T8)

Every country of residence with its share, overnight share, growth, season and neighbourhoods (`nationalities.py`)."""),
    code("""r["nationalities"].head(20).round(3)"""),
    code("""r["regions"].round(3)"""),
    code("""Image(filename=str(R.OUT / "figures" / "nat_markets.png"))"""),
    *question("Q20"),
    *question("Q18", "nat_season_heatmap.png"),
    *question("Q19", "nat_lq_maps.png"),
    md("""### 3.3 Where (3.2.2 geographic analysis)"""),
    *question("Q16"),
    *question("Q8", "q8_rank_season.png"),
    *question("Q10", "q10_lq_maps.png"),
    md("""### 3.4 When (3.2.3 temporal analysis)"""),
    *question("Q7", "q7_nights.png"),
    *question("Q9", "q9_unusual_days.png", "r['Q9']['peaks'][['date', 'weekday', 'visitantes', 'expected', 'deviation']].round(3)"),
    *question("Q15", "q15_rhythm.png"),
    md("""## 4. Neighbourhoods with very few data (I8)

Rule: """ + "mean monthly visitors below 10% of the median neighbourhood, or more than 15% of the T6-T8 rows grouped as NA."),
    code("""low = r["low_data"]
low[low["low_data"]][["barrio_name", "distrito_name", "mean_monthly_visitors", "vs_median", "na_share_T8",
                      "resident_trips_vs_median", "visitor_share_trips", "reason"]].round(3)"""),
    code("""display(Markdown(RR.low_data_md(r, t)))
Image(filename=str(R.OUT / "figures" / "low_data_barris.png"))"""),
    md("""## 5. Outputs written

`python research_report.py` (or this notebook) writes the Markdown reports 3.2.0-3.2.4, the CSV tables and the figures in `deliverables/iteration3/`. The dashboard (`streamlit run app/dashboard.py`) reads the same tables."""),
    code("""RR.write_all(t, r)
sorted(p.name for p in R.OUT.glob("*.md"))"""),
]


def main():
    nb = nbf.v4.new_notebook()
    nb["cells"] = CELLS
    nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nbf.write(nb, "CONVIVE_Iteration3.ipynb")
    print("CONVIVE_Iteration3.ipynb written")


if __name__ == "__main__":
    main()
