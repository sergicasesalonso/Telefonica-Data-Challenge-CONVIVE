"""CONVIVE - Iteration 3 analysis on the aggregated tables (WBS 3.2.1 to 3.2.4).

Reads ONLY aggregated tables (deliverables/iteration2/3.1.6_stats/ and deliverables/iteration3/2.2.1_aggregates/),
never the raw data. Each research question has:

    question -> metric -> explicit threshold (decision rule) -> answer computed from the data -> verdict -> limitation

The thresholds are written in THRESHOLDS below, BEFORE the answer is computed, so the verdict follows from a rule
and not from the number. Run:  python research.py   (writes deliverables/iteration3/3.2.x outputs)
"""

import json
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

import nationalities as N

HERE = Path(__file__).resolve().parent
STATS = HERE / "deliverables" / "iteration2" / "3.1.6_stats"
AGG = HERE / "deliverables" / "iteration3" / "2.2.1_aggregates"
OUT = HERE / "deliverables" / "iteration3"
LEVELS_CSV = HERE / "deliverables" / "iteration2" / "2.1.1_geographic_levels.csv"

VISITOR_ORIGINS = ["Internacional", "Nacional", "Regional"]
ORIGIN_EN = {"Internacional": "International", "Nacional": "National", "Regional": "Regional", "Residente": "Resident",
             "Todos": "All visitors"}
TYPE_EN = {"Turista": "tourists", "Excursionista": "excursionists", "Todos": "all"}
WEEKDAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FULL_YEARS = [2023, 2024]
N_BARRIS = 73

# ---------------------------------------------------------------------------------------------------------------
# Decision rules (3.2.4). Fixed before the answers are computed; changing one is a change request (F/U register).
# ---------------------------------------------------------------------------------------------------------------
THRESHOLDS = {
    "Q1": {"rule": "Visitors are CONCENTRATED if 50% of visitor presences fall in at most 11 neighbourhoods (15% of 73), "
                   "i.e. N50 <= 11. SPREAD if N50 >= 22 (30% of 73). In between: MODERATELY concentrated.",
           "n50_concentrated": 11, "n50_spread": 22},
    "Q2": {"rule": "SUMMER-ONLY pattern if the June-August mean is at least 30% above the mean of the other nine months "
                   "(ratio >= 1.30) in both full years. MODERATE seasonality if 1.10 to 1.30. NO marked seasonality if < 1.10. "
                   "A month counts as a HIGH month if it is at least 90% of that year's peak.",
           "strong": 1.30, "moderate": 1.10, "high_month": 0.90},
    "Q3": {"rule": "Visitors are MOSTLY FOREIGN if international visitors are more than 50% of monthly unique visitors (T1) "
                   "in at least 75% of the months (24 of 32). Countries: a FEW COUNTRIES dominate if the top 5 countries hold "
                   "at least 50% of international presences (T8).",
           "share": 0.50, "months_share": 0.75, "top5": 0.50},
    "Q4": {"rule": "Visitors FLOOD the city at weekends if the mean daily unique visitors on Saturday and Sunday is at least "
                   "10% above Monday to Friday (ratio >= 1.10). NO DIFFERENCE if within +/-5%. FEWER at weekends if <= -5%. "
                   "The same rule is applied to each neighbourhood (T5).",
           "flood": 0.10, "same": 0.05},
    "Q5": {"rule": "Visitors KEEP GROWING if the January-August mean grows by more than 2% in BOTH intervals "
                   "(2023->2024 and 2024->2025). STABLE if both changes are within +/-2%. Otherwise MIXED. "
                   "A neighbourhood is counted only with a base of at least 1,000 visitors per month.",
           "growth": 0.02, "min_base": 1000},
    "Q6": {"rule": "Tourist neighbourhoods = the 10 neighbourhoods with most mean monthly visitors (T4). In a neighbourhood "
                   "visitors' trips OUTNUMBER residents' if the visitor share of incoming trips (M1) is above 50%, and ROBUSTLY "
                   "so if even the low bound (published zeros counted as 14 resident trips) is above 50%.",
           "share": 0.50, "top_n": 10},
    "Q7": {"rule": "The 'weekend tourist' belief holds if at least 50% of the tourists of a week spend at most 2 nights (T3).",
           "short": 2, "share": 0.50},
    "Q8": {"rule": "The ranking is STABLE across seasons if at least 8 of the top 10 neighbourhoods of the peak month are also "
                   "in the top 10 of the lowest month, and the Spearman rank correlation is at least 0.90.",
           "keep": 8, "rho": 0.90},
    "Q9": {"rule": "A day is an UNUSUAL PEAK if its unique visitors are at least 15% above the median of the same weekday in "
                   "the same month (T2), and an UNUSUAL LOW if at least 15% below.",
           "peak": 0.15},
    "Q10": {"rule": "Origins go to the SAME PLACES if at least 7 of the top 10 neighbourhoods by mean monthly visitors "
                    "coincide between two origins. A neighbourhood is SPECIALISED in an origin if LQ >= 1.25.",
            "overlap": 7, "lq": 1.25},
    "Q11": {"rule": "Same as Q3: a few countries dominate if the top 5 hold at least 50% of international presences.",
            "top5": 0.50},
    "Q12": {"rule": "National visitors are MOSTLY FROM MADRID if Madrid is at least 50% of national presences (T7). "
                    "Madrid is the LARGEST single origin if it ranks first.",
            "share": 0.50},
    "Q13": {"rule": "Regional visitors come MOSTLY FROM THE METROPOLITAN RING if the 35 other municipalities of the "
                    "Àrea Metropolitana de Barcelona hold at least 50% of regional presences (T6).",
            "share": 0.50},
    "Q14": {"rule": "Visitors are YOUNG if the 18-39 age groups hold at least 50% of presences, and HIGH-INCOME if the "
                    "'Alto' and 'Medio-Alto' income levels hold at least 50% (T9, national and regional only).",
            "share": 0.50},
    "Q15": {"rule": "Visitors and residents use the city at the SAME TIMES if their weekday profiles (trips per day as an "
                    "index, mean day = 100) differ by less than 5 points on every weekday (M1).",
            "points": 5},
    "Q16": {"rule": "Overnight tourists are MORE CONCENTRATED than excursionists if their N50 (see Q1) is at least 2 "
                    "neighbourhoods lower.",
            "gap": 2},
    "Q17": {"rule": "A country market is GROWING FAST if its January-August presences grew by more than 20% between 2023 "
                    "and 2025. Only countries with at least 1% of international presences in 2023 are ranked.",
            "fast": 0.20, "min_share": 0.01},
    # Q18-Q20 (nationalities, added 18 Nov) reuse thresholds already fixed above: 1.30 (Q2), 7 of 10 and LQ 1.25 (Q10), 50% (Q3).
    "Q18": {"rule": "A country market is a SUMMER MARKET if its June-August monthly mean is at least 1.30 times the mean of the "
                    "other nine months (the Q2 threshold, full years 2023 and 2024). The belief holds if at least 16 of the 20 main "
                    "markets (80%) are summer markets; PARTLY if 10 to 15; NO if fewer than 10.",
            "strong": 1.30, "markets": 20, "holds": 16, "partly": 10},
    "Q19": {"rule": "A country market FOLLOWS the international pattern if at least 7 of its top-10 neighbourhoods are in the top 10 "
                    "of all international visitors (the Q10 threshold). It has its OWN NICHE if a neighbourhood with at least 1,000 "
                    "presences per month of that market has a location quotient >= 1.25. The belief holds if at least 16 of the 20 "
                    "main markets follow the pattern and fewer than half have a niche; PARTLY if they follow it but at least half "
                    "have a niche; NO if fewer than 16 follow it.",
            "overlap": 7, "lq": 1.25, "markets": 20, "holds": 16},
    "Q20": {"rule": "A country market is MOSTLY OVERNIGHT if overnight tourists ('Turista') are at least 50% of its presences (T8). "
                    "The belief holds if at least 16 of the 20 main markets are mostly overnight; PARTLY if 10 to 15; NO if fewer than 10.",
            "share": 0.50, "markets": 20, "holds": 16, "partly": 10},
}

AMB_MUNICIPALITIES = [
    "Badalona", "Badia del Vallès", "Barberà del Vallès", "Begues", "Castellbisbal", "Castelldefels", "Cerdanyola del Vallès",
    "Cervelló", "Corbera de Llobregat", "Cornellà de Llobregat", "Esplugues de Llobregat", "Gavà", "L'Hospitalet de Llobregat",
    "La Palma de Cervelló", "Molins de Rei", "Montcada i Reixac", "Montgat", "Pallejà", "El Papiol", "El Prat de Llobregat",
    "Ripollet", "Sant Adrià de Besòs", "Sant Andreu de la Barca", "Sant Boi de Llobregat", "Sant Climent de Llobregat",
    "Sant Cugat del Vallès", "Sant Feliu de Llobregat", "Sant Joan Despí", "Sant Just Desvern", "Sant Vicenç dels Horts",
    "Santa Coloma de Cervelló", "Santa Coloma de Gramenet", "Tiana", "Torrelles de Llobregat", "Viladecans"]


# ---------------------------------------------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------------------------------------------
NUMERIC = {"visitantes", "presences", "max_barrio", "mean_monthly", "viajes", "mean_weekly_visitors", "share_of_year_origin",
           "n_flows", "n_flows_zero", "n_zero", "share_of_presences", "share_in_barrio", "rows", "rows_grouped_na",
           "max_value", "median_row_value", "share_grouped_na", "rows_vs_median_barrio", "periods_with_data", "days",
           "pernoctaciones", "n_weeks"}


def read(path):
    """Aggregated CSV: text keys kept as text ('NA' is a grouped segment, not missing); '<15' becomes NaN (unknown)."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    for col in df.columns:
        if col in NUMERIC or col in ("year", "month", "weekday_idx", "n_days", "months", "months_present", "n_barrios"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        elif col in ("is_weekend", "incomplete_month", "absent_in_source", "has_grouped"):
            df[col] = df[col].str.lower() == "true"
    return df


def load_all():
    t = {
        "city_monthly": read(STATS / "city_monthly_by_origin_type.csv"),
        "city_daily": read(STATS / "city_daily_by_origin.csv"),
        "barrio_monthly": read(STATS / "barrio_monthly_by_origin_type.csv"),
        "trips": read(STATS / "barrio_incoming_trips_by_origen.csv"),
        "overnight": read(STATS / "overnight_stays_distribution.csv"),
        "city_yoy": read(STATS / "city_yoy_jan_aug.csv"),
        "barrio_yoy": read(STATS / "barrio_yoy_jan_aug.csv"),
        "t5": read(AGG / "t5_barrio_daily_by_origin.csv"),
        "t6_city": read(AGG / "t6_municipality_city_month.csv"),
        "t7_city": read(AGG / "t7_province_city_month.csv"),
        "t8_city": read(AGG / "t8_country_city_month.csv"),
        "t8_barrio": read(AGG / "t8_country_barrio_year.csv"),
        "t9_city": read(AGG / "t9_profile_city_month.csv"),
        "coverage": read(AGG / "coverage_barrio_dataset.csv"),
        "od": read(AGG / "m1_od_year_by_origin.csv"),
        "m1_weekday": read(AGG / "m1_incoming_weekday_by_group.csv"),
        "m1_out": read(AGG / "m1_outgoing_month_by_origin.csv"),
    }
    for key in ("barrio_yoy", "city_yoy"):
        for col in t[key].columns:
            if col.startswith(("mean_monthly", "change", "n_months")):
                t[key][col] = pd.to_numeric(t[key][col], errors="coerce")
    for key in ("city_monthly", "city_daily"):
        t[key]["month"] = pd.to_numeric(t[key]["month"])
    lookup = barrio_lookup()
    t["t5"] = t["t5"].merge(lookup, on="cod_barrio", how="left")
    return t


def barrio_lookup():
    levels = pd.read_csv(LEVELS_CSV, dtype=str)
    b = levels[levels["level"] == "neighbourhood"]
    return b.rename(columns={"code_smart_steps": "cod_barrio", "name": "barrio_name", "district_name": "distrito_name"})[
        ["cod_barrio", "barrio_name", "distrito_name"]]


# ---------------------------------------------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------------------------------------------
def gini(values):
    x = np.sort(np.asarray(values, dtype=float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def n_share(values, share=0.5):
    """Smallest number of neighbourhoods that together hold `share` of the presences."""
    x = np.sort(np.asarray(values, dtype=float))[::-1]
    return int(np.searchsorted(np.cumsum(x) / x.sum(), share) + 1)


def scope(df, origin="Todos", tipo="Todos"):
    part = df
    if origin != "Todos":
        part = part[part["origen"] == origin]
    if tipo != "Todos":
        part = part[part["tipo_visitante"] == tipo]
    return part


def pct(x, d=1):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:.{d}f}%"


def signed(x, d=1):
    return "n/a" if x is None or pd.isna(x) else f"{x * 100:+.{d}f}%"


def num(x):
    return "<15" if x is None or pd.isna(x) or x < 15 else f"{x:,.0f}"


def norm(text):
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower().strip()
    for article in ("l'", "el ", "la ", "els ", "les "):          # "Prat de Llobregat, El" == "El Prat de Llobregat"
        if text.endswith(", " + article.strip()):
            text = article + text[: -len(article.strip()) - 2]
    return text.replace("l' ", "l'")


# ---------------------------------------------------------------------------------------------------------------
# Q1 and Q16 · concentration
# ---------------------------------------------------------------------------------------------------------------
def barrio_means(t, origin="Todos", tipo="Todos", years=None):
    df = scope(t["barrio_monthly"], origin, tipo).dropna(subset=["visitantes"])
    if years:
        df = df[df["year"].isin(years)]
    per_month = df.groupby(["mes", "cod_barrio", "barrio_name", "distrito_name"])["visitantes"].sum().reset_index()
    return per_month.groupby(["cod_barrio", "barrio_name", "distrito_name"])["visitantes"].mean().sort_values(ascending=False).reset_index()


def concentration_row(t, origin, tipo):
    means = barrio_means(t, origin, tipo)
    df = scope(t["barrio_monthly"], origin, tipo).dropna(subset=["visitantes"])
    monthly_n50 = df.groupby(["mes", "cod_barrio"])["visitantes"].sum().groupby("mes").apply(n_share)
    return {"origin": ORIGIN_EN[origin], "type": TYPE_EN[tipo], "n50": n_share(means["visitantes"]),
            "n50_month_min": int(monthly_n50.min()), "n50_month_max": int(monthly_n50.max()),
            "n80": n_share(means["visitantes"], 0.8), "top10_share": float(means["visitantes"].head(10).sum() / means["visitantes"].sum()),
            "gini": gini(means["visitantes"]), "top3": ", ".join(means["barrio_name"].head(3))}


def q1(t):
    rule = THRESHOLDS["Q1"]
    scopes = [("Todos", "Todos"), ("Internacional", "Todos"), ("Internacional", "Turista"), ("Internacional", "Excursionista"),
              ("Nacional", "Todos"), ("Regional", "Todos")]
    table = pd.DataFrame([concentration_row(t, o, ty) for o, ty in scopes])
    table["verdict"] = np.where(table["n50"] <= rule["n50_concentrated"], "Concentrated",
                                np.where(table["n50"] >= rule["n50_spread"], "Spread", "Moderately concentrated"))
    allv = table.iloc[0]
    intl = table.iloc[2]
    answer = (f"Half of all visitor presences fall in {allv.n50} of 73 neighbourhoods ({allv.n50 / N_BARRIS:.0%}); "
              f"N50 ranges {allv.n50_month_min}-{allv.n50_month_max} across the 32 months. The 10 largest hold {pct(allv.top10_share)} "
              f"(Gini {allv.gini:.2f}). International overnight tourists are more concentrated: N50 = {intl.n50} "
              f"({pct(intl.top10_share)} in the top 10: {intl.top3}). Regional visitors are the most spread "
              f"(N50 = {table.iloc[5].n50}).")
    verdict = f"{allv.verdict} for all visitors; {intl.verdict.lower()} for international tourists"
    return {"id": "Q1", "table": table, "answer": answer, "verdict": verdict, "value": int(allv.n50)}


def q16(t, q1_result):
    table = q1_result["table"]
    tour = table[(table["origin"] == "International") & (table["type"] == "tourists")].iloc[0]
    exc = table[(table["origin"] == "International") & (table["type"] == "excursionists")].iloc[0]
    gap = int(exc.n50 - tour.n50)
    more = gap >= THRESHOLDS["Q16"]["gap"]
    answer = (f"N50 is {tour.n50} neighbourhoods for international tourists and {exc.n50} for international excursionists "
              f"(gap {gap}); top-10 share {pct(tour.top10_share)} vs {pct(exc.top10_share)}.")
    if more:
        verdict = "Yes: overnight tourists are more concentrated"
    elif gap <= -THRESHOLDS["Q16"]["gap"]:
        verdict = "No: international excursionists are even more concentrated"
    else:
        verdict = "No clear difference"
    return {"id": "Q16", "answer": answer, "verdict": verdict, "value": gap}


# ---------------------------------------------------------------------------------------------------------------
# Q2 · seasonality
# ---------------------------------------------------------------------------------------------------------------
def q2(t):
    rule = THRESHOLDS["Q2"]
    rows = []
    city = t["city_monthly"]
    for origin, tipo in [("Todos", "Todos"), ("Internacional", "Todos"), ("Internacional", "Turista"), ("Nacional", "Todos"), ("Regional", "Todos")]:
        per_month = scope(city, origin, tipo).groupby(["year", "month"])["visitantes"].sum().reset_index()
        for year in FULL_YEARS:
            g = per_month[per_month["year"] == year].set_index("month")["visitantes"]
            ratio = g[g.index.isin([6, 7, 8])].mean() / g[~g.index.isin([6, 7, 8])].mean()
            high = g[g >= rule["high_month"] * g.max()].index.tolist()
            rows.append({"origin": ORIGIN_EN[origin], "type": TYPE_EN[tipo], "year": year, "summer_vs_rest": ratio,
                         "peak_month": MONTHS_EN[g.idxmax() - 1], "low_month": MONTHS_EN[g.idxmin() - 1],
                         "peak_to_trough": g.max() / g.min(), "high_months": ", ".join(MONTHS_EN[m - 1] for m in high),
                         "n_high_months": len(high), "high_outside_summer": len([m for m in high if m not in (6, 7, 8)])})
    table = pd.DataFrame(rows)
    table["verdict"] = np.where(table["summer_vs_rest"] >= rule["strong"], "Summer-only pattern",
                                np.where(table["summer_vs_rest"] >= rule["moderate"], "Moderate seasonality", "No marked seasonality"))
    a = table[(table["origin"] == "All visitors")]
    i = table[(table["origin"] == "International") & (table["type"] == "tourists")]
    answer = (f"June-August is {a.summer_vs_rest.iloc[0]:.2f}x (2023) and {a.summer_vs_rest.iloc[1]:.2f}x (2024) the other months for all visitors; "
              f"{a.n_high_months.iloc[1]} months of 2024 reach 90% of the peak ({a.high_months.iloc[1]}), "
              f"{a.high_outside_summer.iloc[1]} of them outside summer. International tourists are the most seasonal "
              f"({i.summer_vs_rest.iloc[0]:.2f}x and {i.summer_vs_rest.iloc[1]:.2f}x; peak-to-trough {i.peak_to_trough.iloc[1]:.2f} in 2024).")
    verdict = f"{a.verdict.iloc[1]} overall; {i.verdict.iloc[1].lower()} for international tourists"
    return {"id": "Q2", "table": table, "answer": answer, "verdict": verdict, "value": float(a.summer_vs_rest.iloc[1])}


# ---------------------------------------------------------------------------------------------------------------
# Q3, Q11, Q17 · origin and country of residence
# ---------------------------------------------------------------------------------------------------------------
def country_share(t, tipo=None):
    df = t["t8_city"]
    if tipo:
        df = df[df["tipo_visitante"] == tipo]
    total = df.groupby("country")["presences"].sum()
    share = (total / total.sum()).sort_values(ascending=False)
    return share


def q3(t):
    rule = THRESHOLDS["Q3"]
    city = t["city_monthly"]
    per_month = city.groupby(["mes", "origen"])["visitantes"].sum().unstack()
    intl_share = per_month["Internacional"] / per_month.sum(axis=1)
    months_over = int((intl_share > rule["share"]).sum())
    tour = city[city["tipo_visitante"] == "Turista"].groupby(["mes", "origen"])["visitantes"].sum().unstack()
    tour_share = tour["Internacional"] / tour.sum(axis=1)
    countries = country_share(t)
    named = countries.drop("NA", errors="ignore")
    top5 = float(named.head(5).sum())
    table = pd.DataFrame({"country": countries.index, "share_of_international_presences": countries.values})
    table["rank"] = range(1, len(table) + 1)
    mostly = months_over >= rule["months_share"] * len(intl_share)
    answer = (f"International visitors are {pct(intl_share.mean())} of monthly unique visitors on average and above 50% in "
              f"{months_over} of {len(intl_share)} months (range {pct(intl_share.min())}-{pct(intl_share.max())}). Among overnight "
              f"tourists they are {pct(tour_share.mean())}. By country of residence (T8) the top 5 are "
              + ", ".join(f"{c} {pct(v)}" for c, v in named.head(5).items())
              + f": together {pct(top5)} of international presences; small countries grouped as NA are {pct(countries.get('NA', 0))}.")
    needed = int(np.ceil(rule["months_share"] * len(intl_share)))
    verdict = (f"Mostly foreign: international majority in {months_over} of {len(intl_share)} months" if mostly else
               f"Partly: international majority in {months_over} of {len(intl_share)} months, the rule needs {needed}") + \
              ("; the top 5 countries hold half of international presences" if top5 >= rule["top5"] else "; no small group of countries dominates")
    return {"id": "Q3", "table": table, "answer": answer, "verdict": verdict, "value": float(intl_share.mean()),
            "monthly_share": intl_share, "tourist_share": tour_share}


def q11(t, q3_result):
    by_type = {tipo: country_share(t, tipo).drop("NA", errors="ignore") for tipo in ("Turista", "Excursionista")}
    barrio = t["t8_barrio"]
    barrio = barrio[(barrio["year"] == 2024) & (barrio["country"] != "NA")]
    lead = barrio.sort_values("mean_monthly", ascending=False).groupby(["cod_barrio", "barrio_name"]).head(1)
    lead_counts = lead["country"].value_counts()
    top5_t = float(by_type["Turista"].head(5).sum())
    answer = (f"Among international overnight tourists the top 5 countries hold {pct(top5_t)} ("
              + ", ".join(f"{c} {pct(v)}" for c, v in by_type["Turista"].head(5).items()) + "). In 2024 the leading country "
              f"is {lead_counts.index[0]} in {lead_counts.iloc[0]} of {len(lead)} neighbourhoods"
              + (f", {lead_counts.index[1]} in {lead_counts.iloc[1]}" if len(lead_counts) > 1 else "") + ".")
    verdict = "A few countries dominate" if top5_t >= THRESHOLDS["Q11"]["top5"] else "Diversified: no small group of countries dominates"
    return {"id": "Q11", "answer": answer, "verdict": verdict, "value": top5_t, "lead_counts": lead_counts, "by_type": by_type}


def q17(t):
    rule = THRESHOLDS["Q17"]
    df = t["t8_city"]
    df = df[(df["month"] <= 8) & (df["country"] != "NA")]
    per_year = df.groupby(["country", "year"])["presences"].sum().unstack()
    base_share = per_year[2023] / per_year[2023].sum()
    keep = per_year[base_share >= rule["min_share"]].copy()
    keep["change_2023_2025"] = keep[2025] / keep[2023] - 1
    keep["share_2023"] = base_share
    keep = keep.sort_values("change_2023_2025", ascending=False).reset_index()
    fast = keep[keep["change_2023_2025"] > rule["fast"]]
    answer = (f"{len(fast)} of {len(keep)} country markets with at least 1% of presences grew by more than 20% (January-August, "
              f"2023 to 2025): " + ", ".join(f"{r.country} {signed(r.change_2023_2025)}" for r in fast.head(6).itertuples())
              + f". Lowest: " + ", ".join(f"{r.country} {signed(r.change_2023_2025)}" for r in keep.tail(3).itertuples()) + ".")
    return {"id": "Q17", "table": keep, "answer": answer, "verdict": f"{len(fast)} fast-growing markets", "value": len(fast)}


# ---------------------------------------------------------------------------------------------------------------
# Q18-Q20 · nationalities of international visitors (nationalities.py)
# ---------------------------------------------------------------------------------------------------------------
def _three_way(n, rule):
    return "Yes" if n >= rule["holds"] else ("Partly" if n >= rule["partly"] else "No")


def q18(t, prof):
    rule = THRESHOLDS["Q18"]
    main = prof.head(rule["markets"])
    summer = main[main["summer_ratio"] >= rule["strong"]]
    off = main.sort_values("summer_ratio").head(5)
    n = len(summer)
    answer = (f"{n} of the {rule['markets']} main markets are summer markets (June-August >= 1.30x the other months): "
              + ", ".join(f"{r.country} {r.summer_ratio:.2f}x" for r in summer.sort_values("summer_ratio", ascending=False).itertuples())
              + ". The least seasonal markets peak outside summer: "
              + ", ".join(f"{r.country} {r.summer_ratio:.2f}x (peak {r.peak_month})" for r in off.itertuples())
              + f". The 20 markets hold {pct(main['share'].sum())} of international presences.")
    verdict = {"Yes": "Most markets are summer markets", "Partly": "About half of the markets are summer markets",
               "No": f"Only {n} of {rule['markets']} markets are summer markets"}[_three_way(n, rule)]
    return {"id": "Q18", "answer": answer, "verdict": verdict, "value": n, "table": main}


def q19(t, prof):
    rule = THRESHOLDS["Q19"]
    main = prof.head(rule["markets"])
    follow = int((main["overlap_int_top10"] >= rule["overlap"]).sum())
    niche = main[main["n_barrios_lq_125"] > 0].sort_values("distinctive_lq", ascending=False)
    first_name, first_n = main["top_barrio"].value_counts().index[0], int(main["top_barrio"].value_counts().iloc[0])
    answer = (f"{follow} of the {rule['markets']} main markets share at least 7 of their top-10 neighbourhoods with all international "
              f"visitors ({first_name} is first for {first_n} of them). "
              f"{len(niche)} of {rule['markets']} also have their own niche (LQ >= 1.25 with >= 1,000 presences per month): "
              + ", ".join(f"{r.country} in {r.distinctive_barrio} ({r.distinctive_lq:.2f})" for r in niche.head(6).itertuples()) + ".")
    if follow < rule["holds"]:
        holds, verdict = "No", "Markets go to different places"
    elif len(niche) >= rule["markets"] / 2:
        holds, verdict = "Partly", "Same main neighbourhoods for every market, plus a niche of their own for most"
    else:
        holds, verdict = "Yes", "Same neighbourhoods for every market"
    return {"id": "Q19", "answer": answer, "verdict": verdict, "value": follow, "holds_rule": holds, "table": main}


def q20(t, prof):
    rule = THRESHOLDS["Q20"]
    main = prof.head(rule["markets"])
    n = int((main["tourist_share"] >= rule["share"]).sum())
    low = main.sort_values("tourist_share").head(4)
    wider = prof.head(50)
    day = wider[wider["tourist_share"] < rule["share"]]
    answer = (f"{n} of the {rule['markets']} main markets are mostly overnight tourists. Highest share of overnight tourists: "
              + ", ".join(f"{r.country} {pct(r.tourist_share)}" for r in main.sort_values("tourist_share", ascending=False).head(3).itertuples())
              + "; lowest: " + ", ".join(f"{r.country} {pct(r.tourist_share)}" for r in low.itertuples()) + ". "
              + (f"Among the top 50 countries, mostly day-trippers: " + ", ".join(f"{r.country} {pct(r.tourist_share)}" for r in day.itertuples()) + "."
                 if len(day) else "None of the top 50 countries is mostly day-trippers."))
    verdict = {"Yes": "Mostly overnight tourists in every main market", "Partly": "Mostly overnight in part of the markets",
               "No": "Most markets are mostly day-trippers"}[_three_way(n, rule)]
    return {"id": "Q20", "answer": answer, "verdict": verdict, "value": n, "table": main}


# ---------------------------------------------------------------------------------------------------------------
# Q4 · weekends (city and neighbourhoods)
# ---------------------------------------------------------------------------------------------------------------
def classify_weekend(change):
    rule = THRESHOLDS["Q4"]
    if change >= rule["flood"]:
        return "Weekend flood (>= +10%)"
    if change <= -rule["same"]:
        return "Fewer at weekends (<= -5%)"
    if abs(change) < rule["same"]:
        return "No difference (within ±5%)"
    return "Slightly more at weekends (+5% to +10%)"


def bootstrap_ratio(weekend, weekday, n=2000, seed=7):
    rng = np.random.default_rng(seed)
    a, b = np.asarray(weekend), np.asarray(weekday)
    draws = [rng.choice(a, len(a)).mean() / rng.choice(b, len(b)).mean() - 1 for _ in range(n)]
    return np.percentile(draws, [2.5, 97.5])


def q4(t):
    daily = t["city_daily"]
    rows = []
    for origin, tipo in [("Todos", "Todos"), ("Internacional", "Todos"), ("Internacional", "Turista"), ("Nacional", "Todos"), ("Regional", "Todos")]:
        per_day = scope(daily, origin, tipo).groupby(["date", "is_weekend"])["visitantes"].sum().reset_index()
        we, wd = per_day[per_day["is_weekend"]]["visitantes"], per_day[~per_day["is_weekend"]]["visitantes"]
        change = we.mean() / wd.mean() - 1
        low, high = bootstrap_ratio(we, wd)
        rows.append({"origin": ORIGIN_EN[origin], "type": TYPE_EN[tipo], "weekday_mean": wd.mean(), "weekend_mean": we.mean(),
                     "weekend_change": change, "ci_low": low, "ci_high": high, "verdict": classify_weekend(change)})
    city = pd.DataFrame(rows)
    # Neighbourhoods (T5): total visitors per neighbourhood and day = sum of the three exclusive origins (published values only).
    t5 = t["t5"].dropna(subset=["visitantes"])
    per_day = t5.groupby(["cod_barrio", "barrio_name", "distrito_name", "date", "is_weekend"])["visitantes"].sum().reset_index()
    means = per_day.groupby(["cod_barrio", "barrio_name", "distrito_name", "is_weekend"])["visitantes"].mean().unstack()
    barrio = means.reset_index().rename(columns={False: "weekday_mean", True: "weekend_mean"})
    barrio["weekend_change"] = barrio["weekend_mean"] / barrio["weekday_mean"] - 1
    barrio["verdict"] = barrio["weekend_change"].map(classify_weekend)
    barrio = barrio.sort_values("weekend_change", ascending=False).reset_index(drop=True)
    counts = barrio["verdict"].value_counts()
    a = city.iloc[0]
    flood = barrio[barrio["verdict"].str.startswith("Weekend flood")]
    answer = (f"City (T2): {num(a.weekend_mean)} visitors per weekend day vs {num(a.weekday_mean)} per weekday, "
              f"{signed(a.weekend_change)} (95% bootstrap interval {signed(a.ci_low)} to {signed(a.ci_high)}). International "
              f"{signed(city.iloc[1].weekend_change)}, national {signed(city.iloc[3].weekend_change)}, regional {signed(city.iloc[4].weekend_change)}. "
              f"Neighbourhoods (T5): {len(flood)} of {len(barrio)} meet the weekend-flood rule"
              + (f" ({', '.join(flood['barrio_name'].head(5))})" if len(flood) else "")
              + f"; {counts.get('Fewer at weekends (<= -5%)', 0)} have fewer visitors at weekends.")
    return {"id": "Q4", "table": city, "barrio": barrio, "answer": answer, "verdict": a.verdict, "value": float(a.weekend_change),
            "n_flood": len(flood)}


# ---------------------------------------------------------------------------------------------------------------
# Q5 · growth on equivalent periods
# ---------------------------------------------------------------------------------------------------------------
def classify_growth(a, b):
    g = THRESHOLDS["Q5"]["growth"]
    if a > g and b > g:
        return "Keeps growing"
    if abs(a) <= g and abs(b) <= g:
        return "Stable"
    if a < -g and b < -g:
        return "Keeps falling"
    return "Mixed"


def q5(t):
    rule = THRESHOLDS["Q5"]
    city = t["city_yoy"].copy()
    city["verdict"] = [classify_growth(a, b) for a, b in zip(city["change_2023_2024"], city["change_2024_2025"])]
    b = t["barrio_yoy"]
    b = b[(b["origen"] == "Todos") & (b["tipo_visitante"] == "Todos") & (b["mean_monthly_2023"] >= rule["min_base"])].copy()
    b["verdict"] = [classify_growth(x, y) for x, y in zip(b["change_2023_2024"], b["change_2024_2025"])]
    counts = b["verdict"].value_counts()
    a = city[(city["origen"] == "Todos") & (city["tipo_visitante"] == "Todos")].iloc[0]
    it = city[(city["origen"] == "Internacional") & (city["tipo_visitante"] == "Turista")].iloc[0]
    na = city[(city["origen"] == "Nacional") & (city["tipo_visitante"] == "Todos")].iloc[0]
    answer = (f"All visitors: {signed(a.change_2023_2024)} (2023->2024) and {signed(a.change_2024_2025)} (2024->2025), January-August means. "
              f"International tourists {signed(it.change_2023_2024)} and {signed(it.change_2024_2025)}; national visitors "
              f"{signed(na.change_2023_2024)} and {signed(na.change_2024_2025)}. Neighbourhoods with a base of 1,000+: "
              f"{counts.get('Keeps growing', 0)} keep growing, {counts.get('Stable', 0)} stable, {counts.get('Keeps falling', 0)} keep falling, "
              f"{counts.get('Mixed', 0)} mixed (of {len(b)}).")
    verdict = f"{a.verdict} overall (+2% rule); {it.verdict.lower()} for international tourists; {na.verdict.lower()} for national visitors"
    return {"id": "Q5", "table": city, "barrio": b, "answer": answer, "verdict": verdict, "value": float(a.change_2024_2025)}


# ---------------------------------------------------------------------------------------------------------------
# Q6 · visitors' vs residents' trips in tourist neighbourhoods
# ---------------------------------------------------------------------------------------------------------------
def trip_shares(t, years=None):
    trips = t["trips"]
    if years:
        trips = trips[trips["year"].isin(years)]
    trips = trips.assign(is_visitor=trips["origen"] != "Residente", viajes=trips["viajes"].fillna(0))
    g = trips.groupby(["cod_barrio", "barrio_name", "distrito_name", "is_visitor"])[["viajes", "n_flows_zero"]].sum().unstack("is_visitor")
    v, r = g["viajes"][True], g["viajes"][False]
    zv, zr = g["n_flows_zero"][True] * 14, g["n_flows_zero"][False] * 14
    out = pd.DataFrame({"visitor_trips": v, "resident_trips": r, "visitor_share": v / (v + r),
                        "share_low": v / (v + r + zr), "share_high": (v + zv) / (v + zv + r)}).reset_index()
    return out


def q6(t):
    rule = THRESHOLDS["Q6"]
    shares = trip_shares(t)
    top = barrio_means(t).head(rule["top_n"])
    tourist = shares[shares["cod_barrio"].isin(top["cod_barrio"])].sort_values("visitor_share", ascending=False)
    over = tourist[tourist["visitor_share"] > rule["share"]]
    robust = tourist[tourist["share_low"] > rule["share"]]
    all_over = shares[shares["visitor_share"] > rule["share"]]
    city = shares["visitor_trips"].sum() / (shares["visitor_trips"].sum() + shares["resident_trips"].sum())
    answer = (f"In {len(over)} of the {rule['top_n']} tourist neighbourhoods visitors make more than half of incoming trips "
              f"({len(robust)} robustly): " + ", ".join(f"{r.barrio_name} {pct(r.visitor_share)}" for r in over.itertuples())
              + f". The others stay below 50% (lowest: {tourist.iloc[-1].barrio_name} {pct(tourist.iloc[-1].visitor_share)}). "
              f"City-wide, visitors make {pct(city)} of trips between neighbourhoods; {len(all_over)} of 73 neighbourhoods are above 50%.")
    verdict = f"True in {len(over)} of {rule['top_n']} tourist neighbourhoods; false city-wide"
    return {"id": "Q6", "table": tourist, "all": shares, "answer": answer, "verdict": verdict, "value": len(over)}


# ---------------------------------------------------------------------------------------------------------------
# Q7 · nights per week (tourists)
# ---------------------------------------------------------------------------------------------------------------
def q7(t):
    rule = THRESHOLDS["Q7"]
    df = t["overnight"]
    df = df[df["year"].isin(FULL_YEARS)]
    rows = []
    for (year, origin), g in df.groupby(["year", "origen"]):
        share = g.set_index("pernoctaciones")["share_of_year_origin"]
        mean_nights = float((g["pernoctaciones"] * g["share_of_year_origin"]).sum())
        rows.append({"year": int(year), "origin": ORIGIN_EN[origin], "one_night": share.get(1, 0),
                     "up_to_two": share[share.index <= rule["short"]].sum(), "four_plus": share[share.index >= 4].sum(),
                     "mean_nights": mean_nights})
    table = pd.DataFrame(rows)
    y = table[table["year"] == 2024]
    holds = (y["up_to_two"] >= rule["share"]).all()
    answer = ("In 2024, " + "; ".join(f"{r.origin.lower()} tourists: {pct(r.up_to_two)} spend 1-2 nights in a week, "
                                     f"{pct(r.four_plus)} 4 or more (mean {r.mean_nights:.1f} nights)" for r in y.itertuples()) + ".")
    return {"id": "Q7", "table": table, "answer": answer, "verdict": "Holds: most tourists stay 1-2 nights per week" if holds
            else "Does not hold", "value": float(y["up_to_two"].mean())}


# ---------------------------------------------------------------------------------------------------------------
# Q8 · ranking in high vs low season
# ---------------------------------------------------------------------------------------------------------------
def q8(t):
    rule = THRESHOLDS["Q8"]
    city = t["city_monthly"].groupby(["year", "month"])["visitantes"].sum().reset_index()
    rows = []
    for year in FULL_YEARS:
        g = city[city["year"] == year]
        peak, low = int(g.loc[g["visitantes"].idxmax(), "month"]), int(g.loc[g["visitantes"].idxmin(), "month"])
        b = t["barrio_monthly"].dropna(subset=["visitantes"])
        b = b[b["year"] == year].groupby(["month", "barrio_name"])["visitantes"].sum().unstack("month")
        rank_peak, rank_low = b[peak].rank(ascending=False), b[low].rank(ascending=False)
        top_peak, top_low = set(rank_peak[rank_peak <= 10].index), set(rank_low[rank_low <= 10].index)
        rho = rank_peak.corr(rank_low, method="spearman")
        moved = (rank_peak - rank_low).abs().sort_values(ascending=False)
        rows.append({"year": year, "peak_month": MONTHS_EN[peak - 1], "low_month": MONTHS_EN[low - 1], "top10_kept": len(top_peak & top_low),
                     "spearman": rho, "entered_peak": ", ".join(sorted(top_peak - top_low)), "left_peak": ", ".join(sorted(top_low - top_peak)),
                     "largest_moves": ", ".join(f"{n} ({int(rank_low[n])}->{int(rank_peak[n])})" for n in moved.head(3).index)})
    table = pd.DataFrame(rows)
    stable = ((table["top10_kept"] >= rule["keep"]) & (table["spearman"] >= rule["rho"])).all()
    r = table.iloc[-1]
    answer = (f"2024: {r.top10_kept} of the top 10 in {r.peak_month} (peak) are also top 10 in {r.low_month} (low); Spearman "
              f"{r.spearman:.3f}. Largest rank moves: {r.largest_moves}.")
    return {"id": "Q8", "table": table, "answer": answer, "verdict": "Stable ranking all year" if stable else "Ranking changes by season",
            "value": float(r.spearman)}


# ---------------------------------------------------------------------------------------------------------------
# Q9 · unusual days
# ---------------------------------------------------------------------------------------------------------------
def q9(t):
    rule = THRESHOLDS["Q9"]
    per_day = t["city_daily"].groupby(["date", "year", "month", "weekday_idx"])["visitantes"].sum().reset_index()
    per_day["expected"] = per_day.groupby(["year", "month", "weekday_idx"])["visitantes"].transform("median")
    per_day["deviation"] = per_day["visitantes"] / per_day["expected"] - 1
    per_day["weekday"] = per_day["weekday_idx"].map(dict(enumerate(WEEKDAYS_EN)))
    peaks = per_day[per_day["deviation"] >= rule["peak"]].sort_values("deviation", ascending=False)
    lows = per_day[per_day["deviation"] <= -rule["peak"]].sort_values("deviation")
    answer = (f"{len(peaks)} of {len(per_day)} days are unusual peaks (>= +15% vs the same weekday and month) and {len(lows)} unusual lows. "
              f"Largest peaks: " + ", ".join(f"{r.date} ({r.weekday}, {signed(r.deviation)})" for r in peaks.head(4).itertuples())
              + ". The data date the peaks; naming their cause needs an external event calendar.")
    return {"id": "Q9", "table": per_day, "peaks": peaks, "lows": lows, "answer": answer,
            "verdict": f"{len(peaks)} peak days and {len(lows)} low days found", "value": len(peaks)}


# ---------------------------------------------------------------------------------------------------------------
# Q10 · do origins go to the same places? (location quotient on presences)
# ---------------------------------------------------------------------------------------------------------------
def q10(t):
    rule = THRESHOLDS["Q10"]
    means = {o: barrio_means(t, o).set_index("barrio_name")["visitantes"] for o in VISITOR_ORIGINS}
    frame = pd.DataFrame(means).fillna(0)
    share_in_origin = frame / frame.sum()
    share_all = frame.sum(axis=1) / frame.values.sum()
    lq = share_in_origin.div(share_all, axis=0).round(3)
    tops = {o: set(frame[o].sort_values(ascending=False).head(10).index) for o in VISITOR_ORIGINS}
    overlap = {f"{a}-{b}": len(tops[a] & tops[b]) for a, b in [("Internacional", "Nacional"), ("Internacional", "Regional"), ("Nacional", "Regional")]}
    specialised = {o: int((lq[o] >= rule["lq"]).sum()) for o in VISITOR_ORIGINS}
    same = {k: v >= rule["overlap"] for k, v in overlap.items()}
    answer = ("Overlap of the top-10 neighbourhoods: " + ", ".join(f"{k.replace('Internacional', 'international').replace('Nacional', 'national').replace('Regional', 'regional')} {v}/10"
                                                         for k, v in overlap.items())
              + ". Neighbourhoods specialised (LQ >= 1.25): " + ", ".join(f"{ORIGIN_EN[o].lower()} {n}" for o, n in specialised.items())
              + f". Highest international LQ: {lq['Internacional'].idxmax()} ({lq['Internacional'].max():.2f}); highest regional LQ: "
              f"{lq['Regional'].idxmax()} ({lq['Regional'].max():.2f}).")
    verdict = "Different places: regional day-trippers do not follow foreign tourists" if not same["Internacional-Regional"] else "Same places"
    lq_table = lq.round(3).reset_index().rename(columns={"index": "barrio_name"})
    return {"id": "Q10", "table": lq_table, "answer": answer, "verdict": verdict, "value": overlap["Internacional-Regional"]}


# ---------------------------------------------------------------------------------------------------------------
# Q12, Q13, Q14 · where national and regional visitors live, and who they are
# ---------------------------------------------------------------------------------------------------------------
def q12(t):
    df = t["t7_city"]
    share = (df.groupby("province")["presences"].sum() / df["presences"].sum()).sort_values(ascending=False)
    named = share.drop("NA", errors="ignore")
    madrid = float(share.get("Madrid", 0))
    catalan = float(share[share.index.isin(["Girona", "Tarragona", "Lleida"])].sum())
    answer = (f"Top provinces of national visitors (presences): " + ", ".join(f"{p} {pct(v)}" for p, v in named.head(5).items())
              + f". Madrid is {pct(madrid)}; the other three Catalan provinces together {pct(catalan)}.")
    first, second = named.index[0], named.index[1]
    tie = abs(named.iloc[0] - named.iloc[1]) < 0.005
    verdict = ("Mostly from Madrid" if madrid >= THRESHOLDS["Q12"]["share"] else
               f"Not mostly from Madrid ({pct(madrid)})" + (f"; {first} and {second} are level as the largest" if tie
                                                            else f"; {first} is the largest"))
    return {"id": "Q12", "table": share.rename("share").reset_index(), "answer": answer, "verdict": verdict, "value": madrid,
            "catalan": catalan}


def q13(t):
    df = t["t6_city"]
    share = (df.groupby("municipality")["presences"].sum() / df["presences"].sum()).sort_values(ascending=False)
    amb = {norm(m) for m in AMB_MUNICIPALITIES}
    in_amb = share[[norm(m) in amb for m in share.index]]
    matched = len(in_amb)
    answer = (f"The 35 other AMB municipalities hold {pct(in_amb.sum())} of regional presences ({matched} of 35 found by name). "
              f"Top: " + ", ".join(f"{m} {pct(v)}" for m, v in share.drop('NA', errors='ignore').head(5).items()) + ".")
    verdict = "Mostly from the metropolitan ring" if in_amb.sum() >= THRESHOLDS["Q13"]["share"] else "Not mostly from the metropolitan ring"
    return {"id": "Q13", "table": share.rename("share").reset_index(), "answer": answer, "verdict": verdict, "value": float(in_amb.sum()),
            "amb_matched": matched}


def q14(t):
    df = t["t9_city"]
    df = df[(df["genero"] != "NA") & (df["edad"] != "NA") & (df["nivel_renta"] != "NA") & (df["origen"] != "NA")]
    rows = []
    for origin in ["Todos", "Nacional", "Regional"]:
        part = df if origin == "Todos" else df[df["origen"] == origin]
        age = part.groupby("edad")["presences"].sum() / part["presences"].sum()
        income = part.groupby("nivel_renta")["presences"].sum() / part["presences"].sum()
        gender = part.groupby("genero")["presences"].sum() / part["presences"].sum()
        rows.append({"origin": ORIGIN_EN[origin], "age_18_39": age.get("18-29", 0) + age.get("30-39", 0),
                     "age_60_plus": age.get("60-69", 0) + age.get("70+", 0),
                     "income_high": income.get("Alto", 0) + income.get("Medio-Alto", 0), "income_low": income.get("Bajo", 0),
                     "female": gender.get("f", 0), **{f"age_{k}": v for k, v in age.items()},
                     **{f"income_{k}": v for k, v in income.items()}})
    table = pd.DataFrame(rows)
    a = table.iloc[0]
    young, rich = a.age_18_39 >= THRESHOLDS["Q14"]["share"], a.income_high >= THRESHOLDS["Q14"]["share"]
    answer = (f"National and regional visitors (T9 has no international rows, issue I9): 18-39 years {pct(a.age_18_39)}, 60+ {pct(a.age_60_plus)}; "
              f"high or medium-high income {pct(a.income_high)}, low income {pct(a.income_low)}; women {pct(a.female)}.")
    verdict = (("Young" if young else f"Not young ({pct(a.age_18_39, 0)} aged 18-39)") + ", " +
               ("but high-income" if rich and not young else "and high-income" if rich else "and not mainly high-income")
               + f" ({pct(a.income_high, 0)} high or medium-high); national and regional only")
    return {"id": "Q14", "table": table, "answer": answer, "verdict": verdict, "value": float(a.age_18_39)}


# ---------------------------------------------------------------------------------------------------------------
# Q15 · rhythm of visitors' and residents' trips
# ---------------------------------------------------------------------------------------------------------------
def q15(t):
    df = t["m1_weekday"].dropna(subset=["viajes"])
    per = df.groupby(["group", "weekday_idx"])[["viajes", "days"]].sum()
    per["per_day"] = per["viajes"] / per["days"]
    idx = (per["per_day"] / per.groupby("group")["per_day"].transform("mean") * 100).unstack("group")
    diff = (idx["Visitante"] - idx["Residente"])
    same = (diff.abs() < THRESHOLDS["Q15"]["points"]).all()
    trips = t["trips"].assign(group=lambda d: np.where(d["origen"] == "Residente", "Residente", "Visitante"))
    month = trips.groupby(["group", "year", "month"])["viajes"].sum().reset_index()
    month = month[month["year"].isin(FULL_YEARS)].groupby(["group", "month"])["viajes"].mean().unstack("group")
    month_idx = month / month.mean() * 100
    answer = (f"Weekday index (mean day = 100), visitors vs residents: Saturday {idx.loc[5, 'Visitante']:.0f} vs {idx.loc[5, 'Residente']:.0f}, "
              f"Sunday {idx.loc[6, 'Visitante']:.0f} vs {idx.loc[6, 'Residente']:.0f}; largest gap {diff.abs().max():.0f} points "
              f"({WEEKDAYS_EN[int(diff.abs().idxmax())]}). By month, visitors' trips peak in {MONTHS_EN[int(month_idx['Visitante'].idxmax()) - 1]} "
              f"({month_idx['Visitante'].max():.0f}) while residents' trips are lowest in {MONTHS_EN[int(month_idx['Residente'].idxmin()) - 1]} "
              f"({month_idx['Residente'].min():.0f}).")
    verdict = "Same rhythm" if same else "Different rhythms"
    return {"id": "Q15", "table": idx.reset_index(), "month": month_idx.reset_index(), "answer": answer, "verdict": verdict,
            "value": float(diff.abs().max())}


# ---------------------------------------------------------------------------------------------------------------
# I8 · neighbourhoods with very few data (3.2.2)
# ---------------------------------------------------------------------------------------------------------------
LOW_DATA_RULE = ("A neighbourhood is LOW-DATA if its mean monthly visitors (T4) are below 10% of the median neighbourhood, "
                 "or if more than 15% of its rows in the origin files (T6, T7, T8) are grouped as NA (privacy threshold).")


def low_data(t):
    means = barrio_means(t).set_index("cod_barrio")
    median = means["visitantes"].median()
    cov = t["coverage"]
    piv = cov.pivot_table(index="cod_barrio", columns="dataset", values="share_grouped_na")
    rows_rel = cov.pivot_table(index="cod_barrio", columns="dataset", values="rows_vs_median_barrio")
    shares = trip_shares(t).set_index("cod_barrio")
    od = t["od"].dropna(subset=["viajes"])
    resident_in = od[(od["origen"] == "Residente") & (od["year"] == 2024)].groupby("barrio_destino")["viajes"].sum()
    visitor_in = od[(od["origen"] != "Residente") & (od["year"] == 2024)].groupby("barrio_destino")["viajes"].sum()
    table = pd.DataFrame({
        "barrio_name": means["barrio_name"], "distrito_name": means["distrito_name"],
        "mean_monthly_visitors": means["visitantes"], "vs_median": means["visitantes"] / median,
        "na_share_T6": piv.get("T6"), "na_share_T7": piv.get("T7"), "na_share_T8": piv.get("T8"), "na_share_T9": piv.get("T9"),
        "rows_T8_vs_median": rows_rel.get("T8"),
        "resident_trips_in_2024": resident_in, "visitor_trips_in_2024": visitor_in,
        "visitor_share_trips": shares["visitor_share"]}).rename_axis("cod_barrio").reset_index()
    table["resident_trips_vs_median"] = table["resident_trips_in_2024"] / table["resident_trips_in_2024"].median()
    table["visitors_per_1000_resident_trips"] = table["mean_monthly_visitors"] / table["resident_trips_in_2024"] * 1000 * 12
    cond_value = table["vs_median"] < 0.10
    cond_na = table[["na_share_T6", "na_share_T7", "na_share_T8"]].max(axis=1) > 0.15
    table["low_data"] = cond_value | cond_na
    table["reason"] = np.select([cond_value & cond_na, cond_value, cond_na],
                                ["very low visitors + many grouped segments", "very low visitors", "many grouped segments"], "")
    table = table.sort_values("mean_monthly_visitors").reset_index(drop=True)
    # Monthly stability of the two anomalous neighbourhoods (coefficient of variation).
    bm = t["barrio_monthly"].dropna(subset=["visitantes"]).groupby(["mes", "barrio_name"])["visitantes"].sum().unstack()
    cv_month = (bm.std() / bm.mean()).rename("cv_monthly")
    table = table.merge(cv_month, left_on="barrio_name", right_index=True, how="left")
    return table, median


def belief_holds(qid, res):
    """Does the common belief hold under the decision rule? Yes / Partly / No (derived from the rule, never typed by hand)."""
    v, verdict = res["value"], res["verdict"].lower()
    rules = {
        "Q1": "Yes" if v <= THRESHOLDS["Q1"]["n50_concentrated"] else "No",
        "Q2": "Yes" if v >= THRESHOLDS["Q2"]["strong"] else "No",
        "Q3": "Yes" if verdict.startswith("mostly") else "Partly",
        "Q4": "Yes" if v >= THRESHOLDS["Q4"]["flood"] else "No",
        "Q5": "Yes" if verdict.startswith("keeps growing") else "No",
        "Q6": "Yes" if v == THRESHOLDS["Q6"]["top_n"] else ("Partly" if v > 0 else "No"),
        "Q7": "Yes" if verdict.startswith("holds") else "No",
        "Q8": "Yes" if verdict.startswith("stable") else "No",
        "Q9": "Partly" if v > 0 else "No",
        "Q10": "Yes" if v >= THRESHOLDS["Q10"]["overlap"] else "No",
        "Q11": "Yes" if v >= THRESHOLDS["Q11"]["top5"] else "No",
        "Q12": "Yes" if v >= THRESHOLDS["Q12"]["share"] else "No",
        "Q13": "Yes" if v >= THRESHOLDS["Q13"]["share"] else "No",
        "Q14": "Yes" if verdict.startswith("young and high") else ("Partly" if "high-income" in verdict and "not mainly" not in verdict else "No"),
        "Q15": "Yes" if verdict.startswith("same") else "No",
        "Q16": "Yes" if v >= THRESHOLDS["Q16"]["gap"] else "No",
        "Q17": "No" if v > 0 else "Yes",
        "Q18": _three_way(v, THRESHOLDS["Q18"]) if "Q18" in qid else None,
        "Q19": res.get("holds_rule"),
        "Q20": _three_way(v, THRESHOLDS["Q20"]) if "Q20" in qid else None,
    }
    return rules[qid]


def run_all(t=None):
    t = t or load_all()
    r = {}
    r["Q1"] = q1(t)
    r["Q2"] = q2(t)
    r["Q3"] = q3(t)
    r["Q4"] = q4(t)
    r["Q5"] = q5(t)
    r["Q6"] = q6(t)
    r["Q7"] = q7(t)
    r["Q8"] = q8(t)
    r["Q9"] = q9(t)
    r["Q10"] = q10(t)
    r["Q11"] = q11(t, r["Q3"])
    r["Q12"] = q12(t)
    r["Q13"] = q13(t)
    r["Q14"] = q14(t)
    r["Q15"] = q15(t)
    r["Q16"] = q16(t, r["Q1"])
    r["Q17"] = q17(t)
    r["nationalities"] = N.profile(t)
    r["regions"] = N.region_table(t)
    r["Q18"] = q18(t, r["nationalities"])
    r["Q19"] = q19(t, r["nationalities"])
    r["Q20"] = q20(t, r["nationalities"])
    r["low_data"], r["low_data_median"] = low_data(t)
    for qid in [k for k in r if k[0] == "Q" and k[1:].isdigit()]:
        r[qid]["holds"] = belief_holds(qid, r[qid])
    return t, r


if __name__ == "__main__":
    import research_report
    research_report.main()
