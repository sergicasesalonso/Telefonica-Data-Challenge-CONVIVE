"""CONVIVE - preliminary descriptive statistics (WBS 3.1.6) and standalone maps (WBS 4.2.1).

The CSV files written here are the ONLY data input of the dashboard. Rules applied in this module:
  - Trips and unique visitors are never combined.
  - Unique visitors are never summed across days, months or neighbourhoods to obtain a total. Segments
    (origin, visitor type) inside one place and period are exclusive, so they can be added. Longer periods are
    monthly means.
  - Any exported value below 15 is written as "<15". A neighbourhood segment missing from T4 is also "<15".
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

import analysis as an
import convive as cv
import levels as lv
import loaders as L
import quality as q

STATS_DIR = q.DELIVERABLES / "3.1.6_stats"
THRESHOLD = 15
BELOW = "<15"
ALL = "Todos"
VISITOR_ORIGINS = cv.VISITOR_ORIGINS
SEGMENTS = [("Internacional", "Turista"), ("Internacional", "Excursionista"), ("Nacional", "Turista"),
            ("Nacional", "Excursionista"), ("Regional", "Excursionista")]
COMPARISONS = [(2023, 2024), (2024, 2025), (2023, 2025)]


def apply_threshold(df, columns):
    """Values below the threshold become '<15'. Missing values stay empty."""
    out = df.copy()
    for col in columns:
        values = pd.to_numeric(out[col], errors="coerce")
        text = out[col].astype(object)
        text = text.where(~(values < THRESHOLD), BELOW)
        out[col] = text
    return out


def _save(df, name):
    STATS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(STATS_DIR / name, index=False, encoding="utf-8")
    print(f"  {name}: {len(df):,} rows, {(STATS_DIR / name).stat().st_size / 1024:,.0f} KB", flush=True)
    return df


def _numeric(series):
    return pd.to_numeric(series, errors="coerce")


# ---------------------------------------------------------------------------
# City tables (T1, T2)
# ---------------------------------------------------------------------------
def city_monthly(con):
    t1 = con.execute(f"""SELECT mes, year, month_num AS month, origen, tipo_visitante, visitantes, incomplete_month
                         FROM {L.parquet_glob('T1', 'clean')} ORDER BY 1, 4, 5""").df()
    t1["share_of_month"] = (t1["visitantes"] / t1.groupby("mes")["visitantes"].transform("sum")).round(4)
    return t1


def city_daily(con):
    return con.execute(f"""SELECT date, year, month_num AS month, mes, weekday_idx, weekday, is_weekend, origen, tipo_visitante,
                                  visitantes, incomplete_month
                           FROM {L.parquet_glob('T2', 'clean')} ORDER BY 1, 8, 9""").df()


def city_weekday(daily):
    g = daily.groupby(["year", "weekday_idx", "weekday", "origen", "tipo_visitante"])["visitantes"]
    table = g.agg(mean_visitors="mean", median_visitors="median", n_days="count").reset_index()
    table[["mean_visitors", "median_visitors"]] = table[["mean_visitors", "median_visitors"]].round(1)
    return table.sort_values(["year", "origen", "tipo_visitante", "weekday_idx"])


# ---------------------------------------------------------------------------
# Neighbourhood tables (T4)
# ---------------------------------------------------------------------------
def barrio_monthly(con):
    t4 = con.execute(f"""SELECT mes, year, month_num AS month, cod_barrio, barrio_name, distrito, distrito_name, origen, tipo_visitante,
                                visitantes, incomplete_month, is_grouped_na
                         FROM {L.parquet_glob('T4', 'clean')}""").df()
    grouped = t4[t4["is_grouped_na"]]
    t4 = t4[~t4["is_grouped_na"]]
    # Complete grid: a segment that is absent in a neighbourhood and month is below the threshold.
    months = t4[["mes", "year", "month", "incomplete_month"]].drop_duplicates()
    barrios = t4[["cod_barrio", "barrio_name", "distrito", "distrito_name"]].drop_duplicates()
    segments = pd.DataFrame(SEGMENTS, columns=["origen", "tipo_visitante"])
    grid = months.merge(barrios, how="cross").merge(segments, how="cross")
    merged = grid.merge(t4[["mes", "cod_barrio", "origen", "tipo_visitante", "visitantes"]],
                        on=["mes", "cod_barrio", "origen", "tipo_visitante"], how="left")
    merged["absent_in_source"] = merged["visitantes"].isna()
    return merged.sort_values(["mes", "cod_barrio", "origen", "tipo_visitante"]).reset_index(drop=True), grouped


def _scopes(table):
    """Yield (origin, type, table) for each origin and type, with 'Todos' as the combination of segments."""
    for origin in VISITOR_ORIGINS + [ALL]:
        for tipo in cv.VISITOR_TYPES + [ALL]:
            part = table
            if origin != ALL:
                part = part[part["origen"] == origin]
            if tipo != ALL:
                part = part[part["tipo_visitante"] == tipo]
            if len(part):
                yield origin, tipo, part


def barrio_concentration(monthly):
    """Top-10 share of the ranking and Gini across neighbourhoods. Not a share of the city total."""
    rows = []
    known = monthly.dropna(subset=["visitantes"])
    for origin, tipo, part in _scopes(known):
        by_barrio = part.groupby(["mes", "cod_barrio", "barrio_name"])["visitantes"].sum().reset_index()
        for mes, g in by_barrio.groupby("mes"):
            values = g.sort_values("visitantes", ascending=False)
            rows.append({"mes": mes, "year": int(mes[:4]), "month": int(mes[4:]), "origen": origin, "tipo_visitante": tipo,
                         "n_barrios": len(values),
                         "top10_share_of_ranking": round(values["visitantes"].head(10).sum() / values["visitantes"].sum(), 4),
                         "gini": round(an.gini(values["visitantes"]), 4),
                         "top1_barrio": values["barrio_name"].iloc[0]})
    return pd.DataFrame(rows).sort_values(["mes", "origen", "tipo_visitante"])


def _monthly_means_jan_aug(part, keys):
    """Mean monthly unique visitors per year, using only January to August months."""
    jan_aug = part[part["month"] <= 8]
    per_month = jan_aug.groupby(keys + ["year", "month"])["visitantes"].sum().reset_index()
    return per_month


def barrio_yoy(monthly):
    """Change in mean monthly unique visitors, January to August, only months present in both years."""
    rows = []
    known = monthly.dropna(subset=["visitantes"])
    ids = ["cod_barrio", "barrio_name", "distrito", "distrito_name"]
    for origin, tipo, part in _scopes(known):
        per_month = _monthly_means_jan_aug(part, ids)
        for keys, g in per_month.groupby(ids):
            wide = g.pivot(index="month", columns="year", values="visitantes")
            row = dict(zip(ids, keys))
            row.update({"origen": origin, "tipo_visitante": tipo})
            for year in (2023, 2024, 2025):
                row[f"mean_monthly_{year}"] = round(wide[year].mean(), 1) if year in wide else np.nan
            for a, b in COMPARISONS:
                if a in wide and b in wide:
                    both = wide[[a, b]].dropna()
                    row[f"n_months_{a}_{b}"] = len(both)
                    base, now = both[a].mean(), both[b].mean()
                    row[f"change_{a}_{b}"] = round(now / base - 1, 4) if len(both) and base >= THRESHOLD and now >= THRESHOLD else np.nan
                else:
                    row[f"n_months_{a}_{b}"] = 0
                    row[f"change_{a}_{b}"] = np.nan
            rows.append(row)
    return pd.DataFrame(rows).sort_values(["cod_barrio", "origen", "tipo_visitante"])


def city_yoy(monthly):
    """City version of the same comparison, from T1."""
    rows = []
    for origin, tipo, part in _scopes(monthly):
        per_month = part[part["month"] <= 8].groupby(["year", "month"])["visitantes"].sum().unstack("year")
        row = {"origen": origin, "tipo_visitante": tipo}
        for year in (2023, 2024, 2025):
            row[f"mean_monthly_{year}"] = round(per_month[year].mean(), 1)
        for a, b in COMPARISONS:
            row[f"change_{a}_{b}"] = round(per_month[b].mean() / per_month[a].mean() - 1, 4)
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Trips (M1)
# ---------------------------------------------------------------------------
def barrio_incoming_trips(con):
    """Trips arriving in each neighbourhood. M1 excludes trips inside the same neighbourhood."""
    trips = con.execute(f"""
        SELECT barrio_destino AS cod_barrio, min(barrio_destino_name) AS barrio_name, min(distrito_destino) AS distrito,
               min(distrito_destino_name) AS distrito_name, source_month AS mes, min(year) AS year, min(month_num) AS month,
               weekday_idx, min(weekday) AS weekday, min(is_weekend) AS is_weekend, origen,
               sum(viajes) AS viajes, count(DISTINCT day) AS n_days, count(*) AS n_flows,
               sum(is_censored_zero::BIGINT) AS n_flows_zero, bool_or(incomplete_month) AS incomplete_month
        FROM {L.parquet_glob('M1', 'clean')} GROUP BY barrio_destino, source_month, weekday_idx, origen""").df()
    keys = ["cod_barrio", "mes", "weekday_idx"]
    total = trips.groupby(keys)["viajes"].transform("sum")
    visitors = trips["viajes"].where(trips["origen"] != "Residente", 0).groupby([trips[k] for k in keys]).transform("sum")
    trips["visitor_share"] = (visitors / total.where(total > 0)).round(4)
    return trips.sort_values(keys + ["origen"]).reset_index(drop=True)


def share_bounds(trips, group=None):
    """Visitor share with zero flows at their limits. A published 0 is 0 to 14 trips.

    published: the share with zeros counted as 0.
    low:       zeros of visitors at 0, zeros of residents at 14.
    high:      zeros of visitors at 14, zeros of residents at 0.
    """
    keys = group or []
    frame = trips.assign(is_visitor=trips["origen"] != "Residente")
    grouped = frame.groupby(keys + ["is_visitor"])[["viajes", "n_flows_zero"]].sum().unstack("is_visitor")
    visitors, residents = grouped["viajes"][True], grouped["viajes"][False]
    zero_visitors, zero_residents = grouped["n_flows_zero"][True] * 14, grouped["n_flows_zero"][False] * 14
    return pd.DataFrame({"visitor_share": visitors / (visitors + residents),
                         "share_low": visitors / (visitors + residents + zero_residents),
                         "share_high": (visitors + zero_visitors) / (visitors + zero_visitors + residents)})


def overnight_distribution(con):
    """T3: mean weekly tourists by number of nights. Partial and two-month weeks are excluded."""
    t3 = con.execute(f"""SELECT year, origen, pernoctaciones, visitantes, periodo, partial_week, week_in_two_months
                         FROM {L.parquet_glob('T3', 'clean')}""").df()
    excluded = t3[t3["partial_week"] | t3["week_in_two_months"]]["periodo"].nunique()
    full = t3[~t3["partial_week"] & ~t3["week_in_two_months"]]
    table = full.groupby(["year", "origen", "pernoctaciones"]).agg(
        mean_weekly_visitors=("visitantes", "mean"), n_weeks=("periodo", "nunique")).reset_index()
    table["share_of_year_origin"] = (table["mean_weekly_visitors"]
                                     / table.groupby(["year", "origen"])["mean_weekly_visitors"].transform("sum")).round(4)
    table["mean_weekly_visitors"] = table["mean_weekly_visitors"].round(1)
    return table, excluded


# ---------------------------------------------------------------------------
# Headline numbers (3.1.6_summary.md). Everything is computed from the tables above.
# ---------------------------------------------------------------------------
def headlines(tables):
    h = {}
    city, daily, concentration = tables["city_monthly"], tables["city_daily"], tables["concentration"]
    monthly, yoy, cityoy, trips = tables["barrio_monthly"], tables["barrio_yoy"], tables["city_yoy"], tables["trips"]

    # Q1
    c = concentration[(concentration["origen"] == ALL) & (concentration["tipo_visitante"] == ALL)]
    known = monthly.dropna(subset=["visitantes"])
    per_barrio = known.groupby(["mes", "cod_barrio", "barrio_name"])["visitantes"].sum().groupby(["cod_barrio", "barrio_name"]).mean().sort_values(ascending=False)
    by_origin = {}
    for origin in VISITOR_ORIGINS:
        part = concentration[(concentration["origen"] == origin) & (concentration["tipo_visitante"] == ALL)]
        by_origin[origin] = {"top10_median": float(part["top10_share_of_ranking"].median()), "gini_median": float(part["gini"].median())}
    h["Q1"] = {"top10_median": float(c["top10_share_of_ranking"].median()), "top10_min": float(c["top10_share_of_ranking"].min()),
               "top10_max": float(c["top10_share_of_ranking"].max()), "gini_median": float(c["gini"].median()),
               "gini_min": float(c["gini"].min()), "gini_max": float(c["gini"].max()), "n_months": len(c),
               "top_barrios": [{"name": k[1], "mean_monthly": float(v)} for k, v in per_barrio.head(10).items()],
               "bottom_barrio": {"name": per_barrio.index[-1][1], "mean_monthly": float(per_barrio.iloc[-1])},
               "top_over_bottom": float(per_barrio.iloc[0] / per_barrio.iloc[-1]), "by_origin": by_origin}

    # Q2
    totals = city.groupby(["mes", "year", "month"])["visitantes"].sum().reset_index()
    by_year = {}
    for year, g in totals.groupby("year"):
        peak, low = g.loc[g["visitantes"].idxmax()], g.loc[g["visitantes"].idxmin()]
        by_year[int(year)] = {"peak_month": peak["mes"], "peak": int(peak["visitantes"]), "low_month": low["mes"], "low": int(low["visitantes"]),
                              "ratio": float(peak["visitantes"] / low["visitantes"]), "n_months": len(g)}
    origin_ratio = {}
    origins_by_month = city.groupby(["mes", "year", "origen"])["visitantes"].sum().reset_index()
    for (origin, year), g in origins_by_month.groupby(["origen", "year"]):
        peak, low = g.loc[g["visitantes"].idxmax()], g.loc[g["visitantes"].idxmin()]
        origin_ratio.setdefault(origin, {})[int(year)] = {"ratio": float(peak["visitantes"] / low["visitantes"]),
                                                          "peak_month": peak["mes"], "low_month": low["mes"]}
    summer = totals[totals["month"].isin([6, 7, 8])].groupby("year")["visitantes"].mean()
    rest = totals[~totals["month"].isin([6, 7, 8])].groupby("year")["visitantes"].mean()
    h["Q2"] = {"by_year": by_year, "by_origin": origin_ratio,
               "summer_vs_rest": {int(y): float(summer[y] / rest[y]) for y in summer.index}}

    # Q3
    month_total = city.groupby("mes")["visitantes"].transform("sum")
    shares = city.assign(share=city["visitantes"] / month_total)
    # "mean" is the share of the average month, the same method as the dashboard tiles. min and max are single months.
    origin_share = shares.groupby(["mes", "origen"])["share"].sum().groupby("origen").agg(["min", "max"])
    origin_share["mean"] = city.groupby("origen")["visitantes"].sum() / city["visitantes"].sum()
    type_share = shares.groupby(["mes", "tipo_visitante"])["share"].sum().groupby("tipo_visitante").agg(["min", "max"])
    type_share["mean"] = city.groupby("tipo_visitante")["visitantes"].sum() / city["visitantes"].sum()
    segment_share = city.groupby(["origen", "tipo_visitante"])["visitantes"].sum() / city["visitantes"].sum()
    h["Q3"] = {"origin": {o: {k: float(v) for k, v in r.items()} for o, r in origin_share.to_dict("index").items()},
               "type": {o: {k: float(v) for k, v in r.items()} for o, r in type_share.to_dict("index").items()},
               "segment": {f"{a} {b}": float(v) for (a, b), v in segment_share.items()},
               "mean_monthly_total": float(totals["visitantes"].mean())}

    # Q4
    per_day = daily.groupby(["date", "is_weekend", "weekday_idx", "weekday", "origen"])["visitantes"].sum().reset_index()
    weekend = per_day.groupby(["origen", "is_weekend"])["visitantes"].mean().unstack()
    weekday_mean = per_day.groupby(["origen", "weekday_idx", "weekday"])["visitantes"].mean().reset_index()
    best = weekday_mean.loc[weekday_mean.groupby("origen")["visitantes"].idxmax()].set_index("origen")["weekday"].to_dict()
    low = weekday_mean.loc[weekday_mean.groupby("origen")["visitantes"].idxmin()].set_index("origen")["weekday"].to_dict()
    all_day = per_day.groupby(["date", "is_weekend", "weekday_idx", "weekday"])["visitantes"].sum().reset_index()
    all_week = all_day.groupby("is_weekend")["visitantes"].mean()
    all_wd = all_day.groupby(["weekday_idx", "weekday"])["visitantes"].mean().reset_index()
    h["Q4"] = {"by_origin": {o: {"weekday_mean": float(weekend.loc[o, False]), "weekend_mean": float(weekend.loc[o, True]),
                                 "weekend_vs_weekday": float(weekend.loc[o, True] / weekend.loc[o, False]),
                                 "highest_day": best[o], "lowest_day": low[o]} for o in weekend.index},
               "all": {"weekday_mean": float(all_week[False]), "weekend_mean": float(all_week[True]),
                       "weekend_vs_weekday": float(all_week[True] / all_week[False]),
                       "highest_day": all_wd.loc[all_wd["visitantes"].idxmax(), "weekday"],
                       "lowest_day": all_wd.loc[all_wd["visitantes"].idxmin(), "weekday"]},
               "n_days": int(all_day["date"].nunique())}

    # Q5
    row = {f"{r.origen}|{r.tipo_visitante}": r for r in cityoy.itertuples()}
    h["Q5"] = {"city": {k: {"mean_2023": float(r.mean_monthly_2023), "mean_2024": float(r.mean_monthly_2024), "mean_2025": float(r.mean_monthly_2025),
                            "change_2023_2024": float(r.change_2023_2024), "change_2024_2025": float(r.change_2024_2025),
                            "change_2023_2025": float(r.change_2023_2025)} for k, r in row.items()}}
    b = yoy[(yoy["origen"] == ALL) & (yoy["tipo_visitante"] == ALL)].dropna(subset=["change_2023_2025"]).sort_values("change_2023_2025")
    h["Q5"]["barrios"] = {"n": len(b), "up": int((b["change_2023_2025"] > 0).sum()), "down": int((b["change_2023_2025"] < 0).sum()),
                          "top": [{"name": r.barrio_name, "change": float(r.change_2023_2025)} for r in b.tail(3)[::-1].itertuples()],
                          "bottom": [{"name": r.barrio_name, "change": float(r.change_2023_2025)} for r in b.head(3).itertuples()]}

    # Q6
    city_bound = share_bounds(trips.assign(all="city"), ["all"]).iloc[0]
    barrio_bound = share_bounds(trips, ["cod_barrio", "barrio_name"]).reset_index().sort_values("visitor_share", ascending=False)
    origin_trips = trips.groupby("origen")["viajes"].sum()
    h["Q6"] = {"city": {k: float(v) for k, v in city_bound.items()},
               "origin_share": {o: float(v / origin_trips.sum()) for o, v in origin_trips.items()},
               "over_half": int((barrio_bound["visitor_share"] > 0.5).sum()),
               "over_half_low": int((barrio_bound["share_low"] > 0.5).sum()),
               "over_half_high": int((barrio_bound["share_high"] > 0.5).sum()),
               "n_barrios": len(barrio_bound),
               "top": [{"name": r.barrio_name, "share": float(r.visitor_share), "low": float(r.share_low), "high": float(r.share_high)}
                       for r in barrio_bound.head(5).itertuples()],
               "bottom": [{"name": r.barrio_name, "share": float(r.visitor_share)} for r in barrio_bound.tail(3)[::-1].itertuples()],
               "zero_share_flows": float(trips["n_flows_zero"].sum() / trips["n_flows"].sum())}
    return h


def _pct(x, digits=1):
    return f"{x * 100:.{digits}f}%"


def _signed(x, digits=1):
    return f"{x * 100:+.{digits}f}%"


def _month(mes):
    return pd.to_datetime(str(mes), format="%Y%m").strftime("%B %Y")


WEEKDAY_EN = dict(zip(cv.WEEKDAYS, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]))


def question_paragraphs(h):
    """Neutral text for 3.1.6_summary.md and the delivery document. Patterns only, numbers computed."""
    q1, q2, q3, q4, q5, q6 = (h[f"Q{i}"] for i in range(1, 7))
    top3 = ", ".join(f"{b['name']} ({b['mean_monthly']:,.0f})" for b in q1["top_barrios"][:3])
    o = q1["by_origin"]
    y = q2["by_year"]
    origin_ratio = "; ".join(f"{k} {v[2024]['ratio']:.2f}" for k, v in q2["by_origin"].items())
    g = q3["origin"]
    w = q4["by_origin"]
    weekend_text = "; ".join(f"{k} {_signed(v['weekend_vs_weekday'] - 1)}" for k, v in w.items())
    c = q5["city"]
    all_city = c[f"{ALL}|{ALL}"]
    origin_change = "; ".join(f"{o} {_signed(c[f'{o}|{ALL}']['change_2023_2025'])}" for o in VISITOR_ORIGINS)
    b = q5["barrios"]
    return {
        "Q1": {"title": "How concentrated are visitors across the 73 neighbourhoods?",
               "text": f"In the median month, the 10 highest neighbourhoods hold {_pct(q1['top10_median'])} of the neighbourhood ranking "
                       f"(range {_pct(q1['top10_min'])} to {_pct(q1['top10_max'])} over {q1['n_months']} months). 10 of 73 is {_pct(10 / 73)} of the neighbourhoods. "
                       f"The median Gini across neighbourhoods is {q1['gini_median']:.3f}. The highest monthly averages are {top3}; the lowest is "
                       f"{q1['bottom_barrio']['name']} ({q1['bottom_barrio']['mean_monthly']:,.0f}, an unusually low value flagged in 3.1.2). Median top-10 share by origin: "
                       f"Internacional {_pct(o['Internacional']['top10_median'])}, Nacional {_pct(o['Nacional']['top10_median'])}, Regional {_pct(o['Regional']['top10_median'])}.",
               "limit": "Neighbourhood values are not additive: a person visiting two neighbourhoods counts in both, so this is a share of the ranking, not of the city total."},
        "Q2": {"title": "How much do visitors change from month to month, by origin?",
               "text": f"Peak-to-trough ratio of monthly unique visitors: {y[2023]['ratio']:.2f} in 2023 (peak {_month(y[2023]['peak_month'])}, low {_month(y[2023]['low_month'])}) and "
                       f"{y[2024]['ratio']:.2f} in 2024 (peak {_month(y[2024]['peak_month'])}, low {_month(y[2024]['low_month'])}). June to August average is "
                       f"{q2['summer_vs_rest'][2023]:.2f} and {q2['summer_vs_rest'][2024]:.2f} times the other months of 2023 and 2024. Ratio by origin in 2024: {origin_ratio}.",
               "limit": "2025 covers January to August only, so it has no full-year ratio. Monthly values of months with a missing day are flagged."},
        "Q3": {"title": "What share of monthly visitors is international, national or regional, tourist or excursionist?",
               "text": f"Share of the average month's unique visitors: Internacional {_pct(g['Internacional']['mean'])} (range {_pct(g['Internacional']['min'])} to {_pct(g['Internacional']['max'])}), "
                       f"Regional {_pct(g['Regional']['mean'])}, Nacional {_pct(g['Nacional']['mean'])}. Tourists are {_pct(q3['type']['Turista']['mean'])} and excursionists "
                       f"{_pct(q3['type']['Excursionista']['mean'])}. International tourists alone are {_pct(q3['segment']['Internacional Turista'])}.",
               "limit": "Regional visitors are always excursionists by definition, which raises the excursionist share."},
        "Q4": {"title": "Are daily visitors higher at weekends than on weekdays, and for which origins?",
               "text": f"Mean daily unique visitors are {q4['all']['weekend_mean']:,.0f} on weekend days and {q4['all']['weekday_mean']:,.0f} on weekdays "
                       f"({_signed(q4['all']['weekend_vs_weekday'] - 1)}). Weekend difference by origin: {weekend_text}. Highest day by origin: "
                       + "; ".join(f"{k} {WEEKDAY_EN[v['highest_day']]}" for k, v in w.items()) + ".",
               "limit": f"Means per day over {q4['n_days']} days; daily values cannot be summed into weekly totals, and 3 days are missing."},
        "Q5": {"title": "Did visitors grow between equivalent periods (January to August)?",
               "text": f"Mean monthly unique visitors, January to August: {all_city['mean_2023']:,.0f} in 2023, {all_city['mean_2024']:,.0f} in 2024 and {all_city['mean_2025']:,.0f} in 2025 "
                       f"({_signed(all_city['change_2023_2024'])} and {_signed(all_city['change_2024_2025'])}). From 2023 to 2025 by origin: {origin_change}. "
                       f"Of {b['n']} neighbourhoods, {b['up']} show a higher value and {b['down']} a lower one in 2025 than in 2023.",
               "limit": "Only the 8 equivalent months are compared, and February 2024, April 2025 and May 2025 each miss one day. Change over two intervals cannot show a long-term trend."},
        "Q6": {"title": "What share of incoming trips is made by visitors, and by residents?",
               "text": f"Visitors make {_pct(q6['city']['visitor_share'])} of published trips between neighbourhoods (bound {_pct(q6['city']['share_low'])} to {_pct(q6['city']['share_high'])}, "
                       f"treating each published 0 as 0 to 14 trips). Visitors make more than half of incoming trips in {q6['over_half']} of {q6['n_barrios']} neighbourhoods "
                       f"(bound {q6['over_half_low']} to {q6['over_half_high']}). Highest: " + ", ".join(f"{t['name']} ({_pct(t['share'])})" for t in q6["top"][:3]) +
                       ". Lowest: " + ", ".join(f"{t['name']} ({_pct(t['share'])})" for t in q6["bottom"][:2]) + " (both flagged in 3.1.2).",
               "limit": "Trips, not people. Trips inside the same neighbourhood are excluded, and flows below 15 appear as 0, which hides more visitor flows than resident flows. The bound covers published zeros only; routes with no row in the file are not covered."},
    }


def write_summary(h, overnight_excluded, tables):
    paragraphs = question_paragraphs(h)
    parts = ["""
# 3.1.6 Preliminary descriptive statistics: headline numbers

CONVIVE · Team 102_A · Iteration 2. Generated by `descriptives.py` from `3.1.6_stats/`. Every number is computed by the code. The results describe patterns, not causes.
"""]
    for qid, p in paragraphs.items():
        parts.append(f"\n## {qid}. {p['title']}\n\n{p['text']}\n\n*Limitation:* {p['limit']}\n")
    o = tables["overnight"]
    if len(o):
        latest = o[o["year"] == 2024].sort_values(["origen", "pernoctaciones"])
        one = latest[latest["pernoctaciones"] == "1"].set_index("origen")["share_of_year_origin"].to_dict() if latest["pernoctaciones"].dtype == object else latest[latest["pernoctaciones"] == 1].set_index("origen")["share_of_year_origin"].to_dict()
        parts.append(f"\n## Q7 (Iteration 3, table ready)\n\nShare of weekly tourists with 1 night in 2024: "
                     + ", ".join(f"{k} {_pct(v)}" for k, v in one.items()) + f". {overnight_excluded} weeks are excluded as partial or under two months.\n")
    return q.write_md("3.1.6_summary.md", "".join(parts))


README = """# 3.1.6 Aggregated statistics tables

CONVIVE · Team 102_A · Iteration 2. These aggregated tables are the dashboard's only data input. Generated by `descriptives.py`.

**Threshold rule.** Any value below 15 is written as `<15`. In M1, each published flow below 15 trips is 0, so an aggregated trips value only adds flows of 15 or more, and `<15` means no published flow reached 15, not that the real total is below 15. In T4, a segment absent from the source for a neighbourhood and month is written as `<15` and marked `absent_in_source`. Empty cells mean not computable.

| Table | Source | Measure | Questions | Limitations |
|---|---|---|---|---|
| `city_monthly_by_origin_type.csv` | T1 | Unique visitors | Q2, Q3, Q5 | Not additive across months. Regional visitors are always excursionists. Months with missing days are flagged |
| `city_weekday_by_origin.csv` | T2 | Unique visitors (mean, median, number of days) | Q4 | Means per day; never summed into weeks. 3 days missing |
| `city_daily_by_origin.csv` | T2 | Unique visitors | Q4, Q9 | Not additive across days. 3 days missing |
| `city_yoy_jan_aug.csv` | T1 | Unique visitors (mean per month, change) | Q5 | January to August only |
| `barrio_monthly_by_origin_type.csv` | T4 | Unique visitors | Q1, Q5 | Not additive across neighbourhoods or months. One grouped NA row in the source is left out (see `3.1.3_cleaning_log.md`) |
| `barrio_concentration.csv` | T4 | Share of the ranking, Gini | Q1 | The share is of the neighbourhood ranking, not of the city total. `Todos` adds exclusive segments inside each neighbourhood |
| `barrio_yoy_jan_aug.csv` | T4 | Unique visitors (mean per month, change) | Q5 | January to August, months present in both years. Very small bases give large changes |
| `barrio_incoming_trips_by_origen.csv` | M1 | Trips | Q6 | Trips, not people. Internal trips are excluded. Zeros mean fewer than 15 trips, so totals are lower estimates; `n_flows_zero` allows a bound. No visitor type in M1 |
| `overnight_stays_distribution.csv` | T3 | Tourists by nights per week | Q7 (Iteration 3) | Municipality level, national and international only. Partial and two-month weeks are excluded |
"""


def run(con):
    print("Computing statistics tables", flush=True)
    tables = {}
    tables["city_monthly"] = city_monthly(con)
    tables["city_daily"] = city_daily(con)
    tables["city_weekday"] = city_weekday(tables["city_daily"])
    tables["barrio_monthly"], grouped = barrio_monthly(con)
    tables["concentration"] = barrio_concentration(tables["barrio_monthly"])
    tables["barrio_yoy"] = barrio_yoy(tables["barrio_monthly"])
    tables["city_yoy"] = city_yoy(tables["city_monthly"])
    tables["trips"] = barrio_incoming_trips(con)
    tables["overnight"], excluded = overnight_distribution(con)

    # Headlines use unrounded, unmasked values; exports apply the threshold.
    h = headlines(tables)

    _save(apply_threshold(tables["city_monthly"], ["visitantes"]), "city_monthly_by_origin_type.csv")
    _save(apply_threshold(tables["city_weekday"], ["mean_visitors", "median_visitors"]), "city_weekday_by_origin.csv")
    _save(apply_threshold(tables["city_daily"], ["visitantes"]), "city_daily_by_origin.csv")
    monthly = tables["barrio_monthly"].copy()
    monthly["visitantes"] = monthly["visitantes"].astype("Int64").astype(object).where(~monthly["absent_in_source"], BELOW)
    _save(apply_threshold(monthly, ["visitantes"]), "barrio_monthly_by_origin_type.csv")
    _save(tables["concentration"], "barrio_concentration.csv")
    means = [f"mean_monthly_{y}" for y in (2023, 2024, 2025)]
    _save(apply_threshold(tables["barrio_yoy"], means), "barrio_yoy_jan_aug.csv")
    _save(apply_threshold(tables["city_yoy"], means), "city_yoy_jan_aug.csv")
    _save(apply_threshold(tables["trips"], ["viajes"]), "barrio_incoming_trips_by_origen.csv")
    _save(apply_threshold(tables["overnight"], ["mean_weekly_visitors"]), "overnight_stays_distribution.csv")
    (STATS_DIR / "README.md").write_text(README, encoding="utf-8", newline="\n")
    print(write_summary(h, excluded, tables))
    (q.DELIVERABLES / "3.1.6_summary.json").write_text(
        json.dumps({"numbers": h, "paragraphs": question_paragraphs(h)}, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    return tables, h


# ---------------------------------------------------------------------------
# WBS 4.2.1 Standalone maps
# ---------------------------------------------------------------------------
def _choropleth(geo, frame, value, title, colorbar, hover, colorscale="Purples", tick=None):
    import plotly.graph_objects as go
    # The blank "white-bg" style needs no tiles or basemap file, so the page works offline (see app/dashboard.py).
    fig = go.Figure(go.Choroplethmap(geojson=geo, locations=frame["cod_barrio"], z=frame[value],
                                     featureidkey="properties.cod_barrio_ss", colorscale=colorscale,
                                     marker={"opacity": 1, "line": {"color": "#a9a9a9", "width": 0.6}},
                                     colorbar={"title": colorbar, "tickformat": tick}, customdata=frame[["barrio_name", "distrito_name"]],
                                     hovertemplate=hover))
    fig.update_layout(title=title, height=720, margin={"l": 0, "r": 0, "t": 90, "b": 30},
                      map={"style": "white-bg", "center": cv.map_center(geo), "zoom": 10.7},
                      annotations=[{"text": "CONVIVE · Team 102_A · Preliminary, Iteration 2 · Smart Steps data supplied under NDA · aggregated, threshold 15",
                                    "x": 0, "y": -0.03, "xref": "paper", "yref": "paper", "showarrow": False, "font": {"size": 11, "color": "#555"}}])
    return fig


def export_maps():
    """Two self-contained HTML maps built from the 3.1.6 tables only. No external requests when opened."""
    geo, _ = cv.load_barris()
    monthly = pd.read_csv(STATS_DIR / "barrio_monthly_by_origin_type.csv", dtype={"cod_barrio": str, "mes": str, "distrito": str})
    monthly["value"] = _numeric(monthly["visitantes"])
    per_month = monthly.groupby(["mes", "cod_barrio", "barrio_name", "distrito_name"])["value"].sum().reset_index()
    visitors = per_month.groupby(["cod_barrio", "barrio_name", "distrito_name"])["value"].mean().reset_index()
    fig = _choropleth(geo, visitors, "value",
                      "Q1 · Mean monthly unique visitors per neighbourhood, January 2023 to August 2025<br><sup>All origins and visitor types. Neighbourhood values are not additive.</sup>",
                      "Visitors per month", "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{z:,.0f} visitors per month<extra></extra>")
    fig.write_html(q.DELIVERABLES / "4.2.1_map_visitors.html", include_plotlyjs=True)

    trips = pd.read_csv(STATS_DIR / "barrio_incoming_trips_by_origen.csv", dtype={"cod_barrio": str, "mes": str, "distrito": str})
    trips["value"] = _numeric(trips["viajes"]).fillna(0)
    total = trips.groupby(["cod_barrio", "barrio_name", "distrito_name"])["value"].sum()
    visitor = trips[trips["origen"] != "Residente"].groupby(["cod_barrio", "barrio_name", "distrito_name"])["value"].sum()
    share = (visitor / total).rename("share").reset_index()
    fig = _choropleth(geo, share, "share",
                      "Q6 · Visitor share of incoming trips per neighbourhood, January 2023 to August 2025<br><sup>Trips, not people. Internal trips excluded. Flows below 15 appear as 0.</sup>",
                      "Visitor share", "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{z:.1%} of incoming trips by visitors<extra></extra>",
                      tick=".0%")
    fig.write_html(q.DELIVERABLES / "4.2.1_map_visitor_share_trips.html", include_plotlyjs=True)
    print("Maps written")
    return True
