"""CONVIVE - how much do the verdicts depend on the thresholds? (final iteration, supports C12 and WBS 5.3)

The thresholds are the team's and still need the Business Manager's validation, so every question is recomputed with its
main threshold made 10% and 20% easier and harder. A verdict is ROBUST if "belief holds?" does not change in any of the four
variants, MODERATE if it changes only at +/-20%, and FRAGILE if it already changes at +/-10%.

Nothing is typed by hand: the questions are recomputed with research.py and coexistence.py under the changed rule.

    python sensitivity.py
"""

import copy
import sys

import pandas as pd

import coexistence as C
import research as R

STEPS = (-0.20, -0.10, 0.10, 0.20)
# question: (key in THRESHOLDS, what the threshold is, kind)
#   share   the threshold itself is scaled (capped at 1)
#   excess  only the part above 1 is scaled (1.30 -> 1.24 ... 1.36)
#   count   scaled and rounded to a whole number, at least one unit away
SPEC = {
    "Q1": ("n50_concentrated", "N50 in neighbourhoods", "count"),
    "Q2": ("strong", "summer / other months", "excess"),
    "Q3": ("months_share", "share of months with an international majority", "share"),
    "Q4": ("flood", "weekend change", "share"),
    "Q5": ("growth", "yearly growth", "share"),
    "Q6": ("share", "visitor share of incoming trips", "share"),
    "Q7": ("share", "share of tourists with 1-2 nights", "share"),
    "Q8": ("keep", "top-10 neighbourhoods kept", "count"),
    "Q9": ("peak", "deviation of a day", "share"),
    "Q10": ("overlap", "top-10 overlap", "count"),
    "Q11": ("top5", "share of the top 5 countries", "share"),
    "Q12": ("share", "share of Madrid", "share"),
    "Q13": ("share", "share of the metropolitan ring", "share"),
    "Q14": ("share", "share young / high income", "share"),
    "Q15": ("points", "gap in index points", "share"),
    "Q16": ("gap", "difference in N50", "count"),
    "Q17": ("fast", "growth of a market", "share"),
    "Q18": ("strong", "summer / other months", "excess"),
    "Q19": ("overlap", "top-10 overlap of a market", "count"),
    "Q20": ("share", "share of overnight tourists", "share"),
}


def scaled(value, step, kind):
    if kind == "excess":
        return 1 + (value - 1) * (1 + step)
    if kind == "count":
        change = max(1, round(value * abs(step)))
        return int(value + change * (1 if step > 0 else -1))
    return value * (1 + step)


def answer_one(qid, t, base):
    """Recompute one question under the current R.THRESHOLDS."""
    f = {"Q3": lambda: R.q3(t), "Q11": lambda: R.q11(t, base["Q3"]), "Q16": lambda: R.q16(t, base["Q1"]),
         "Q18": lambda: R.q18(t, base["nationalities"]), "Q19": lambda: R.q19(t, base["nationalities"]),
         "Q20": lambda: R.q20(t, base["nationalities"])}.get(qid) or (lambda: getattr(R, qid.lower())(t))
    res = f()
    return R.belief_holds(qid, res), res["verdict"]


def label(outcomes, base):
    """outcomes: {step: holds}"""
    if any(outcomes[s] != base for s in (-0.10, 0.10)):
        return "Fragile"
    if any(outcomes[s] != base for s in (-0.20, 0.20)):
        return "Moderate"
    return "Robust"


def charter_question(t):
    """Q0 under the same changes: the 2-point rule and, separately, the 37-neighbourhood rule."""
    rows = []
    for key, what, kind in (("points", "change in the visitor share (points)", "share"), ("holds", "neighbourhoods needed", "count")):
        original = C.RULES[key]
        base = C.run(t)["belief_holds"]
        row, outcomes = {"id": "Q0", "threshold": what, "value": original, "base": base}, {}
        for step in STEPS:
            C.RULES[key] = scaled(original, step, kind)
            outcomes[step] = C.run(t)["belief_holds"]
            row[f"{step:+.0%}"] = outcomes[step]
        C.RULES[key] = original
        row["robustness"] = label(outcomes, base)
        rows.append(row)
    return rows


def run(t=None, base=None):
    if t is None or base is None:
        t, base = R.run_all()
    rows = charter_question(t)
    original = copy.deepcopy(R.THRESHOLDS)
    try:
        for qid, (key, what, kind) in SPEC.items():
            holds = base[qid]["holds"]
            row, outcomes = {"id": qid, "threshold": what, "value": original[qid][key], "base": holds}, {}
            for step in STEPS:
                R.THRESHOLDS[qid][key] = scaled(original[qid][key], step, kind)
                outcomes[step], _ = answer_one(qid, t, base)
                row[f"{step:+.0%}"] = outcomes[step]
                R.THRESHOLDS[qid][key] = original[qid][key]
            row["robustness"] = label(outcomes, holds)
            rows.append(row)
    finally:
        for qid in original:
            R.THRESHOLDS[qid].clear()
            R.THRESHOLDS[qid].update(original[qid])
    return pd.DataFrame(rows)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    table = run()
    print(table.to_string(index=False))
    print(table["robustness"].value_counts().to_string())
