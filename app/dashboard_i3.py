"""Data logic of the Iteration 3 dashboard pages (WBS 4.2.2 charts and indicators, 4.2.3 filters). No Streamlit here.

Reads only aggregated outputs: deliverables/iteration3/2.2.1_aggregates/*.csv and the 3.2.x result tables written by
research_report.py. Sums of unique visitors across neighbourhoods are always labelled 'presences'.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import nationalities as N  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
I3 = ROOT / "deliverables" / "iteration3"
AGG = I3 / "2.2.1_aggregates"
FIGURES = I3 / "figures"


def _read(path, **kw):
    if not path.exists():
        return None
    return pd.read_csv(path, dtype={"mes": str, "cod_barrio": str, "barrio_origen": str, "barrio_destino": str}, keep_default_na=False, **kw)


def _num(df, *cols):
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load():
    t = {
        "answers": _read(I3 / "3.2.4_quantified_answers.csv"),
        "low_data": _read(I3 / "3.2.2_low_data_barris.csv"),
        "validation": _read(I3 / "2.2.2_validation_log.csv"),
        "lq": _read(I3 / "3.2.2_location_quotients.csv"),
        "weekend": _read(I3 / "3.2.3_weekend_by_barrio.csv"),
        "t8_city": _read(AGG / "t8_country_city_month.csv"),
        "t7_city": _read(AGG / "t7_province_city_month.csv"),
        "t6_city": _read(AGG / "t6_municipality_city_month.csv"),
        "t9_city": _read(AGG / "t9_profile_city_month.csv"),
        "t8_barrio": _read(AGG / "t8_country_barrio_year.csv"),
        "t7_barrio": _read(AGG / "t7_province_barrio_year.csv"),
        "t6_barrio": _read(AGG / "t6_municipality_barrio_year.csv"),
        "od": _read(AGG / "m1_od_year_by_origin.csv"),
        "nat_profile": _read(I3 / "3.2.1_nationality_profile.csv"),
        "nat_regions": _read(I3 / "3.2.1_world_regions.csv"),
    }
    if t["nat_profile"] is not None:
        _num(t["nat_profile"], "rank", "share", "tourist_share", "growth_23_25", "summer_ratio", "distinctive_lq", "overlap_int_top10")
    if t["nat_regions"] is not None:
        _num(t["nat_regions"], "share_jan_aug_2023", "share_jan_aug_2024", "share_jan_aug_2025", "growth_23_25")
    for key in ("t8_city", "t7_city", "t6_city", "t9_city"):
        if t[key] is not None:
            _num(t[key], "presences", "year", "month")
    for key in ("t8_barrio", "t7_barrio", "t6_barrio"):
        if t[key] is not None:
            _num(t[key], "mean_monthly", "year", "share_in_barrio")
    if t["od"] is not None:
        _num(t["od"], "viajes", "year", "n_zero", "n_flows")
    if t["low_data"] is not None:
        _num(t["low_data"], "mean_monthly_visitors", "vs_median", "visitor_share_trips", "resident_trips_vs_median")
        t["low_data"]["low_data"] = t["low_data"]["low_data"].astype(str).str.lower() == "true"
    if t["weekend"] is not None:
        _num(t["weekend"], "weekend_change", "weekday_mean", "weekend_mean")
    if t["lq"] is not None:
        _num(t["lq"], "Internacional", "Nacional", "Regional")
    return t


def available(t):
    return t["answers"] is not None


# 4.2.2 · residence rankings (Q3, Q11-Q13) -------------------------------------------------------------------------
RESIDENCE = {"Country (international, T8)": ("t8_city", "country"), "Province (national, T7)": ("t7_city", "province"),
             "Municipality (regional, T6)": ("t6_city", "municipality")}


def residence_ranking(t, which, f, tipo=None, top=15):
    key, column = RESIDENCE[which]
    df = t[key]
    df = df[df["year"].isin(f.years) & df["month"].between(f.month_from, f.month_to)]
    if tipo:
        df = df[df["tipo_visitante"].isin(tipo)]
    if df.empty:
        return df
    total = df.groupby(column)["presences"].sum()
    out = (total / total.sum()).rename("share").reset_index().sort_values("share", ascending=False)
    out["monthly_presences"] = out[column].map(total / df["mes"].nunique())
    return out.head(top).rename(columns={column: "place"})


def residence_trend(t, which, places, tipo=None):
    key, column = RESIDENCE[which]
    df = t[key]
    if tipo:
        df = df[df["tipo_visitante"].isin(tipo)]
    month_total = df.groupby("mes")["presences"].sum()
    out = df[df[column].isin(places)].groupby(["mes", column])["presences"].sum().reset_index()
    out["share"] = out["presences"] / out["mes"].map(month_total)
    out["date"] = pd.to_datetime(out["mes"], format="%Y%m")
    return out.rename(columns={column: "place"})


def profile(t, f, dimension):
    df = t["t9_city"]
    df = df[df["year"].isin(f.years) & df["month"].between(f.month_from, f.month_to) & df["origen"].isin(f.visitor_origins)
            & df["tipo_visitante"].isin(f.types) & (df[dimension] != "NA")]
    if df.empty:
        return df
    out = df.groupby(["origen", dimension])["presences"].sum().reset_index()
    out["share"] = out["presences"] / out.groupby("origen")["presences"].transform("sum")
    return out


# 4.2.3 · neighbourhood explorer ------------------------------------------------------------------------------------
def explorer(t, tables, cod_barrio, f):
    """Every indicator of one neighbourhood, from the aggregated tables (period and origin filters applied)."""
    bm = tables["barrio_monthly"]
    bm = bm[bm["year"].isin(f.years) & bm["month"].between(f.month_from, f.month_to) & bm["tipo_visitante"].isin(f.types)]
    per = bm.dropna(subset=["visitantes"]).groupby(["mes", "cod_barrio"])["visitantes"].sum().groupby("cod_barrio").mean()
    rank = per.rank(ascending=False)
    series = bm[(bm["cod_barrio"] == cod_barrio) & bm["origen"].isin(f.visitor_origins)].groupby(["mes", "origen"])["visitantes"].sum(min_count=1).reset_index()
    series["date"] = pd.to_datetime(series["mes"], format="%Y%m")
    trips = tables["trips"]
    trips = trips[(trips["cod_barrio"] == cod_barrio) & trips["year"].isin(f.years) & trips["month"].between(f.month_from, f.month_to)]
    trip_by_origin = trips.groupby("origen")["viajes"].sum()
    visitor_share = trip_by_origin.drop("Residente", errors="ignore").sum() / trip_by_origin.sum() if trip_by_origin.sum() else None
    t5 = tables.get("t5")
    weekday = None
    if t5 is not None:
        d = t5[(t5["cod_barrio"] == cod_barrio) & t5["year"].isin(f.years) & t5["month"].between(f.month_from, f.month_to)
               & t5["origen"].isin(f.visitor_origins)].dropna(subset=["visitantes"])
        if len(d):
            weekday = d.groupby(["date", "weekday_idx", "origen"])["visitantes"].sum().reset_index() \
                       .groupby(["weekday_idx", "origen"])["visitantes"].mean().reset_index()
    years = [y for y in f.years if y in set(t["t8_barrio"]["year"])]
    countries = t["t8_barrio"][(t["t8_barrio"]["cod_barrio"] == cod_barrio) & t["t8_barrio"]["year"].isin(years) & (t["t8_barrio"]["country"] != "NA")]
    countries = countries.groupby("country")["mean_monthly"].mean().sort_values(ascending=False).head(8)
    low = t["low_data"].set_index("cod_barrio") if t["low_data"] is not None else None
    lq = t["lq"].set_index("barrio_name") if t["lq"] is not None else None
    full = tables["barrio_monthly"]
    name = full.loc[full["cod_barrio"] == cod_barrio, "barrio_name"].iloc[0]
    return {"name": name, "mean_monthly": per.get(cod_barrio), "rank": rank.get(cod_barrio), "n": len(per), "series": series,
            "visitor_share": visitor_share, "trip_by_origin": trip_by_origin, "weekday": weekday, "countries": countries,
            "low_data": bool(low.loc[cod_barrio, "low_data"]) if low is not None and cod_barrio in low.index else False,
            "low_reason": low.loc[cod_barrio, "reason"] if low is not None and cod_barrio in low.index else "",
            "lq": lq.loc[name] if lq is not None and name in lq.index else None}


# 4.2.2 · nationalities (T8) -----------------------------------------------------------------------------------------
def _months(f):
    return list(range(f.month_from, f.month_to + 1))


def country_ranking(t, f):
    share = N.shares(t, years=f.years, months=_months(f), tipo=f.types)
    if share.empty:
        return pd.DataFrame(columns=["country", "share"])
    return share.rename("share").reset_index().rename(columns={"index": "country"})


def country_card(t, f, country, ranking):
    """KPIs of one country: share and rank in the selection; type split in the selection; whole-period growth and season."""
    rank = int(ranking.index[ranking["country"] == country][0]) + 1
    sel = N.shares(t, years=f.years, months=_months(f))
    tour = N.shares(t, years=f.years, months=_months(f), tipo="Turista")
    city = t["t8_city"]
    city = city[(city["country"] == country) & city["year"].isin(f.years) & city["month"].between(f.month_from, f.month_to)]
    tourist_share = city.loc[city["tipo_visitante"] == "Turista", "presences"].sum() / city["presences"].sum() if city["presences"].sum() else None
    prof = t["nat_profile"].set_index("country") if t.get("nat_profile") is not None else None
    row = prof.loc[country] if prof is not None and country in prof.index else {}
    return {"share": float(ranking.set_index("country").loc[country, "share"]), "rank": rank, "tourist_share": tourist_share,
            "growth_23_25": row.get("growth_23_25") if len(row) else None, "peak_month": row.get("peak_month", "") if len(row) else "",
            "summer_ratio": row.get("summer_ratio", float("nan")) if len(row) else float("nan"), "region": N.region(country)}


def country_monthly(t, f, country):
    return N.monthly(t, country, years=f.years, months=_months(f), tipo=f.types)


def country_season(t, country):
    idx = N.seasonal_index(t, [country]).loc[country]
    return pd.DataFrame({"month": N.MONTHS_EN, "index": idx.reindex(range(1, 13)).values})


def country_lq(t, f, country):
    lq = N.location_quotients(t, years=[y for y in f.years if y in set(t["t8_barrio"]["year"])] or None)
    return lq[lq["country"] == country]
