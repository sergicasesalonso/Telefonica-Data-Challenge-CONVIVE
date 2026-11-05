"""Checks for the dashboard (WBS 4.2.0, final check of the Iteration 2 plan).

  1. Each filter changes each view, computed on the view's data.
  2. The app runs without an exception on normal and edge-case selections.
  3. Every CSV applies the <15 rule.

Run:  python app/check_dashboard.py
"""

import hashlib
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

import dashboard_data as dd   # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ALL_YEARS = [2023, 2024, 2025]
BASE = dd.Filters(ALL_YEARS, 1, 12, dd.VISITOR_ORIGINS, dd.VISITOR_TYPES)
VARIANTS = {
    "year": dd.Filters([2023, 2024], 1, 12, dd.VISITOR_ORIGINS, dd.VISITOR_TYPES),
    "month range": dd.Filters(ALL_YEARS, 3, 5, dd.VISITOR_ORIGINS, dd.VISITOR_TYPES),
    "origin": dd.Filters(ALL_YEARS, 1, 12, ["Internacional", "Regional"], dd.VISITOR_TYPES),
    "type": dd.Filters(ALL_YEARS, 1, 12, dd.VISITOR_ORIGINS, ["Turista"]),
}
# Mobility has no visitor type, so this one cannot change. The view says so on screen.
EXPECTED_UNCHANGED = {("Q6 trip share", "type")}


def fingerprint(value):
    if isinstance(value, tuple):
        value = value[0]
    if isinstance(value, pd.DataFrame):
        value = value.round(6).to_csv(index=False)
    return hashlib.md5(str(value).encode()).hexdigest()


def views(tables, f):
    return {"Q3 KPI tiles": dd.kpis(tables, f), "Q3 stacked bars": dd.segments_by_month(tables, f),
            "Q2 monthly evolution": dd.monthly_evolution(tables, f), "Q5 city comparison": dd.yoy_city(tables, f),
            "Q5 neighbourhood change": dd.yoy_barrio(tables, f), "Q4 weekday": dd.weekday_pattern(tables, f),
            "Q1 map and top 10": dd.barrio_values(tables, f), "Q6 trip share": dd.trip_share(tables, f)}


def check_filters(tables):
    base = {k: fingerprint(v) for k, v in views(tables, BASE).items()}
    rows, failures = [], 0
    for name, f in VARIANTS.items():
        for view, value in views(tables, f).items():
            changed = fingerprint(value) != base[view]
            expected = (view, name) not in EXPECTED_UNCHANGED
            failures += changed != expected
            rows.append({"filter": name, "view": view, "changes": changed, "expected": expected})
    table = pd.DataFrame(rows).pivot(index="view", columns="filter", values="changes")
    print(table.to_string())
    # Residente is a trips-only origin: it must change Q6 and nothing else.
    with_residents = dd.Filters(ALL_YEARS, 1, 12, dd.TRIP_ORIGINS, dd.VISITOR_TYPES)
    for view, value in views(tables, with_residents).items():
        changed = fingerprint(value) != base[view]
        if changed != (view == "Q6 trip share"):
            failures += 1
            print("Residente: unexpected result in", view)
    print("Residente changes only Q6: checked")
    return failures


def check_rules(tables):
    failures = 0
    k = dd.kpis(tables, BASE)
    per_month = tables["city_monthly"].groupby("mes")["visitantes"].sum()
    if abs(k["visitors"] - per_month.mean()) > 1:
        failures += 1
        print("KPI is not the monthly mean")
    print(f"KPI uses the monthly mean over {k['n_months']} months, and is below the sum of months: {k['visitors'] < per_month.sum()}")
    return failures


def check_thresholds():
    failures = 0
    for path in sorted(dd.STATS_DIR.glob("*.csv")):
        df = pd.read_csv(path, dtype=str)
        columns = [c for c in df.columns if c in ("visitantes", "viajes", "mean_visitors", "median_visitors", "mean_weekly_visitors")
                   or c.startswith("mean_monthly_")]
        below, marked = 0, 0
        for c in columns:
            numbers = pd.to_numeric(df[c], errors="coerce")
            below += int((numbers < 15).sum())
            marked += int((df[c] == "<15").sum())
        failures += below
        print(f"{path.name:44s} value columns: {len(columns)}; visible values below 15: {below}; cells marked <15: {marked}")
    return failures


def check_app():
    from streamlit.testing.v1 import AppTest
    cases = {
        "default": {},
        "one year": {"f_years": [2024]},
        "one month": {"f_months": (7, 7), "f_years": [2024]},
        "two years": {"f_years": [2023, 2025]},
        "2025 and autumn": {"f_months": (9, 12)},
        "only Residente": {"f_origins": ["Residente"]},
        "no origin": {"f_origins": []},
        "no year": {"f_years": []},
        "no type": {"f_types": []},
        "Regional tourists (empty by definition)": {"f_origins": ["Regional"], "f_types": ["Turista"]},
        "residents and visitors": {"f_origins": dd.TRIP_ORIGINS},
        "excursionists": {"f_types": ["Excursionista"]},
    }
    failures = 0
    for name, state in cases.items():
        at = AppTest.from_file(str(HERE / "dashboard.py"), default_timeout=240)
        at.run()
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        problems = [e.value for e in at.exception]
        failures += len(problems)
        print(f"{name:42s} exceptions: {len(problems)}  metrics: {len(at.metric)}  warnings: {len(at.warning)}")
        for p in problems:
            print("   ", p[:300])
    return failures


def main():
    tables = dd.load_tables()
    failures = check_filters(tables)
    failures += check_rules(tables)
    failures += check_thresholds()
    failures += check_app()
    print("\nALL CHECKS PASSED" if not failures else f"\n{failures} CHECK(S) FAILED")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
