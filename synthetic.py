"""CONVIVE - synthetic data generator (ONLY until the real Telefónica files arrive).

Creates files with exactly the columns of the official description
("Smart Steps - Challenge 2026") so the whole pipeline can be built and tested.

The data are made up, but they are generated from an explicit model, so the
methods in the notebook can be *validated*: we know what they should find.
  - neighbourhood attractiveness, origin mix and seasonality per neighbourhood
  - weekday rhythms that differ by visitor origin
  - a "diffusion" trend: visitors grow faster in some neighbourhoods outside the old town
  - planted events (approximate dates) that a good method must detect
  - planted data-quality problems that the data review must detect
  - trips between neighbourhoods from a gravity model with a known distance decay

Nothing here describes the real situation in Barcelona.
"""

import json

import numpy as np
import pandas as pd

import convive as cv

SEED = 2026
DAYS = pd.date_range("2023-01-01", "2025-08-31", freq="D")
M1_WEEKS = {"winter": ("2025-02-10", "2025-02-16"), "summer": ("2025-08-04", "2025-08-10")}

# Neighbourhood attractiveness for visitors (unit-less). Defaults: see DEFAULT_BY_DISTRICT
ATTRACTION = {
    "80190102": 6.0,   # el Barri Gòtic
    "80190207": 5.0,   # la Dreta de l'Eixample
    "80190206": 4.5,   # la Sagrada Família
    "80190104": 4.5,   # Sant Pere, Santa Caterina i la Ribera
    "80190101": 4.0,   # el Raval
    "80190103": 4.0,   # la Barceloneta
    "80190630": 2.5,   # la Salut
    "80190631": 2.5,   # la Vila de Gràcia
    "80191067": 2.5,   # la Vila Olímpica del Poblenou
    "80190208": 2.0,   # l'Antiga Esquerra de l'Eixample
    "80190311": 2.0,   # el Poble-sec
    "80190210": 1.5,   # Sant Antoni
    "80191068": 1.5,   # el Poblenou
    "80191069": 1.5,   # Diagonal Mar i el Front Marítim del Poblenou
    "80190318": 1.2,   # Sants
    "80190205": 0.9,   # el Fort Pienc
    "80190419": 0.9,   # les Corts
    "80190522": 0.8,   # Vallvidrera, el Tibidabo i les Planes
    "80191066": 0.8,   # el Parc i la Llacuna del Poblenou
    "80190526": 0.7,   # Sant Gervasi - Galvany
    "80190737": 0.6,   # el Carmel
    "80190421": 0.6,   # Pedralbes
}
BEACH = ["80190103", "80191067", "80191068", "80191069"]
BUSINESS = ["80190207", "80191066", "80190419", "80191069"]
# Faster growth outside the old town (the "diffusion" the analysis should find)
GROWTH_INTL = {"80191068": 0.24, "80191066": 0.26, "80190210": 0.20, "80190311": 0.18,
               "80190631": 0.15, "80190205": 0.15, "80191071": 0.18, "80191069": 0.12,
               "80190102": -0.05, "80190103": -0.02, "80190101": -0.01, "80190104": 0.00, "80190206": 0.01}

ORIGIN_BASE = {"Internacional": 4200, "Nacional": 1600, "Regional": 3300}
TOURIST_SHARE = {"Internacional": 0.78, "Nacional": 0.55, "Regional": 0.0}
WEEKDAY = {  # Monday ... Sunday
    "Internacional": [0.92, 0.90, 0.92, 0.97, 1.05, 1.15, 1.09],
    "Nacional": [0.80, 0.78, 0.80, 0.88, 1.20, 1.40, 1.14],
    "Regional": [0.85, 0.85, 0.88, 0.92, 1.05, 1.35, 1.10],
    "Residente": [1.08, 1.10, 1.10, 1.10, 1.07, 0.80, 0.75],
}
# Days a person is present in a neighbourhood per month: converts daily into monthly unique visitors
TURNOVER = {("Internacional", "Turista"): 4.0, ("Internacional", "Excursionista"): 1.2,
            ("Nacional", "Turista"): 3.0, ("Nacional", "Excursionista"): 1.4,
            ("Regional", "Excursionista"): 2.3}
OVERLAP_DAY, OVERLAP_MONTH = 1.9, 1.7   # people visit several neighbourhoods

# Planted events: (name, start, end, neighbourhoods or None = whole city, {origin: multiplier})
EVENTS = [
    ("Mobile World Congress 2023", "2023-02-27", "2023-03-02", None, {"Internacional": 1.35}),
    ("Mobile World Congress 2024", "2024-02-26", "2024-02-29", None, {"Internacional": 1.35}),
    ("Mobile World Congress 2025", "2025-03-03", "2025-03-06", None, {"Internacional": 1.35}),
    ("Easter 2023", "2023-04-02", "2023-04-09", None, {"Nacional": 1.45, "Internacional": 1.10}),
    ("Easter 2024", "2024-03-24", "2024-03-31", None, {"Nacional": 1.45, "Internacional": 1.10}),
    ("Easter 2025", "2025-04-13", "2025-04-20", None, {"Nacional": 1.45, "Internacional": 1.10}),
    ("Primavera Sound 2023", "2023-06-01", "2023-06-03", ["80191069"], {"Internacional": 3.0, "Nacional": 3.0, "Regional": 2.5}),
    ("Primavera Sound 2024", "2024-05-29", "2024-06-01", ["80191069"], {"Internacional": 3.0, "Nacional": 3.0, "Regional": 2.5}),
    ("Primavera Sound 2025", "2025-06-04", "2025-06-07", ["80191069"], {"Internacional": 3.0, "Nacional": 3.0, "Regional": 2.5}),
    ("Sant Joan 2023", "2023-06-23", "2023-06-23", BEACH, {"Regional": 2.6, "Nacional": 1.6}),
    ("Sant Joan 2024", "2024-06-23", "2024-06-23", BEACH, {"Regional": 2.6, "Nacional": 1.6}),
    ("Sant Joan 2025", "2025-06-23", "2025-06-23", BEACH, {"Regional": 2.6, "Nacional": 1.6}),
    ("La Mercè 2023", "2023-09-22", "2023-09-25", ["80190102", "80190104", "80190101"], {"Regional": 2.0, "Nacional": 1.3}),
    ("La Mercè 2024", "2024-09-20", "2024-09-24", ["80190102", "80190104", "80190101"], {"Regional": 2.0, "Nacional": 1.3}),
    ("America's Cup 2024", "2024-08-22", "2024-10-19", ["80190103", "80191067"], {"Internacional": 1.35}),
    ("Christmas 2023", "2023-12-20", "2024-01-06", None, {"Nacional": 1.25, "Regional": 1.15}),
    ("Christmas 2024", "2024-12-20", "2025-01-06", None, {"Nacional": 1.25, "Regional": 1.15}),
]

# Planted data-quality problems (the data review must find them)
MISSING_DAYS = pd.date_range("2024-11-12", "2024-11-14")
UNKNOWN_CODE = "80190399"           # appears in T4 for the first 3 months of 2023
M1_DUPLICATES = 40

COUNTRIES = {  # share of international visitors, seasonal amplitude, peak month, yearly growth
    "Francia": (0.14, 0.35, 8, 0.02), "Reino Unido": (0.12, 0.20, 6, 0.03),
    "Estados Unidos": (0.11, 0.35, 6, 0.08), "Italia": (0.09, 0.40, 8, 0.02),
    "Alemania": (0.08, 0.20, 5, 0.01), "Países Bajos": (0.05, 0.30, 7, 0.03),
    "Irlanda": (0.03, 0.25, 7, 0.04), "Suiza": (0.03, 0.15, 5, 0.02),
    "Bélgica": (0.03, 0.25, 7, 0.02), "Portugal": (0.02, 0.20, 8, 0.03),
    "China": (0.03, 0.10, 10, 0.25), "Japón": (0.015, 0.15, 9, 0.10),
    "México": (0.02, 0.20, 7, 0.06), "Argentina": (0.02, 0.25, 1, 0.04),
    "Resto del mundo": (0.215, 0.20, 7, 0.04),
}


DEFAULT_BY_DISTRICT = {"07": 0.15, "08": 0.08, "09": 0.10}   # residential districts: few visitors


def _attraction(codes):
    return np.array([ATTRACTION.get(c, DEFAULT_BY_DISTRICT.get(c[4:6], 0.30)) for c in codes])


def _event_matrix(codes, origin):
    """Multiplier per (day, neighbourhood) for one origin."""
    mult = np.ones((len(DAYS), len(codes)))
    col = {c: i for i, c in enumerate(codes)}
    for _, start, end, where, effect in EVENTS:
        if origin not in effect:
            continue
        rows = (DAYS >= start) & (DAYS <= end)
        cols = list(range(len(codes))) if where is None else [col[c] for c in where]
        mult[np.ix_(rows, cols)] *= effect[origin]
    return mult


def daily_visitors(codes, rng):
    """Daily unique visitors per neighbourhood: {origin: array(days, neighbourhoods)}."""
    w = _attraction(codes)
    doy = DAYS.dayofyear.to_numpy()[:, None]
    years = ((DAYS - DAYS[0]).days.to_numpy() / 365.25)[:, None]
    dow = DAYS.dayofweek.to_numpy()
    amp = np.where(np.isin(codes, BEACH), 0.45, np.where(w > 3, 0.30, 0.18))
    business = np.isin(codes, BUSINESS)
    out = {}
    for origin, base in ORIGIN_BASE.items():
        if origin == "Internacional":
            weight = w ** 1.2
            growth = np.array([GROWTH_INTL.get(c, 0.04) for c in codes])
            season = 1 + amp * np.cos(2 * np.pi * (doy - 200) / 365.25)
        elif origin == "Nacional":
            weight = w
            growth = np.full(len(codes), 0.02)
            season = 1 + 0.8 * amp * np.cos(2 * np.pi * (doy - 215) / 365.25)
        else:
            weight = 0.5 * w + 0.6
            growth = np.full(len(codes), 0.01)
            season = (1 - 0.18 * np.exp(-((doy - 225) / 12) ** 2)       # August: locals on holiday
                      + 0.12 * np.exp(-((doy - 355) / 10) ** 2)) * np.ones((1, len(codes)))
        week = np.array(WEEKDAY[origin])[dow][:, None] * np.ones((1, len(codes)))
        if origin == "Internacional":
            week[:, business] *= np.where(dow < 4, 1.08, 0.90)[:, None]
        trend = (1 + growth[None, :]) ** years
        noise = rng.lognormal(0, 0.06, (len(DAYS), len(codes)))
        out[origin] = base * weight[None, :] * season * week * trend * _event_matrix(codes, origin) * noise
    return out


def make_all(seed=SEED, folder=None):
    rng = np.random.default_rng(seed)
    folder = folder or cv.SAMPLE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    geo, barris = cv.load_barris()
    codes = barris["cod_barrio"].to_numpy()
    daily = daily_visitors(codes, rng)
    mes = DAYS.strftime("%Y%m").to_numpy()
    files = {}

    # --- T5 (daily per neighbourhood) and T4 (monthly per neighbourhood)
    t5, t4 = [], []
    for origin, arr in daily.items():
        for tipo in cv.VISITOR_TYPES:
            share = TOURIST_SHARE[origin] if tipo == "Turista" else 1 - TOURIST_SHARE[origin]
            if share == 0:
                continue
            values = arr * share
            day_df = pd.DataFrame(values, index=DAYS, columns=codes)
            long = day_df.stack().rename("visitantes").reset_index()
            long.columns = ["date_dt", "cod_barrio", "visitantes"]
            long["origen"], long["tipo_visitante"] = origin, tipo
            t5.append(long)
            month = day_df.groupby(mes).sum() / TURNOVER[(origin, tipo)]
            mlong = month.stack().rename("visitantes").reset_index()
            mlong.columns = ["mes", "cod_barrio", "visitantes"]
            mlong["origen"], mlong["tipo_visitante"] = origin, tipo
            t4.append(mlong)
    t5 = pd.concat(t5, ignore_index=True)
    t4 = pd.concat(t4, ignore_index=True)

    # --- T2 / T1 (municipality): people visit several neighbourhoods, so not the plain sum
    t2 = (t5.groupby(["date_dt", "origen", "tipo_visitante"])["visitantes"].sum() / OVERLAP_DAY).reset_index()
    t1 = (t4.groupby(["mes", "origen", "tipo_visitante"])["visitantes"].sum() / OVERLAP_MONTH).reset_index()

    def finish(df, key, daily_file):
        df = df.copy()
        if daily_file:
            df["mes"] = df["date_dt"].dt.strftime("%Y%m")
            df["date_dt"] = df["date_dt"].dt.strftime("%Y-%m-%d")
        df["año"] = df["mes"].str[:4].astype(int)
        df["cod_municipio"], df["desc_municipio"] = cv.BCN_MUNICIPIO, "Barcelona"
        v = df["visitantes"].round()
        df["visitantes"] = v.where(v >= 15).astype("Int64")       # NA = anonymised (< 15 people)
        return df[cv.SCHEMAS[key]["columns"]]

    t5, t4 = finish(t5, "T5", True), finish(t4, "T4", False)
    t2, t1 = finish(t2, "T2", True), finish(t1, "T1", False)

    # planted problems: missing days and an unknown neighbourhood code
    gone = MISSING_DAYS.strftime("%Y-%m-%d")
    t5 = t5[~t5["date_dt"].isin(gone)]
    t2 = t2[~t2["date_dt"].isin(gone)]
    bad = t4[(t4["cod_barrio"] == "80190312") & (t4["mes"] <= "202303")].index
    t4.loc[bad, "cod_barrio"] = UNKNOWN_CODE

    # --- T3: tourists by number of nights per week (municipality)
    t3 = _overnights(t2, rng)

    # --- T8: international visitors per neighbourhood and country
    t8 = _countries(t4, rng)

    # --- M1: trips between neighbourhoods, two sample weeks, gravity model
    m1 = _trips(geo, barris, rng)

    files = {"T1": t1, "T2": t2, "T3": t3, "T4": t4, "T5": t5, "T8": t8, "M1": m1}
    for key, df in files.items():
        df.reset_index(drop=True).to_parquet(folder / f"{cv.SCHEMAS[key]['file']}.parquet", index=False)
    truth = {"events": [e[:3] for e in EVENTS],
             "missing_days": list(gone), "unknown_code": UNKNOWN_CODE, "m1_duplicates": M1_DUPLICATES,
             "growth_intl": GROWTH_INTL, "gravity_beta_per_km": GRAVITY_BETA}
    (folder / "_synthetic_truth.json").write_text(json.dumps(truth, indent=1, ensure_ascii=False))
    return {k: len(v) for k, v in files.items()}


def _overnights(t2, rng):
    tour = t2[t2["tipo_visitante"] == "Turista"].copy()
    tour["date"] = pd.to_datetime(tour["date_dt"])
    tour["week_start"] = tour["date"] - pd.to_timedelta(tour["date"].dt.dayofweek, unit="D")
    weekly = tour.groupby(["week_start", "origen"])["visitantes"].sum().reset_index()
    weekly = weekly[(weekly["week_start"] >= DAYS[0]) & (weekly["week_start"] + pd.Timedelta(days=6) <= DAYS[-1])]
    rows = []
    for _, r in weekly.iterrows():
        summer = 0.5 + 0.5 * np.cos(2 * np.pi * (r.week_start.dayofyear - 205) / 365.25)
        mean_n = (3.4 if r.origen == "Internacional" else 2.2) + 0.7 * summer
        nights = np.arange(1, 8)
        p = np.exp(-nights / mean_n)
        p /= p.sum()
        people = r.visitantes / (p * nights).sum()
        for n, pn in zip(nights, p):
            v = int(people * pn * rng.lognormal(0, 0.03))
            end = r.week_start + pd.Timedelta(days=6)
            rows.append([r.week_start.year, r.week_start.strftime("%Y%m"), int(r.week_start.isocalendar().week),
                         f"{r.week_start:%Y-%m-%d}/{end:%Y-%m-%d}", cv.BCN_MUNICIPIO, "Barcelona",
                         r.origen, int(n), v if v >= 15 else pd.NA])
    return pd.DataFrame(rows, columns=cv.SCHEMAS["T3"]["columns"]).astype({"visitantes": "Int64"})


def _countries(t4, rng):
    intl = t4[(t4["origen"] == "Internacional")].dropna(subset=["visitantes"])
    names = list(COUNTRIES)
    share, amp, peak, growth = (np.array([COUNTRIES[c][i] for c in names]) for i in range(4))
    rows = []
    for (mes, tipo), g in intl.groupby(["mes", "tipo_visitante"]):
        m, y = int(mes[4:]), int(mes[:4]) - 2023 + (int(mes[4:]) - 1) / 12
        s = share * (1 + amp * np.cos(2 * np.pi * (m - peak) / 12)) * (1 + growth) ** y
        s = s / s.sum()
        for _, r in g.iterrows():
            tilt = rng.dirichlet(s * 400)       # small differences between neighbourhoods
            v = np.round(r.visitantes * tilt)
            for c, val in zip(names, v):
                rows.append([int(mes[:4]), mes, r.cod_barrio, cv.BCN_MUNICIPIO, "Barcelona", c, tipo,
                             int(val) if val >= 15 else pd.NA])
    return pd.DataFrame(rows, columns=cv.SCHEMAS["T8"]["columns"]).astype({"visitantes": "Int64"})


GRAVITY_BETA = {"Residente": 0.30, "Regional": 0.45, "Nacional": 0.55, "Internacional": 0.65}


def _trips(geo, barris, rng):
    import analysis as an
    cent = an.centroids(geo).set_index("cod_barrio").loc[barris["cod_barrio"]]
    d = an.distance_matrix(cent[["lon", "lat"]].to_numpy())
    codes = barris["cod_barrio"].to_numpy()
    names = barris["barrio_name"].to_numpy()
    w = _attraction(codes)
    resident_mass = rng.lognormal(0, 0.35, len(codes)) * np.where(np.char.startswith(codes.astype(str), "801902"), 1.6, 1.0)
    scale = {"Residente": 14, "Regional": 9, "Nacional": 4.5, "Internacional": 9}
    i_idx, j_idx = np.where(~np.eye(len(codes), dtype=bool))
    rows = []
    for season, (a, b) in M1_WEEKS.items():
        for day in pd.date_range(a, b):
            dow = day.dayofweek
            for origin, beta in GRAVITY_BETA.items():
                if origin == "Residente":
                    mo, md = resident_mass, 0.6 * resident_mass + 0.25 * w
                else:
                    sea = 1.4 if (season == "summer" and origin != "Regional") else (0.85 if origin == "Regional" and season == "summer" else 1.0)
                    mo = md = w * sea
                lam = scale[origin] * WEEKDAY[origin][dow] * mo[i_idx] * md[j_idx] * np.exp(-beta * d[i_idx, j_idx]) * 10
                trips = rng.poisson(lam)
                trips = np.where(trips < 15, 0, trips)    # privacy rule
                rows.append(pd.DataFrame({
                    "day": day.strftime("%Y-%m-%d"), "day_of_the_week": cv.WEEKDAYS[dow], "month": day.month,
                    "origen": origin, "municipio_origen": cv.BCN_MUNICIPIO, "municipio_origen_name": "Barcelona",
                    "barrio_origen": codes[i_idx], "barrio_origen_name": names[i_idx],
                    "municipio_destino": cv.BCN_MUNICIPIO, "municipio_destino_name": "Barcelona",
                    "barrio_destino": codes[j_idx], "barrio_destino_name": names[j_idx], "viajes": trips}))
    m1 = pd.concat(rows, ignore_index=True)
    m1 = pd.concat([m1, m1.sample(M1_DUPLICATES, random_state=1)], ignore_index=True)
    return m1
