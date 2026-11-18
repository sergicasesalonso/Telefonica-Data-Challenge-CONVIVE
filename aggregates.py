"""CONVIVE - aggregation data generation (WBS 2.2.1, Iteration 3).

Builds the aggregated tables that Iteration 3 needs and that the Iteration 2 statistics (3.1.6) do not cover:
countries (T8), provinces (T7), municipalities of residence (T6), visitor profile (T9), daily visitors per
neighbourhood (T5), data coverage per neighbourhood, and trips between neighbourhoods by year (M1).

It reads the monthly CSV files directly with pandas, so it runs on any computer with pandas and numpy only
(no DuckDB, no Parquet). Memory stays low: one monthly file at a time.

    python aggregates.py tourism            T5 to T9, about 1-2 minutes
    python aggregates.py mobility           M1, one month at a time; resumable (cache in data/processed/tmp/)
    python aggregates.py all

Output: deliverables/iteration3/2.2.1_aggregates/*.csv. Everything under data/ stays on this computer (NDA).

Rules applied (same as 3.1.6, see README):
  - Unique visitors are never summed across days, months or neighbourhoods to get a number of people.
    When values of different neighbourhoods are added, the result is labelled `presences`
    (person x neighbourhood). `max_barrio` is the largest single neighbourhood, a lower bound of the people.
  - Segments inside one place and period (visitor type, grouped NA) are exclusive, so they can be added.
  - Trips and unique visitors are never combined.
  - Any exported value below 15 is written as "<15".
"""

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
TOURISM_DIR = HERE / "data" / "output_limite_legal_turismo"
MOBILITY_DIR = HERE / "data" / "output_limite_legal_mobilidad"
CACHE_DIR = HERE / "data" / "processed" / "tmp" / "i3_m1"          # git-ignored, stays on this computer
OUT_DIR = HERE / "deliverables" / "iteration3" / "2.2.1_aggregates"
LEVELS_CSV = HERE / "deliverables" / "iteration2" / "2.1.1_geographic_levels.csv"

THRESHOLD = 15
BELOW = "<15"
GROUPED = "NA"
MONTHS = [p.strftime("%Y%m") for p in pd.period_range("2023-01", "2025-08", freq="M")]
WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

TOURISM_FILES = {
    "T5": "visitantes_unicos_barrio_date_dt",
    "T6": "visitantes_regionales_barrio_yearmon",
    "T7": "visitantes_nacionales_barrio_yearmon",
    "T8": "visitantes_internacionales_barrio_yearmon",
    "T9": "visitantes_sociodemografico_barrio_yearmon",
}
# Dimension that each origin file adds, and its readable name in the outputs.
ORIGIN_DIMENSION = {"T6": ("municipio_residencia", "municipality"), "T7": ("provincia_residencia", "province"),
                    "T8": ("pais_residencia", "country")}
AGE_LABELS = {"1829": "18-29", "3039": "30-39", "4049": "40-49", "5059": "50-59", "6069": "60-69", "7099": "70+"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def suppress(df, columns):
    """Values below the threshold become '<15' on export. Empty stays empty."""
    out = df.copy()
    for col in columns:
        values = pd.to_numeric(out[col], errors="coerce")
        text = out[col].astype(object)
        out[col] = text.where(~(values < THRESHOLD), BELOW)
    return out


def save(df, name, numeric=()):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = suppress(df, numeric) if numeric else df
    df.to_csv(OUT_DIR / name, index=False, encoding="utf-8")
    print(f"  {name}: {len(df):,} rows, {(OUT_DIR / name).stat().st_size / 1024:,.0f} KB", flush=True)


def read_csv(path, usecols=None):
    """Monthly Smart Steps CSV: ';' separator, every column as text except the measure."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(path, sep=";", dtype=str, usecols=usecols, encoding=encoding, keep_default_na=False)
            break
        except UnicodeDecodeError:
            continue
    for measure in ("visitantes", "viajes", "pernoctaciones"):
        if measure in df.columns:
            df[measure] = pd.to_numeric(df[measure], errors="coerce")
    return df


def barrio_lookup():
    levels = pd.read_csv(LEVELS_CSV, dtype=str)
    b = levels[levels["level"] == "neighbourhood"]
    return b.rename(columns={"code_smart_steps": "cod_barrio", "name": "barrio_name", "code_district": "distrito"})[
        ["cod_barrio", "barrio_name", "distrito", "district_name"]].rename(columns={"district_name": "distrito_name"})


def tourism_months(key):
    paths = [(m, TOURISM_DIR / m / f"{TOURISM_FILES[key]}.csv") for m in MONTHS]
    found = [(m, p) for m, p in paths if p.exists()]
    missing = [m for m, p in paths if not p.exists()]
    if missing:
        print(f"  {key}: {len(missing)} monthly files not found: {missing}", flush=True)
    return found


def load_tourism(key):
    frames = []
    for mes, path in tourism_months(key):
        df = read_csv(path)
        df["mes"] = mes
        frames.append(df)
    if not frames:
        raise FileNotFoundError(f"No CSV for {key} in {TOURISM_DIR}")
    df = pd.concat(frames, ignore_index=True).drop(columns=["año", "cod_municipio", "desc_municipio"], errors="ignore")
    df["year"] = df["mes"].str[:4].astype(int)
    df["month"] = df["mes"].str[4:].astype(int)
    return df


# ---------------------------------------------------------------------------
# T6, T7, T8: where visitors live (Q3 country breakdown, Q11, Q12, Q13)
# ---------------------------------------------------------------------------
def origin_tables(key):
    column, label = ORIGIN_DIMENSION[key]
    df = load_tourism(key)
    if key == "T6":
        df[column] = df[column].where(df[column] != "", GROUPED)
    df = df.rename(columns={column: label})
    df = df[df["cod_barrio"] != GROUPED]

    # City per month: presences (sum over neighbourhoods), largest neighbourhood (lower bound of people).
    city = df.groupby(["mes", "year", "month", "tipo_visitante", label]).agg(
        presences=("visitantes", "sum"), max_barrio=("visitantes", "max"), n_barrios=("cod_barrio", "nunique")).reset_index()
    city["share_of_presences"] = (city["presences"] / city.groupby(["mes", "tipo_visitante"])["presences"].transform("sum")).round(5)
    save(city.sort_values(["mes", "tipo_visitante", "presences"], ascending=[True, True, False]),
         f"{key.lower()}_{label}_city_month.csv", ["presences", "max_barrio"])

    # Neighbourhood per year: mean monthly visitors of each place of residence (visitor types added, exclusive).
    per_month = df.groupby(["year", "mes", "cod_barrio", label])["visitantes"].sum().reset_index()
    barrio = per_month.groupby(["year", "cod_barrio", label]).agg(
        mean_monthly=("visitantes", "mean"), months_present=("mes", "nunique")).reset_index()
    months_in_year = df.groupby("year")["mes"].nunique().rename("months_in_year")
    barrio = barrio.merge(months_in_year, on="year")
    barrio["mean_monthly"] = barrio["mean_monthly"].round(1)
    barrio["share_in_barrio"] = (barrio["mean_monthly"] / barrio.groupby(["year", "cod_barrio"])["mean_monthly"].transform("sum")).round(5)
    barrio = barrio.merge(barrio_lookup(), on="cod_barrio", how="left")
    save(barrio.sort_values(["year", "cod_barrio", "mean_monthly"], ascending=[True, True, False]),
         f"{key.lower()}_{label}_barrio_year.csv", ["mean_monthly"])
    return city, barrio


# ---------------------------------------------------------------------------
# T9: visitor profile (Q14)
# ---------------------------------------------------------------------------
def profile_tables():
    df = load_tourism("T9")
    df = df[df["cod_barrio"] != GROUPED]
    df["edad"] = df["edad"].map(AGE_LABELS).fillna(df["edad"])
    dims = ["origen", "tipo_visitante", "genero", "edad", "nivel_renta"]
    city = df.groupby(["mes", "year", "month"] + dims).agg(
        presences=("visitantes", "sum"), n_barrios=("cod_barrio", "nunique")).reset_index()
    save(city, "t9_profile_city_month.csv", ["presences"])

    rows = []
    for dimension in ("genero", "edad", "nivel_renta"):
        part = df.groupby(["year", "mes", "cod_barrio", "origen", dimension])["visitantes"].sum().reset_index()
        part = part.groupby(["year", "cod_barrio", "origen", dimension])["visitantes"].mean().reset_index()
        part = part.rename(columns={dimension: "category", "visitantes": "mean_monthly"})
        part["dimension"] = dimension
        rows.append(part)
    barrio = pd.concat(rows, ignore_index=True)
    barrio["share_in_barrio"] = (barrio["mean_monthly"]
                                 / barrio.groupby(["year", "cod_barrio", "origen", "dimension"])["mean_monthly"].transform("sum")).round(5)
    barrio["mean_monthly"] = barrio["mean_monthly"].round(1)
    barrio = barrio.merge(barrio_lookup(), on="cod_barrio", how="left")
    save(barrio, "t9_profile_barrio_year.csv", ["mean_monthly"])
    return city, barrio


# ---------------------------------------------------------------------------
# T5: daily visitors per neighbourhood (Q4 and Q9 per neighbourhood, 4.2.3 neighbourhood filter)
# ---------------------------------------------------------------------------
def daily_tables():
    df = load_tourism("T5")
    df = df[df["cod_barrio"] != GROUPED]
    df["date"] = pd.to_datetime(df["date_dt"], errors="coerce")
    df = df.dropna(subset=["date"])
    # Segments of one neighbourhood, day and origin are exclusive (types and the grouped NA type).
    daily = df.groupby(["date", "mes", "cod_barrio", "origen"]).agg(
        visitantes=("visitantes", "sum"), n_segments=("visitantes", "size"),
        has_grouped=("tipo_visitante", lambda s: bool((s == GROUPED).any()))).reset_index()
    daily["weekday_idx"] = daily["date"].dt.dayofweek
    daily["weekday"] = daily["weekday_idx"].map(dict(enumerate(WEEKDAYS)))
    daily["is_weekend"] = daily["weekday_idx"] >= 5
    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    save(daily.sort_values(["date", "cod_barrio", "origen"]), "t5_barrio_daily_by_origin.csv", ["visitantes"])
    return daily


# ---------------------------------------------------------------------------
# Coverage per neighbourhood and dataset (issue I8: neighbourhoods with very few data)
# ---------------------------------------------------------------------------
def coverage_table(frames):
    rows = []
    for key, df in frames.items():
        df = df[df["cod_barrio"] != GROUPED]
        text_dims = [c for c in df.columns if df[c].dtype == object and c not in ("cod_barrio", "mes", "date_dt", "date")]
        is_grouped = np.zeros(len(df), dtype=bool)
        for c in text_dims:
            is_grouped |= (df[c] == GROUPED).to_numpy()
        df = df.assign(is_grouped=is_grouped)
        unit = "date_dt" if key == "T5" else "mes"
        g = df.groupby("cod_barrio")
        part = pd.DataFrame({
            "rows": g.size(),
            "rows_grouped_na": g["is_grouped"].sum(),
            "periods_with_data": g[unit].nunique(),
            "max_value": g["visitantes"].max(),
            "median_row_value": g["visitantes"].median(),
            "rows_below_100": g["visitantes"].apply(lambda s: int((s < 100).sum())),
        }).reset_index()
        part["dataset"] = key
        part["share_grouped_na"] = (part["rows_grouped_na"] / part["rows"]).round(4)
        part["rows_vs_median_barrio"] = (part["rows"] / part["rows"].median()).round(4)
        rows.append(part)
    table = pd.concat(rows, ignore_index=True).merge(barrio_lookup(), on="cod_barrio", how="left")
    save(table.sort_values(["dataset", "rows"]), "coverage_barrio_dataset.csv", ["max_value", "median_row_value"])
    return table


def run_tourism():
    started = time.time()
    frames = {}
    for key in ("T6", "T7", "T8"):
        print(f"{key}...", flush=True)
        origin_tables(key)
        frames[key] = load_tourism(key)
    print("T9...", flush=True)
    profile_tables()
    frames["T9"] = load_tourism("T9")
    print("T5...", flush=True)
    daily_tables()
    frames["T5"] = load_tourism("T5")
    print("Coverage...", flush=True)
    coverage_table(frames)
    print(f"Tourism done in {time.time() - started:.0f}s", flush=True)


# ---------------------------------------------------------------------------
# M1: trips between neighbourhoods by year and origin (Q6 detail, Q15, I8 diagnosis)
# ---------------------------------------------------------------------------
M1_COLUMNS = ["day", "origen", "barrio_origen", "barrio_origen_name", "barrio_destino", "barrio_destino_name", "viajes"]


def m1_path(mes):
    dashed = f"{mes[:4]}-{mes[4:]}"
    return MOBILITY_DIR / dashed / f"movilidad_barrios_{dashed}_origen.csv"


def m1_month(mes, force=False):
    """One month of M1 reduced to (origin neighbourhood, destination neighbourhood, origen, weekday). Cached."""
    out = CACHE_DIR / f"{mes}.csv"
    if out.exists() and not force:
        return pd.read_csv(out, dtype={"barrio_origen": str, "barrio_destino": str})
    path = m1_path(mes)
    if not path.exists():
        print(f"  M1 {mes}: not found", flush=True)
        return None
    parts = []
    names = {}
    for chunk in pd.read_csv(path, sep=",", dtype=str, usecols=M1_COLUMNS, chunksize=1_000_000, keep_default_na=False):
        chunk["viajes"] = pd.to_numeric(chunk["viajes"], errors="coerce")
        chunk = chunk.drop_duplicates()
        for side in ("origen", "destino"):
            names.update(dict(zip(chunk[f"barrio_{side}"], chunk[f"barrio_{side}_name"])))
        chunk["weekday_idx"] = pd.to_datetime(chunk["day"]).dt.dayofweek
        chunk["is_zero"] = chunk["viajes"] == 0
        parts.append(chunk.groupby(["barrio_origen", "barrio_destino", "origen", "weekday_idx"]).agg(
            viajes=("viajes", "sum"), n_flows=("viajes", "size"), n_zero=("is_zero", "sum"), n_days=("day", "nunique")).reset_index())
    df = pd.concat(parts).groupby(["barrio_origen", "barrio_destino", "origen", "weekday_idx"]).agg(
        viajes=("viajes", "sum"), n_flows=("n_flows", "sum"), n_zero=("n_zero", "sum"), n_days=("n_days", "max")).reset_index()
    df["mes"] = mes
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    pd.Series(names).rename_axis("cod_barrio").rename("name").to_csv(CACHE_DIR / f"{mes}_names.csv")
    return df


def run_mobility(months=None, force=False, budget_seconds=None):
    """Process the months not cached yet; stop early after budget_seconds (resumable)."""
    started = time.time()
    for mes in months or MONTHS:
        if budget_seconds and time.time() - started > budget_seconds:
            print("Time budget reached: run the same command again to continue", flush=True)
            return False
        t = time.time()
        cached = (CACHE_DIR / f"{mes}.csv").exists() and not force
        m1_month(mes, force=force)
        if not cached:
            print(f"  M1 {mes}: {time.time() - t:.0f}s", flush=True)
    combine_mobility()
    return True


def combine_mobility():
    frames = [pd.read_csv(p, dtype={"barrio_origen": str, "barrio_destino": str, "mes": str})
              for p in sorted(CACHE_DIR.glob("2*.csv")) if not p.stem.endswith("_names")]
    if len(frames) < len(MONTHS):
        print(f"  M1: only {len(frames)} of {len(MONTHS)} months cached, combining what exists", flush=True)
    df = pd.concat(frames, ignore_index=True)
    df["year"] = df["mes"].str[:4].astype(int)

    # Name check: the code-to-name correspondence of 2.1.1 must hold in every month.
    names = pd.concat([pd.read_csv(p, dtype=str) for p in CACHE_DIR.glob("*_names.csv")]).drop_duplicates()
    lookup = barrio_lookup().set_index("cod_barrio")["barrio_name"]
    names["expected"] = names["cod_barrio"].map(lookup)
    mismatches = names[names["expected"].str.lower() != names["name"].str.lower()]
    save(names.assign(matches=names["expected"].str.lower() == names["name"].str.lower()), "m1_name_check.csv")
    if len(mismatches):
        print(f"  WARNING: {len(mismatches)} code/name mismatches in M1", flush=True)

    od = df.groupby(["year", "barrio_origen", "barrio_destino", "origen"]).agg(
        viajes=("viajes", "sum"), n_flows=("n_flows", "sum"), n_zero=("n_zero", "sum"), months=("mes", "nunique")).reset_index()
    save(od, "m1_od_year_by_origin.csv", ["viajes"])

    out_month = df.groupby(["mes", "barrio_origen", "origen"]).agg(
        viajes=("viajes", "sum"), n_flows=("n_flows", "sum"), n_zero=("n_zero", "sum")).reset_index()
    save(out_month.rename(columns={"barrio_origen": "cod_barrio"}), "m1_outgoing_month_by_origin.csv", ["viajes"])

    # Q15: index by weekday and month, incoming trips per neighbourhood, visitors vs residents.
    df["group"] = np.where(df["origen"] == "Residente", "Residente", "Visitante")
    wk = df.groupby(["year", "barrio_destino", "group", "weekday_idx"]).agg(
        viajes=("viajes", "sum"), days=("n_days", "sum")).reset_index()
    save(wk.rename(columns={"barrio_destino": "cod_barrio"}), "m1_incoming_weekday_by_group.csv", ["viajes"])
    print("M1 combined", flush=True)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="CONVIVE 2.2.1: aggregated tables for Iteration 3")
    parser.add_argument("part", choices=["tourism", "mobility", "combine", "all"])
    parser.add_argument("--months", nargs="*", help="only these months (YYYYMM), mobility only")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--budget", type=float, help="stop the mobility step after this many seconds (resumable)")
    args = parser.parse_args(argv)
    if args.part in ("tourism", "all"):
        run_tourism()
    if args.part in ("mobility", "all"):
        run_mobility(args.months, args.force, args.budget)
    if args.part == "combine":
        combine_mobility()


if __name__ == "__main__":
    main()
