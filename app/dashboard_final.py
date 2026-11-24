"""Data logic of the final dashboard tabs (WBS 4.3.1, 4.3.2). No Streamlit here, so it can be tested on its own.

    Key findings            five findings and the Charter question (final_outputs.py)
    Visitors and residents  trips of visitors and residents by month, weekday and neighbourhood (RQ-04, M1)
    Overnight stays         nights per week, municipality level only (RQ-06, T3)

Reads only aggregated tables. Trips and unique visitors are never combined.
"""

from pathlib import Path

import numpy as np
import pandas as pd

import dashboard_data as dd

ROOT = Path(__file__).resolve().parent.parent
DELIVERABLES = ROOT / "deliverables"
FINAL = DELIVERABLES / "final"
OVERNIGHT_CSV = dd.STATS_DIR / "overnight_stays_distribution.csv"
EN = {"Internacional": "International", "Nacional": "National", "Regional": "Regional", "Residente": "Resident",
      "Turista": "Overnight tourist", "Excursionista": "Day-tripper"}
WEEKDAYS_EN = list(dd.WEEKDAYS_EN.values())


def en(value):
    return EN.get(value, value)


def load():
    def read(name, **kw):
        path = FINAL / name
        return pd.read_csv(path, dtype={"cod_barrio": str, "mes": str, "month": str}, **kw) if path.exists() else None

    overnight = pd.read_csv(OVERNIGHT_CSV) if OVERNIGHT_CSV.exists() else None
    if overnight is not None:
        for c in ("mean_weekly_visitors", "share_of_year_origin"):
            overnight[c] = dd.to_number(overnight[c])
    return {"findings": read("5.2_key_findings.csv"), "charter": read("5.2_charter_answer.csv"), "barrios": read("5.2_charter_question.csv"),
            "robustness": read("5.3_verdict_robustness.csv"), "shifts": read("5.3_level_shifts.csv"), "overnight": overnight}


def available(t):
    return t["findings"] is not None and t["charter"] is not None


def robustness_of(t, qid):
    """Weakest robustness label of a question (Robust, Moderate, Fragile), or None."""
    order = ["Robust", "Moderate", "Fragile"]
    if t["robustness"] is None:
        return None
    labels = t["robustness"].loc[t["robustness"]["id"] == qid, "robustness"]
    return max(labels, key=order.index) if len(labels) else None


# Visitors and residents (M1) ----------------------------------------------------------------------------------
def _trips(tables, f):
    """Trips of the selected period, days and area. The origin filter does not apply: the comparison needs all four."""
    df = dd._area(dd._days(dd._period(tables["trips"], f), f), f)
    return df.assign(group=np.where(df["origen"] == "Residente", "Residents", "Visitors"))


def _days_in(df, keys):
    """Observed days per group of `keys`: each month and weekday counts once, whatever the neighbourhood or origin."""
    per = df.groupby(["mes", "year", "month", "weekday_idx"], as_index=False)["n_days"].max()
    return per.groupby(keys)["n_days"].sum()


def monthly_trips(tables, f):
    df = _trips(tables, f)
    if df.empty:
        return df
    out = df.groupby(["mes", "group"])["viajes"].sum().unstack("group").reindex(columns=["Visitors", "Residents"]).fillna(0)
    out = out.div(_days_in(df, "mes"), axis=0)
    total = out["Visitors"] + out["Residents"]
    out["visitor_share"] = (out["Visitors"] / total).where(total > 0)
    months = pd.period_range(f"{out.index.min()[:4]}-{out.index.min()[4:]}", f"{out.index.max()[:4]}-{out.index.max()[4:]}", freq="M")
    out = out.reindex(months.strftime("%Y%m")).reset_index(names="mes")        # months not selected break the line
    out["date"] = pd.to_datetime(out["mes"], format="%Y%m")
    return out


def weekday_trips(tables, f):
    """Trips per day as an index (mean day = 100) for visitors and residents."""
    df = _trips(tables, f)
    if df.empty:
        return df
    per = df.groupby(["weekday_idx", "group"])["viajes"].sum().unstack("group").div(_days_in(df, "weekday_idx"), axis=0)
    out = (per / per.mean() * 100).reset_index()
    out["weekday"] = out["weekday_idx"].map(dict(enumerate(WEEKDAYS_EN)))
    return out


def barrio_share(tables, f):
    df = _trips(tables, f)
    if df.empty:
        return df
    keys = ["cod_barrio", "barrio_name", "distrito_name"]
    g = df.groupby(keys + ["group"])["viajes"].sum().unstack("group").fillna(0)
    total = g["Visitors"] + g["Residents"]
    out = g.assign(share=(g["Visitors"] / total).where(total > 0)).reset_index()
    return out.sort_values("share", ascending=False).reset_index(drop=True)


def share_change(tables, f):
    """Change in the visitor share between the first and the last selected year, equivalent months only."""
    if len(f.years) < 2:
        return None, None, None, []
    months = dd.equivalent_months(tables, f)
    first, last = min(f.years), max(f.years)
    df = _trips(tables, f)
    df = df[df["month"].isin(months) & df["year"].isin([first, last])]
    if df.empty:
        return None, first, last, months
    g = df.groupby(["cod_barrio", "barrio_name", "distrito_name", "year", "group"])["viajes"].sum().unstack("group").fillna(0)
    total = g["Visitors"] + g["Residents"]
    share = (g["Visitors"] / total).where(total > 0).unstack("year").dropna()
    out = share.reset_index().rename(columns={first: "base", last: "latest"})
    out["points"] = (out["latest"] - out["base"]) * 100
    return out.sort_values("points", ascending=False).reset_index(drop=True), first, last, months


def city_summary(tables, f):
    df = _trips(tables, f)
    if df.empty:
        return None
    by = df.groupby("group")["viajes"].sum()
    days = _days_in(df, "mes").sum()
    v, r = by.get("Visitors", 0), by.get("Residents", 0)
    return {"visitors_per_day": v / days, "residents_per_day": r / days, "share": v / (v + r) if v + r else None}


# Overnight stays (T3) -----------------------------------------------------------------------------------------
def overnight(t, f):
    """Distribution of nights per week by origin, mean of the selected years. 2025 covers January to August."""
    df = t["overnight"]
    if df is None:
        return pd.DataFrame()
    df = df[df["year"].isin(f.years) & df["origen"].isin(f.visitor_origins)]
    if df.empty:
        return df
    df = df.assign(weighted=df["mean_weekly_visitors"] * df["n_weeks"])
    g = df.groupby(["origen", "pernoctaciones"])["weighted"].sum().reset_index()
    g["share"] = g["weighted"] / g.groupby("origen")["weighted"].transform("sum")
    return g.drop(columns="weighted")


def overnight_summary(dist):
    rows = {}
    for origin, g in dist.groupby("origen"):
        rows[origin] = {"mean": float((g["pernoctaciones"] * g["share"]).sum()), "short": float(g.loc[g["pernoctaciones"] <= 2, "share"].sum()),
                        "long": float(g.loc[g["pernoctaciones"] >= 4, "share"].sum())}
    return rows
