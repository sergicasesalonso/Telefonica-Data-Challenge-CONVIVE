"""CONVIVE - the Charter question (Q0): how does the presence of visitors change over time in the neighbourhoods of
Barcelona, compared with residents? (SC-07, RQ-04; final iteration)

Residents exist only in the mobility product (M1), so the comparison uses incoming trips. Reads only aggregated tables.
The decision rules below were written before the answer was computed, as for Q1-Q20.

    python coexistence.py      prints the answer
"""

import sys

import numpy as np
import pandas as pd

import research as R

RULES = {
    "points": 0.02,        # change in the visitor share of incoming trips, January-August 2023 -> 2025
    "holds": 37,           # more than half of the 73 neighbourhoods
    "partly": 19,          # more than a quarter
    "even_low": 0.40,      # 40%-60% of incoming trips made by visitors = shared neighbourhood
    "even_high": 0.60,
}
RULE_TEXT = ("Visitors GAIN GROUND in a neighbourhood if their share of incoming trips (M1, January-August) rises by at least "
             "2 percentage points between 2023 and 2025, LOSE GROUND if it falls by at least 2 points, and are STABLE in between. "
             "The belief holds if they gain ground in at least 37 of 73 neighbourhoods (half); PARTLY if 19 to 36; NO if fewer.")
BELIEF = "Visitors are gaining ground on residents across the neighbourhoods of Barcelona."
QUESTION = ("Did the visitor share of incoming trips rise by at least 2 points in at least half of the 73 neighbourhoods "
            "between 2023 and 2025?")
LIMITATION = ("Trips, not people; trips inside a neighbourhood are excluded; a published 0 means fewer than 15 trips, so each "
              "share has bounds; two intervals cannot prove a long-term trend; no cause can be inferred.")
YEARS = [2023, 2024, 2025]


def _jan_aug(t):
    df = t["trips"]
    return df[df["month"].astype(int).between(1, 8)].assign(viajes=lambda d: d["viajes"].fillna(0))


def shares_by_year(t):
    """Visitor share of incoming trips per neighbourhood and year (January-August), with bounds for published zeros."""
    trips = _jan_aug(t)
    return pd.concat([R.trip_shares({"trips": trips}, [y]).assign(year=y) for y in YEARS], ignore_index=True)


def classify(change):
    if change >= RULES["points"]:
        return "Gains ground"
    if change <= -RULES["points"]:
        return "Loses ground"
    return "Stable"


def profile(share):
    """Who makes most incoming trips: residents, both, or visitors."""
    if share > RULES["even_high"]:
        return "Visitor-dominated (>60%)"
    if share >= RULES["even_low"]:
        return "Shared (40-60%)"
    return "Resident-dominated (<40%)"


def barrio_table(t):
    s = shares_by_year(t)
    wide = s.pivot(index=["cod_barrio", "barrio_name", "distrito_name"], columns="year", values="visitor_share")
    wide.columns = [f"share_{y}" for y in wide.columns]
    low = s.pivot(index="cod_barrio", columns="year", values="share_low")
    high = s.pivot(index="cod_barrio", columns="year", values="share_high")
    out = wide.reset_index()
    out["change"] = out["share_2025"] - out["share_2023"]
    out["status"] = out["change"].map(classify)
    out["profile_2025"] = out["share_2025"].map(profile)
    for y in (2023, 2025):
        out[f"low_{y}"] = out["cod_barrio"].map(low[y])
        out[f"high_{y}"] = out["cod_barrio"].map(high[y])
    # A change is robust to the privacy threshold if the two ranges of possible shares do not overlap.
    out["robust"] = (out["low_2025"] > out["high_2023"]) | (out["high_2025"] < out["low_2023"])
    trips = _jan_aug(t).assign(group=lambda d: np.where(d["origen"] == "Residente", "resident", "visitor"))
    g = trips.groupby(["cod_barrio", "group", "year"])["viajes"].sum().unstack("year")
    growth = (g[2025] / g[2023] - 1).unstack("group")
    out["visitor_trips_growth"] = out["cod_barrio"].map(growth["visitor"])
    out["resident_trips_growth"] = out["cod_barrio"].map(growth["resident"])
    return out.sort_values("change", ascending=False).reset_index(drop=True)


def observed_days(trips):
    """Days with data per year: M1 misses some days, so levels are compared per observed day."""
    per = trips.groupby(["year", "month", "weekday_idx"])["n_days"].max()
    return per.groupby("year").sum()


def origin_table(t):
    """City trips per day by origin, January-August of each year: level, share and change."""
    df = _jan_aug(t)
    trips = df.groupby(["origen", "year"])["viajes"].sum().unstack("year")
    days = observed_days(df)
    per_day = trips / days
    out = pd.DataFrame({"origin": [R.ORIGIN_EN[o] for o in per_day.index], "origen": per_day.index})
    for y in YEARS:
        out[f"per_day_{y}"] = per_day[y].values
        out[f"share_{y}"] = (trips[y] / trips[y].sum()).values
    out["change_23_24"] = out["per_day_2024"] / out["per_day_2023"] - 1
    out["change_24_25"] = out["per_day_2025"] / out["per_day_2024"] - 1
    out["change_23_25"] = out["per_day_2025"] / out["per_day_2023"] - 1
    return out, days


def city_month(t):
    """Trips per observed day and month, residents and visitors (level and visitor share)."""
    df = t["trips"].assign(group=lambda d: np.where(d["origen"] == "Residente", "resident", "visitor"), viajes=lambda d: d["viajes"].fillna(0))
    days = df.groupby(["mes", "weekday_idx"])["n_days"].max().groupby("mes").sum()
    out = df.groupby(["mes", "group"])["viajes"].sum().unstack("group").div(days, axis=0)
    out["visitor_share"] = out["visitor"] / (out["visitor"] + out["resident"])
    return out.reset_index()


def run(t):
    table = barrio_table(t)
    origins, days = origin_table(t)
    counts = table["status"].value_counts()
    n_gain, n_loss, n_stable = (int(counts.get(k, 0)) for k in ("Gains ground", "Loses ground", "Stable"))
    holds = "Yes" if n_gain >= RULES["holds"] else "Partly" if n_gain >= RULES["partly"] else "No"
    o = origins.set_index("origen")
    city = {y: 1 - float(o.loc["Residente", f"share_{y}"]) for y in YEARS}
    vis = o.drop("Residente")
    vis_growth = float(vis["per_day_2025"].sum() / vis["per_day_2023"].sum() - 1)
    res_growth = float(o.loc["Residente", "change_23_25"])
    prof = table["profile_2025"].value_counts()
    answer = (f"Visitors made {R.pct(city[2023])} of the trips between neighbourhoods in January-August 2023, {R.pct(city[2024])} in "
              f"2024 and {R.pct(city[2025])} in 2025. Trips per day changed by {R.signed(vis_growth)} for visitors and "
              f"{R.signed(res_growth)} for residents between 2023 and 2025 (international "
              f"{R.signed(o.loc['Internacional', 'change_23_25'])}, national {R.signed(o.loc['Nacional', 'change_23_25'])}, regional "
              f"{R.signed(o.loc['Regional', 'change_23_25'])}). Visitors gain ground in {n_gain} of 73 neighbourhoods, are stable in "
              f"{n_stable} and lose ground in {n_loss}. In 2025 visitors dominate (above 60%) in "
              f"{int(prof.get('Visitor-dominated (>60%)', 0))} neighbourhoods, visitors and residents share "
              f"{int(prof.get('Shared (40-60%)', 0))} (40-60%) and residents dominate {int(prof.get('Resident-dominated (<40%)', 0))}.")
    return {"id": "Q0", "belief": BELIEF, "question": QUESTION, "data": "M1", "decision_rule": RULE_TEXT, "answer": answer,
            "metric": "Visitor share of incoming trips per neighbourhood, January-August 2023, 2024 and 2025",
            "verdict": f"Visitors gain ground in {n_gain} of 73 neighbourhoods and lose it in {n_loss}", "belief_holds": holds,
            "limitation": LIMITATION, "table": table, "origins": origins, "days": days, "month": city_month(t), "city": city,
            "visitor_growth": vis_growth, "resident_growth": res_growth, "n_gain": n_gain, "n_loss": n_loss, "n_stable": n_stable}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    res = run(R.load_all())
    print(res["answer"])
    print(res["verdict"], "| belief holds:", res["belief_holds"])
