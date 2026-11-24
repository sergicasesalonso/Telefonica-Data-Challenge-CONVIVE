"""Builds CONVIVE_Final.ipynb (WBS 3.3.2, RQ-13): preparation, validation and analysis from start to finish. Execute it with:

    python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=-1 CONVIVE_Final.ipynb

With the raw data in data/ it runs every step from the monthly files. Without them it starts at the aggregated tables.
"""

import nbformat as nbf

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell
QUESTION_FIGURES = [
    ("Where", [("Q1", "q1_concentration"), ("Q6", "q6_tourist_barris"), ("Q8", "q8_rank_season"), ("Q10", "q10_lq_maps"), ("Q16", None)]),
    ("When", [("Q2", "q2_seasonality"), ("Q4", "q4_weekend_barrios"), ("Q5", "q5_growth"), ("Q7", "q7_nights"), ("Q9", "q9_unusual_days"),
              ("Q15", "q15_rhythm")]),
    ("Who", [("Q3", "q3_origin_countries"), ("Q11", None), ("Q12", "q12_q13_residence"), ("Q13", None), ("Q14", "q14_profile"),
             ("Q17", "q17_country_growth"), ("Q18", "nat_season_heatmap"), ("Q19", "nat_lq_maps"), ("Q20", "nat_markets")])]


def figure(path):
    return code(f'Image(filename=str(R.HERE / "deliverables" / "{path}"))')


def question_cells():
    cells = []
    for title, questions in QUESTION_FIGURES:
        cells.append(md(f"### {title}"))
        for qid, name in questions:
            cells.append(code(f'show("{qid}")'))
            if name:
                cells.append(figure(f"iteration3/figures/{name}.png"))
    return cells


CELLS = [
    md("""# CONVIVE · Final notebook

Team 102_A (Convive Lab) · Project Management GP2627, UPF · final delivery, November 2026 · WBS 3.3.2

**Question of the Project Charter.** How does the presence of regional, national and international visitors change over time in the neighbourhoods of Barcelona, compared with residents?

| Part | What it does | WBS |
|---|---|---|
| 1 | Preparation: reads the monthly Smart Steps files, checks and cleans them, builds the aggregated tables | 3.1.x, 2.2.1 |
| 2 | Validation of the aggregated tables | 2.2.2 |
| 3 | Answer to the Charter question | 5.2 |
| 4 | Answers to Q1-Q20, each with a decision rule fixed in advance | 3.2.x |
| 5 | Robustness of the verdicts and limits of the data | 5.3 |

**How to read it.** Trips, unique visitors and presences are three different measures and are never mixed. A count below 15 reads `<15` and never means "nobody". The results describe patterns, not causes. Outputs show aggregated values only (NDA)."""),
    code("""from pathlib import Path
import pandas as pd
from IPython.display import Image, Markdown, display

import aggregates as A
import breaks as B
import coexistence as C
import final_outputs as F
import research as R
import research_report as RR
import sensitivity as S
import validation as V

pd.set_option("display.max_colwidth", 110, "display.width", 200, "display.max_rows", 80)
RAW = A.TOURISM_DIR.exists() and A.MOBILITY_DIR.exists()
print("Raw data on this computer:", RAW)"""),
    md("""## 1. Preparation

With the raw files this part runs the whole pipeline: CSV to Parquet, inventory, inspection, geographic and temporal levels, quality checks, cleaning, descriptive statistics and the aggregated tables. Every step writes its own report in `deliverables/`. Without the raw files the notebook uses the aggregated tables already built."""),
    code("""if RAW:
    import run_iteration2
    run_iteration2.main()
else:
    print("No raw data here: starting from the aggregated tables")"""),
    code("""if RAW:
    A.run_tourism()
    A.run_mobility()
sorted(p.name for p in R.AGG.glob("*.csv")) + sorted(p.name for p in R.STATS.glob("*.csv"))"""),
    md("""## 2. Validation

Seventeen checks. The strongest one compares the trip totals through two separate paths (raw CSV with pandas, clean Parquet with DuckDB)."""),
    code("""failed = V.main()
assert not failed, "A blocking validation check failed"
pd.read_csv(V.OUT_CSV)[["#", "area", "check", "result"]]"""),
    md("""## 3. The Charter question

Residents exist only in the mobility product, so visitors and residents are compared with trips between neighbourhoods (M1)."""),
    code("""t, r = R.run_all()
RR.make_figures(t, r)
RR.write_all(t, r)
F.main()
q0 = C.run(t)
display(Markdown(f"**{q0['question']}**\\n\\n*Rule.* {q0['decision_rule']}\\n\\n{q0['answer']}\\n\\n**Verdict: {q0['verdict']}. "
                 f"Belief holds: {q0['belief_holds']}.**\\n\\n*Limitation.* {q0['limitation']}"))"""),
    code("""q0["origins"].drop(columns="origen").round(3)"""),
    figure("final/figures/charter_maps.png"),
    figure("final/figures/charter_time.png"),
    figure("final/figures/charter_barrios.png"),
    md("""## 4. Twenty questions, twenty rules

`R.THRESHOLDS` holds the rules. They were written before the answers were computed, so the rule decides the verdict and not the number."""),
    code("""answers = RR.answers_table(r)


def show(qid):
    row = answers.set_index("id").loc[qid]
    display(Markdown(f"#### {qid} · {row.question}\\n\\n*Belief:* “{row.belief}”  \\n*Rule:* {row.decision_rule}\\n\\n{row.answer}\\n\\n"
                     f"**Verdict: {row.verdict}. Belief holds: {row.belief_holds}.**  \\n*Limitation:* {row.limitation}"))


answers[["id", "belief", "verdict", "belief_holds"]]"""),
    *question_cells(),
    md("""## 5. Robustness and limits

Each question is recomputed with its main threshold 10% and 20% lower and higher. A verdict is fragile if it changes already at 10%."""),
    code("""robust = S.run(t, r)
robust"""),
    figure("final/figures/verdict_robustness.png"),
    md("""The scan below looks for level shifts in the 73 neighbourhood series (issue I8)."""),
    code("""shifts = B.run(t)
shifts["found"][["barrio_name", "distrito_name", "product", "month", "ratio"]].round(2)"""),
    code("""shifts["pair"].round(2)"""),
    figure("final/figures/level_shifts.png"),
    code("""low = r["low_data"]
low[low["low_data"]][["barrio_name", "distrito_name", "mean_monthly_visitors", "vs_median", "resident_trips_vs_median", "visitor_share_trips", "reason"]].round(3)"""),
    md("""**Open data questions for the Business Manager.** I7: repeated keys in M3 (not used here). I8: low-data neighbourhoods and level shifts. I9: no international visitors in T9.

**Dashboard.** `python -m streamlit run app/dashboard.py` reads the tables written by this notebook."""),
]


def main():
    nb = nbf.v4.new_notebook()
    nb["cells"] = CELLS
    nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
    nbf.write(nb, "CONVIVE_Final.ipynb")
    print("CONVIVE_Final.ipynb written")


if __name__ == "__main__":
    main()
