"""CONVIVE - helper functions for the Iteration 1 notebook.

Iteration 1 increment (PWP, SC-04):
  1. Notebook structure
  2. Base neighbourhood map of Barcelona
  3. Data review and cleaning plan (implemented as automatic checks)

The Telefónica Tech (Smart Steps) files are not available yet. Until they are,
`make_synthetic_data()` creates SYNTHETIC files with exactly the same columns
as the official data description ("Smart Steps - Challenge 2026"), so that the
whole pipeline can already run. Numbers in the synthetic files are made up.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).parent
RAW_DIR = HERE / "data" / "raw"          # put the real Telefónica files here (never commit them)
SAMPLE_DIR = HERE / "data" / "sample"    # synthetic files are written here
GEO_CANDIDATES = [HERE / "data" / "geo" / "barris_bcn.geojson",
                  HERE / "data" / "Synthetic" / "geo" / "barris_bcn.geojson"]
GEO_FILE = next((p for p in GEO_CANDIDATES if p.exists()), GEO_CANDIDATES[0])
OUT_DIR = HERE / "outputs"

BCN_MUNICIPIO = "08019"
PERIOD_START, PERIOD_END = "2023-01", "2025-08"   # 32 months
ORIGINS = ["Internacional", "Nacional", "Regional", "Residente"]
VISITOR_ORIGINS = ["Internacional", "Nacional", "Regional"]  # tourism files have no residents
VISITOR_TYPES = ["Turista", "Excursionista"]
WEEKDAYS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
# District names are not in the GeoJSON: official list of the Ajuntament de Barcelona, keyed by DISTRICTE.
DISTRICT_NAMES = {"01": "Ciutat Vella", "02": "Eixample", "03": "Sants-Montjuïc", "04": "Les Corts",
                  "05": "Sarrià-Sant Gervasi", "06": "Gràcia", "07": "Horta-Guinardó", "08": "Nou Barris",
                  "09": "Sant Andreu", "10": "Sant Martí"}

# ---------------------------------------------------------------------------
# Data catalogue, taken from "Smart Steps - Challenge 2026" (Telefónica Tech).
# Column names follow the official description; loaders.COLUMN_RENAMES maps the
# few names that differ in the real files. Mobility file names are the real ones:
# <file>_YYYY-MM_origen.csv in one folder per month.
# ---------------------------------------------------------------------------
SCHEMAS = {
    "M1": {
        "file": "movilidad_barrios",
        "description": "Trips between Barcelona neighbourhoods, per day",
        "columns": ["day", "day_of_the_week", "month", "origen",
                    "municipio_origen", "municipio_origen_name", "barrio_origen", "barrio_origen_name",
                    "municipio_destino", "municipio_destino_name", "barrio_destino", "barrio_destino_name",
                    "viajes"],
    },
    "M2": {
        "file": "movilidad_municipios",
        "description": "Trips between municipalities of the province, per day",
        "columns": ["day", "day_of_the_week", "month", "origen",
                    "municipio_origen", "municipio_origen_name",
                    "municipio_destino", "municipio_destino_name", "viajes"],
    },
    "M3": {
        "file": "movilidad_mun_barrios",
        "description": "Trips between Barcelona neighbourhoods and municipalities, per day",
        "columns": ["day", "day_of_the_week", "month", "origen",
                    "municipio_origen", "municipio_origen_name", "barrio_origen", "barrio_origen_name",
                    "municipio_destino", "municipio_destino_name", "barrio_destino", "barrio_destino_name",
                    "viajes"],
    },
    "T1": {
        "file": "visitantes_unicos_municipio_yearmon",
        "description": "Unique visitors in the municipality, per month",
        "columns": ["año", "mes", "cod_municipio", "desc_municipio", "origen", "tipo_visitante", "visitantes"],
    },
    "T2": {
        "file": "visitantes_unicos_municipio_date_dt",
        "description": "Unique visitors in the municipality, per day",
        "columns": ["año", "mes", "date_dt", "cod_municipio", "desc_municipio", "origen", "tipo_visitante", "visitantes"],
    },
    "T3": {
        "file": "pernoctaciones_semana",
        "description": "Tourists by number of overnight stays, per week (municipality)",
        "columns": ["año", "mes", "semana", "periodo", "cod_municipio", "desc_municipio", "origen",
                    "pernoctaciones", "visitantes"],
    },
    "T4": {
        "file": "visitantes_unicos_barrio_yearmon",
        "description": "Unique visitors per neighbourhood, per month",
        "columns": ["año", "mes", "cod_municipio", "desc_municipio", "cod_barrio", "origen", "tipo_visitante", "visitantes"],
    },
    "T5": {
        "file": "visitantes_unicos_barrio_date_dt",
        "description": "Unique visitors per neighbourhood, per day",
        "columns": ["año", "mes", "date_dt", "cod_municipio", "cod_barrio", "desc_municipio", "origen",
                    "tipo_visitante", "visitantes"],
    },
    "T6": {
        "file": "visitantes_regionales_barrio_yearmon",
        "description": "Regional visitors per neighbourhood and municipality of residence, per month",
        "columns": ["año", "mes", "cod_barrio", "cod_municipio", "desc_municipio",
                    "cod_municipio_residencia", "municipio_residencia", "tipo_visitante", "visitantes"],
    },
    "T7": {
        "file": "visitantes_nacionales_barrio_yearmon",
        "description": "National visitors per neighbourhood and province of residence, per month",
        "columns": ["año", "mes", "cod_municipio", "desc_municipio", "cod_barrio", "provincia_residencia",
                    "tipo_visitante", "visitantes"],
    },
    "T8": {
        "file": "visitantes_internacionales_barrio_yearmon",
        "description": "International visitors per neighbourhood and country of residence, per month",
        "columns": ["año", "mes", "cod_barrio", "cod_municipio", "desc_municipio", "pais_Residencia",
                    "tipo_visitante", "visitantes"],
    },
    "T9": {
        "file": "visitantes_sociodemografico_barrio_yearmon",
        "description": "Visitors per neighbourhood by gender, age and income level, per month",
        "columns": ["año", "mes", "cod_barrio", "cod_municipio", "desc_municipio", "origen", "tipo_visitante",
                    "genero", "edad", "nivel_renta", "visitantes"],
    },
}

# Code columns must be read as text, otherwise "08019" becomes 8019.
TEXT_COLUMNS = ["municipio_origen", "municipio_destino", "barrio_origen", "barrio_destino",
                "cod_municipio", "cod_barrio", "cod_municipio_residencia", "mes"]


def catalogue():
    """Table with the 12 data files we will receive."""
    rows = [{"id": k, "file": v["file"], "description": v["description"], "n_columns": len(v["columns"])}
            for k, v in SCHEMAS.items()]
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Neighbourhood map
# ---------------------------------------------------------------------------
def load_barris():
    """73 Barcelona neighbourhoods (Open Data BCN, CC BY 4.0).

    Two codes per neighbourhood:
      cod_barrio     "8019" + DISTRICTE + BARRI, the Iteration 1 assumption. Used by the synthetic data.
                     BARRI is numbered across the whole city (01 to 73), so this form matches the real
                     data only in district 01.
      cod_barrio_ss  the real Smart Steps code: "08019" + DISTRICTE + position of the neighbourhood inside
                     its district (el Bon Pastor = 080190903). Verified against the names in M1 (WBS 2.1.1).
    """
    geo = json.loads(GEO_FILE.read_text(encoding="utf-8"))
    order = sorted(geo["features"], key=lambda f: (f["properties"]["DISTRICTE"], f["properties"]["BARRI"]))
    position = {}
    for f in order:
        p = f["properties"]
        position[p["DISTRICTE"]] = position.get(p["DISTRICTE"], 0) + 1
        p["cod_barrio"] = "8019" + p["DISTRICTE"] + p["BARRI"]
        p["cod_barrio_ss"] = "08019" + p["DISTRICTE"] + f"{position[p['DISTRICTE']]:02d}"
        p["distrito_name"] = DISTRICT_NAMES.get(p["DISTRICTE"], "")
    table = pd.DataFrame([f["properties"] for f in geo["features"]])
    table = table.rename(columns={"NOM": "barrio_name", "DISTRICTE": "distrito"})
    columns = ["cod_barrio", "barrio_name", "distrito", "cod_barrio_ss", "distrito_name"]
    return geo, table[columns].sort_values("cod_barrio").reset_index(drop=True)


def map_center(geo):
    """Centre of the neighbourhoods' bounding box, for the Plotly map view."""
    points = np.array([point for f in geo["features"] for ring in _rings(f["geometry"]) for point in ring])
    return {"lon": float((points[:, 0].min() + points[:, 0].max()) / 2), "lat": float((points[:, 1].min() + points[:, 1].max()) / 2)}


def _rings(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    return [poly[0] for poly in geometry["coordinates"]]


def plot_map(geo, values=None, ax=None, title="", cmap="YlOrRd", label=None, legend_label="",
             norm=None, log=False, categories=None, colorbar=True):
    """Draw the neighbourhoods.

    values:     optional {cod_barrio: number} dict (choropleth)
    norm / log: colour scale (e.g. TwoSlopeNorm for values around 1, or log=True)
    categories: optional {cod_barrio: colour} dict (categorical map, e.g. clusters)
    """
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    from matplotlib import cm, colors

    if ax is None:
        _, ax = plt.subplots(figsize=(8, 8))
    polys, codes = [], []
    for f in geo["features"]:
        for ring in _rings(f["geometry"]):
            polys.append(ring)
            codes.append(f["properties"]["cod_barrio"])
    if categories is not None:
        facecolors = [categories.get(c, "lightgrey") for c in codes]
    elif values is None:
        district = [int(c[4:6]) for c in codes]
        facecolors = plt.get_cmap("tab10")([(d - 1) % 10 for d in district])
    else:
        vals = np.array([values.get(c, np.nan) for c in codes], dtype=float)
        if norm is None:
            vmin, vmax = np.nanmin(vals), np.nanmax(vals)
            norm = colors.LogNorm(vmin=vmin, vmax=vmax) if log else colors.Normalize(vmin=vmin, vmax=vmax)
        facecolors = [plt.get_cmap(cmap)(norm(v)) if not np.isnan(v) else "lightgrey" for v in vals]
        if colorbar:
            sm = cm.ScalarMappable(norm=norm, cmap=cmap)
            ax.figure.colorbar(sm, ax=ax, shrink=0.6, label=legend_label)
    ax.add_collection(PolyCollection(polys, facecolors=facecolors, edgecolors="white", linewidths=0.6))
    if label:
        for f in geo["features"]:
            if f["properties"]["cod_barrio"] in label:
                ring = np.array(_rings(f["geometry"])[0])
                x, y = ring.mean(axis=0)
                ax.text(x, y, f["properties"]["NOM"], fontsize=7, ha="center")
    ax.autoscale()
    ax.set_aspect(1 / np.cos(np.radians(41.39)))  # keep Barcelona's real proportions
    ax.set_axis_off()
    ax.set_title(title)
    return ax


def interactive_map(geo, table, value_col=None, path=None):
    """Interactive HTML map (folium) with the name of each neighbourhood on hover."""
    import folium

    m = folium.Map(location=[41.395, 2.17], zoom_start=12, tiles="OpenStreetMap")
    if value_col is not None:
        folium.Choropleth(geo_data=geo, data=table, columns=["cod_barrio", value_col],
                          key_on="feature.properties.cod_barrio", fill_color="YlOrRd",
                          fill_opacity=0.7, line_opacity=0.3, legend_name=value_col).add_to(m)
    folium.GeoJson(geo, style_function=lambda f: {"fillOpacity": 0, "color": "#555", "weight": 0.8},
                   tooltip=folium.GeoJsonTooltip(fields=["NOM", "cod_barrio"],
                                                 aliases=["Barrio", "Code"])).add_to(m)
    if path:
        m.save(str(path))
    return m


# ---------------------------------------------------------------------------
# Synthetic data (only until the real files arrive): see synthetic.py
# ---------------------------------------------------------------------------
def _months():
    return pd.period_range(PERIOD_START, PERIOD_END, freq="M")


def make_synthetic_data():
    import synthetic
    return synthetic.make_all()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _find(folder, name):
    for ext in (".csv", ".parquet", ".csv.gz", ".txt"):
        path = folder / f"{name}{ext}"
        if path.exists():
            return path
    return None


def load(key, mode="auto", months=None, stage="raw"):
    """Load one file by its id (M1..T9).

    mode="real":      real monthly files through loaders.py (Parquet). `months` limits the months and
                      `stage` picks 'raw' or 'clean'. M2 and M3 need `months`: the full period does not fit in
                      pandas (use loaders.load_mobility(key, lazy=True) for those).
    mode="synthetic": synthetic file in data/sample/ (Iteration 1 behaviour).
    mode="auto":      a single file in data/raw/ if it exists, otherwise the synthetic one (Iteration 1 behaviour).
    Returns (dataframe, source) or (None, "missing").
    """
    if mode == "real":
        import loaders
        if key in ("M2", "M3") and months is None:
            raise ValueError(f"{key} is too large for pandas: pass months=[...] or use loaders.load_mobility('{key}', lazy=True)")
        reader = loaders.load_mobility if key in loaders.MOBILITY_KEYS else loaders.load_tourism
        try:
            return reader(key, months=months, stage=stage), "real"
        except FileNotFoundError:
            return None, "missing"
    name = SCHEMAS[key]["file"]
    path = _find(RAW_DIR, name) if mode == "auto" else None
    source = "real"
    if path is None and mode in ("auto", "synthetic"):
        path, source = _find(SAMPLE_DIR, name), "synthetic"
    if path is None:
        return None, "missing"
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
        for c in TEXT_COLUMNS:
            if c in df.columns:
                df[c] = df[c].astype(str)
    else:
        with open(path, encoding="utf-8") as fh:
            sep = ";" if fh.readline().count(";") > 0 else ","
        dtypes = {c: str for c in TEXT_COLUMNS}
        df = pd.read_csv(path, sep=sep, dtype=dtypes)
    return df, source


# ---------------------------------------------------------------------------
# Data review (the cleaning plan, as automatic checks)
# ---------------------------------------------------------------------------
def review(df, key, barris=None):
    """Run the data review checks on one file. Returns a list of (check, result, ok)."""
    expected = SCHEMAS[key]["columns"]
    out = []
    missing = [c for c in expected if c not in df.columns]
    extra = [c for c in df.columns if c not in expected and c != "source_month"]
    out.append(("Columns match the official description", f"missing={missing or '-'}, extra={extra or '-'}",
                not missing))
    out.append(("Rows", f"{len(df):,}", len(df) > 0))
    dup = int(df.drop(columns="source_month", errors="ignore").duplicated().sum())
    out.append(("Duplicated rows", f"{dup:,}", dup == 0))
    nulls = df.drop(columns=[measure_col for measure_col in ("viajes", "visitantes") if measure_col in df.columns]).isna().sum()
    nulls = nulls[nulls > 0]
    out.append(("Empty values in other columns",
                ", ".join(f"{c}: {n:,}" for c, n in nulls.items()) or "none", True))
    grouped = {c: int((df[c] == "NA").sum()) for c in df.columns
               if not pd.api.types.is_numeric_dtype(df[c]) and (df[c] == "NA").any()}
    if grouped:
        out.append(("Grouped 'NA' values (segments < 15 people, kept as NA)",
                    ", ".join(f"{c}: {n:,}" for c, n in grouped.items()), True))
    measure = "viajes" if "viajes" in df.columns else "visitantes"
    if measure in df.columns and df[measure].isna().any():
        out.append((f"Share of {measure} = NA (anonymised, < 15 people)", f"{df[measure].isna().mean():.1%}", True))
    if measure in df.columns:
        zeros = (df[measure] == 0).mean()
        out.append((f"Share of {measure} = 0 (privacy threshold, NOT 'no mobility')", f"{zeros:.1%}", True))
        neg = int((df[measure] < 0).sum())
        out.append((f"Negative {measure}", f"{neg}", neg == 0))
    if "origen" in df.columns:
        values = sorted(df["origen"].dropna().unique())
        unknown = [v for v in values if v not in ORIGINS + ["NA"]]
        out.append(("Values of 'origen'", ", ".join(values), not unknown))
    if "tipo_visitante" in df.columns:
        values = sorted(df["tipo_visitante"].dropna().unique())
        out.append(("Values of 'tipo_visitante'", ", ".join(values),
                    all(v in VISITOR_TYPES + ["NA"] for v in values)))
    if "mes" in df.columns:
        months = sorted(df["mes"].astype(str).unique())
        expected_n = len(_months())
        out.append(("Period covered", f"{months[0]} to {months[-1]} ({len(months)} of {expected_n} months)",
                    len(months) == expected_n))
    for col in ("date_dt", "day"):
        if col in df.columns:
            days = pd.to_datetime(df[col], errors="coerce").dropna()   # "NA" = grouped segment, not a day
            full = pd.date_range(days.min(), days.max())
            gaps = full.difference(days.unique())
            out.append(("Days covered", f"{days.min():%Y-%m-%d} to {days.max():%Y-%m-%d}, {days.nunique()} days, "
                        f"missing: {', '.join(f'{d:%Y-%m-%d}' for d in gaps) or 'none'}", len(gaps) == 0))
    if barris is not None:
        out.extend(check_barrio_codes(df, barris))
    return out


def check_barrio_codes(df, barris):
    """Do the neighbourhood codes in the data match the 73 neighbourhoods of the map?"""
    known = set(barris["cod_barrio"])
    if "cod_barrio_ss" in barris.columns:
        known |= set(barris["cod_barrio_ss"])
    out = []
    for col in ("cod_barrio", "barrio_origen", "barrio_destino"):
        if col in df.columns:
            codes = set(df[col].dropna().astype(str)) - {"-", "NA"}
            unknown = sorted(codes - known)
            out.append((f"'{col}' codes found on the map", f"{len(codes & known)} of {len(codes)} "
                        f"(unknown: {unknown[:5] or '-'})", not unknown))
    return out


def review_table(results):
    return pd.DataFrame(results, columns=["check", "result", "ok"]).assign(
        ok=lambda d: d["ok"].map({True: "OK", False: "REVIEW"}))
