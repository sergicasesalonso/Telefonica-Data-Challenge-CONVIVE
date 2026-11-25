"""Unit tests of the rules that must never break (WBS 4.3.1). They use small made-up tables, so they need no NDA data.

    python -m pytest tests -q
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

import aggregates as A          # noqa: E402
import breaks as B              # noqa: E402
import coexistence as C         # noqa: E402
import dashboard_data as dd     # noqa: E402
import dashboard_final as df4   # noqa: E402
import research as R            # noqa: E402
import sensitivity as S         # noqa: E402


def trips_table():
    """Two neighbourhoods, two years, two months: the visitor share of A rises from 40% to 50%, B stays at 20%."""
    rows = []
    for year, visitors in ((2023, 400), (2024, 450), (2025, 600)):
        for month in (1, 2):
            for code, name, v, r in (("A", "Alpha", visitors, 600), ("B", "Beta", 200, 800)):
                for origin, value in (("Internacional", v), ("Residente", r)):
                    rows.append({"cod_barrio": code, "barrio_name": name, "distrito_name": "D", "mes": f"{year}{month:02d}", "year": year,
                                 "month": month, "weekday_idx": 0, "weekday": "Lunes", "is_weekend": False, "origen": origin, "viajes": value,
                                 "n_days": 4, "n_flows": 10, "n_flows_zero": 0})
    return pd.DataFrame(rows)


# Privacy ------------------------------------------------------------------------------------------------------
def test_suppress_writes_below_15():
    out = A.suppress(pd.DataFrame({"v": [0, 1, 14, 15, 2000]}), ["v"])
    text = out["v"].astype(str).tolist()
    assert "<15" in text[1] and "<15" in text[2]
    assert float(text[3]) == 15 and float(text[4]) == 2000


@pytest.mark.parametrize("value, shown", [(None, "<15"), (np.nan, "<15"), (3, "<15"), (14.9, "<15"), (15, "15"), (12345, "12,345")])
def test_dashboard_never_shows_small_counts(value, shown):
    assert dd.format_count(value) == shown


def test_suppressed_is_unknown_not_zero():
    assert dd.to_number(pd.Series(["<15", "", "20"])).isna().tolist() == [True, True, False]


@pytest.mark.parametrize("dtype", ["object", "string"])
def test_grouped_segments_are_counted_with_any_text_type(dtype, monkeypatch):
    """pandas 3 reads text as 'str' and not 'object': the count of grouped NA rows must not depend on it."""
    df = pd.DataFrame({"cod_barrio": ["080190101"] * 4, "mes": ["202301"] * 4, "pais": ["France", "NA", "NA", "Italy"],
                       "visitantes": [20.0, 30.0, 40.0, 50.0]}).astype({"cod_barrio": dtype, "mes": dtype, "pais": dtype})
    monkeypatch.setattr(A, "save", lambda *a, **k: None)
    lookup = pd.DataFrame({"cod_barrio": ["080190101"], "barrio_name": ["el Raval"], "distrito": ["01"], "distrito_name": ["Ciutat Vella"]})
    monkeypatch.setattr(A, "barrio_lookup", lambda: lookup)
    assert A.coverage_table({"T8": df})["rows_grouped_na"].tolist() == [2]


# Metrics ------------------------------------------------------------------------------------------------------
def test_n50():
    assert R.n_share([50, 30, 20]) == 1
    assert R.n_share([40, 30, 30]) == 2
    assert R.n_share(np.ones(10)) == 5


def test_gini_limits():
    assert R.gini(np.ones(73)) == pytest.approx(0, abs=1e-9)
    assert R.gini(np.r_[np.zeros(72), 1]) == pytest.approx(72 / 73)


@pytest.mark.parametrize("a, b, expected", [(0.05, 0.03, "Keeps growing"), (0.01, -0.01, "Stable"), (-0.05, -0.03, "Keeps falling"), (0.05, 0.0, "Mixed")])
def test_growth_rule(a, b, expected):
    assert R.classify_growth(a, b) == expected


def test_trip_share_bounds_contain_the_share():
    t = trips_table()
    t["n_flows_zero"] = 3
    s = R.trip_shares({"trips": t})
    assert ((s["share_low"] <= s["visitor_share"]) & (s["visitor_share"] <= s["share_high"])).all()


# Charter question ---------------------------------------------------------------------------------------------
def test_charter_question_change_and_status():
    table = C.barrio_table({"trips": trips_table()}).set_index("barrio_name")
    assert table.loc["Alpha", "change"] == pytest.approx(0.10)
    assert table.loc["Alpha", "status"] == "Gains ground"
    assert table.loc["Beta", "status"] == "Stable"


def test_charter_question_uses_january_august_only():
    t = trips_table()
    extra = t[t["month"] == 1].assign(month=12, viajes=lambda d: d["viajes"] * np.where(d["origen"] == "Residente", 1, 100))
    both = C.barrio_table({"trips": pd.concat([t, extra])})
    pd.testing.assert_frame_equal(both, C.barrio_table({"trips": t}))


def test_trips_per_day_do_not_depend_on_the_number_of_neighbourhoods():
    table, days = C.origin_table({"trips": trips_table()})
    assert days[2023] == 8
    assert table.set_index("origen").loc["Residente", "per_day_2023"] == pytest.approx((600 + 800) * 2 / 8)


# Robustness and level shifts ------------------------------------------------------------------------------------
@pytest.mark.parametrize("value, step, kind, expected", [(0.5, 0.1, "share", 0.55), (1.30, -0.2, "excess", 1.24), (11, 0.1, "count", 12), (2, -0.1, "count", 1)])
def test_threshold_scaling(value, step, kind, expected):
    assert S.scaled(value, step, kind) == pytest.approx(expected)


def test_robustness_labels():
    same = {s: "Yes" for s in S.STEPS}
    assert S.label(same, "Yes") == "Robust"
    assert S.label({**same, 0.20: "No"}, "Yes") == "Moderate"
    assert S.label({**same, -0.10: "No"}, "Yes") == "Near threshold"


def test_level_shift_is_found_and_stable_series_are_not():
    months = pd.period_range("2023-01", periods=24, freq="M").strftime("%Y%m")
    frame = pd.DataFrame({"steady": 1000.0, "other": 1000.0, "jump": [10.0] * 12 + [30.0] * 12}, index=months)
    found = B.scan(frame, "x").set_index("barrio_name")
    assert found.loc["jump", "shift"] and found.loc["jump", "month"] == "202401"
    assert not found.loc["steady", "shift"]


# Dashboard logic ----------------------------------------------------------------------------------------------
F_ALL = dd.Filters([2023, 2025], 1, 12, dd.VISITOR_ORIGINS, dd.VISITOR_TYPES)


def dashboard_tables():
    t = trips_table()
    return {"trips": t, "city_monthly": t[["mes", "year", "month"]].drop_duplicates()}


def test_visitors_and_residents_summary():
    s = df4.city_summary(dashboard_tables(), F_ALL)
    assert s["share"] == pytest.approx((400 + 600 + 400) / (400 + 600 + 400 + 2 * 1400))


def test_share_change_in_points():
    table, first, last, months = df4.share_change(dashboard_tables(), F_ALL)
    assert (first, last, months) == (2023, 2025, [1, 2])
    assert table.set_index("barrio_name").loc["Alpha", "points"] == pytest.approx(10)


def test_no_data_selection_returns_none():
    assert df4.city_summary(dashboard_tables(), dd.Filters([2025], 9, 12, dd.VISITOR_ORIGINS, dd.VISITOR_TYPES)) is None


def test_unique_visitors_are_a_monthly_mean_never_a_sum():
    city = pd.DataFrame({"mes": ["202301", "202302"], "year": 2023, "month": [1, 2], "origen": "Regional", "tipo_visitante": "Excursionista",
                         "visitantes": [100.0, 300.0]})
    k = dd.kpis({"city_monthly": city}, dd.Filters([2023], 1, 12, ["Regional"], ["Excursionista"]))
    assert k["visitors"] == 200


def test_every_question_has_a_rule_and_a_robustness_spec():
    assert set(S.SPEC) == set(R.THRESHOLDS) == {f"Q{i}" for i in range(1, 21)}
    assert all(R.THRESHOLDS[q]["rule"] for q in R.THRESHOLDS)
