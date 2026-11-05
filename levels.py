"""CONVIVE - geographic and temporal aggregation levels (WBS 2.1.1 and 2.1.2)."""

import re
import unicodedata

import pandas as pd

import convive as cv
import loaders as L

BCN = "08019"
WEEKDAY_ORDER = cv.WEEKDAYS
WEEKEND = {"Sábado", "Domingo"}
JAN_AUG = [f"{m:02d}" for m in range(1, 9)]


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------
def normalise_name(text):
    """Compare names ignoring accents, case and punctuation."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


_WEEKDAY_LOOKUP = {normalise_name(d): d for d in WEEKDAY_ORDER}


def normalise_weekday(name):
    """'SABADO', 'sábado' and 'Sábado' all become 'Sábado'. Unknown names become None."""
    return _WEEKDAY_LOOKUP.get(normalise_name(name))


# ---------------------------------------------------------------------------
# WBS 2.1.1 Geographic levels
# ---------------------------------------------------------------------------
def _codes(con, key, column):
    return {r[0] for r in con.execute(f'SELECT DISTINCT "{column}" FROM {L.parquet_glob(key)}').fetchall()}


def smart_steps_names(con):
    """Code -> name pairs found in M1 and M3 (T files carry codes only)."""
    pairs = []
    for key in ("M1", "M3"):
        for side in ("origen", "destino"):
            pairs.append(f'SELECT DISTINCT barrio_{side} AS code, barrio_{side}_name AS name FROM {L.parquet_glob(key)}')
    return con.execute(" UNION ".join(pairs)).df()


def build_geographic_levels(con):
    """Returns (levels table, report dict)."""
    _, barris = cv.load_barris()
    names = smart_steps_names(con)
    real = names[~names["code"].isin(["-", "NA"])].copy()
    ambiguous = real[real.duplicated("code", keep=False)]
    real = real.drop_duplicates("code")

    # Independent checks: rule (district + position inside district) and neighbourhood names.
    table = barris.merge(real, how="outer", left_on="cod_barrio_ss", right_on="code", indicator=True)
    table["same_name"] = table["barrio_name"].map(normalise_name, na_action="ignore") == table["name"].map(
        normalise_name, na_action="ignore")

    sources = {"M1 origin": ("M1", "barrio_origen"), "M1 destination": ("M1", "barrio_destino"),
               "M3 origin": ("M3", "barrio_origen"), "M3 destination": ("M3", "barrio_destino"),
               "T4": ("T4", "cod_barrio"), "T5": ("T5", "cod_barrio"), "T6": ("T6", "cod_barrio"),
               "T7": ("T7", "cod_barrio"), "T8": ("T8", "cod_barrio"), "T9": ("T9", "cod_barrio")}
    known = set(barris["cod_barrio_ss"])
    legacy = set("0" + barris["cod_barrio"])
    coverage = []
    found = {}
    for label, (key, column) in sources.items():
        codes = _codes(con, key, column)
        found[label] = codes
        real_codes = codes - {"-", "NA"}
        coverage.append({"source": label, "distinct codes": len(real_codes),
                         "match the map": len(real_codes & known),
                         "in data, not on map": ", ".join(sorted(real_codes - known)) or "none",
                         "on map, not in data": ", ".join(sorted(known - real_codes)) or "none",
                         "placeholders": ", ".join(sorted(codes & {"-", "NA"})) or "none",
                         "matches with Iteration 1 rule": len(real_codes & legacy)})

    rows = [{"level": "municipality", "code_smart_steps": BCN, "code_map_iteration1": "", "code_district": "",
             "name": "Barcelona", "district_name": "", "parent_code": "08 (province)",
             "in_M1": True, "in_M3": True, "in_T4": True, "in_T5": True, "match_method": "direct"}]
    for code, name in sorted(cv.DISTRICT_NAMES.items()):
        rows.append({"level": "district", "code_smart_steps": f"{BCN}{code}", "code_map_iteration1": "", "code_district": code,
                     "name": name, "district_name": name, "parent_code": BCN,
                     "in_M1": True, "in_M3": True, "in_T4": True, "in_T5": True, "match_method": "first 2 digits after 08019"})
    for r in table.sort_values("cod_barrio_ss").itertuples():
        rows.append({"level": "neighbourhood", "code_smart_steps": r.cod_barrio_ss, "code_map_iteration1": r.cod_barrio,
                     "code_district": r.distrito, "name": r.barrio_name, "district_name": r.distrito_name,
                     "parent_code": f"{BCN}{r.distrito}",
                     "in_M1": r.cod_barrio_ss in found["M1 destination"], "in_M3": r.cod_barrio_ss in found["M3 destination"],
                     "in_T4": r.cod_barrio_ss in found["T4"], "in_T5": r.cod_barrio_ss in found["T5"],
                     "match_method": "name and district + position rule" if r.same_name else "REVIEW: names differ"})
    levels = pd.DataFrame(rows)

    municipalities = con.execute(f"""
        SELECT code, min(name) AS name, count(DISTINCT name) AS names FROM (
            SELECT DISTINCT municipio_origen AS code, municipio_origen_name AS name FROM {L.parquet_glob('M2')}
            UNION SELECT DISTINCT municipio_destino, municipio_destino_name FROM {L.parquet_glob('M2')}
        ) GROUP BY 1 ORDER BY 1""").df()
    report = {"coverage": pd.DataFrame(coverage),
              "n_map": len(barris),
              "name_matches": int(table["same_name"].sum()),
              "rule_only_in_data": table[table["_merge"] == "right_only"]["code"].tolist(),
              "rule_only_on_map": table[table["_merge"] == "left_only"]["cod_barrio_ss"].tolist(),
              "name_mismatches": table[(table["_merge"] == "both") & ~table["same_name"]][["cod_barrio_ss", "barrio_name", "name"]],
              "ambiguous_codes": sorted(ambiguous["code"].unique().tolist()),
              "legacy_matches": len(set(real["code"]) & legacy),
              "n_municipalities": len(municipalities),
              "municipalities_multiple_names": municipalities[municipalities["names"] > 1]["code"].tolist(),
              "districts_in_data": sorted({c[5:7] for c in known})}
    return levels, report


def barrio_lookup():
    """cod_barrio_ss -> name, district, district name, Iteration 1 code (for cleaning and statistics)."""
    _, barris = cv.load_barris()
    return barris.rename(columns={"cod_barrio": "cod_barrio_map", "cod_barrio_ss": "cod_barrio"})[
        ["cod_barrio", "cod_barrio_map", "barrio_name", "distrito", "distrito_name"]]


# ---------------------------------------------------------------------------
# WBS 2.1.2 Temporal levels
# ---------------------------------------------------------------------------
DAILY = {"M1": "day", "M2": "day", "M3": "day", "T2": "date_dt", "T5": "date_dt"}
MONTHLY = ["T1", "T4", "T6", "T7", "T8", "T9"]


def calendar_table():
    """One row per calendar day of the challenge period with every temporal level."""
    days = pd.date_range("2023-01-01", "2025-08-31")
    iso = days.isocalendar()
    return pd.DataFrame({"date": days, "year": days.year, "month": days.month, "mes": days.strftime("%Y%m"),
                         "iso_year": iso["year"].to_numpy(), "iso_week": iso["week"].to_numpy(),
                         "weekday_idx": days.dayofweek, "weekday": [WEEKDAY_ORDER[d] for d in days.dayofweek],
                         "is_weekend": days.dayofweek >= 5, "jan_aug": days.month <= 8})


def missing_days(con, key):
    column = DAILY[key]
    have = {r[0] for r in con.execute(
        f"SELECT DISTINCT TRY_CAST(\"{column}\" AS DATE) FROM {L.parquet_glob(key)} WHERE TRY_CAST(\"{column}\" AS DATE) IS NOT NULL").fetchall()}
    return [d for d in calendar_table()["date"].dt.date if d not in have]


def incomplete_months(days):
    """{mes: number of missing days} from a list of missing dates."""
    out = {}
    for day in days:
        out[day.strftime("%Y%m")] = out.get(day.strftime("%Y%m"), 0) + 1
    return out


def temporal_report(con):
    rows, missing_all = [], {}
    for key in L.ALL_KEYS:
        source = L.parquet_glob(key)
        if key in DAILY:
            column = DAILY[key]
            lo, hi, n = con.execute(f"""SELECT min(d), max(d), count(DISTINCT d) FROM
                (SELECT TRY_CAST("{column}" AS DATE) d FROM {source}) WHERE d IS NOT NULL""").fetchone()
            gaps = missing_days(con, key)
            missing_all[key] = gaps
            rows.append({"dataset": key, "finest grain": "day", "date column": column, "first": str(lo), "last": str(hi),
                         "periods found": f"{n} of 974 days", "missing": ", ".join(str(g) for g in gaps) or "none"})
        elif key == "T3":
            lo, hi, n = con.execute(f"SELECT min(periodo), max(periodo), count(DISTINCT periodo) FROM {source}").fetchone()
            rows.append({"dataset": key, "finest grain": "week (Mon to Sun)", "date column": "periodo",
                         "first": lo.split(" | ")[0], "last": hi.split(" | ")[1], "periods found": f"{n} weeks",
                         "missing": "see the T3 notes"})
        else:
            lo, hi, n = con.execute(f"SELECT min(mes), max(mes), count(DISTINCT mes) FROM {source}").fetchone()
            rows.append({"dataset": key, "finest grain": "month", "date column": "mes", "first": lo, "last": hi,
                         "periods found": f"{n} of 32 months", "missing": "none" if n == 32 else "see inventory"})
    coverage = pd.DataFrame(rows)

    # Weekday labels: compare with the real calendar.
    weekday_rows = []
    for key in ("M1", "M2", "M3"):
        for label, n, bad in con.execute(f"""
            SELECT day_of_the_week, count(*), sum((strftime(TRY_CAST(day AS DATE), '%w') <>
                CASE day_of_the_week WHEN 'Domingo' THEN '0' WHEN 'Lunes' THEN '1' WHEN 'Martes' THEN '2'
                     WHEN 'Miércoles' THEN '3' WHEN 'Jueves' THEN '4' WHEN 'Viernes' THEN '5' WHEN 'Sábado' THEN '6' END)::INT)
            FROM {L.parquet_glob(key)} GROUP BY 1""").fetchall():
            weekday_rows.append({"dataset": key, "label in file": label, "normalised": normalise_weekday(label),
                                 "rows": n, "rows on the wrong calendar day": bad})
    weekdays = pd.DataFrame(weekday_rows).sort_values(["dataset", "normalised"])

    t3 = con.execute(f"SELECT DISTINCT semana, periodo, mes FROM {L.parquet_glob('T3')}").df()
    t3["start"] = pd.to_datetime(t3["periodo"].str.split(" | ", regex=False).str[0])
    t3["end"] = pd.to_datetime(t3["periodo"].str.split(" | ", regex=False).str[1])
    t3["iso_week"] = t3["start"].dt.isocalendar()["week"].astype(int)
    counts = con.execute(f"SELECT periodo, origen, count(DISTINCT pernoctaciones) AS n FROM {L.parquet_glob('T3')} GROUP BY 1, 2").df()
    t3_notes = {"weeks": t3["periodo"].nunique(),
                "first_monday": t3["start"].min().date(), "last_sunday": t3["end"].max().date(),
                "all_monday_sunday": bool(((t3["start"].dt.dayofweek == 0) & (t3["end"].dt.dayofweek == 6)).all()),
                "semana_equals_iso": bool((t3["semana"].astype(int) == t3["iso_week"]).all()),
                "weeks_in_two_months": sorted(t3.groupby("periodo")["mes"].nunique().loc[lambda s: s > 1].index),
                "partial_weeks": sorted(counts.loc[counts["n"] < 7, "periodo"].unique()),
                "days_before_first_week": (t3["start"].min() - pd.Timestamp("2023-01-01")).days}
    # A week assigned to one month by its start or by its end?
    t3["by_start"] = t3["start"].dt.strftime("%Y%m") == t3["mes"]
    t3["by_end"] = t3["end"].dt.strftime("%Y%m") == t3["mes"]
    t3_notes["month_by_start"] = int(t3["by_start"].sum())
    t3_notes["month_by_end"] = int(t3["by_end"].sum())
    t3_notes["rows_distinct"] = len(t3)

    calendar = calendar_table()
    gaps = sorted({d for days in missing_all.values() for d in days})
    available = calendar[~calendar["date"].dt.date.isin(gaps)]
    periods = (calendar[calendar["jan_aug"]].groupby("year").size().rename("calendar days Jan-Aug").to_frame()
               .join(available[available["jan_aug"]].groupby("year").size().rename("days with data"))
               .reset_index())
    same_gaps = len({tuple(v) for v in missing_all.values()}) == 1
    return {"coverage": coverage, "weekdays": weekdays, "t3": t3_notes, "periods": periods, "missing": gaps,
            "incomplete": incomplete_months(gaps), "same_gaps": same_gaps, "calendar": calendar}


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
def write_geographic(levels, report):
    import quality as q
    q.DELIVERABLES.mkdir(parents=True, exist_ok=True)
    levels.to_csv(q.DELIVERABLES / "2.1.1_geographic_levels.csv", index=False, encoding="utf-8")
    counts = levels["level"].value_counts()
    mismatches = report["name_mismatches"]
    return q.write_md("2.1.1_geographic_levels.md", f"""
# 2.1.1 Geographic aggregation definition

CONVIVE · Team 102_A · Iteration 2. Generated by `levels.build_geographic_levels()`. The table is in `2.1.1_geographic_levels.csv`.

## Levels

| Level | Units in the table | Code | Datasets |
|---|---|---|---|
| Neighbourhood | {counts['neighbourhood']} | 9 digits: `08019` + district (2) + position inside the district (2), e.g. `080190903` | M1, M3 (Barcelona side), T4 to T9 |
| District | {counts['district']} | `08019` + district (2), the two digits after the municipality code | Derived from the neighbourhood code |
| Municipality | {counts['municipality']} (Barcelona) | 5 digits with a leading zero: `08019` | T1, T2, T3 and the municipality columns of M1 to M3 |

M2 and M3 also cover other municipalities of the province ({report['n_municipalities']} codes in total in M2). These are outside the neighbourhood map.

## Main finding: the Iteration 1 code rule was wrong

Iteration 1 assumed the code was `8019` + `DISTRICTE` + `BARRI` from the GeoJSON. The two examples in the official description (`80190101`, `80190103`) fit this rule, but both are in district 01.

- `BARRI` in the GeoJSON is numbered across the **whole city** (01 to 73), while Smart Steps numbers neighbourhoods **inside each district**.
- The real codes have **9 digits**, with a leading zero, while the description shows 8.
- With the old rule, only **{report['legacy_matches']} of {report['n_map']}** codes match. This triggers R1 in the Follow-up Register.

**Correct rule:** `08019` + `DISTRICTE` + position of `BARRI` inside its district. It is now in `convive.load_barris()` as `cod_barrio_ss`. The synthetic mode of Iteration 1 keeps its old `cod_barrio`.

Two independent checks support it:
- By rule: codes found only in the data: {report['rule_only_in_data'] or 'none'}; only on the map: {report['rule_only_on_map'] or 'none'}.
- By name: **{report['name_matches']} of {report['n_map']}** names in M1 and M3 equal the GeoJSON names, ignoring accents and case. Differences: {'none' if mismatches.empty else mismatches.to_dict('records')}. Codes with more than one name: {report['ambiguous_codes'] or 'none'}.

## Unmatched codes, in each direction

{q.md_table(report['coverage'])}

- `NA` is the grouped segment (fewer than 15 people) and `-` is a municipality outside Barcelona in M3. Neither is a neighbourhood. They stay unassigned and are never distributed among neighbourhoods.
- Municipality codes with more than one name in M2: {report['municipalities_multiple_names'] or 'none'}.

## Aggregation rules

- **Trips (M1 to M3)** can be added across days and neighbourhoods, but the published zeros (fewer than 15 trips) add nothing, so totals are lower estimates.
- **Unique visitors (T1 to T9)** are not additive across days or neighbourhoods. District values cannot be obtained by summing T4 or T5, and city totals come from T1 and T2. A district value in this project is therefore only a ranking indicator or a mean of neighbourhoods, and is labelled that way.
- District names are not in the GeoJSON. They come from the official list of the Ajuntament de Barcelona (`convive.DISTRICT_NAMES`).
""")


def write_temporal(report):
    import quality as q
    t3 = report["t3"]
    incomplete = pd.DataFrame([{"month": m, "missing days": n} for m, n in report["incomplete"].items()])
    return q.write_md("2.1.2_temporal_levels.md", f"""
# 2.1.2 Temporal aggregation definition

CONVIVE · Team 102_A · Iteration 2. Generated by `levels.temporal_report()`. The calendar logic is in `levels.calendar_table()`.

## Levels

| Level | Definition | Column in the clean data |
|---|---|---|
| Day | Calendar date | `date` |
| Weekday / weekend | Monday to Friday / Saturday and Sunday | `weekday`, `weekday_idx` (0 = Monday), `is_weekend` |
| ISO week | Monday to Sunday, ISO 8601 number | `iso_year`, `iso_week` |
| Month | `YYYYMM` | `mes` or `source_month`, `month_num` |
| Year | Calendar year | `year` |
| Equivalent period | January to August of 2023, 2024 and 2025 | `month_num` from 1 to 8 |

## Real granularity per dataset

{q.md_table(report['coverage'])}

All daily files miss the same days: {'yes' if report['same_gaps'] else 'NO, see the table'}.

## Weekday names

Names are normalised with `levels.normalise_weekday()`, which ignores accents and case. Clean columns use one spelling and are derived from the date.

{q.md_table(report['weekdays'])}

## Incomplete months

A month is incomplete if a daily file misses at least one of its days. It keeps its data and gets `incomplete_month = true`. Nothing is imputed.

{q.md_table(incomplete)}

Monthly files (T1, T4, T6 to T9) cannot show whether these days were left out of their counts, so their values for these months are flagged as well.

## Equivalent comparison periods

{q.md_table(report['periods'])}

- 2024 is a leap year, so its January to August has one more calendar day. Monthly unique visitors are compared as a mean per month, so the extra day is not added to any total. Daily comparisons use means per day.
- 2025 stops in August, so full-year comparisons with 2025 are not possible.
- Unique visitors are not summed across months. A longer period is shown as a monthly average.

## T3 weekly data

- {t3['weeks']} weeks from {t3['first_monday']} to {t3['last_sunday']}. All run Monday to Sunday: {t3['all_monday_sunday']}. `semana` equals the ISO week number: {t3['semana_equals_iso']}.
- {t3['days_before_first_week']} day(s) of the period fall before the first week (1 January 2023 is a Sunday).
- Each week × month pair: {t3['rows_distinct']}. The month matches the week's start in {t3['month_by_start']} and its end in {t3['month_by_end']}.
- Weeks under two months: {t3['weeks_in_two_months'] or 'none'}. Flagged and excluded from the T3 distribution.
- Weeks with fewer than 7 night values: {t3['partial_weeks'] or 'none'}. Flagged.
""")
