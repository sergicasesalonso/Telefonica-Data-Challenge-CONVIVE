# CONVIVE

Team 102_A (Convive Lab) · Mobile Data Challenge 2026, Challenge #2 "Visitors and residents in the same space".

- **Final delivery (current, 29 Nov 2026):** final dashboard with nine tabs, one command for the whole pipeline, final notebook, user guide, tests, the answer to the Charter question (visitors against residents), robustness of the 21 verdicts and a scan of level shifts in the source.
- **Iteration 3 (10-23 Nov 2026):** validated aggregated tables, research questions Q1-Q20 quantified with explicit decision rules, low-data neighbourhoods and nationalities.
- **Iteration 2 (27 Oct-9 Nov):** real Smart Steps data, aggregated statistics and a preliminary dashboard answering Q1 to Q6.
- **Iteration 1 (19-26 Oct):** notebook structure, base map, data review plan and analytical toolkit, on synthetic data. It still runs.

## Final delivery: how to run

```bash
python -m pip install -r requirements.txt
python run_final.py                  # everything, from the monthly files (needs data/)
python run_final.py --from-tables    # from the aggregated tables (no raw data)
python -m streamlit run app/dashboard.py     # or start_dashboard.bat on Windows
```

| WBS | Output | Where |
|---|---|---|
| 2.2.1, 2.2.2 | 14 aggregated tables and their validation log | `deliverables/iteration3/` |
| 3.2.x | Quantified answers Q1-Q20 and analysis reports | `deliverables/iteration3/` |
| 3.3.1 | Reproducibility test record | `deliverables/final/3.3.1_reproducibility_test.md` |
| 3.3.2 | Final notebook and user guide | `CONVIVE_Final.ipynb`, `deliverables/final/3.3.2_user_guide.md` |
| 4.3.1 | Test checklist, unit tests and integration checks | `deliverables/final/4.3.1_test_checklist.md`, `tests/`, `app/check_dashboard.py` |
| 4.3.2 | Final dashboard | `app/dashboard.py`, `start_dashboard.bat` |
| 5.2 | Charter question and key findings | `deliverables/final/5.2_key_findings.md`, `coexistence.py` |
| 5.3 | Robustness, level shifts, open data questions | `deliverables/final/5.3_limitations.md`, `sensitivity.py`, `breaks.py` |

`python make_package.py` builds the hand-over zip. With `--with-tables` it adds the aggregated tables, only for people covered by the NDA. `requirements-lock.txt` holds the exact versions of the reproducibility test.

## Iteration 3: how to run

```bash
pip install -r requirements.txt

# 1. Iteration 2 statistics must exist (they are compared with Iteration 3 in the validation)
python run_iteration2.py stats

# 2. Iteration 3: aggregate (2.2.1, pandas only), validate (2.2.2), answer Q1-Q20 and write reports and figures (3.2.x)
python run_iteration3.py                 # or: python run_iteration3.py validate report   (no raw data needed)

# 3. Notebook and dashboard
python make_notebook_i3.py
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=-1 CONVIVE_Iteration3.ipynb
streamlit run app/dashboard.py
```

The dashboard is now the final one (see above); `python app/check_dashboard.py` tests it.

The aggregation step reads the monthly CSV files directly with pandas, so it also runs on a computer without DuckDB or Parquet support (3.3.1 reproducibility). Everything after it reads only aggregated tables.

| WBS | Output (in `deliverables/iteration3/` unless stated) | Code |
|---|---|---|
| 2.2.1 | `2.2.1_aggregates/*.csv`: countries (T8), provinces (T7), municipalities (T6), profile (T9), daily neighbourhood visitors (T5), coverage, trips between neighbourhoods by year (M1) | `aggregates.py` |
| 2.2.2 | `2.2.2_validation_log.md` / `.csv`: 17 checks, including identical M1 totals through two independent paths | `validation.py` |
| 3.2.0 | `3.2.0_ResearchQuestions_v0.3.md`: every question with metric, decision rule and verdict | `research_report.py` |
| 3.2.4 | `3.2.4_quantified_answers.md` / `.csv`: question -> metric -> threshold -> answer -> verdict | `research.py` (`THRESHOLDS`) |
| 3.2.1 | `3.2.1_exploratory_analysis.md`: countries, provinces, municipalities, profile, market growth, nationalities of international visitors (Q11-Q14, Q17-Q20) | `research.py`, `nationalities.py` |
| 3.2.2 | `3.2.2_geographic_analysis.md`: concentration, LQ, rankings, trips, **low-data neighbourhoods (I8)** | `research.py` |
| 3.2.3 | `3.2.3_temporal_analysis.md`: seasonality, weekends, growth, nights, unusual days, rhythm (Q2, Q4, Q5, Q7, Q9, Q15) | `research.py` |
| 4.2.2 | Dashboard tabs "Research answers", "Who visits", "Data quality"; `figures/*.png` | `app/dashboard.py`, `app/dashboard_i3.py` |
| 4.2.3 | Sidebar filters by district, neighbourhood and day type, applied to every view; "Neighbourhood explorer" tab | `app/dashboard_data.py` |
| Notebook | `CONVIVE_Iteration3.ipynb` at the repository root | `make_notebook_i3.py` |

## Iteration 2: how to run

```bash
pip install -r requirements.txt

# 1. Convert the monthly CSVs to Parquet once (data/processed/, git-ignored)
python -m loaders build

# 2. Run everything end to end on the real data: quality checks, cleaning, statistics, maps
python make_notebook.py
python -m jupyter nbconvert --execute --to notebook --inplace --ExecutePreprocessor.timeout=-1 CONVIVE_Iteration2.ipynb

# 3. Start the dashboard (local only)
streamlit run app/dashboard.py
```

Optional steps:

```bash
python run_iteration2.py            # the same pipeline as step 2, without the notebook
python app/check_dashboard.py       # checks that every filter changes every view, plus edge cases and the <15 rule
python app/take_screenshots.py      # PNG screenshots of each view (needs: playwright install chromium)
python make_delivery.py             # the delivery document
```

The data go in `data/output_limite_legal_mobilidad/YYYY-MM/` and `data/output_limite_legal_turismo/YYYYMM/`. The neighbourhood GeoJSON is found in `data/geo/` or `data/Synthetic/geo/`.

## Confidentiality rules (NDA)

- The Smart Steps data are under a signed NDA. **Never commit, push or upload anything in `data/`.** It is git-ignored.
- Everything outside `data/` must be aggregated. In exported tables, values below 15 are written as `<15` or left empty.
- The dashboard runs on `localhost` only. Do not deploy it online.
- The aggregated tables, maps and screenshots are also git-ignored, so they need a deliberate decision before being shared. They are regenerated by the steps above.

## Rules for reading the data

- Trips (M1 to M3) and unique visitors (T1 to T9) are different measures and are never mixed.
- Unique visitors are not additive across days or neighbourhoods. City totals come from T1 and T2.
- A 0 in mobility means fewer than 15 trips. `NA` in tourism groups segments below 15 people. Neither means "nobody".
- `origen` is the visitor segment, not where a trip starts. Residents appear only in mobility.
- The results describe patterns, not causes.

## Folder map

```
CONVIVE_Iteration2.ipynb     WBS 3.1.7: end-to-end notebook on the real data (built by make_notebook.py)
loaders.py                   WBS 3.1.1: CSV to Parquet, load_mobility(), load_tourism()
levels.py                    WBS 2.1.1, 2.1.2: geographic and temporal levels
quality.py                   WBS 3.1.0, 3.1.1, 3.1.2: inventory, inspection, data quality checks
cleaning.py                  WBS 3.1.3: clean Parquet and cleaning log
descriptives.py              WBS 3.1.6, 4.2.1: aggregated tables, headline numbers, standalone maps
run_iteration2.py            runs the pipeline steps
aggregates.py                WBS 2.2.1: Iteration 3 aggregated tables (pandas only)
validation.py                WBS 2.2.2: validation log of the aggregated tables
research.py                  WBS 3.2.1-3.2.4: decision rules (THRESHOLDS) and answers to Q1-Q20, low-data neighbourhoods
nationalities.py             WBS 3.2.1: nationalities of international visitors (T8): profile per country, season, neighbourhoods (LQ), world regions
research_report.py           WBS 3.2.0-3.2.4: Markdown reports, CSV tables and figures
run_iteration3.py            runs the Iteration 3 steps
make_notebook_i3.py          builds CONVIVE_Iteration3.ipynb
app/dashboard_i3.py          data logic of the Iteration 3 dashboard tabs
coexistence.py               Charter question: visitors against residents, per neighbourhood and year
sensitivity.py               robustness of the verdicts when the thresholds move
breaks.py                    level shifts in the neighbourhood series (I8)
final_outputs.py             WBS 5.2, 5.3: key findings, limitations, figures
run_final.py                 one command for the whole product
make_notebook_final.py       builds CONVIVE_Final.ipynb
make_package.py              builds the hand-over zip
tests/                       unit tests (no NDA data needed)
app/dashboard_final.py       data logic of the final tabs
make_delivery.py             builds the Iteration 2 delivery document
app/dashboard.py             WBS 4.3.2: Streamlit dashboard (dashboard_data.py holds its logic)
app/check_dashboard.py       automatic checks of the dashboard
app/hello_streamlit.py       WBS 4.1.3: minimal test page
app/make_layout_sketch.py    WBS 4.1.1: wireframe PNG
app/take_screenshots.py      screenshots of the final dashboard
deliverables/iteration2/     one output per WBS ID (see below)
convive.py                   data catalogue, load(), review(), maps
analysis.py                  analysis methods, including the cross-file checks
synthetic.py                 synthetic data generator (Iteration 1)
CONVIVE_Iteration1.ipynb     Iteration 1 notebook
data_review_plan.md          data review and cleaning plan
data/                        all data (git-ignored), with processed/ for Parquet
outputs/                     Iteration 1 figures
```

### `deliverables/iteration2/`

| WBS | Output |
|---|---|
| 2.1.1 | `2.1.1_geographic_levels.csv`, `2.1.1_geographic_levels.md` |
| 2.1.2 | `2.1.2_temporal_levels.md` |
| 3.1.0 | `3.1.0_data_inventory.md` |
| 3.1.1 | `3.1.1_inspection_summary.md` |
| 3.1.2 | `3.1.2_data_quality_report.md` |
| 3.1.3 | `3.1.3_cleaning_log.md` |
| 3.1.6 | `3.1.6_summary.md`, `3.1.6_stats/` |
| 3.1.7 | `CONVIVE_Iteration2.ipynb` at the repository root |
| 3.2.0 | `3.2.0_ResearchQuestions.md` |
| 4.1.1 | `4.1.1_dashboard_layout.md`, `4.1.1_dashboard_layout.png` |
| 4.1.3 | `4.1.3_VisualisationEnvironment.md`, `app/hello_streamlit.py` |
| 4.2.0 | `app/dashboard.py`, `4.2.0_dashboard_notes.md` |
| 4.2.1 | `4.2.1_map_visitors.html`, `4.2.1_map_visitor_share_trips.html` |
| Delivery | `CONVIVE_Iteration2_Delivery.docx`, `screenshots/` |

## Iteration 1: synthetic data

```bash
jupyter notebook CONVIVE_Iteration1.ipynb     # then "Run All" (about 1 minute)
```

The notebook runs on **synthetic data** with the same columns as the official description. **All its numbers and patterns are made up.** Because the synthetic model is known, each method is validated: we check that it recovers what was planted. On the first run it generates the synthetic files in `data/sample/`.

| § | Content | Methods |
|---|---|---|
| 1 | Data catalogue and interpretation rules | 12 files, rules from the data description |
| 2 | **Data review and cleaning** | Schema and content checks, coverage calendar, cross-file consistency, logged cleaning actions, detection of planted problems |
| 3 | **Base neighbourhood map** | 73 neighbourhoods, areas, centroids, k-nearest-neighbour spatial weights |
| 4 | When | Robust harmonic regression, event detection, same-weekday year-on-year change |
| 5 | Where | Density per km², location quotients, Gini and Lorenz curves, Moran's I and LISA hot spots, mean centre and standard distance, growth on equivalent periods |
| 6 | Neighbourhood typologies | k-means on 7 indicators, silhouette selection, PCA |
| 7 | Visitors vs residents | Gravity model corrected for the privacy threshold (censored Poisson MLE), PageRank, visitor share of arrivals |
| 8 | Coexistence Pressure Index | Composite index with a weight-sensitivity analysis |
| 9 | Who | Country seasonality and growth, length of stay |
| 10 | Traceability | Coverage of the PWP requirements RQ-01 to RQ-18, limitations, next steps |

Neighbourhood boundaries: Ajuntament de Barcelona, Open Data BCN ("Unitats administratives de la ciutat de Barcelona"), CC BY 4.0.
