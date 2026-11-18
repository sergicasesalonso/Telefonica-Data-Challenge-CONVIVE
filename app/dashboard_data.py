"""Data logic of the CONVIVE dashboard (no Streamlit here, so it can be tested on its own).

Reads ONLY aggregated tables: deliverables/iteration2/3.1.6_stats/*.csv and, since Iteration 3 (WBS 4.2.3), the daily
neighbourhood table of deliverables/iteration3/2.2.1_aggregates/. Rules enforced here:
  - unique visitors are never summed across months: a period is a monthly mean;
  - segments (origin, visitor type) inside one month and place are exclusive, so they can be added;
  - neighbourhood values are never added up to a city total;
  - trips and unique visitors are never combined.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STATS_DIR = ROOT / "deliverables" / "iteration2" / "3.1.6_stats"
AGG_DIR = ROOT / "deliverables" / "iteration3" / "2.2.1_aggregates"
DAY_TYPES = ["All days", "Weekdays (Mon-Fri)", "Weekends (Sat-Sun)"]

VISITOR_ORIGINS = ["Internacional", "Nacional", "Regional"]
TRIP_ORIGINS = VISITOR_ORIGINS + ["Residente"]
VISITOR_TYPES = ["Turista", "Excursionista"]
WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
WEEKDAYS_EN = dict(zip(WEEKDAYS, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]))
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MIN_BASE_FOR_CHANGE = 1000    # small bases give meaningless percentages


@dataclass
class Filters:
    years: list
    month_from: int
    month_to: int
    origins: list
    types: list
    day_type: str = "All days"      # 4.2.3: applies to the daily views (Q4) and to trips (Q6)
    area: list = None               # 4.2.3: selected neighbourhood codes (from the district and neighbourhood filters); None = city

    @property
    def visitor_origins(self):
        return [o for o in self.origins if o in VISITOR_ORIGINS]

    @property
    def has_area(self):
        return bool(self.area)


def area_codes(lookup, districts, barrios):
    """Neighbourhood codes selected by the district and neighbourhood filters. None means the whole city."""
    if barrios:
        return sorted(lookup.loc[lookup["barrio_name"].isin(barrios), "cod_barrio"])
    if districts:
        return sorted(lookup.loc[lookup["distrito_name"].isin(districts), "cod_barrio"])
    return None


def barrio_lookup(tables):
    return tables["barrio_monthly"][["cod_barrio", "barrio_name", "distrito_name"]].drop_duplicates().sort_values(["distrito_name", "barrio_name"])


def _area(df, f):
    return df[df["cod_barrio"].isin(f.area)] if f.has_area else df


def _days(df, f):
    if f.day_type == DAY_TYPES[1]:
        return df[~df["is_weekend"]]
    if f.day_type == DAY_TYPES[2]:
        return df[df["is_weekend"]]
    return df


def _monthly_source(tables, f):
    """City (T1, people) or selected neighbourhoods (T4, presences: a person in two selected neighbourhoods counts twice)."""
    if f.has_area:
        df = _area(tables["barrio_monthly"], f).dropna(subset=["visitantes"])
        return df.groupby(["mes", "year", "month", "origen", "tipo_visitante"], as_index=False)["visitantes"].sum()
    return tables["city_monthly"]


def measure_label(f):
    return "presences in the selected area" if f.has_area else "unique visitors"


def to_number(series):
    """'<15' and empty cells become NaN: unknown, never zero."""
    return pd.to_numeric(series, errors="coerce")


def load_tables(stats_dir=STATS_DIR):
    text = {"mes": str, "cod_barrio": str, "distrito": str}
    tables = {
        "city_monthly": pd.read_csv(stats_dir / "city_monthly_by_origin_type.csv", dtype=text),
        "city_daily": pd.read_csv(stats_dir / "city_daily_by_origin.csv", dtype=text, parse_dates=["date"]),
        "barrio_monthly": pd.read_csv(stats_dir / "barrio_monthly_by_origin_type.csv", dtype=text),
        "trips": pd.read_csv(stats_dir / "barrio_incoming_trips_by_origen.csv", dtype=text),
    }
    t5_path = AGG_DIR / "t5_barrio_daily_by_origin.csv"
    if t5_path.exists():
        tables["t5"] = pd.read_csv(t5_path, dtype=text, parse_dates=["date"])
        tables["t5"]["visitantes"] = to_number(tables["t5"]["visitantes"])
        tables["t5"]["is_weekend"] = tables["t5"]["is_weekend"].astype(str).str.lower() == "true"
        tables["t5"]["year"] = tables["t5"]["date"].dt.year
        tables["t5"]["month"] = tables["t5"]["date"].dt.month
    for key in ("city_daily", "trips"):
        if tables[key]["is_weekend"].dtype == object:
            tables[key]["is_weekend"] = tables[key]["is_weekend"].astype(str).str.lower() == "true"
    tables["city_monthly"]["visitantes"] = to_number(tables["city_monthly"]["visitantes"])
    tables["city_daily"]["visitantes"] = to_number(tables["city_daily"]["visitantes"])
    tables["barrio_monthly"]["visitantes"] = to_number(tables["barrio_monthly"]["visitantes"])
    # A published zero adds nothing to a sum of trips: `<15` counts as 0 here and the view says so.
    tables["trips"]["viajes"] = to_number(tables["trips"]["viajes"]).fillna(0)
    return tables


def _period(df, f):
    return df[df["year"].isin(f.years) & df["month"].between(f.month_from, f.month_to)]


def _visitors(df, f):
    return _period(df, f)[lambda d: d["origen"].isin(f.visitor_origins) & d["tipo_visitante"].isin(f.types)]


def incomplete_months(tables, f):
    df = _period(tables["city_monthly"], f)
    return sorted(df.loc[df["incomplete_month"], "mes"].unique())


# Q3 --------------------------------------------------------------------------------------------
def kpis(tables, f):
    """Visitors from T1. One month: its value. Several months: the monthly mean, never the sum."""
    df = _visitors(_monthly_source(tables, f), f)
    if df.empty:
        return None
    n_months = df["mes"].nunique()
    per_month = df.groupby("mes")["visitantes"].sum()
    total = df["visitantes"].sum()
    return {"n_months": n_months, "single_month": df["mes"].iloc[0] if n_months == 1 else None,
            "visitors": float(per_month.mean()),
            "origin_share": {o: float(df.loc[df["origen"] == o, "visitantes"].sum() / total) for o in f.visitor_origins},
            "tourist_share": float(df.loc[df["tipo_visitante"] == "Turista", "visitantes"].sum() / total)}


def segments_by_month(tables, f):
    df = _visitors(_monthly_source(tables, f), f)
    return df[["mes", "year", "month", "origen", "tipo_visitante", "visitantes"]].sort_values(["mes", "origen", "tipo_visitante"])


# Q2 --------------------------------------------------------------------------------------------
def monthly_evolution(tables, f):
    """One row per selected calendar month and origin. Months outside the selection are NaN, so lines break."""
    df = _visitors(_monthly_source(tables, f), f)
    if df.empty:
        return df
    values = df.groupby(["mes", "origen"])["visitantes"].sum().unstack("origen")
    months = pd.period_range(values.index.min()[:4] + "-" + values.index.min()[4:],
                             values.index.max()[:4] + "-" + values.index.max()[4:], freq="M").strftime("%Y%m")
    values = values.reindex(months)
    out = values.reset_index(names="mes").melt(id_vars="mes", var_name="origen", value_name="visitantes")
    out["date"] = pd.to_datetime(out["mes"], format="%Y%m")
    return out.sort_values(["origen", "date"])


def peak_to_trough(evolution):
    rows = []
    for (origin, year), g in evolution.dropna(subset=["visitantes"]).assign(year=lambda d: d["date"].dt.year).groupby(["origen", "year"]):
        rows.append({"origin": origin, "year": year, "months": len(g),
                     "peak": g.loc[g["visitantes"].idxmax(), "date"].strftime("%b"),
                     "low": g.loc[g["visitantes"].idxmin(), "date"].strftime("%b"),
                     "peak / low": round(g["visitantes"].max() / g["visitantes"].min(), 2)})
    return pd.DataFrame(rows)


# Q5 --------------------------------------------------------------------------------------------
def equivalent_months(tables, f):
    """Calendar months present in every selected year (and inside the month range)."""
    df = _period(tables["city_monthly"], f)
    if df.empty or len(f.years) < 2:
        return []
    per_year = df.groupby("year")["month"].unique()
    common = set(range(1, 13))
    for year in f.years:
        common &= set(per_year.get(year, []))
    return sorted(common)


def yoy_city(tables, f):
    months = equivalent_months(tables, f)
    df = _visitors(_monthly_source(tables, f), f)
    df = df[df["month"].isin(months)]
    if df.empty:
        return df, months
    per_month = df.groupby(["year", "month", "origen"])["visitantes"].sum().reset_index()
    table = per_month.groupby(["origen", "year"])["visitantes"].mean().reset_index(name="mean_monthly_visitors")
    table["change_vs_previous_year"] = table.sort_values("year").groupby("origen")["mean_monthly_visitors"].pct_change()
    return table, months


def yoy_barrio(tables, f):
    """Change in mean monthly visitors per neighbourhood: first against last selected year, equivalent months."""
    months = equivalent_months(tables, f)
    df = _area(_visitors(tables["barrio_monthly"], f), f)
    df = df[df["month"].isin(months)].dropna(subset=["visitantes"])
    if df.empty:
        return df, None, None
    first, last = min(f.years), max(f.years)
    per_month = df[df["year"].isin([first, last])].groupby(
        ["cod_barrio", "barrio_name", "distrito_name", "year", "month"])["visitantes"].sum().unstack("year")
    per_month = per_month.dropna()
    table = per_month.groupby(["cod_barrio", "barrio_name", "distrito_name"]).mean().reset_index()
    table = table.rename(columns={first: "base", last: "latest"})
    table["change"] = (table["latest"] / table["base"] - 1).where(table["base"] >= MIN_BASE_FOR_CHANGE)
    return table, first, last


# Q4 --------------------------------------------------------------------------------------------
def _daily_source(tables, f):
    """City (T2) or selected neighbourhoods (T5, presences). T5 has no visitor type: the type filter cannot apply there."""
    if f.has_area and "t5" in tables:
        df = _area(tables["t5"], f)
        df = _period(df, f)[lambda d: d["origen"].isin(f.visitor_origins)]
        return _days(df.dropna(subset=["visitantes"]), f)
    return _days(_visitors(tables["city_daily"], f), f)


def weekday_pattern(tables, f):
    df = _daily_source(tables, f)
    if df.empty:
        return df
    per_day = df.groupby(["date", "weekday_idx", "weekday", "origen"])["visitantes"].sum().reset_index()
    out = per_day.groupby(["weekday_idx", "weekday", "origen"])["visitantes"].agg(
        mean_visitors="mean", median_visitors="median", n_days="count").reset_index()
    return out.sort_values(["origen", "weekday_idx"])


def weekend_difference(tables, f):
    if f.day_type != DAY_TYPES[0]:
        return {}
    df = _daily_source(tables, f)
    if df.empty:
        return {}
    per_day = df.groupby(["date", "is_weekend", "origen"])["visitantes"].sum().reset_index()
    means = per_day.groupby(["origen", "is_weekend"])["visitantes"].mean().unstack()
    if True not in means or False not in means:
        return {}
    return (means[True] / means[False] - 1).dropna().to_dict()


# Q1 --------------------------------------------------------------------------------------------
def barrio_values(tables, f):
    """Monthly mean of unique visitors per neighbourhood. Not additive across neighbourhoods."""
    df = _area(_visitors(tables["barrio_monthly"], f), f).dropna(subset=["visitantes"])
    if df.empty:
        return df
    per_month = df.groupby(["mes", "cod_barrio", "barrio_name", "distrito_name"])["visitantes"].sum().reset_index()
    out = per_month.groupby(["cod_barrio", "barrio_name", "distrito_name"])["visitantes"].mean().reset_index()
    return out.sort_values("visitantes", ascending=False).reset_index(drop=True)


def gini(values):
    x = np.sort(np.asarray(values, dtype=float))
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def concentration(values):
    if values.empty:
        return None
    return {"top10_share": float(values["visitantes"].head(10).sum() / values["visitantes"].sum()),
            "gini": gini(values["visitantes"]), "n_barrios": len(values)}


# Q6 --------------------------------------------------------------------------------------------
def trip_share(tables, f):
    """Share of incoming trips made by the selected origins, over all four origins. Trips, not people.
    M1 has no visitor type, so the visitor-type filter cannot apply to this view."""
    df = _area(_days(_period(tables["trips"], f), f), f)
    if df.empty or not f.origins:
        return pd.DataFrame()
    keys = ["cod_barrio", "barrio_name", "distrito_name"]
    total = df.groupby(keys)["viajes"].sum().rename("all_trips")
    selected = df[df["origen"].isin(f.origins)].groupby(keys)["viajes"].sum().rename("selected_trips")
    out = pd.concat([total, selected], axis=1).fillna({"selected_trips": 0}).reset_index()
    out["share"] = (out["selected_trips"] / out["all_trips"]).where(out["all_trips"] > 0)
    return out.sort_values("share", ascending=False).reset_index(drop=True)


def city_trip_share(share):
    return float(share["selected_trips"].sum() / share["all_trips"].sum()) if len(share) else None


def format_count(value):
    """Display rule: anything below 15 reads <15."""
    if value is None or pd.isna(value):
        return "<15"
    return "<15" if value < 15 else f"{value:,.0f}"
