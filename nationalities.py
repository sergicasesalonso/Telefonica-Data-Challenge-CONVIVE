"""CONVIVE - nationalities of international visitors (WBS 3.2.1, extended in Iteration 3 after the 18 Nov request).

Country of residence comes from T8 (unique visitors per neighbourhood, month, visitor type and country). Every value
here is a share or a mean of PRESENCES (person x neighbourhood), because unique visitors cannot be added across
neighbourhoods. Countries below 15 people in a neighbourhood are grouped by Telefónica as 'NA' and kept apart.

Indicators per country:
    share of international presences, rank, world region
    tourist share (overnight 'Turista' vs day-trip 'Excursionista')
    January-August growth 2023->2024, 2024->2025, 2023->2025
    seasonality: June-August vs the other nine months (full years 2023 and 2024), peak and lowest month
    geography: top neighbourhoods, overlap with the international top 10, N50, most over-represented neighbourhood (LQ)
"""

import numpy as np
import pandas as pd

MAIN_MARKETS = 20          # the 20 largest countries are the "main markets" of Q18-Q20
LQ_MIN_BASE = 1000         # LQ only where the country has at least 1,000 mean monthly presences (stable ratio)
SUMMER = [6, 7, 8]
FULL_YEARS = [2023, 2024]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

REGION_OF = {}
for region, names in {
    "Western Europe": ["France", "Germany", "Netherlands", "Belgium", "Switzerland", "Austria", "Luxembourg", "Monaco", "Liechtenstein"],
    "UK & Ireland": ["United Kingdom", "Ireland", "Gibraltar"],
    "Southern Europe": ["Italy", "Portugal", "Greece", "Malta", "Cyprus", "Andorra", "Croatia", "Slovenia", "Albania", "Montenegro",
                        "Serbia", "Bosnia & Herzegov.", "Macedonia"],
    "Northern Europe": ["Sweden", "Norway", "Denmark", "Finland", "Iceland", "Faroe Islands", "Greenland", "Estonia", "Latvia", "Lithuania"],
    "Central & Eastern Europe": ["Poland", "Czech Rep.", "Slovakia", "Hungary", "Romania", "Bulgaria", "Ukraine", "Moldova", "Belarus",
                                 "Russian Federation", "Georgia", "Armenia", "Azerbaijan", "Turkey"],
    "North America": ["United States", "Canada", "Bermuda", "Puerto Rico"],
    "Latin America & Caribbean": ["Mexico", "Argentina Republic", "Brazil", "Chile", "Colombia", "Peru", "Uruguay", "Paraguay", "Bolivia",
                                  "Ecuador", "Venezuela", "Costa Rica", "Panama", "Guatemala", "Honduras", "El Salvador", "Nicaragua",
                                  "Cuba", "Dominican Republic", "Jamaica", "Trinidad and Tobago", "Bahamas", "Barbados", "Aruba",
                                  "Cayman Islands", "Netherlands Antilles", "Antigua and Barbuda", "Saint Kitts and Nevis", "Saint Lucia",
                                  "St. Vincent & Gren.", "Guyana"],
    "Asia & Pacific": ["China", "Japan", "Korea S, Republic of", "Taiwan", "Hongkong, China", "Macao, China", "India", "Singapore",
                       "Malaysia", "Thailand", "Indonesia", "Philippines", "Viet Nam", "Australia", "New Zealand", "Pakistan",
                       "Bangladesh", "Sri Lanka", "Nepal", "Cambodia", "Myanmar (Burma)", "Maldives", "Kazakhstan", "Kyrgyzstan",
                       "Uzbekistan", "Turkmenistan", "New Caledonia", "Samoa"],
    "Middle East & Africa": ["Israel", "United Arab Emirates", "Saudi Arabia", "Qatar", "Kuwait", "Bahrain", "Oman", "Jordan", "Lebanon",
                             "Iran", "Iraq", "Syrian Arab Republic", "Palestinian Territory", "Egypt", "Morocco", "Algeria", "Tunisia",
                             "Libya", "South Africa", "Nigeria", "Senegal", "Ghana", "Kenya", "Ivory Coast", "Cameroon", "Ethiopia",
                             "Angola", "Mali", "Mauritania", "Gambia", "Guinea", "Equatorial Guinea", "Cape Verde", "Benin", "Togo",
                             "Burkina Faso", "Congo, Dem. Rep.", "Congo, Republic", "Gabon", "Madagascar", "Mauritius", "Mozambique",
                             "Namibia", "Sudan", "Tanzania", "Uganda", "Zambia", "Zimbabwe", "Reunion"],
}.items():
    for name in names:
        REGION_OF[name] = region


def region(country):
    return REGION_OF.get(country, "Other")


def _city(t):
    df = t["t8_city"]
    return df[df["country"] != "NA"]


def _barrio(t):
    df = t["t8_barrio"]
    return df[df["country"] != "NA"]


def shares(t, years=None, months=None, tipo=None):
    """Share of international presences per country (named countries; NA kept out of the denominator)."""
    df = _city(t)
    if years:
        df = df[df["year"].isin(years)]
    if months:
        df = df[df["month"].isin(months)]
    if tipo:
        df = df[df["tipo_visitante"].isin(tipo if isinstance(tipo, (list, tuple)) else [tipo])]
    total = df.groupby("country")["presences"].sum()
    return (total / total.sum()).sort_values(ascending=False) if total.sum() else total


def seasonal_index(t, countries=None):
    """Country x month index (mean month = 100), mean of the full years 2023 and 2024."""
    df = _city(t)
    df = df[df["year"].isin(FULL_YEARS)]
    m = df.groupby(["country", "year", "month"])["presences"].sum()
    idx = (m / m.groupby(["country", "year"]).transform("mean") * 100).groupby(["country", "month"]).mean().unstack()
    if countries is not None:
        idx = idx.reindex(countries)
    return idx


def summer_ratio(t):
    """June-August mean / mean of the other nine months, per country and full year, then averaged (same metric as Q2)."""
    df = _city(t)
    df = df[df["year"].isin(FULL_YEARS)]
    m = df.groupby(["country", "year", "month"])["presences"].sum().reset_index()
    m["summer"] = m["month"].isin(SUMMER)
    means = m.groupby(["country", "year", "summer"])["presences"].mean().unstack()
    ratio = (means[True] / means[False]).unstack()
    return ratio.mean(axis=1), ratio


def growth(t):
    """January-August presences per year and changes."""
    df = _city(t)
    df = df[df["month"] <= 8]
    y = df.groupby(["country", "year"])["presences"].sum().unstack()
    return pd.DataFrame({"jan_aug_2023": y.get(2023), "jan_aug_2024": y.get(2024), "jan_aug_2025": y.get(2025),
                         "growth_23_24": y.get(2024) / y.get(2023) - 1, "growth_24_25": y.get(2025) / y.get(2024) - 1,
                         "growth_23_25": y.get(2025) / y.get(2023) - 1})


def barrio_means(t, years=None):
    """Mean monthly presences per country and neighbourhood (mean of the selected years)."""
    df = _barrio(t)
    if years:
        df = df[df["year"].isin(years)]
    return df.groupby(["country", "cod_barrio", "barrio_name", "distrito_name"])["mean_monthly"].mean().reset_index()


def location_quotients(t, years=None):
    """LQ = share of a neighbourhood in the country's presences / share of that neighbourhood in all international presences.
    LQ > 1: the country is over-represented there. 'reliable' marks a base of at least LQ_MIN_BASE presences per month."""
    b = barrio_means(t, years)
    country_total = b.groupby("country")["mean_monthly"].transform("sum")
    barrio_all = b.groupby("cod_barrio")["mean_monthly"].transform("sum")
    b["share_of_country"] = b["mean_monthly"] / country_total
    b["share_of_international"] = barrio_all / b["mean_monthly"].sum()
    b["lq"] = b["share_of_country"] / b["share_of_international"]
    b["reliable"] = b["mean_monthly"] >= LQ_MIN_BASE
    return b


def international_top10(t, years=None):
    b = barrio_means(t, years)
    return b.groupby("barrio_name")["mean_monthly"].sum().sort_values(ascending=False).head(10).index.tolist()


def n50(values):
    v = np.sort(np.asarray(values, dtype=float))[::-1]
    if v.sum() == 0:
        return np.nan
    return int(np.searchsorted(np.cumsum(v) / v.sum(), 0.5) + 1)


def profile(t, top=None):
    """One row per named country: every indicator of the nationality analysis."""
    share = shares(t)
    tour = _city(t)
    tour_share = (tour[tour["tipo_visitante"] == "Turista"].groupby("country")["presences"].sum()
                  / tour.groupby("country")["presences"].sum())
    sr, _ = summer_ratio(t)
    idx = seasonal_index(t)
    g = growth(t)
    lq = location_quotients(t)
    top10_int = set(international_top10(t))
    lead = lq.sort_values("mean_monthly", ascending=False).groupby("cod_barrio").head(1)["country"].value_counts()
    months_city = _city(t)["mes"].nunique()
    rows = []
    for rank, (country, s) in enumerate(share.items(), start=1):
        b = lq[lq["country"] == country].sort_values("mean_monthly", ascending=False)
        rel = b[b["reliable"]].sort_values("lq", ascending=False)
        rows.append({
            "rank": rank, "country": country, "region": region(country), "share": s,
            "mean_monthly_presences": _city(t).loc[lambda d: d["country"] == country, "presences"].sum() / months_city,
            "tourist_share": tour_share.get(country, np.nan), "summer_ratio": sr.get(country, np.nan),
            "peak_month": MONTHS_EN[int(idx.loc[country].idxmax()) - 1] if country in idx.index and idx.loc[country].notna().any() else "",
            "low_month": MONTHS_EN[int(idx.loc[country].idxmin()) - 1] if country in idx.index and idx.loc[country].notna().any() else "",
            "growth_23_24": g["growth_23_24"].get(country, np.nan), "growth_24_25": g["growth_24_25"].get(country, np.nan),
            "growth_23_25": g["growth_23_25"].get(country, np.nan),
            "top_barrio": b["barrio_name"].iloc[0] if len(b) else "", "top3_barrios": ", ".join(b["barrio_name"].head(3)),
            "overlap_int_top10": len(set(b["barrio_name"].head(10)) & top10_int), "n50": n50(b["mean_monthly"]) if len(b) else np.nan,
            "n_barrios": int((b["mean_monthly"] > 0).sum()),
            "distinctive_barrio": rel["barrio_name"].iloc[0] if len(rel) else "", "distinctive_lq": rel["lq"].iloc[0] if len(rel) else np.nan,
            "n_barrios_lq_125": int((rel["lq"] >= 1.25).sum()), "barrios_leading": int(lead.get(country, 0)),
        })
    out = pd.DataFrame(rows)
    return out.head(top) if top else out


def region_table(t):
    """Share of international presences by world region, January-August of each year, and growth."""
    df = _city(t)
    df = df[df["month"] <= 8].assign(region=lambda d: d["country"].map(region))
    y = df.groupby(["region", "year"])["presences"].sum().unstack()
    out = (y / y.sum()).add_prefix("share_jan_aug_")
    out["growth_23_25"] = y[2025] / y[2023] - 1
    return out.sort_values("share_jan_aug_2025", ascending=False).reset_index()


def monthly(t, country, years=None, months=None, tipo=None):
    """Monthly presences of one country by visitor type, and its share of international presences."""
    df = _city(t)
    if years:
        df = df[df["year"].isin(years)]
    if months:
        df = df[df["month"].isin(months)]
    if tipo:
        df = df[df["tipo_visitante"].isin(tipo)]
    all_month = df.groupby("mes")["presences"].sum()
    one = df[df["country"] == country].groupby(["mes", "tipo_visitante"])["presences"].sum().unstack(fill_value=0)
    one["share"] = one.sum(axis=1) / all_month.reindex(one.index)
    one.index = pd.to_datetime(one.index, format="%Y%m")
    return one
