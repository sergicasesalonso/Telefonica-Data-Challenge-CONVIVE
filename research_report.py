"""CONVIVE - outputs of the Iteration 3 analysis (WBS 3.2.0 to 3.2.4): tables, figures and Markdown reports.

    python research_report.py

Writes to deliverables/iteration3/:
    3.2.0_ResearchQuestions_v0.3.md        questions with metric, decision rule, answer and limit (Q1-Q20)
    3.2.4_quantified_answers.md / .csv     question -> metric -> threshold -> answer -> verdict table (Q1-Q6 + Q7-Q17)
    3.2.1_exploratory_analysis.md          who and where from: Q3 countries, Q11-Q14, Q17
    3.2.2_geographic_analysis.md           where: Q1, Q6, Q8, Q10, Q16 and the low-data neighbourhoods (I8)
    3.2.3_temporal_analysis.md             when: Q2, Q4, Q5, Q7, Q9, Q15
    figures/*.png                          one figure per question (aggregated values only)
"""

from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import colors as mcolors  # noqa: E402

import convive as cv  # noqa: E402
import research as R  # noqa: E402

FIG = R.OUT / "figures"
# Okabe-Ito, the same colour per origin as the dashboard. Validated with the dataviz checks: CVD separation of the
# pink/green pair is in the 6-8 band, so every chart adds a second encoding (markers, direct labels or a table).
COLORS = {"International": "#0072B2", "National": "#E69F00", "Regional": "#009E73", "Resident": "#CC79A7",
          "All visitors": "#333333", "Visitors": "#0072B2"}
MARKERS = {"International": "o", "National": "s", "Regional": "D", "Resident": "^", "All visitors": "o", "Visitors": "o"}
INK, MUTED, GRID = "#1f1f1f", "#5f5f5f", "#e6e6e6"
SOURCE = "Source: Smart Steps (Telefónica Tech), aggregated, threshold 15. CONVIVE Team 102_A."

QUESTIONS = {
    "Q1": ("Tourists are everywhere in Barcelona.", "How concentrated are visitors across the 73 neighbourhoods?", "T4",
           "N50: smallest number of neighbourhoods holding 50% of visitor presences (mean monthly visitors per neighbourhood); "
           "top-10 share; Gini", "Neighbourhood values are not additive: shares are of presences (person x neighbourhood), not of people."),
    "Q2": ("Tourism is only a summer problem.", "How much higher are June-August than the rest of the year, by origin?", "T1",
           "Ratio of the June-August monthly mean to the mean of the other nine months, full years 2023 and 2024; months within 90% of the peak",
           "2025 covers January-August only and has no full-year ratio."),
    "Q3": ("Most visitors are foreign tourists.", "In how many months are international visitors the majority, and from which countries?",
           "T1, T8", "Monthly international share of unique visitors (T1); share of international presences by country of residence (T8)",
           "Country shares are of presences; countries below 15 people per neighbourhood are grouped as NA."),
    "Q4": ("Visitors flood the city at weekends.", "Are mean daily visitors on Saturday-Sunday at least 10% above Monday-Friday?",
           "T2, T5", "Weekend vs weekday mean daily unique visitors, city (T2) and each neighbourhood (T5); 95% bootstrap interval",
           "Daily values are never summed into weeks; 3 days are missing; T5 uses published values only."),
    "Q5": ("Tourism keeps growing every year.", "Did January-August visitors grow by more than 2% in both 2024 and 2025?", "T1, T4",
           "Change in the January-August monthly mean, 2023->2024 and 2024->2025, city and neighbourhoods (base >= 1,000)",
           "Two intervals cannot prove a long-term trend; Feb 2024, Apr 2025 and May 2025 miss one day."),
    "Q6": ("In tourist neighbourhoods, visitors' movement outnumbers residents'.",
           "In the 10 most-visited neighbourhoods, do visitors make more than 50% of incoming trips?", "T4, M1",
           "Visitor share of incoming trips (M1), with bounds that treat each published 0 as 0-14 trips",
           "Trips, not people. Trips inside a neighbourhood are excluded."),
    "Q7": ("Tourists only stay for a weekend.", "Do at least half of the tourists of a week spend at most 2 nights?", "T3",
           "Share of weekly tourists by number of nights in the week", "Municipality level; national and international tourists only; nights within one week."),
    "Q8": ("The tourist neighbourhoods are the same all year round.", "Does the top 10 change between the peak and the lowest month?", "T1, T4",
           "Top-10 overlap and Spearman rank correlation between the peak and the lowest month", "Monthly values only."),
    "Q9": ("Big events and holidays create visible peaks.", "Which days are at least 15% above (or below) the same weekday of the same month?", "T2",
           "Daily unique visitors vs the median of the same weekday in the same month", "The data date the peaks but cannot name their cause."),
    "Q10": ("Regional day-trippers go to the same places as foreign tourists.", "Do the top-10 neighbourhoods of each origin coincide (7 of 10)?", "T4",
            "Top-10 overlap between origins; location quotient (LQ) per neighbourhood and origin", "LQ uses presences, not people."),
    "Q11": ("International visitors come from a few countries.", "Do the top 5 countries hold at least half of international tourists?", "T8",
            "Share of international presences by country, tourists and excursionists; leading country per neighbourhood",
            "Small countries are grouped as NA in each neighbourhood."),
    "Q12": ("National visitors are mostly from Madrid.", "Is Madrid at least half of national visitors?", "T7",
            "Share of national presences by province of residence", "'National' excludes the province of Barcelona (those are regional)."),
    "Q13": ("Regional visitors come from the metropolitan ring.", "Do the other 35 AMB municipalities send at least half of regional visitors?", "T6",
            "Share of regional presences by municipality of residence", "M3 (trips) is not used because of the repeated keys (I7)."),
    "Q14": ("Visitors are young and high-income.", "Are at least half aged 18-39, and at least half high or medium-high income?", "T9",
            "Shares of presences by age group, income level and gender", "T9 has no international visitors (I9): national and regional only."),
    "Q15": ("Visitors and residents use the city at the same times.", "Do their weekday profiles differ by less than 5 points every day?", "M1",
            "Trips per day by weekday as an index (mean day = 100), visitors vs residents; same by month", "Trips only; no hourly data."),
    "Q16": ("Overnight tourists crowd the same few places more than day-trippers.",
            "Is N50 of international tourists at least 2 neighbourhoods lower than for international excursionists?", "T4",
            "N50 (see Q1) by visitor type", "Same as Q1."),
    "Q17": ("The tourist mix is always the same countries.", "Which country markets grew more than 20% (January-August 2023->2025)?", "T8",
            "Change in January-August presences per country with at least 1% of presences", "Presences, not people; equivalent months only."),
    "Q18": ("Foreign tourists all come in summer.", "Are at least 16 of the 20 main country markets summer markets (June-August >= 1.30x the other months)?",
            "T8", "June-August / other nine months per country (full years 2023-2024); seasonal index per month; peak and lowest month",
            "Presences, not people; small countries grouped as NA are left out."),
    "Q19": ("Every nationality goes to the same neighbourhoods.", "Do the 20 main markets share at least 7 of their top-10 neighbourhoods, and do they have niches of their own?",
            "T8", "Overlap of each market's top 10 with the international top 10; location quotient (LQ) per neighbourhood with a base of 1,000 presences per month",
            "Neighbourhood x country values exist by year only (no visitor type); LQ uses presences."),
    "Q20": ("International visitors are overnight tourists.", "Are overnight tourists at least half of the presences in at least 16 of the 20 main markets?",
            "T8", "Share of overnight tourists ('Turista') in each country's presences",
            "Presences, not people; a person who is a tourist one month and an excursionist another counts in both."),
}
SHORT_NAMES = {"Vallvidrera, el Tibidabo i les Planes": "Vallvidrera-Tibidabo", "Sant Pere, Santa Caterina i la Ribera": "Sant Pere-la Ribera",
               "la Vila Olímpica del Poblenou": "Vila Olímpica"}
NAT_COLORS = {"Turista": "#0072B2", "Excursionista": "#56B4E9"}


# ---------------------------------------------------------------------------------------------------------------
# Figure helpers
# ---------------------------------------------------------------------------------------------------------------
def style(ax, ylabel="", yfmt=None):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#9a9a9a")
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=9)
    if yfmt == "pct":
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    elif yfmt == "k":
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:.0f}k"))


def save(fig, name, title, subtitle=""):
    h = fig.get_figheight()
    fig.text(0.01, 1 - 0.12 / h, title, ha="left", va="top", fontsize=12.5, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.01, 1 - 0.42 / h, subtitle, ha="left", va="top", fontsize=9.5, color=MUTED)
    fig.text(0.01, 0.06 / h, SOURCE, ha="left", va="bottom", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.25 / h, 1, 1 - (0.75 if subtitle else 0.45) / h))
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / name, dpi=170, facecolor="white")
    plt.close(fig)
    return FIG / name


def map_values(values_by_ss):
    """{cod_barrio_ss: value} -> {map code: value} for convive.plot_map."""
    geo, table = cv.load_barris()
    to_map = dict(zip(table["cod_barrio_ss"], table["cod_barrio"]))
    return geo, {to_map[k]: v for k, v in values_by_ss.items() if k in to_map}


# ---------------------------------------------------------------------------------------------------------------
# Figures
# ---------------------------------------------------------------------------------------------------------------
def fig_q1(t, r):
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for origin, tipo, label in [("Todos", "Todos", "All visitors"), ("Internacional", "Turista", "International"),
                                ("Nacional", "Todos", "National"), ("Regional", "Todos", "Regional")]:
        v = np.sort(R.barrio_means(t, origin, tipo)["visitantes"].to_numpy())[::-1]
        cum = np.cumsum(v) / v.sum()
        x = np.arange(1, len(v) + 1)
        ax.plot(x, cum, color=COLORS[label], lw=2, label=label + (" tourists" if label == "International" else ""))
        n50 = R.n_share(v)
        ax.plot([n50], [cum[n50 - 1]], marker=MARKERS[label], ms=8, color=COLORS[label], mec="white")
        offset = {"All visitors": (-62, 10), "International": (-62, 12), "National": (8, -16), "Regional": (10, -4)}[label]
        ax.annotate(f"N50 = {n50}", (n50, cum[n50 - 1]), xytext=offset, textcoords="offset points", fontsize=8.5,
                    color=COLORS[label] if label != "National" else INK, fontweight="bold")
    ax.axhline(0.5, color="#9a9a9a", lw=1, ls="--")
    ax.axvspan(0, 11, color="#0072B2", alpha=0.06)
    ax.text(5.5, 0.06, "Concentrated\nzone (N50 ≤ 11)", ha="center", fontsize=8, color=MUTED)
    ax.set_xlim(0, 73)
    ax.set_xlabel("Neighbourhoods, from most to least visited", color=MUTED, fontsize=9)
    style(ax, "Cumulative share of presences", "pct")
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    return save(fig, "q1_concentration.png", "Q1 · Half of all visitor presences fall in 10 of 73 neighbourhoods",
                "Cumulative share of mean monthly visitor presences, Jan 2023-Aug 2025. Rule: concentrated if N50 ≤ 11 (15% of neighbourhoods).")


def fig_q2(t, r):
    city = t["city_monthly"]
    fig, ax = plt.subplots(figsize=(9, 4.4))
    for origin, tipo, label in [("Todos", "Todos", "All visitors"), ("Internacional", "Turista", "International"),
                                ("Nacional", "Todos", "National"), ("Regional", "Todos", "Regional")]:
        g = R.scope(city, origin, tipo).groupby(["year", "month"])["visitantes"].sum().reset_index()
        g = g[g["year"].isin(R.FULL_YEARS)].groupby("month")["visitantes"].mean()
        idx = g / g.mean() * 100
        ax.plot(idx.index, idx.values, color=COLORS[label], lw=2, marker=MARKERS[label], ms=5, mec="white",
                label=label + (" tourists" if label == "International" else ""))
    ax.axvspan(5.5, 8.5, color="#E69F00", alpha=0.08)
    ax.text(7, 63, "Jun-Aug", ha="center", fontsize=8.5, color=MUTED)
    ax.axhline(100, color="#9a9a9a", lw=1)
    ax.set_xticks(range(1, 13), R.MONTHS_EN)
    style(ax, "Index, mean month = 100")
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="upper left")
    ax.set_ylim(60, 150)
    q = r["Q2"]["table"]
    a = q[q["origin"] == "All visitors"]["summer_vs_rest"].round(2).tolist()
    return save(fig, "q2_seasonality.png", "Q2 · Seasonality is moderate: summer is 13-14% above the other months",
                f"Monthly index, mean of 2023 and 2024. Summer / rest = {a[0]} and {a[1]} for all visitors. Rule: summer-only if ≥ 1.30.")


def fig_q3(t, r):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1.35, 1]})
    s = r["Q3"]["monthly_share"]
    dates = pd.to_datetime(s.index, format="%Y%m")
    colors = ["#0072B2" if v > 0.5 else "#a6c8e0" for v in s.values]
    a1.bar(dates, s.values, width=20, color=colors)
    a1.axhline(0.5, color=INK, lw=1, ls="--")
    a1.text(dates[0], 0.515, "50% majority line", fontsize=8, color=INK)
    style(a1, "International share of monthly visitors", "pct")
    a1.set_ylim(0, 0.75)
    a1.set_title(f"International majority in {int((s > 0.5).sum())} of {len(s)} months (rule needs 24)", fontsize=10, loc="left", color=INK)
    top = R.country_share(t).drop("NA", errors="ignore").head(10)[::-1]
    a2.barh(top.index, top.values, color="#0072B2", height=0.6)
    for y, v in enumerate(top.values):
        a2.text(v + 0.002, y, f"{v:.1%}", va="center", fontsize=8.5, color=INK)
    style(a2, "", None)
    a2.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    a2.yaxis.grid(False)
    a2.set_title("Top 10 countries, share of international presences", fontsize=10, loc="left", color=INK)
    return save(fig, "q3_origin_countries.png", "Q3 · Foreign visitors are the majority in most months, but not in winter",
                "Left: T1 unique visitors. Right: T8 presences by country of residence, Jan 2023-Aug 2025.")


def fig_q4(t, r):
    b = r["Q4"]["barrio"].sort_values("weekend_change")
    fig, ax = plt.subplots(figsize=(11, 4.8))
    colors = np.where(b["weekend_change"] >= 0.10, "#0072B2", np.where(b["weekend_change"] <= -0.05, "#E69F00", "#bdbdbd"))
    ax.bar(range(len(b)), b["weekend_change"], color=colors, width=0.75)
    ax.axhline(0.10, color="#0072B2", lw=1, ls="--")
    ax.axhline(-0.05, color="#E69F00", lw=1, ls="--")
    ax.text(0, 0.11, "+10%: weekend flood", fontsize=8, color=INK)
    ax.text(0, -0.04, "-5%: fewer at weekends", fontsize=8, color=INK)
    for i, row in enumerate(b.itertuples()):
        if i < 3 or i >= len(b) - 4:
            ax.text(i, row.weekend_change + (0.01 if row.weekend_change > 0 else -0.01), row.barrio_name, rotation=90,
                    fontsize=7, ha="center", va="bottom" if row.weekend_change > 0 else "top", color=INK)
    ax.set_ylim(-0.75, 0.45)
    ax.set_xticks([])
    ax.set_xlabel("73 neighbourhoods, sorted", color=MUTED, fontsize=9)
    style(ax, "Weekend vs weekday, mean daily visitors", "pct")
    c = r["Q4"]["table"].iloc[0]
    return save(fig, "q4_weekend_barrios.png", f"Q4 · Only {r['Q4']['n_flood']} of 73 neighbourhoods get a weekend flood; the city has {c.weekend_change:+.1%} at weekends",
                "Mean daily unique visitors on Saturday-Sunday vs Monday-Friday per neighbourhood (T5), Jan 2023-Aug 2025.")


def fig_q5(t, r):
    city = r["Q5"]["table"]
    rows = [("Todos", "Todos", "All visitors"), ("Internacional", "Turista", "International tourists"),
            ("Internacional", "Excursionista", "International excursionists"), ("Nacional", "Todos", "National"), ("Regional", "Todos", "Regional")]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    width = 0.24
    shades = {2023: "#c7c7c7", 2024: "#8a8a8a", 2025: "#333333"}
    for j, year in enumerate((2023, 2024, 2025)):
        vals = [city[(city["origen"] == o) & (city["tipo_visitante"] == ty)][f"mean_monthly_{year}"].iloc[0] for o, ty, _ in rows]
        ax.bar(np.arange(len(rows)) + (j - 1) * width, vals, width=width * 0.92, color=shades[year], label=str(year))
    for i, (o, ty, _) in enumerate(rows):
        row = city[(city["origen"] == o) & (city["tipo_visitante"] == ty)].iloc[0]
        top = row[["mean_monthly_2023", "mean_monthly_2024", "mean_monthly_2025"]].max()
        ax.text(i, top * 1.03, f"{row.change_2023_2024:+.1%} / {row.change_2024_2025:+.1%}\n{row.verdict}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(range(len(rows)), [x[2] for x in rows], fontsize=9)
    style(ax, "Mean unique visitors per month, Jan-Aug", "k")
    ax.legend(frameon=False, fontsize=9, ncol=3, loc="upper right")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    return save(fig, "q5_growth.png", "Q5 · Growth continues but slows; it comes from international visitors",
                "January-August monthly means (equivalent months). Labels: change 2023->2024 / 2024->2025. Rule: keeps growing if > +2% in both.")


def fig_q6(t, r):
    d = r["Q6"]["table"].sort_values("visitor_share")
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    y = np.arange(len(d))
    ax.hlines(y, d["share_low"], d["share_high"], color="#9a9a9a", lw=3, alpha=0.6, label="Bound (zeros = 0-14 trips)")
    ax.plot(d["visitor_share"], y, "o", color="#0072B2", ms=8, mec="white", label="Visitor share of incoming trips")
    for yy, row in zip(y, d.itertuples()):
        ax.text(row.share_high + 0.01, yy, f"{row.visitor_share:.1%}", va="center", fontsize=8.5, color=INK)
    ax.axvline(0.5, color=INK, lw=1, ls="--")
    ax.set_yticks(y, d["barrio_name"], fontsize=9)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID)
    ax.set_xlim(0.35, 0.8)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    return save(fig, "q6_tourist_barris.png", f"Q6 · Visitors make most incoming trips in {r['Q6']['value']} of the 10 most-visited neighbourhoods",
                "Share of trips arriving in each neighbourhood made by visitors (M1, Jan 2023-Aug 2025). Rule: > 50%, robust if the low bound is > 50%.")


def fig_q7(t, r):
    df = t["overnight"]
    df = df[df["year"] == 2024]
    fig, ax = plt.subplots(figsize=(8.5, 4))
    for i, (origin, label) in enumerate([("Internacional", "International"), ("Nacional", "National")]):
        g = df[df["origen"] == origin].sort_values("pernoctaciones")
        ax.bar(g["pernoctaciones"] + (i - 0.5) * 0.38, g["share_of_year_origin"], width=0.36, color=COLORS[label], label=label + " tourists")
    ax.axvspan(0.5, 2.5, color="#9a9a9a", alpha=0.08)
    ax.text(1.5, 0.52, "1-2 nights", ha="center", fontsize=8.5, color=MUTED)
    ax.set_xticks(range(1, 8))
    ax.set_xlabel("Nights spent in Barcelona within the week", color=MUTED, fontsize=9)
    style(ax, "Share of the week's tourists", "pct")
    ax.legend(frameon=False, fontsize=9)
    y = r["Q7"]["table"]
    y = y[y["year"] == 2024]
    return save(fig, "q7_nights.png", "Q7 · Most tourists spend one or two nights in a given week",
                f"T3, 2024, complete weeks. 1-2 nights: international {y.iloc[0].up_to_two:.0%}, national {y.iloc[1].up_to_two:.0%}. Rule: belief holds if ≥ 50%.")


def fig_q9(t, r):
    d = r["Q9"]["table"].copy()
    d["date"] = pd.to_datetime(d["date"])
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.plot(d["date"], d["deviation"], color="#bdbdbd", lw=0.8)
    p, lo = r["Q9"]["peaks"], r["Q9"]["lows"]
    ax.plot(pd.to_datetime(p["date"]), p["deviation"], "o", color="#0072B2", ms=6, mec="white", label="Unusual peak (≥ +15%)")
    ax.plot(pd.to_datetime(lo["date"]), lo["deviation"], "s", color="#E69F00", ms=5, mec="white", label="Unusual low (≤ -15%)")
    for row in p.head(4).itertuples():
        ax.annotate(f"{row.date}", (pd.Timestamp(row.date), row.deviation), xytext=(4, 2), textcoords="offset points", fontsize=7.5, color=INK)
    ax.axhline(0.15, color="#0072B2", lw=0.8, ls="--")
    ax.axhline(-0.15, color="#E69F00", lw=0.8, ls="--")
    style(ax, "Deviation from same weekday & month", "pct")
    ax.legend(frameon=False, fontsize=8.5, loc="lower left")
    return save(fig, "q9_unusual_days.png", f"Q9 · {len(p)} unusual peak days and {len(lo)} unusual low days in 971 days",
                "Daily unique visitors (T2) against the median of the same weekday in the same month and year.")


def fig_q10(t, r):
    lq = r["Q10"]["table"].set_index("barrio_name")
    _, table = cv.load_barris()
    name_to_ss = dict(zip(table["barrio_name"], table["cod_barrio_ss"]))
    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6))
    norm = mcolors.TwoSlopeNorm(vmin=0.3, vcenter=1, vmax=2.5)
    for ax, origin, label in zip(axes, R.VISITOR_ORIGINS, ["International", "National", "Regional"]):
        geo, values = map_values({name_to_ss[n]: v for n, v in lq[origin].items() if n in name_to_ss})
        cv.plot_map(geo, values, ax=ax, cmap="RdBu_r", norm=norm, colorbar=False)
        n_spec = int((lq[origin] >= 1.25).sum())
        ax.set_title(f"{label}\n{n_spec} neighbourhoods with LQ ≥ 1.25", fontsize=10, color=INK)
    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap="RdBu_r")
    fig.colorbar(sm, ax=axes, shrink=0.7, label="Location quotient (1 = city mix)")
    fig.text(0.01, 1.06, "Q10 · Regional day-trippers and foreign tourists are over-represented in different neighbourhoods",
             ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.01, 1.01, "Location quotient of mean monthly presences by origin (T4). Red: more of this origin than the city mix; blue: less.",
             fontsize=9.5, color=MUTED)
    fig.text(0.01, -0.02, SOURCE, fontsize=7.5, color=MUTED)
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "q10_lq_maps.png", dpi=170, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def fig_residence(t, r):
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.6))
    prov = r["Q12"]["table"].set_index("province")["share"].drop("NA", errors="ignore").head(10)[::-1]
    a1.barh(prov.index, prov.values, color="#E69F00", height=0.6)
    for yy, v in enumerate(prov.values):
        a1.text(v + 0.002, yy, f"{v:.1%}", va="center", fontsize=8.5, color=INK)
    a1.set_title("National visitors: top 10 provinces (T7)", fontsize=10, loc="left", color=INK)
    mun = r["Q13"]["table"].set_index("municipality")["share"].drop("NA", errors="ignore").head(10)[::-1]
    amb = {R.norm(m) for m in R.AMB_MUNICIPALITIES}
    a2.barh(mun.index, mun.values, color=["#009E73" if R.norm(m) in amb else "#9ad3c0" for m in mun.index], height=0.6)
    for yy, v in enumerate(mun.values):
        a2.text(v + 0.001, yy, f"{v:.1%}", va="center", fontsize=8.5, color=INK)
    a2.set_title("Regional visitors: top 10 municipalities (T6; dark = AMB)", fontsize=10, loc="left", color=INK)
    for a in (a1, a2):
        style(a)
        a.yaxis.grid(False)
        a.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
        a.tick_params(axis="y", labelsize=8.5)
    return save(fig, "q12_q13_residence.png",
                f"Q12-Q13 · Madrid is {r['Q12']['value']:.0%} of national visitors; the metropolitan ring is {r['Q13']['value']:.0%} of regional ones",
                "Shares of presences by place of residence, Jan 2023-Aug 2025.")


def fig_q14(t, r):
    a = r["Q14"]["table"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    ages = ["18-29", "30-39", "40-49", "50-59", "60-69", "70+"]
    incomes = ["Bajo", "Medio", "Medio-Alto", "Alto"]
    for i, (origin, label) in enumerate([("National", "National"), ("Regional", "Regional")]):
        row = a[a["origin"] == origin].iloc[0]
        a1.bar(np.arange(6) + (i - 0.5) * 0.38, [row.get(f"age_{x}", 0) for x in ages], width=0.36, color=COLORS[label], label=label)
        a2.bar(np.arange(4) + (i - 0.5) * 0.38, [row.get(f"income_{x}", 0) for x in incomes], width=0.36, color=COLORS[label], label=label)
    a1.set_xticks(range(6), ages)
    a2.set_xticks(range(4), ["Low", "Medium", "Medium-high", "High"])
    a1.set_title("Age group", fontsize=10, loc="left", color=INK)
    a2.set_title("Income level (of the area of residence)", fontsize=10, loc="left", color=INK)
    for ax in (a1, a2):
        style(ax, "Share of presences", "pct")
        ax.legend(frameon=False, fontsize=9)
    return save(fig, "q14_profile.png", "Q14 · Visitors are not mainly young, but mostly medium-high or high income",
                "T9, national and regional visitors (the file has no international rows, issue I9). Shares of presences.")


def fig_q15(t, r):
    idx = r["Q15"]["table"].set_index("weekday_idx")
    month = r["Q15"]["month"].set_index("month")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    for col, label in [("Visitante", "Visitors"), ("Residente", "Resident")]:
        a1.plot(range(7), idx[col].values, color=COLORS[label], lw=2, marker=MARKERS[label], ms=7, mec="white", label=label + ("s" if label == "Resident" else ""))
        a2.plot(month.index, month[col].values, color=COLORS[label], lw=2, marker=MARKERS[label], ms=6, mec="white", label=label + ("s" if label == "Resident" else ""))
    a1.set_xticks(range(7), R.WEEKDAYS_EN)
    a2.set_xticks(range(1, 13), R.MONTHS_EN)
    a1.set_title("By weekday (mean day = 100)", fontsize=10, loc="left", color=INK)
    a2.set_title("By month, 2023-2024 (mean month = 100)", fontsize=10, loc="left", color=INK)
    for ax in (a1, a2):
        ax.axhline(100, color="#9a9a9a", lw=1)
        style(ax, "Index of incoming trips")
        ax.legend(frameon=False, fontsize=9)
    return save(fig, "q15_rhythm.png", f"Q15 · Visitors and residents move at different times (gap up to {r['Q15']['value']:.0f} points)",
                "Trips between neighbourhoods (M1). Residents drop at weekends and in August; visitors much less so.")


def fig_q17(t, r):
    k = r["Q17"]["table"].sort_values("change_2023_2025")
    fig, ax = plt.subplots(figsize=(9.5, 5))
    colors = ["#0072B2" if v > 0.2 else ("#bdbdbd" if v >= 0 else "#E69F00") for v in k["change_2023_2025"]]
    ax.barh(k["country"], k["change_2023_2025"], color=colors, height=0.6)
    for yy, v in enumerate(k["change_2023_2025"]):
        ax.text(v + (0.02 if v >= 0 else -0.02), yy, f"{v:+.0%}", va="center", ha="left" if v >= 0 else "right", fontsize=8.5, color=INK)
    ax.axvline(0.2, color="#0072B2", lw=1, ls="--")
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_xlim(min(-0.7, k["change_2023_2025"].min() - 0.2), k["change_2023_2025"].max() + 0.25)
    style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.tick_params(axis="y", labelsize=8.5)
    return save(fig, "q17_country_growth.png", f"Q17 · {r['Q17']['value']} country markets grew by more than 20% between 2023 and 2025",
                "Change in January-August presences (T8), countries with at least 1% of international presences in 2023.")


def fig_nat_markets(t, r):
    """Q20 and the main markets: share of international presences, split overnight / day trip."""
    p = r["nationalities"].head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 6.2))
    tour = p["share"] * p["tourist_share"]
    exc = p["share"] - tour
    ax.barh(p["country"], tour, color=NAT_COLORS["Turista"], height=0.62, label="Overnight tourists", edgecolor="white", linewidth=1)
    ax.barh(p["country"], exc, left=tour, color=NAT_COLORS["Excursionista"], height=0.62, label="Day-trippers (excursionists)",
            edgecolor="white", linewidth=1, hatch="///")
    for yy, row in enumerate(p.itertuples()):
        ax.text(row.share + 0.002, yy, f"{row.share:.1%}  ·  {row.tourist_share:.0%} overnight  ·  {row.growth_23_25:+.0%} since 2023",
                va="center", fontsize=8, color=INK)
    style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.set_xlim(0, p["share"].max() * 1.6)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(0.02))
    ax.tick_params(axis="y", labelsize=9)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    ax.set_xlabel("Share of international presences, Jan 2023-Aug 2025 (growth: January-August 2023->2025)", color=MUTED, fontsize=9)
    return save(fig, "nat_markets.png", f"Nationalities · the 20 main markets hold {r['nationalities'].head(20)['share'].sum():.0%} of international presences",
                "T8, country of residence. Every main market is mostly overnight tourists (Q20); France and Korea have the most day-trippers.")


def fig_nat_season(t, r):
    """Q18: seasonal index per country and month (mean month = 100)."""
    import nationalities as N
    p = r["nationalities"].head(20).sort_values("summer_ratio", ascending=False)
    idx = N.seasonal_index(t, p["country"].tolist())
    fig, ax = plt.subplots(figsize=(10.5, 7.2))
    norm = mcolors.TwoSlopeNorm(vmin=50, vcenter=100, vmax=150)
    im = ax.imshow(idx.values, cmap="RdBu_r", norm=norm, aspect="auto")
    for i in range(idx.shape[0]):
        for j in range(idx.shape[1]):
            v = idx.values[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7.5, color="white" if abs(v - 100) > 32 else INK)
    ax.set_xticks(range(12), R.MONTHS_EN, fontsize=9)
    labels = [f"{c}  ({x:.2f}x){'  ●' if x >= 1.30 else ''}" for c, x in zip(p["country"], p["summer_ratio"])]
    ax.set_yticks(range(len(p)), labels, fontsize=8.5)
    ax.add_patch(matplotlib.patches.Rectangle((4.5, -0.5), 3, len(p), fill=False, edgecolor=INK, linewidth=1.6))
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    cb = fig.colorbar(im, ax=ax, shrink=0.6, pad=0.02)
    cb.set_label("Index (mean month of the country = 100)", color=MUTED, fontsize=9)
    n = r["Q18"]["value"]
    return save(fig, "nat_season_heatmap.png", f"Q18 · Only {n} of the 20 main markets are summer markets; Asian markets peak in autumn and winter",
                "Monthly index per country, mean of 2023 and 2024. Box: June-August. In brackets: summer / other months; ● = summer market (>= 1.30).")


def fig_nat_maps(t, r):
    """Q19: where each nationality is over-represented (LQ), six markets."""
    import nationalities as N
    lq = N.location_quotients(t)
    countries = ["France", "United Kingdom", "United States", "Germany", "Korea S, Republic of", "China"]
    fig, axes = plt.subplots(2, 3, figsize=(12, 8.4))
    norm = mcolors.TwoSlopeNorm(vmin=0.3, vcenter=1, vmax=2.5)
    prof = r["nationalities"].set_index("country")
    for ax, c in zip(axes.flat, countries):
        d = lq[(lq["country"] == c) & lq["reliable"]]
        geo, values = map_values(dict(zip(d["cod_barrio"], d["lq"].clip(upper=2.5))))
        cv.plot_map(geo, values, ax=ax, cmap="RdBu_r", norm=norm, colorbar=False)
        row = prof.loc[c]
        name = "South Korea" if c.startswith("Korea") else c
        niche = SHORT_NAMES.get(row["distinctive_barrio"], row["distinctive_barrio"])
        ax.set_title(f"{name} · {row['share']:.1%} of presences\nmost over-represented: {niche} (LQ {row['distinctive_lq']:.2f})",
                     fontsize=9.5, color=INK)
    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap="RdBu_r")
    fig.colorbar(sm, ax=axes, shrink=0.55, pad=0.04, label="Location quotient (1 = mix of all international visitors)")
    fig.text(0.01, 1.04, "Q19 · Every nationality shares the central neighbourhoods, but most have a niche of their own",
             ha="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.01, 1.005, "Location quotient by neighbourhood (T8, mean 2023-2025). Red: over-represented. Grey: fewer than 1,000 presences per month of that country.",
             fontsize=9.5, color=MUTED)
    fig.text(0.01, -0.01, SOURCE, fontsize=7.5, color=MUTED)
    fig.savefig(FIG / "nat_lq_maps.png", dpi=170, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def fig_nat_regions(t, r):
    reg = r["regions"].iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    yy = np.arange(len(reg))
    for k, (year, colour) in enumerate([(2023, "#BDBDBD"), (2024, "#7F7F7F"), (2025, "#333333")]):
        ax.barh(yy + (k - 1) * 0.26, reg[f"share_jan_aug_{year}"], height=0.24, color=colour, label=f"Jan-Aug {year}")
    for i, row in enumerate(reg.itertuples()):
        ax.text(max(row.share_jan_aug_2023, row.share_jan_aug_2025) + 0.006, i, f"{row.growth_23_25:+.0%}", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(yy, reg["region"], fontsize=9)
    style(ax)
    ax.yaxis.grid(False)
    ax.xaxis.grid(True, color=GRID)
    ax.xaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1, decimals=0))
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    ax.set_xlabel("Share of international presences (labels: change in presences 2023->2025)", color=MUTED, fontsize=9)
    return save(fig, "nat_regions.png", "Nationalities · Asia-Pacific (+76%) and Central-Eastern Europe (+66%) grow fastest; UK & Ireland fall",
                "World regions of residence, January-August of each year (T8).")


def fig_q8(t, r):
    year = 2024
    row = r["Q8"]["table"].query("year == @year").iloc[0]
    peak, low = R.MONTHS_EN.index(row.peak_month) + 1, R.MONTHS_EN.index(row.low_month) + 1
    b = t["barrio_monthly"].dropna(subset=["visitantes"])
    b = b[b["year"] == year].groupby(["month", "barrio_name"])["visitantes"].sum().unstack("month")
    rp, rl = b[peak].rank(ascending=False), b[low].rank(ascending=False)
    show = rl[(rl <= 12) | (rp <= 12)].index
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    for n in show:
        moved = rl[n] != rp[n]
        ax.plot([0, 1], [rl[n], rp[n]], color="#0072B2" if moved else "#bdbdbd", lw=2 if moved else 1.2, marker="o", ms=6, mec="white")
        ax.text(-0.03, rl[n], f"{int(rl[n])}. {n}", ha="right", va="center", fontsize=8, color=INK)
        ax.text(1.03, rp[n], f"{int(rp[n])}. {n}", ha="left", va="center", fontsize=8, color=INK)
    ax.set_xlim(-0.9, 1.9)
    ax.invert_yaxis()
    ax.set_xticks([0, 1], [f"{row.low_month} {year} (lowest)", f"{row.peak_month} {year} (peak)"])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    return save(fig, "q8_rank_season.png", f"Q8 · The top 10 hardly changes between seasons ({row.top10_kept}/10 kept, ρ = {row.spearman:.3f})",
                "Rank by unique visitors (T4). Blue: neighbourhoods that change position.")


def fig_low_data(t, r):
    d = r["low_data"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={"width_ratios": [1.1, 1]})
    flag = d["low_data"]
    a1.scatter(d.loc[~flag, "resident_trips_in_2024"], d.loc[~flag, "mean_monthly_visitors"], s=26, color="#9a9a9a", label="Other neighbourhoods")
    a1.scatter(d.loc[flag, "resident_trips_in_2024"], d.loc[flag, "mean_monthly_visitors"], s=40, color="#E69F00", marker="D", ec="white", label="Low-data rule")
    for row in d[flag].itertuples():
        a1.annotate(row.barrio_name, (row.resident_trips_in_2024, row.mean_monthly_visitors), xytext=(5, -3), textcoords="offset points", fontsize=8, color=INK)
    a1.set_xscale("log")
    a1.set_yscale("log")
    a1.set_xlabel("Residents' trips into the neighbourhood, 2024 (M1)", color=MUTED, fontsize=9)
    style(a1, "Mean monthly unique visitors (T4)")
    a1.legend(frameon=False, fontsize=8.5, loc="lower right")
    a1.set_title("Residents move normally; visitors almost absent", fontsize=10, loc="left", color=INK)
    bm = t["barrio_monthly"].dropna(subset=["visitantes"]).groupby(["mes", "barrio_name"])["visitantes"].sum().unstack()
    dates = pd.to_datetime(bm.index, format="%Y%m")
    for name, color, marker in [("Verdun", "#E69F00", "D"), ("la Teixonera", "#CC79A7", "^"), ("les Roquetes", "#9a9a9a", "s"),
                                ("la Prosperitat", "#0072B2", "o")]:
        a2.plot(dates, bm[name], color=color, lw=2, marker=marker, ms=4, label=name)
    a2.set_yscale("log")
    style(a2, "Unique visitors per month (log)")
    a2.legend(frameon=False, fontsize=8.5, ncol=2, loc="lower left")
    a2.set_title("Verdun and la Teixonera vs their neighbours", fontsize=10, loc="left", color=INK)
    return save(fig, "low_data_barris.png", "I8 · Neighbourhoods with very few data: few visitors, not missing files",
                "Left: each dot is a neighbourhood. Right: monthly T4 series. The two outliers are low in every month and in two independent products (T4 and M1).")


def fig_low_data_map(t, r):
    d = r["low_data"]
    _, table = cv.load_barris()
    name_to_ss = dict(zip(table["barrio_name"], table["cod_barrio_ss"]))
    geo, values = map_values({name_to_ss[n]: v for n, v in zip(d["barrio_name"], d["vs_median"]) if n in name_to_ss})
    fig, ax = plt.subplots(figsize=(7.5, 6))
    cv.plot_map(geo, values, ax=ax, cmap="Purples", log=True, legend_label="Visitors vs median neighbourhood (log)")
    low = d[d["low_data"]]
    _, codes = map_values({name_to_ss[n]: 1 for n in low["barrio_name"]})
    for f in geo["features"]:
        if f["properties"]["cod_barrio"] in codes:
            ring = np.array(cv._rings(f["geometry"])[0])
            ax.plot(ring[:, 0], ring[:, 1], color="#E69F00", lw=1.8)
            x, y = ring.mean(axis=0)
            ax.text(x, y, f["properties"]["NOM"], fontsize=7, ha="center", color=INK)
    return save(fig, "low_data_map.png", f"I8 · {len(low)} low-data neighbourhoods, all on the northern edge",
                "Mean monthly visitors relative to the median neighbourhood (T4). Orange outline: low-data rule.")


def make_figures(t, r):
    for f in (fig_q1, fig_q2, fig_q3, fig_q4, fig_q5, fig_q6, fig_q7, fig_q8, fig_q9, fig_q10, fig_residence, fig_q14, fig_q15,
              fig_q17, fig_low_data, fig_low_data_map, fig_nat_markets, fig_nat_season, fig_nat_maps, fig_nat_regions):
        f(t, r)
        print(f"  figure: {f.__name__}", flush=True)


# ---------------------------------------------------------------------------------------------------------------
# Markdown and CSV
# ---------------------------------------------------------------------------------------------------------------
def answers_table(r):
    rows = []
    for qid, (belief, question, data, metric, limit) in QUESTIONS.items():
        rows.append({"id": qid, "belief": belief, "question": question, "data": data, "metric": metric,
                     "decision_rule": R.THRESHOLDS[qid]["rule"], "answer": r[qid]["answer"], "verdict": r[qid]["verdict"],
                     "belief_holds": r[qid]["holds"],
                     "limitation": limit, "iteration": "Q1-Q6 quantified (3.2.4)" if int(qid[1:]) <= 6 else "New in Iteration 3 (3.2.1-3.2.3)"})
    return pd.DataFrame(rows)


def write_md(path, title, intro, sections):
    lines = [f"# {title}", "", f"CONVIVE · Team 102_A · Iteration 3 · generated by `research_report.py` on {date.today():%d %b %Y} "
             "from aggregated tables only. The results describe patterns, not causes.", "", intro, ""]
    for heading, body in sections:
        lines += [f"## {heading}", "", body, ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  {path.name}")


def q_block(r, qid, figure=None):
    belief, question, data, metric, limit = QUESTIONS[qid]
    text = (f"*Belief:* \"{belief}\"  \n*Question:* {question}  \n*Data:* {data} · *Metric:* {metric}  \n"
            f"*Decision rule:* {R.THRESHOLDS[qid]['rule']}  \n\n**Answer.** {r[qid]['answer']}  \n**Verdict: {r[qid]['verdict']}.** "
            f"Belief holds: **{r[qid]['holds']}**.  \n"
            f"*Limitation:* {limit}")
    if figure:
        text += f"\n\n![{qid}](figures/{figure})"
    return (f"{qid} · {question}", text)


def verdun_break(t):
    bm = t["barrio_monthly"].dropna(subset=["visitantes"]).groupby(["mes", "barrio_name"])["visitantes"].sum().unstack()["Verdun"]
    change = bm.pct_change()
    m = change.idxmin()
    before, after = bm.shift(1)[m], bm[m]
    return m, before, after, change[m], bm[bm.index < m].mean(), bm[bm.index >= m].mean()


def low_data_md(r, t):
    d = r["low_data"]
    low = d[d["low_data"]]
    v = d[d["barrio_name"] == "Verdun"].iloc[0]
    tx = d[d["barrio_name"] == "la Teixonera"].iloc[0]
    brk = verdun_break(t)
    pr = d[d["barrio_name"] == "la Prosperitat"].iloc[0]
    rows = "\n".join(f"| {x.barrio_name} | {x.distrito_name} | {x.mean_monthly_visitors:,.0f} | {x.vs_median:.1%} | "
                     f"{max(x.na_share_T6, x.na_share_T7, x.na_share_T8):.1%} | {x.resident_trips_vs_median:.2f} | {x.visitor_share_trips:.1%} | {x.reason} |"
                     for x in low.itertuples())
    return f"""The Business Manager asked us on 9 Nov to find out why some neighbourhoods have so few data (issue I8).

*Rule:* {R.LOW_DATA_RULE}

**{len(low)} of 73 neighbourhoods meet the rule**, all on the northern edge of the city (Nou Barris, Horta-Guinardó and Gràcia hills):

| Neighbourhood | District | Visitors per month (T4) | vs median | Max NA share T6-T8 | Residents' trips vs median | Visitor share of trips (M1) | Reason |
|---|---|---|---|---|---|---|---|
{rows}

**What the data show.**

1. **It is not a loading or code error.** The 73 codes match their names in every month of M1 (2.2.2 check 14), every file has its 32 months
   and T5 has data for Verdun on all 971 days. The low values come from Telefónica's files as published.
2. **Two kinds of "few data".** Most low-data neighbourhoods are small residential areas with few visitors, so many of their segments fall under
   the privacy threshold of 15 and are grouped as NA (e.g. {pct_fmt(low['na_share_T8'].max())} of Verdun's country rows). This is expected behaviour of the anonymisation.
3. **Verdun and la Teixonera are different: they are outliers, not just small.** Their residents' trips are normal ({v.resident_trips_vs_median:.2f}x and
   {tx.resident_trips_vs_median:.2f}x the median neighbourhood), but visitors are only {v.vs_median:.1%} and {tx.vs_median:.1%} of the median. Their neighbour la Prosperitat,
   with a similar number of residents' trips ({pr.resident_trips_vs_median:.2f}x), has {pr.mean_monthly_visitors / v.mean_monthly_visitors:,.0f} times more visitors than Verdun.
   The visitor share of incoming trips is {v.visitor_share_trips:.1%} in Verdun and {tx.visitor_share_trips:.1%} in la Teixonera (city: 44.7%).
4. **Two independent products agree.** T4 (people) and M1 (trips) are built differently, and both show almost no visitors there. So the cause lies upstream
   of both, in how Telefónica assigns visitors to these two areas, or in the areas themselves.
5. **Verdun has a break in its series.** Its visitors fall from {brk[1]:,.0f} to {brk[2]:,.0f} between {month_name(brk[0], -1)} and {month_name(brk[0])} ({brk[3]:+.0%}),
   and the mean before the break ({brk[4]:,.0f} per month) is {brk[4] / brk[5]:.1f} times the mean after it ({brk[5]:,.0f}). No neighbour shows this step
   (la Teixonera, les Roquetes and la Prosperitat stay level), so the break suggests a change in how Verdun is measured rather than a real collapse of visitors (to confirm with the BM).
   Even before the break, Verdun was far below its neighbours. Coefficient of variation: {v.cv_monthly:.2f} (la Teixonera {tx.cv_monthly:.2f}).

**Hypotheses we cannot test with these data** (to ask the Business Manager / Telefónica, recorded as I8 in the F/U register):
(a) the network-coverage areas used to place people are assigned to the neighbouring neighbourhoods; (b) the visitor classification (people whose
residence is outside Barcelona) leaves very few people in two purely residential areas; (c) a known limitation of the Smart Steps zoning.

**Decision for the analysis.** Low-data neighbourhoods stay in every table and map, flagged. They are excluded only where a ratio would be
unstable: change rates (base of 1,000 visitors, Q5) and rankings at the bottom. The dashboard shows the flag next to their values."""


def month_name(mes, shift=0):
    p = pd.Period(f"{mes[:4]}-{mes[4:]}", freq="M") + shift
    return p.strftime("%B %Y")


# Public calendar dates that coincide with a detected peak. A coincidence, not a proven cause.
CALENDAR = {"2023-04-23": "Sant Jordi (23 April)", "2025-04-28": "Iberian Peninsula power outage (28 April 2025)",
            "2023-05-28": "Spanish municipal elections (28 May 2023)"}


def q9_table(r):
    p = r["Q9"]["peaks"]
    lines = ["| Date | Weekday | Visitors | Expected (median) | Deviation | Public calendar coincidence (to verify) |", "|---|---|---|---|---|---|"]
    for row in p.itertuples():
        lines.append(f"| {row.date} | {row.weekday} | {row.visitantes:,.0f} | {row.expected:,.0f} | {row.deviation:+.1%} | {CALENDAR.get(row.date, '-')} |")
    return "\n".join(lines)


def nationality_md(r):
    p = r["nationalities"].head(20)
    rows = "\n".join(f"| {x.rank} | {x.country} | {x.region} | {x.share:.1%} | {x.tourist_share:.0%} | {x.growth_23_25:+.0%} | {x.summer_ratio:.2f} | "
                     f"{x.peak_month} | {x.top_barrio} | {x.distinctive_barrio} ({x.distinctive_lq:.2f}) |" for x in p.itertuples())
    reg = "\n".join(f"| {x.region} | {x.share_jan_aug_2023:.1%} | {x.share_jan_aug_2024:.1%} | {x.share_jan_aug_2025:.1%} | {x.growth_23_25:+.0%} |"
                     for x in r["regions"].itertuples())
    return f"""Country of residence of international visitors (T8), {len(r['nationalities'])} named countries. Shares are of presences
(person x neighbourhood); countries below 15 people in a neighbourhood are grouped as NA by Telefónica and left out of the denominator.
The full table, with every indicator for every country, is `3.2.1_nationality_profile.csv`.

**The 20 main markets** ({p['share'].sum():.1%} of international presences):

| # | Country | Region | Share | Overnight | Jan-Aug 2023->2025 | Summer / rest | Peak month | First neighbourhood | Most over-represented (LQ) |
|---|---|---|---|---|---|---|---|---|---|
{rows}

**World regions** (January-August, share of international presences):

| Region | 2023 | 2024 | 2025 | Change 2023->2025 |
|---|---|---|---|---|
{reg}

![Main markets](figures/nat_markets.png)

![Regions](figures/nat_regions.png)"""


def pct_fmt(x):
    return f"{x:.0%}"


def write_all(t, r):
    R.OUT.mkdir(parents=True, exist_ok=True)
    answers = answers_table(r)
    answers.to_csv(R.OUT / "3.2.4_quantified_answers.csv", index=False)
    r["low_data"].to_csv(R.OUT / "3.2.2_low_data_barris.csv", index=False)
    r["Q4"]["barrio"].to_csv(R.OUT / "3.2.3_weekend_by_barrio.csv", index=False)
    r["Q9"]["peaks"].to_csv(R.OUT / "3.2.3_unusual_days.csv", index=False)
    r["Q10"]["table"].to_csv(R.OUT / "3.2.2_location_quotients.csv", index=False)
    r["Q17"]["table"].to_csv(R.OUT / "3.2.1_country_growth.csv", index=False)
    r["nationalities"].to_csv(R.OUT / "3.2.1_nationality_profile.csv", index=False)
    r["regions"].to_csv(R.OUT / "3.2.1_world_regions.csv", index=False)
    summary = {k: {"verdict": v["verdict"], "answer": v["answer"], "value": v["value"]} for k, v in r.items() if isinstance(v, dict)}
    (R.OUT / "3.2.4_summary.json").write_text(pd.Series(summary).to_json(indent=1, force_ascii=False), encoding="utf-8")

    figures = {"Q1": "q1_concentration.png", "Q2": "q2_seasonality.png", "Q3": "q3_origin_countries.png", "Q4": "q4_weekend_barrios.png",
               "Q5": "q5_growth.png", "Q6": "q6_tourist_barris.png", "Q7": "q7_nights.png", "Q8": "q8_rank_season.png",
               "Q9": "q9_unusual_days.png", "Q10": "q10_lq_maps.png", "Q12": "q12_q13_residence.png", "Q14": "q14_profile.png",
               "Q15": "q15_rhythm.png", "Q17": "q17_country_growth.png",
               "Q18": "nat_season_heatmap.png", "Q19": "nat_lq_maps.png", "Q20": "nat_markets.png"}
    table_lines = ["| ID | Belief | Metric | Decision rule | Answer | Verdict | Belief holds? |", "|---|---|---|---|---|---|---|"]
    for row in answers.itertuples():
        table_lines.append(f"| {row.id} | {row.belief} | {row.metric} | {row.decision_rule} | {row.answer} | **{row.verdict}** | {row.belief_holds} |")
    write_md(R.OUT / "3.2.4_quantified_answers.md", "3.2.4 Quantified criteria and answers (Q1-Q6, plus Q7-Q20)",
             "Business Manager feedback of 9 Nov (I10): every question must be precise and quantified, with an explicit criterion so that the data can "
             "answer it. Each rule below was fixed in `research.THRESHOLDS` before the answer was computed. A change to a rule is a change request.",
             [("Question -> metric -> threshold -> answer", "\n".join(table_lines))] + [q_block(r, q, figures.get(q)) for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6"]])
    write_md(R.OUT / "3.2.1_exploratory_analysis.md", "3.2.1 Exploratory analysis: who visits and where they come from",
             "Questions about the visitors themselves, with the tourist focus asked for at the Iteration 2 demo: country of residence, province, municipality, profile and market growth.",
             [q_block(r, "Q11", "q3_origin_countries.png"), q_block(r, "Q12", "q12_q13_residence.png"), q_block(r, "Q13"),
              q_block(r, "Q14", "q14_profile.png"), q_block(r, "Q17", "q17_country_growth.png"),
              ("Nationalities of international visitors in detail", nationality_md(r)),
              q_block(r, "Q20", "nat_markets.png"), q_block(r, "Q18", "nat_season_heatmap.png"), q_block(r, "Q19", "nat_lq_maps.png"),
              ("Data limits found", "- T9 has no international visitors (I9), so the profile covers national and regional visitors only.\n"
               "- Country, province and municipality shares are shares of presences (person x neighbourhood). The largest single neighbourhood value is a lower bound of people.\n"
               "- M3 (trips from municipalities to neighbourhoods) still has 43.7% repeated keys (I7); Q13 uses T6 only until the BM answers.")])
    write_md(R.OUT / "3.2.2_geographic_analysis.md", "3.2.2 Geographic analysis: where visitors are",
             "Concentration, specialisation by origin, stability of the ranking, visitors' vs residents' trips, and the neighbourhoods with very few data (I8).",
             [q_block(r, "Q1", "q1_concentration.png"), q_block(r, "Q16"), q_block(r, "Q6", "q6_tourist_barris.png"),
              q_block(r, "Q8", "q8_rank_season.png"), q_block(r, "Q10", "q10_lq_maps.png"),
              ("I8 · Neighbourhoods with very few data", low_data_md(r, t) + "\n\n![I8](figures/low_data_barris.png)\n\n![I8 map](figures/low_data_map.png)")])
    write_md(R.OUT / "3.2.3_temporal_analysis.md", "3.2.3 Temporal analysis: when visitors come",
             "Months, weekdays, equivalent January-August periods, unusual days, length of stay and the rhythm of visitors vs residents.",
             [q_block(r, "Q2", "q2_seasonality.png"), q_block(r, "Q4", "q4_weekend_barrios.png"), q_block(r, "Q5", "q5_growth.png"),
              q_block(r, "Q7", "q7_nights.png"), q_block(r, "Q9", "q9_unusual_days.png"), ("Q9 · Peak days", q9_table(r)), q_block(r, "Q15", "q15_rhythm.png"),
              ("Data limits found", "- Three days are missing in every daily file (2024-02-11, 2025-04-13, 2025-05-20); no imputation.\n"
               "- 2025 covers January to August: growth uses equivalent months only.\n"
               "- The causes of peak days need an external event calendar; the data only date them.")])
    rq = ["| ID | Belief | Question (quantified) | Data | Metric | Decision rule | Verdict | Belief holds? |", "|---|---|---|---|---|---|---|---|"]
    for row in answers.itertuples():
        rq.append(f"| {row.id} | {row.belief} | {row.question} | {row.data} | {row.metric} | {row.decision_rule} | {row.verdict} | {row.belief_holds} |")
    write_md(R.OUT / "3.2.0_ResearchQuestions_v0.3.md", "CONVIVE Research Questions v0.3 (WBS 3.2.0)",
             "v0.3 applies the Business Manager feedback of 9 Nov (I10, change C12): every question now states a metric and an explicit threshold, "
             "Q3 adds the breakdown by country of residence, Q16-Q17 add more concrete questions about tourists, and Q18-Q20 analyse the "
             "nationalities of international visitors (season, neighbourhoods, overnight vs day trip). Validation by the BM is pending.",
             [("Questions", "\n".join(rq)),
              ("Version history", "| Version | Date | Change |\n|---|---|---|\n| v0.1 | 5 Nov 2026 | 15 questions, Q1-Q6 for the 9 Nov demo |\n"
               "| v0.2 | 8 Nov 2026 | One-page version of Q1-Q6 for the professor |\n"
               "| v0.3 | 18 Nov 2026 | Metric and decision rule for every question; Q3 by country (T8); new tourist questions Q16-Q17; low-data neighbourhoods (I8); nationalities Q18-Q20 |")])


def main():
    t, r = R.run_all()
    print("Writing figures...")
    make_figures(t, r)
    print("Writing reports...")
    write_all(t, r)


if __name__ == "__main__":
    main()
