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

- **Privacy threshold (15 people).** According to the official data description, the mobility files (M1 to M3) show trips below 15 as 0. The tourism files (T1 to T9) instead group segments of fewer than 15 people under the value NA in `origen` / `tipo_visitante`, so the real T4 will have an NA category, not zeros or gaps. The app shows any row with NA in `origen` or `tipo_visitante` as its own series, "NA (grouped, below 15)", and never adds it to a known origin. The current synthetic files do not model this (they put NA in `visitantes` instead), so this behaviour was tested with a small fake table.
- **Not additive.** The description says unique visitors "no son sumables": adding days does not give the month, and adding neighbourhoods does not give the municipality. The app shows one neighbourhood at a time and never adds across neighbourhoods or days.
- **Turista + Excursionista.** The app adds the two types within the same neighbourhood, month and origin, as the notebook does. The notebook does this in §4.1 (cell In [10]), and also in §4.2 [11], §4.3 [12], §5.1 [15], §5.3 [17], §5.5 [19] and §6 [20]. The cells in §4.3 and §6 also add across origins. The description does not say explicitly whether the two types can be added. It defines them as mutually exclusive (Turista: lives outside the province and stayed at least one night; Excursionista: all other visitors; regional visitors are always Excursionista), so adding them within the same neighbourhood, month and origin looks logically consistent, but it is not stated. To be confirmed with the mentor.
- This is a "hello world" version: one chart and one filter, on T4 only.
