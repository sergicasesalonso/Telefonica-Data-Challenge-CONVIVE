# Visualisation environment (Iteration 2, P2)

**Decision (proposed, to be confirmed by the team): Streamlit, run locally.** Owner: Martí (P2). Used by: Pau (P6) for the preliminary dashboard.

## Comparison

Scores: 1 = poor, 2 = acceptable, 3 = good.

| Criterion | Streamlit (local) | Jupyter + Plotly + ipywidgets | Power BI Desktop (local) |
|---|---|---|---|
| (a) NDA-safe: local, no upload to an external cloud | 3 | 3 | 2 |
| (b) Learning effort, 6 people, 1 week | 2 | 2 | 2 |
| (c) Reuse of convive.py, analysis.py, folium maps | 3 | 3 | 1 |
| (d) Filters: period, origin, neighbourhood | 3 | 2 | 3 |
| (e) Demo-friendly for 9 Nov | 3 | 2 | 3 |
| (f) Free | 3 | 3 | 2 |
| **Total** | **17** | **15** | **13** |

- **Streamlit.** It is a plain Python script that imports our modules directly, and the filters are one line each (`st.selectbox`, `st.slider`). It opens in the browser as a clean page with no code visible. It is a new library for everyone, so learning gets a 2, but its API is small. By default it sends anonymous usage statistics (not our data); `.streamlit/config.toml` turns this off.
- **Jupyter + Plotly + ipywidgets.** A very close second: the team already uses the notebook and nothing new needs installing. But ipywidgets callbacks are fiddly, the demo shows code, and it depends on the cells being run in the right order.
- **Power BI Desktop.** Its slicers and demo look are the best, but it cannot reuse our Python code or folium maps, so the logic would be rebuilt in DAX. Its default aggregation is SUM, which would silently add unique visitors across neighbourhoods. It runs only on Windows, and sharing needs the Power BI cloud service (Pro licence), which our NDA rules out.

I agree with the Streamlit suggestion. If the team prefers no new tool, Jupyter is a reasonable fallback.

## Install and run (from the repo root)

```bash
pip install -r requirements.txt
streamlit run dashboard/app.py
```

The app opens at http://localhost:8501. It reads `CONVIVE_DATA_MODE` (`auto` by default, also `synthetic` or `real`), which works like `DATA_MODE` in the notebook. The first run creates the synthetic files in `data/sample/`. Run it from the repo root so that `.streamlit/config.toml` is used. Never deploy it to Streamlit Community Cloud or any other host.

## Limits

- The app shows one neighbourhood at a time and never adds unique visitors across neighbourhoods. Values below the privacy threshold are shown as gaps, not zeros.
- The app adds Turista and Excursionista within the same neighbourhood, month and origin, as the notebook does. The notebook does this in §4.1 (cell In [10], with the comment "tourists + excursionists are different people"), and also in §4.2 [11], §4.3 [12], §5.1 [15], §5.3 [17], §5.5 [19] and §6 [20]. The cells in §4.3 and §6 also add across origins.
- **We cannot tell whether the data description allows this.** The official "Smart Steps - Challenge 2026" document is not in the repo, and neither the README nor data_review_plan.md mentions adding across visitor types. If one person can be an excursionist on one day and a tourist later in the same month, the monthly sum would count them twice. To be confirmed with the mentor. Until then, the dashboard can show the two types separately.
- This is a "hello world" version: one chart and one filter, on T4 only.
