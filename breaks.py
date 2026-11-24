"""CONVIVE - level shifts in the neighbourhood series (extends issue I8; final iteration, WBS 5.3 limitations).

Iteration 3 found one break by eye (Verdun, August 2023). Here the same check runs on the 73 neighbourhoods and on two
separate products: T4 (unique visitors) and M1 (visitors' incoming trips per observed day).

Rule (fixed before the scan): a series has a LEVEL SHIFT if the median of its share of the city in the six months from month m
is at least 1.5 times, or at most 1/1.5 of, the median in the six months before m. Taking shares of the city removes the season
and the city trend. The ratio is the largest one; the month is the largest jump around it. The scan locates shifts; it cannot name their cause.

    python breaks.py
"""

import sys

import numpy as np
import pandas as pd

import research as R

WINDOW = 6
FACTOR = 1.5
RULE_TEXT = ("A neighbourhood series has a LEVEL SHIFT if the median of its share of the city total in the six months from a month "
             "is at least 1.5 times (or at most 1/1.5 of) the median of the six months before it.")


def t4_series(t):
    return t["barrio_monthly"].dropna(subset=["visitantes"]).groupby(["mes", "barrio_name"])["visitantes"].sum().unstack()


def m1_series(t):
    df = t["trips"]
    df = df[df["origen"] != "Residente"].assign(viajes=lambda d: d["viajes"].fillna(0))
    return df.groupby(["mes", "barrio_name"])["viajes"].sum().unstack()      # the share of the city cancels the number of days


def scan(series, product):
    share = series.div(series.sum(axis=1), axis=0)
    rows = []
    for name in share.columns:
        s = share[name].dropna()
        candidates = []
        for i in range(WINDOW, len(s) - WINDOW + 1):
            before, after = s.iloc[i - WINDOW:i].median(), s.iloc[i:i + WINDOW].median()
            if before > 0 and after > 0 and s.iloc[i] > 0 and s.iloc[i - 1] > 0:
                candidates.append((s.index[i], after / before, s.iloc[i] / s.iloc[i - 1]))
        if not candidates:
            continue
        largest = max(candidates, key=lambda c: abs(np.log(c[1])))
        # Medians give almost the same ratio in the months around the shift: date it at the largest month-on-month jump
        # in the direction of the shift.
        sign = np.sign(np.log(largest[1]))
        close = [c for c in candidates if abs(np.log(c[1])) >= 0.9 * abs(np.log(largest[1])) and np.sign(np.log(c[1])) == sign]
        dated = max(close, key=lambda c: sign * np.log(c[2]))
        rows.append({"barrio_name": name, "product": product, "month": dated[0], "ratio": largest[1], "month_on_month": dated[2],
                     "shift": largest[1] >= FACTOR or largest[1] <= 1 / FACTOR})
    return pd.DataFrame(rows)


def pair_transfer(t, a="Can Peguera", b="el Turó de la Peira", month="202404"):
    """Two adjacent neighbourhoods that shift in the same month and in opposite directions: mean of the six months before and
    after, for each and for both together. If the total is stable, the shift is a transfer between zones."""
    residents = t["trips"][t["trips"]["origen"] == "Residente"].assign(viajes=lambda d: d["viajes"].fillna(0))
    days = t["trips"].groupby(["mes", "weekday_idx"])["n_days"].max().groupby("mes").sum()
    products = {"T4 visitors per month": t4_series(t), "M1 visitors' trips per day": m1_series(t).div(days, axis=0),
                "M1 residents' trips per day": residents.groupby(["mes", "barrio_name"])["viajes"].sum().unstack().div(days, axis=0)}
    rows = []
    for product, frame in products.items():
        i = list(frame.index).index(month)
        before, after = frame.iloc[i - WINDOW:i].mean(), frame.iloc[i:i + WINDOW].mean()
        for label, cols in ((a, [a]), (b, [b]), ("both", [a, b])):
            rows.append({"product": product, "area": label, "before": before[cols].sum(), "after": after[cols].sum(),
                         "change": after[cols].sum() / before[cols].sum() - 1})
    return pd.DataFrame(rows)


def run(t):
    both = pd.concat([scan(t4_series(t), "T4 visitors"), scan(m1_series(t), "M1 visitor trips")], ignore_index=True)
    both = both.merge(R.barrio_lookup()[["barrio_name", "distrito_name"]], on="barrio_name", how="left")
    found = both[both["shift"]].copy()
    found["size"] = np.log(found["ratio"]).abs()
    found = found.sort_values("size", ascending=False).drop(columns="size").reset_index(drop=True)
    return {"all": both, "found": found, "pair": pair_transfer(t)}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    result = run(R.load_all())
    print(result["found"].round(2).to_string(index=False))
    print(result["pair"].round(2).to_string(index=False))
