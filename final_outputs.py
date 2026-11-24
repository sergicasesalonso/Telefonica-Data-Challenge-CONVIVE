"""CONVIVE - final analysis outputs (WBS 5.2 and 5.3): Charter question, key findings, robustness of the verdicts, level shifts.

    python final_outputs.py

Writes to deliverables/final/ (tables and figures are git-ignored, they come from NDA data):
    5.2_charter_question.csv / _origins.csv / _month.csv    Q0 per neighbourhood, per origin and per month
    5.2_key_findings.md / .csv                              five findings with evidence, robustness and limit
    5.3_verdict_robustness.csv                              verdicts under thresholds 10% and 20% easier or harder
    5.3_level_shifts.csv                                    level shifts of the 73 neighbourhood series
    5.3_limitations.md                                      robustness, level shifts and the open data questions I7-I9
    figures/*.png
Needs the aggregated tables of Iterations 2 and 3 (python run_final.py builds everything in order).
"""

import sys
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import colors as mcolors  # noqa: E402

import breaks as B  # noqa: E402
import coexistence as C  # noqa: E402
import convive as cv  # noqa: E402
import research as R  # noqa: E402
import research_report as RR  # noqa: E402
import sensitivity as S  # noqa: E402

OUT = R.HERE / "deliverables" / "final"
FIG = OUT / "figures"
INK, MUTED, GRID = RR.INK, RR.MUTED, RR.GRID
VISITOR, RESIDENT = "#0072B2", "#CC79A7"
LEVEL = {"Robust": "#009E73", "Moderate": "#E69F00", "Fragile": "#D55E00"}


def save(fig, name, title, subtitle=""):
    """Same frame as the Iteration 3 figures, written to deliverables/final/figures."""
    previous, RR.FIG = RR.FIG, FIG
    try:
        return RR.save(fig, name, title, subtitle)
    finally:
        RR.FIG = previous


# ---------------------------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------------------------
def fig_charter_maps(q0):
    d = q0["table"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    geo, level = RR.map_values(dict(zip(d["cod_barrio"], d["share_2025"])))
    cv.plot_map(geo, level, ax=axes[0], cmap="RdBu_r", norm=mcolors.TwoSlopeNorm(0.5, 0, 0.75), legend_label="Visitor share of incoming trips")
    axes[0].set_title("Share in January-August 2025", fontsize=10, loc="left", color=INK)
    geo, change = RR.map_values(dict(zip(d["cod_barrio"], (d["change"] * 100).clip(-8, 8))))
    cv.plot_map(geo, change, ax=axes[1], cmap="PuOr_r", norm=mcolors.TwoSlopeNorm(0, -8, 8), legend_label="Change 2023-2025, points (capped at 8)")
    axes[1].set_title("Change since January-August 2023", fontsize=10, loc="left", color=INK)
    return save(fig, "charter_maps.png", f"Visitors gain ground in {q0['n_gain']} of 73 neighbourhoods and lose it in {q0['n_loss']}",
                "Share of incoming trips made by visitors (M1). Gains or loses ground: at least 2 percentage points.")


def fig_charter_time(q0):
    m = q0["month"]
    x = pd.to_datetime(m["mes"], format="%Y%m")
    fig, (a, b) = plt.subplots(2, 1, figsize=(9.5, 5.8), sharex=True, gridspec_kw={"height_ratios": [1.25, 1]})
    for col, colour, marker, label in (("resident", RESIDENT, "^", "Residents"), ("visitor", VISITOR, "o", "Visitors")):
        a.plot(x, m[col], color=colour, lw=2, marker=marker, ms=4)
        a.annotate(label, (x.iloc[-1], m[col].iloc[-1]), xytext=(8, -3 if col == "resident" else 4), textcoords="offset points", fontsize=9, color=INK)
    RR.style(a, "Trips per day", "k")
    a.set_ylim(0)
    b.plot(x, m["visitor_share"], color=VISITOR, lw=2, marker="o", ms=4)
    b.axhline(0.5, color="#9a9a9a", lw=1, ls="--")
    for year in C.YEARS:
        g = m[(m["mes"].str[:4] == str(year)) & (m["mes"].str[4:] == "08")]
        if len(g):
            xv, yv = pd.to_datetime(g["mes"].iloc[0], format="%Y%m"), g["visitor_share"].iloc[0]
            b.annotate(f"Aug {year}: {yv:.1%}", (xv, yv), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=8.5, color=INK)
    RR.style(b, "Visitor share of trips", "pct")
    b.set_ylim(0.35, 0.57)
    a.set_xlim(x.iloc[0] - pd.Timedelta(days=20), x.iloc[-1] + pd.Timedelta(days=110))
    return save(fig, "charter_time.png", "In August, when residents travel least, visitors make half of the trips",
                "Trips between neighbourhoods per observed day, January 2023-August 2025 (M1).")


def fig_charter_barrios(q0, shifted):
    d = q0["table"]
    d = d[~d["barrio_name"].isin(shifted)]
    pick = pd.concat([d.head(10), d.tail(6)]).sort_values("change")
    fig, ax = plt.subplots(figsize=(9.5, 6))
    y = np.arange(len(pick))
    up = pick["change"] >= 0
    ax.hlines(y, pick["share_2023"], pick["share_2025"], color=np.where(up, VISITOR, RESIDENT), lw=2.5)
    ax.scatter(pick["share_2023"], y, s=42, color="white", edgecolor=np.where(up, VISITOR, RESIDENT), lw=1.8, zorder=3, label="2023")
    ax.scatter(pick["share_2025"], y, s=48, color=np.where(up, VISITOR, RESIDENT), zorder=3, label="2025")
    for i, r in enumerate(pick.itertuples()):
        ax.text(max(r.share_2023, r.share_2025) + 0.012, i, f"{r.change * 100:+.1f}", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(y, [RR.SHORT_NAMES.get(n, n) for n in pick["barrio_name"]])
    RR.style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.axvline(0.5, color="#9a9a9a", lw=1, ls="--")
    ax.set_xlabel("Visitor share of incoming trips, January-August (open 2023, filled 2025); label: change in points", color=MUTED, fontsize=9)
    return save(fig, "charter_barrios.png", "Where visitors gained and lost most ground, 2023 to 2025",
                "Ten largest rises and six largest falls. Neighbourhoods with a level shift in M1 are left out.")


def fig_robustness(table):
    d = table.copy()
    d["label"] = [f"{r.id}  {r.threshold}" for r in d.itertuples()]
    colours = {"Yes": "#0072B2", "Partly": "#A9CBE3", "No": "#D9D9D9"}
    columns = ["-20%", "-10%", "base", "+10%", "+20%"]
    fig, ax = plt.subplots(figsize=(9.5, 8))
    for i, r in d.reset_index(drop=True).iterrows():
        for j, col in enumerate(columns):
            ax.add_patch(plt.Rectangle((j, -i - 0.5), 0.96, 0.9, color=colours[r[col]]))
            ax.text(j + 0.48, -i - 0.05, r[col], ha="center", va="center", fontsize=8, color="white" if r[col] == "Yes" else INK)
        ax.text(5.15, -i - 0.05, r["robustness"], va="center", fontsize=9, color=LEVEL[r["robustness"]], fontweight="bold")
    ax.set_xlim(0, 6.2)
    ax.set_ylim(-len(d) + 0.3, 0.6)
    ax.set_yticks([-i - 0.05 for i in range(len(d))], d["label"], fontsize=8.5)
    ax.set_xticks([j + 0.48 for j in range(5)], ["20% lower", "10% lower", "as fixed", "10% higher", "20% higher"], fontsize=9)
    ax.xaxis.tick_top()
    ax.tick_params(length=0, colors=INK)
    ax.spines[:].set_visible(False)
    return save(fig, "verdict_robustness.png", "Does the belief hold if the threshold is moved?",
                "Every question recomputed with its main threshold 10% and 20% lower and higher.")


def fig_shifts(t, res):
    series = {"T4 visitors": B.t4_series(t), "M1 visitor trips": B.m1_series(t)}
    names = ["Verdun", "Can Peguera", "el Turó de la Peira", "la Font de la Guatlla"]
    fig, axes = plt.subplots(2, 2, figsize=(10, 5.6), sharex=True)
    for ax, name in zip(axes.flat, names):
        for (product, frame), colour, style in zip(series.items(), (VISITOR, "#E69F00"), ("-", "--")):
            s = frame[name]
            ax.plot(pd.to_datetime(s.index, format="%Y%m"), s / s.mean() * 100, color=colour, ls=style, lw=2, label=product)
        ax.set_title(name, fontsize=10, loc="left", color=INK)
        RR.style(ax, "Mean = 100")
        ax.set_ylim(0)
    for ax in axes[1]:
        ax.xaxis.set_major_locator(matplotlib.dates.YearLocator())
        ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter('%Y'))
    axes[0, 0].legend(frameon=False, fontsize=8.5)
    return save(fig, "level_shifts.png", "Level shifts: some neighbourhoods change level from one month to the next",
                "Monthly series of two independent products, as an index of their own mean.")


# ---------------------------------------------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------------------------------------------
def level_of(table, qid):
    order = ["Robust", "Moderate", "Fragile"]
    return max(table.loc[table["id"] == qid, "robustness"], key=order.index)


def key_findings(t, r, q0, rob, shifts):
    q1, q2, q4, q5 = r["Q1"]["table"], r["Q2"]["table"], r["Q4"], r["Q5"]
    everyone = q1.iloc[0]
    tour = q1[(q1["origin"] == "International") & (q1["type"] == "tourists")].iloc[0]
    regional = q1[q1["origin"] == "Regional"].iloc[0]
    s = q2[q2["origin"] == "All visitors"]["summer_vs_rest"]
    city4 = q4["table"].iloc[0]
    growth = q5["table"]
    allv = growth[(growth["origen"] == "Todos") & (growth["tipo_visitante"] == "Todos")].iloc[0]
    it = growth[(growth["origen"] == "Internacional") & (growth["tipo_visitante"] == "Turista")].iloc[0]
    na = growth[(growth["origen"] == "Nacional") & (growth["tipo_visitante"] == "Todos")].iloc[0]
    prof = r["nationalities"].set_index("country")
    q15 = r["Q15"]["table"].set_index("weekday_idx")
    over = r["Q6"]["table"]
    o = q0["origins"].set_index("origen")
    m1_shifted = set(shifts["found"].loc[shifts["found"]["product"] == "M1 visitor trips", "barrio_name"])
    d = q0["table"]
    clean = d[~d["barrio_name"].isin(m1_shifted)]
    n_clean = int((clean["status"] == "Gains ground").sum())
    n_robust = int(((d["status"] == "Gains ground") & d["robust"]).sum())
    rows = [
        {"id": "F1", "title": "Visitors are concentrated: half of their presences are in 10 of 73 neighbourhoods",
         "evidence": f"N50 = {everyone.n50} neighbourhoods (between {everyone.n50_month_min} and {everyone.n50_month_max} in the 32 months); the ten largest "
                     f"hold {R.pct(everyone.top10_share)}. International tourists are more concentrated (N50 = {tour.n50}) and regional visitors "
                     f"more spread (N50 = {regional.n50}). The ranking is the same in high and low season ({r['Q8']['table'].iloc[-1].top10_kept} of the "
                     f"top 10 kept, Spearman {r['Q8']['table'].iloc[-1].spearman:.3f}).",
         "questions": "Q1, Q8", "robustness": level_of(rob, "Q1"), "figure": "iteration3/figures/q1_concentration.png",
         "limitation": "Shares are of presences (person x neighbourhood), because unique visitors cannot be added across neighbourhoods."},
        {"id": "F2", "title": "Visitors' trips grow faster than residents' trips, and visitors gain ground in 39 of 73 neighbourhoods",
         "evidence": f"January-August trips per day, 2023 to 2025: visitors {R.signed(q0['visitor_growth'])}, residents {R.signed(q0['resident_growth'])}. "
                     f"The visitor share goes from {R.pct(q0['city'][2023])} to {R.pct(q0['city'][2025])}. International visitors add "
                     f"{R.num(o.loc['Internacional', 'per_day_2025'] - o.loc['Internacional', 'per_day_2023'])} trips per day "
                     f"({R.signed(o.loc['Internacional', 'change_23_25'])}), regional visitors "
                     f"{R.num(o.loc['Regional', 'per_day_2025'] - o.loc['Regional', 'per_day_2023'])} ({R.signed(o.loc['Regional', 'change_23_25'])}) and "
                     f"national visitors make {R.num(o.loc['Nacional', 'per_day_2023'] - o.loc['Nacional', 'per_day_2025'])} fewer "
                     f"({R.signed(o.loc['Nacional', 'change_23_25'])}). "
                     f"Visitors gain at least 2 points in {q0['n_gain']} neighbourhoods and lose them in {q0['n_loss']}; {n_robust} of the gains are "
                     f"larger than the uncertainty of the privacy threshold, and {n_clean} of {len(clean)} ({n_clean / len(clean):.0%}) remain after leaving "
                     f"out the {len(m1_shifted)} neighbourhoods with a level shift in M1.",
         "questions": "Q0", "robustness": level_of(rob, "Q0"), "figure": "final/figures/charter_maps.png",
         "limitation": "The rule needs 37 neighbourhoods, so the verdict is close to the line: the direction is clear, the count is not. Trips, not people."},
        {"id": "F3", "title": "Visitors neither flood the city at weekends nor come only in summer",
         "evidence": f"Saturdays and Sundays have {abs(city4.weekend_change):.1%} fewer visitors than weekdays (95% interval {R.signed(city4.ci_low)} to "
                     f"{R.signed(city4.ci_high)}); only {q4['n_flood']} of 73 neighbourhoods get at least 10% more. June-August is {s.iloc[0]:.2f} and "
                     f"{s.iloc[1]:.2f} times the other months (2023, 2024), far from the 1.30 rule.",
         "questions": "Q2, Q4", "robustness": level_of(rob, "Q4"), "figure": "iteration3/figures/q4_weekend_barrios.png",
         "limitation": "2025 stops in August and three days are missing in the daily files."},
        {"id": "F4", "title": "Growth comes from international tourists and the mix of countries is changing",
         "evidence": f"January-August visitors grow {R.signed(allv.change_2023_2024)} and {R.signed(allv.change_2024_2025)}; international tourists "
                     f"{R.signed(it.change_2023_2024)} and {R.signed(it.change_2024_2025)}; national visitors {R.signed(na.change_2023_2024)} and "
                     f"{R.signed(na.change_2024_2025)}. Between 2023 and 2025 Poland grows {R.signed(prof.loc['Poland', 'growth_23_25'], 0)} and the United "
                     f"States {R.signed(prof.loc['United States', 'growth_23_25'], 0)}, while the United Kingdom falls "
                     f"{R.signed(prof.loc['United Kingdom', 'growth_23_25'], 0)} and Germany {R.signed(prof.loc['Germany', 'growth_23_25'], 0)}. "
                     f"Only {r['Q18']['value']} of the 20 main markets are summer markets.",
         "questions": "Q5, Q17, Q18", "robustness": level_of(rob, "Q5"), "figure": "iteration3/figures/q17_country_growth.png",
         "limitation": "Two intervals cannot prove a long-term trend; country figures are presences."},
        {"id": "F5", "title": "In the most visited neighbourhoods visitors make most of the trips, and on a different rhythm from residents",
         "evidence": f"In {int((over['visitor_share'] > 0.5).sum())} of the 10 most visited neighbourhoods visitors make more than half of the incoming trips "
                     f"(el Barri Gòtic {R.pct(over['visitor_share'].max())}); city-wide {R.pct(1 - r['Q6']['all']['resident_trips'].sum() / (r['Q6']['all']['resident_trips'].sum() + r['Q6']['all']['visitor_trips'].sum()))}. "
                     f"On Saturdays the index of residents' trips is {q15.loc[5, 'Residente']:.0f} and that of visitors {q15.loc[5, 'Visitante']:.0f} (mean day = 100).",
         "questions": "Q6, Q15", "robustness": level_of(rob, "Q6"), "figure": "iteration3/figures/q6_tourist_barris.png",
         "limitation": "Trips inside a neighbourhood are excluded, so residents' short trips are not counted. The 'all ten' version of the belief fails by one neighbourhood."},
    ]
    rows[1]["title"] = f"Visitors' trips grow faster than residents' trips, and visitors gain ground in {q0['n_gain']} of 73 neighbourhoods"
    return pd.DataFrame(rows), {"n_clean": n_clean, "n_robust": n_robust, "m1_shifted": sorted(m1_shifted), "n_clean_total": len(clean)}


def header(title):
    return [f"# {title}", "", f"CONVIVE · Team 102_A · final delivery · generated by `final_outputs.py` on {date.today():%d %b %Y} from aggregated "
            "tables only. The results describe patterns, not causes.", ""]


def write_findings(findings, q0, extra):
    lines = header("5.2 Key findings")
    lines += ["## Charter question (Q0)", "", f"*Question:* {q0['question']}  ", f"*Decision rule:* {q0['decision_rule']}", "",
              f"**Answer.** {q0['answer']}", "", f"**Verdict: {q0['verdict']}.** Belief \"{q0['belief']}\" holds: **{q0['belief_holds']}**, "
              f"and the verdict is **fragile**: {extra['n_robust']} of the gains exceed the uncertainty of the privacy threshold, and {extra['n_clean']} of "
              f"{extra['n_clean_total']} remain without the neighbourhoods that have a level shift in M1.", "", f"*Limitation:* {q0['limitation']}", ""]
    for f in findings.itertuples():
        lines += [f"## {f.id} · {f.title}", "", f.evidence, "", f"*Questions:* {f.questions} · *Robustness of the verdict:* {f.robustness}  ",
                  f"*Limitation:* {f.limitation}", "", f"![{f.id}](../{f.figure})", ""]
    (OUT / "5.2_key_findings.md").write_text("\n".join(lines), encoding="utf-8")


def md_table(df):
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    return lines + ["| " + " | ".join(str(v) for v in row) + " |" for row in df.itertuples(index=False)]


def write_limitations(rob, shifts, extra):
    found = shifts["found"]
    per_question = rob.groupby("id")["robustness"].agg(lambda x: max(x, key=["Robust", "Moderate", "Fragile"].index))
    counts = per_question.value_counts()
    lines = header("5.3 Robustness, level shifts and open data questions")
    lines += ["## Robustness of the verdicts", "", f"Of {len(per_question)} questions (Q0-Q20), {counts.get('Robust', 0)} verdicts are robust, "
              f"{counts.get('Moderate', 0)} moderate and {counts.get('Fragile', 0)} fragile ({', '.join(per_question[per_question == 'Fragile'].index)}). "
              "Robust: the verdict is the same with the threshold 10% and 20% lower or higher. Fragile: it already changes at 10%. "
              "For the fragile questions the number is the result and the Yes/No is only a reading of it.", ""]
    show = rob.copy()
    show["value"] = show["value"].map("{:g}".format)
    lines += md_table(show) + [""]
    lines += ["## Level shifts in the neighbourhood series (extends I8)", "", f"*Rule:* {B.RULE_TEXT}", "",
              f"{len(found)} shifts in {found['barrio_name'].nunique()} of 73 neighbourhoods, {int((found['distrito_name'] == 'Nou Barris').sum())} of them "
              "in Nou Barris. Iteration 3 reported Verdun as the only break; the scan of all the neighbourhoods corrects that. Verdun falls in both products in August 2023, but M1 recovers in two months while T4 stays low; in la Font de la Guatlla both products rise together, which could be real. The scan cannot tell one case from the other.", ""]
    table = found[["barrio_name", "distrito_name", "product", "month", "ratio"]].copy()
    table["ratio"] = table["ratio"].map("{:.2f}".format)
    lines += md_table(table) + [""]
    pair = shifts["pair"].copy()
    lines += ["### Can Peguera and el Turó de la Peira: evidence of a change of zones in April 2024", "",
              "These two neighbourhoods are next to each other and shift in the same month in opposite directions, for visitors and for residents "
              "alike. Together they change much less (means of the six months before and after). Real visitors and residents would hardly swap "
              "neighbourhoods overnight; a change in how the network areas are assigned would do exactly this. It is the most concrete evidence "
              "we can give Telefónica for I8.", ""]
    for c in ("before", "after"):
        pair[c] = pair[c].map(R.num)
    pair["change"] = pair["change"].map(lambda v: R.signed(v, 0))
    lines += md_table(pair) + [""]
    lines += ["## Open data questions for the Business Manager", "",
              "| ID | Question | What we did meanwhile | What changes with the answer |", "|---|---|---|---|",
              "| I7 | 43.7% of the M3 rows repeat a day x origin x route key with different trip counts. Is a key column missing, or should the rows be added? | "
              "M3 is kept out of every answer; Q13 uses T6. | M3 could add trips from each municipality to each neighbourhood. |",
              f"| I8 | Why do six neighbourhoods have so few visitors, and was the zoning changed? Level shifts affect {found['barrio_name'].nunique()} neighbourhoods, {int(found['month'].between('202307', '202405').sum())} of {len(found)} shifts between July 2023 and May 2024. | "
              "Values are kept and flagged; Q0 is also reported without the affected neighbourhoods. | Series could be corrected or cut at the change. |",
              "| I9 | T9 has no international visitors although the description lists them. Is it the scope of the file or a missing extract? | "
              "Q14 is answered for national and regional visitors only. | Age and income profile of international visitors. |"]
    (OUT / "5.3_limitations.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build():
    t, r = R.run_all()
    q0 = C.run(t)
    rob = S.run(t, r)
    shifts = B.run(t)
    findings, extra = key_findings(t, r, q0, rob, shifts)
    return t, r, q0, rob, shifts, findings, extra


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t, r, q0, rob, shifts, findings, extra = build()
    q0["table"].to_csv(OUT / "5.2_charter_question.csv", index=False)
    q0["origins"].to_csv(OUT / "5.2_charter_origins.csv", index=False)
    q0["month"].to_csv(OUT / "5.2_charter_month.csv", index=False)
    summary = {k: q0[k] for k in ("id", "belief", "question", "data", "metric", "decision_rule", "answer", "verdict", "belief_holds", "limitation")}
    pd.DataFrame([summary]).to_csv(OUT / "5.2_charter_answer.csv", index=False)
    findings.to_csv(OUT / "5.2_key_findings.csv", index=False)
    rob.to_csv(OUT / "5.3_verdict_robustness.csv", index=False)
    shifts["found"].to_csv(OUT / "5.3_level_shifts.csv", index=False)
    shifts["pair"].to_csv(OUT / "5.3_zone_transfer.csv", index=False)
    write_findings(findings, q0, extra)
    write_limitations(rob, shifts, extra)
    fig_charter_maps(q0)
    fig_charter_time(q0)
    fig_charter_barrios(q0, extra["m1_shifted"])
    fig_robustness(rob)
    fig_shifts(t, shifts)
    for path in sorted(OUT.glob("5.*")) + sorted(FIG.glob("*.png")):
        print("  ", path.relative_to(OUT))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
