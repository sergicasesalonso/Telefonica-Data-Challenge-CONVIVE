"""CONVIVE - analysis methods used in the notebook.

Each function is small and documented so the team can reuse it on the real data.
Methods:
  geography      centroids, areas, distances, k-nearest-neighbour spatial weights
  quality        logical consistency checks between files, completeness grid
  time           robust harmonic regression (trend + yearly + weekly), event detection, same-weekday YoY
  space          location quotient, Gini / Lorenz, Moran's I and LISA, mean centre / standard distance
  typologies     k-means clustering of neighbourhoods with silhouette selection and PCA
  mobility       Poisson gravity model with fixed effects, censoring-aware version (privacy threshold), PageRank
  index          composite Coexistence Pressure Index with a weight-sensitivity check
"""

import numpy as np
import pandas as pd

EARTH_KM = 6371.0
PLACA_CATALUNYA = (2.1700, 41.3870)   # lon, lat, reference point for distances


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------
def _polygons(geometry):
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]


def _ring_area_centroid(ring):
    """Shoelace formula on a local equirectangular projection (km)."""
    xy = np.array(ring)
    lat0 = np.radians(41.39)
    x = np.radians(xy[:, 0]) * EARTH_KM * np.cos(lat0)
    y = np.radians(xy[:, 1]) * EARTH_KM
    a = x[:-1] * y[1:] - x[1:] * y[:-1]
    area = a.sum() / 2
    if area == 0:
        return 0.0, xy[:, 0].mean(), xy[:, 1].mean()
    cx = ((x[:-1] + x[1:]) * a).sum() / (6 * area)
    cy = ((y[:-1] + y[1:]) * a).sum() / (6 * area)
    return abs(area), np.degrees(cx / (EARTH_KM * np.cos(lat0))), np.degrees(cy / EARTH_KM)


def centroids(geo):
    """Area (km²) and area-weighted centroid of every neighbourhood."""
    rows = []
    for f in geo["features"]:
        parts = [_ring_area_centroid(poly[0]) for poly in _polygons(f["geometry"])]
        total = sum(p[0] for p in parts)
        lon = sum(p[0] * p[1] for p in parts) / total
        lat = sum(p[0] * p[2] for p in parts) / total
        rows.append({"cod_barrio": f["properties"]["cod_barrio"], "area_km2": total, "lon": lon, "lat": lat})
    return pd.DataFrame(rows)


def distance_matrix(lonlat):
    """Great-circle distances (km) between points given as an (n, 2) lon/lat array."""
    lon, lat = np.radians(lonlat[:, 0]), np.radians(lonlat[:, 1])
    dlon = lon[:, None] - lon[None, :]
    dlat = lat[:, None] - lat[None, :]
    h = np.sin(dlat / 2) ** 2 + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(h))


def knn_weights(lonlat, k=5):
    """Row-standardised spatial weights: each neighbourhood linked to its k nearest ones."""
    d = distance_matrix(lonlat)
    np.fill_diagonal(d, np.inf)
    W = np.zeros_like(d)
    nearest = np.argsort(d, axis=1)[:, :k]
    for i, js in enumerate(nearest):
        W[i, js] = 1
    W = np.maximum(W, W.T)                     # symmetric neighbourhood relation
    return W / W.sum(axis=1, keepdims=True)


# ---------------------------------------------------------------------------
# Data quality: logical consistency between files
# ---------------------------------------------------------------------------
def consistency_checks(t1, t2, t4, t5):
    """Unique visitors are not additive, but they must respect some inequalities."""
    out = []
    key = ["mes", "cod_barrio", "origen", "tipo_visitante"]
    daily_max = t5.groupby(key)["visitantes"].max()
    monthly = t4.set_index(key)["visitantes"]
    both = pd.concat([daily_max.rename("daily_max"), monthly.rename("monthly")], axis=1).dropna()
    bad = int((both["daily_max"] > both["monthly"]).sum())
    out.append(("Neighbourhood: max daily unique ≤ monthly unique (T5 vs T4)", f"{bad} violations in {len(both):,} cells", bad == 0))

    key = ["mes", "origen", "tipo_visitante"]
    barri_max = t4.groupby(key)["visitantes"].max()
    city = t1.set_index(key)["visitantes"]
    both = pd.concat([barri_max.rename("barri_max"), city.rename("city")], axis=1).dropna()
    bad = int((both["barri_max"] > both["city"]).sum())
    out.append(("Month: largest neighbourhood ≤ whole city (T4 vs T1)", f"{bad} violations in {len(both):,} cells", bad == 0))

    key = ["date_dt", "origen", "tipo_visitante"]
    barri_sum = t5.groupby(key)["visitantes"].sum()
    city = t2.set_index(key)["visitantes"]
    ratio = (barri_sum / city).dropna()
    out.append(("Day: sum of neighbourhoods / city (T5 vs T2) = average neighbourhoods visited",
                f"median {ratio.median():.2f} (range {ratio.min():.2f} to {ratio.max():.2f})", bool((ratio >= 1).all())))
    return pd.DataFrame(out, columns=["check", "result", "ok"]).assign(ok=lambda d: d["ok"].map({True: "OK", False: "REVIEW"}))


def missing_days(dates, start="2023-01-01", end="2025-08-31"):
    full = pd.date_range(start, end)
    have = pd.to_datetime(pd.Series(dates).unique())
    return full.difference(have)


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------
def harmonic_design(index, harmonics=6):
    """Regressors for a daily series: quadratic trend, yearly Fourier terms, day-of-week dummies."""
    t = ((index - pd.Timestamp("2023-01-01")).days / 365.25).to_numpy()
    doy = index.dayofyear.to_numpy() / 365.25
    X = {"const": np.ones(len(index)), "t": t, "t2": t ** 2}
    for k in range(1, harmonics + 1):
        X[f"sin{k}"] = np.sin(2 * np.pi * k * doy)
        X[f"cos{k}"] = np.cos(2 * np.pi * k * doy)
    for d in range(1, 7):
        X[f"dow{d}"] = (index.dayofweek == d).astype(float)
    return pd.DataFrame(X, index=index)


def decompose(series, harmonics=6, threshold=3.5):
    """Robust harmonic regression on log(visitors):
        log y_t = trend (quadratic) + yearly cycle (Fourier, K harmonics) + weekday effect + residual
    Fitted twice: days with extreme residuals in the first fit get zero weight in the second, so
    events do not bend the seasonal curve. Missing days are simply left out (no interpolation)."""
    y = np.log(series.dropna().astype(float))
    y = y[np.isfinite(y)]
    X = harmonic_design(y.index, harmonics)
    keep = np.ones(len(y), bool)
    for _ in range(2):
        b, *_ = np.linalg.lstsq(X.to_numpy()[keep], y.to_numpy()[keep], rcond=None)
        resid = y.to_numpy() - X.to_numpy() @ b
        keep = np.abs(robust_z(resid)) <= threshold
    b = pd.Series(b, index=X.columns)
    cols = lambda pre: [c for c in X.columns if c.startswith(pre)]
    weekly = X[cols("dow")] @ b[cols("dow")]
    shift = b[cols("dow")].sum() / 7                     # centre the weekday effect on the average day
    trend = X[["const", "t", "t2"]] @ b[["const", "t", "t2"]] + shift
    yearly = X[cols("sin") + cols("cos")] @ b[cols("sin") + cols("cos")]
    return pd.DataFrame({"observed": y, "trend": trend, "yearly": yearly, "weekly": weekly - shift,
                         "resid": resid}, index=y.index)


def robust_z(x):
    """z-score using median and MAD (not distorted by the outliers it is looking for)."""
    med = np.nanmedian(x)
    mad = np.nanmedian(np.abs(x - med)) * 1.4826
    return (x - med) / mad


def detect_events(resid, threshold=3.5, min_effect=0.10, min_gap=2):
    """Days that are both statistically extreme (|robust z| > threshold) and practically relevant
    (|effect| > min_effect, e.g. 10%), grouped into episodes when they are at most `min_gap` days apart."""
    z = pd.Series(robust_z(resid.to_numpy()), index=resid.index)
    flagged = z[(z.abs() > threshold) & (np.abs(np.expm1(resid)) > min_effect)]
    episodes, current = [], []
    for day in flagged.index:
        if current and (day - current[-1]).days > min_gap:
            episodes.append(current)
            current = []
        current.append(day)
    if current:
        episodes.append(current)
    cols = ["start", "end", "days", "peak_z", "effect"]
    if not episodes:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([{"start": e[0].date(), "end": e[-1].date(), "days": len(e),
                          "peak_z": round(float(z.loc[e].abs().max()), 1),
                          "effect": f"{np.exp(resid.loc[e].mean()) - 1:+.0%}"} for e in episodes])


def match_events(found, truth, tolerance_days=2):
    """Compare detected episodes with known (planted) events: recall and precision."""
    rows = []
    for name, start, end in truth:
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        hit = found[(pd.to_datetime(found["start"]) <= e + pd.Timedelta(days=tolerance_days)) &
                    (pd.to_datetime(found["end"]) >= s - pd.Timedelta(days=tolerance_days))]
        rows.append({"event": name, "dates": f"{start} to {end}", "detected": "yes" if len(hit) else "no",
                     "detected as": ", ".join(f"{r.start}→{r.end}" for r in hit.itertuples()) or "-"})
    table = pd.DataFrame(rows)
    matched = sum(
        any((pd.Timestamp(s) - pd.Timedelta(days=tolerance_days) <= pd.Timestamp(r.end)) and
            (pd.Timestamp(r.start) <= pd.Timestamp(e) + pd.Timedelta(days=tolerance_days)) for _, s, e in truth)
        for r in found.itertuples())
    precision = matched / len(found) if len(found) else float("nan")
    recall = (table["detected"] == "yes").mean()
    return table, precision, recall


def yoy_same_weekday(daily, min_days=20):
    """Year-on-year change comparing each day with the same weekday 52 weeks earlier (364 days).
    Only days present in both years count; months with fewer than `min_days` such days are dropped."""
    prev = daily.shift(364, freq="D")
    both = pd.concat([daily.rename("now"), prev.rename("prev")], axis=1).dropna()
    g = both.groupby(both.index.to_period("M"))
    monthly = g.sum()[g.size() >= min_days]
    return (monthly["now"] / monthly["prev"] - 1).rename("yoy")


# ---------------------------------------------------------------------------
# Spatial distribution
# ---------------------------------------------------------------------------
def location_quotient(table):
    """LQ[b, o] = (share of origin o in neighbourhood b) / (share of origin o in the city).
    LQ > 1: the origin is over-represented in that neighbourhood."""
    share_b = table.div(table.sum(axis=1), axis=0)
    share_city = table.sum() / table.to_numpy().sum()
    return share_b / share_city


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    x = x[~np.isnan(x)]
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def lorenz(x):
    x = np.sort(np.asarray(x, dtype=float))
    return np.insert(np.arange(1, len(x) + 1) / len(x), 0, 0), np.insert(np.cumsum(x) / x.sum(), 0, 0)


def morans_i(x, W, permutations=999, seed=0):
    """Global Moran's I with a permutation test (pseudo p-value)."""
    rng = np.random.default_rng(seed)
    z = (x - x.mean()) / x.std()
    I = float(z @ W @ z / len(z))
    sims = np.array([(zp := rng.permutation(z)) @ W @ zp / len(z) for _ in range(permutations)])
    p = (np.sum(np.abs(sims) >= abs(I)) + 1) / (permutations + 1)
    return I, p, sims


def local_moran(x, W, permutations=999, seed=0, alpha=0.05):
    """LISA: local Moran's I, conditional permutation p-values and cluster type (HH, LL, HL, LH)."""
    rng = np.random.default_rng(seed)
    z = (x - x.mean()) / x.std()
    lag = W @ z
    Ii = z * lag
    n = len(z)
    p = np.ones(n)
    for i in range(n):
        others = np.delete(z, i)
        w = W[i][np.arange(n) != i]
        sims = np.array([z[i] * (w @ rng.permutation(others)) for _ in range(permutations)])
        p[i] = (np.sum(np.abs(sims) >= abs(Ii[i])) + 1) / (permutations + 1)
    quad = np.where(z > 0, np.where(lag > 0, "HH hot spot", "HL outlier"), np.where(lag > 0, "LH outlier", "LL cold spot"))
    quad = np.where(p < alpha, quad, "not significant")
    return pd.DataFrame({"Ii": Ii, "p": p, "type": quad})


def matched_growth(pivot, year_a="2023", year_b="2025", months=("01", "02", "03", "04", "05", "06", "07", "08")):
    """Annualised growth between equivalent months of two years, per column.
    `pivot`: rows = YYYYMM, columns = areas. Only months present in BOTH years count for each area."""
    a = pivot.reindex([year_a + m for m in months]).set_axis(months)
    b = pivot.reindex([year_b + m for m in months]).set_axis(months)
    both = a.notna() & b.notna()
    years = int(year_b) - int(year_a)
    return (b.where(both).sum() / a.where(both).sum()) ** (1 / years) - 1


def mean_centre(lonlat, weights):
    """Weighted mean centre and standard distance (km): where visitors are and how spread out."""
    w = np.asarray(weights, float) / np.sum(weights)
    c = (lonlat * w[:, None]).sum(axis=0)
    d = distance_matrix(np.vstack([c, lonlat]))[0, 1:]
    return c, float(np.sqrt((w * d ** 2).sum()))


# ---------------------------------------------------------------------------
# Typologies
# ---------------------------------------------------------------------------
def cluster_neighbourhoods(features, k_range=range(3, 7), seed=0):
    """Standardise, choose k with the silhouette score, k-means, and a 2D PCA for plotting."""
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    X = StandardScaler().fit_transform(features)
    scores = {}
    for k in k_range:
        labels = KMeans(k, n_init=20, random_state=seed).fit_predict(X)
        scores[k] = silhouette_score(X, labels)
    best = max(scores, key=scores.get)
    km = KMeans(best, n_init=20, random_state=seed).fit(X)
    pca = PCA(2).fit(X)
    return {"k": best, "silhouette": scores, "labels": km.labels_, "pca": pca.transform(X),
            "explained": pca.explained_variance_ratio_, "loadings": pd.DataFrame(pca.components_.T, index=features.columns, columns=["PC1", "PC2"])}


# ---------------------------------------------------------------------------
# Mobility
# ---------------------------------------------------------------------------
def gravity_model(od, dist_km):
    """Poisson gravity model with origin and destination fixed effects:
        log E[T_ij] = a_i + b_j - beta * d_ij
    beta is the distance decay (per km): higher beta = shorter trips.
    `od` has columns barrio_origen, barrio_destino, viajes. Zeros are kept (that is why Poisson)."""
    import statsmodels.api as sm
    df = od.copy()
    df["d"] = dist_km
    X = pd.get_dummies(df[["barrio_origen", "barrio_destino"]].astype(str), drop_first=True, dtype=float)
    X["d"] = df["d"]
    X = sm.add_constant(X)
    fit = sm.GLM(df["viajes"].to_numpy(), X, family=sm.families.Poisson()).fit()
    beta = -fit.params["d"]
    lo, hi = -fit.conf_int().loc["d"][::-1]
    pseudo_r2 = 1 - fit.deviance / fit.null_deviance
    return {"beta": beta, "ci": (lo, hi), "pseudo_r2": pseudo_r2}


def pagerank(od, weight="viajes"):
    """Importance of each neighbourhood as a destination in the trip network."""
    import networkx as nx
    g = nx.DiGraph()
    for r in od[od[weight] > 0].itertuples():
        g.add_edge(r.barrio_origen, r.barrio_destino, weight=getattr(r, weight))
    return pd.Series(nx.pagerank(g, weight="weight"))


# ---------------------------------------------------------------------------
# Composite index
# ---------------------------------------------------------------------------
def minmax(s):
    return (s - s.min()) / (s.max() - s.min())


def composite_index(indicators, weights=None):
    """Weighted mean of min-max normalised indicators, scaled 0-100."""
    norm = indicators.apply(minmax)
    w = pd.Series(weights if weights is not None else 1.0, index=indicators.columns, dtype=float)
    return 100 * (norm * w).sum(axis=1) / w.sum()


def weight_sensitivity(indicators, n=500, seed=0):
    """Rank stability: Spearman correlation between the equal-weights ranking and rankings
    with random weights (Dirichlet). Values close to 1 mean the ranking does not depend on the weights."""
    from scipy.stats import spearmanr
    rng = np.random.default_rng(seed)
    base = composite_index(indicators)
    rhos, top10 = [], []
    base_top = set(base.nlargest(10).index)
    for _ in range(n):
        w = rng.dirichlet(np.ones(indicators.shape[1]))
        alt = composite_index(indicators, w)
        rhos.append(spearmanr(base, alt)[0])
        top10.append(len(base_top & set(alt.nlargest(10).index)) / 10)
    return np.array(rhos), np.array(top10)


def censored_gravity(od_daily, dist_km, threshold=15):
    """Gravity model that knows about the privacy rule.

    Daily flows below `threshold` are published as 0, so a published 0 means "0 to threshold-1 trips",
    not "no trips". Treating those zeros as real zeros makes long, thin flows look rarer than they are and
    overstates the distance decay. Here each published 0 contributes P(T < threshold) to the likelihood
    (a censored Poisson), and each published count contributes its Poisson probability:
        log lambda = a_origin + b_destination + c_day - beta * d
    Fitted by maximum likelihood (L-BFGS with analytic gradient)."""
    from scipy.optimize import minimize
    from scipy.stats import poisson

    o_codes, o_idx = np.unique(od_daily["barrio_origen"], return_inverse=True)
    d_codes, d_idx = np.unique(od_daily["barrio_destino"], return_inverse=True)
    t_codes, t_idx = np.unique(od_daily["day"], return_inverse=True)
    y = od_daily["viajes"].to_numpy(float)
    d = np.asarray(dist_km, float)
    cens = y < threshold
    k = threshold - 1
    no, nd, nt = len(o_codes), len(d_codes), len(t_codes)

    def unpack(p):
        a = p[:no]
        b = np.concatenate([[0.0], p[no:no + nd - 1]])
        c = np.concatenate([[0.0], p[no + nd - 1:no + nd + nt - 2]])
        return a, b, c, p[-1]

    def negll(p):
        a, b, c, beta = unpack(p)
        eta = np.clip(a[o_idx] + b[d_idx] + c[t_idx] - beta * d, -30, 12)
        lam = np.exp(eta)
        logpmf = poisson.logpmf(k, lam)
        logcdf = poisson.logcdf(k, lam)
        logcdf = np.where(np.isfinite(logcdf), logcdf, logpmf)       # far tail: P(T <= k) ~ P(T = k)
        ll = np.where(cens, logcdf, y * eta - lam)
        # derivative of each term with respect to log(lambda)
        g = np.where(cens, -lam * np.exp(np.minimum(logpmf - logcdf, 0)), y - lam)
        grad = np.concatenate([np.bincount(o_idx, g, no), np.bincount(d_idx, g, nd)[1:],
                               np.bincount(t_idx, g, nt)[1:], [-(g * d).sum()]])
        return -ll.sum() / len(y), -grad / len(y)

    p0 = np.concatenate([np.full(no, np.log(y.mean() + 1)), np.zeros(nd - 1 + nt - 1), [0.5]])
    res = minimize(negll, p0, jac=True, method="L-BFGS-B", options={"maxiter": 2000})
    return {"beta": unpack(res.x)[3], "converged": res.success, "message": res.message, "nit": res.nit}
