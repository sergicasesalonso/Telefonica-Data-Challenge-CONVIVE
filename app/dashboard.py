"""CONVIVE dashboard. Iteration 2: preliminary dashboard (WBS 4.2.0) and interactive maps (4.2.1).
Iteration 3: charts and indicators for the quantified research questions (4.2.2) and geographic and temporal filters
applied to every view (4.2.3), in five tabs.

Run locally:  streamlit run app/dashboard.py
Data input:   only aggregated tables (deliverables/iteration2/3.1.6_stats/, deliverables/iteration3/) and the
              neighbourhood GeoJSON. Nothing leaves this computer.
"""

import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import convive as cv                  # noqa: E402
import dashboard_data as dd           # noqa: E402
import dashboard_i3 as d3             # noqa: E402

# Okabe-Ito, colour-blind safe (validated). The same colour per origin everywhere, plus legends, line markers,
# direct labels and a table under each view, so identity never depends on colour alone.
ORIGIN_COLORS = {"Internacional": "#0072B2", "Nacional": "#E69F00", "Regional": "#009E73", "Residente": "#CC79A7"}
ORIGIN_SYMBOLS = {"Internacional": "circle", "Nacional": "square", "Regional": "diamond", "Residente": "triangle-up"}
YEAR_COLORS = {2023: "#BDBDBD", 2024: "#7F7F7F", 2025: "#333333"}
SEQUENTIAL = "Purples"
DIVERGING = "RdBu"
INK, MUTED, GRID, OUTLINE = "#1f1f1f", "#5f5f5f", "#e6e6e6", "#a9a9a9"
FOOTER = "CONVIVE · Team 102_A · Dashboard, Iteration 3 · Smart Steps data supplied under NDA · aggregated, threshold 15"

st.set_page_config(page_title="CONVIVE dashboard", page_icon="🗺️", layout="wide")
st.markdown("""<style>
  .block-container {padding-top: 2.2rem; max-width: 1280px;}
  [data-testid="stMetricValue"] {font-size: 1.65rem;}
  .limit {color: #5f5f5f; font-size: 0.86rem; margin-top: -0.4rem; margin-bottom: 0.6rem;}
  .footer {color: #5f5f5f; font-size: 0.8rem; text-align: center; padding: 1rem 0 0.5rem 0;}
</style>""", unsafe_allow_html=True)


@st.cache_data(show_spinner="Loading aggregated tables…")
def load():
    return dd.load_tables()


@st.cache_data(show_spinner="Loading Iteration 3 results…")
def load_i3():
    return d3.load()


@st.cache_data
def load_geo():
    geo, _ = cv.load_barris()
    return geo


def base_layout(fig, height=360, y_title="", y_format=None):
    fig.update_layout(height=height, margin={"l": 10, "r": 10, "t": 30, "b": 10}, plot_bgcolor="white", paper_bgcolor="white",
                      font={"color": INK, "size": 13}, legend={"orientation": "h", "y": 1.12, "x": 0, "title": None},
                      hoverlabel={"bgcolor": "white"})
    fig.update_xaxes(showgrid=False, linecolor="#9a9a9a", tickfont={"color": MUTED})
    fig.update_yaxes(gridcolor=GRID, zeroline=False, rangemode="tozero", title=y_title, tickfont={"color": MUTED}, tickformat=y_format)
    return fig


def choropleth(frame, value, colorbar, hover, colorscale=SEQUENTIAL, tick=None, zmid=None, height=520, zlimits=(None, None), zoom=10.6):
    """Grey base layer for all 73 neighbourhoods, so a neighbourhood without a value is visibly 'no value'.

    Choroplethmap with the blank "white-bg" style needs no map tiles or basemap file, so it makes no external
    requests and works without internet. The older go.Choropleth fetches a basemap and draws nothing offline.
    """
    geo = load_geo()
    codes = [f["properties"]["cod_barrio_ss"] for f in geo["features"]]
    fig = go.Figure(go.Choroplethmap(geojson=geo, locations=codes, z=[0] * len(codes), featureidkey="properties.cod_barrio_ss",
                                     colorscale=[[0, "#ececec"], [1, "#ececec"]], showscale=False, hoverinfo="skip",
                                     marker={"opacity": 1, "line": {"color": OUTLINE, "width": 0.6}}))
    shown = frame.dropna(subset=[value])
    fig.add_trace(go.Choroplethmap(geojson=geo, locations=shown["cod_barrio"], z=shown[value], featureidkey="properties.cod_barrio_ss",
                                   colorscale=colorscale, zmid=zmid, zmin=zlimits[0], zmax=zlimits[1],
                                   marker={"opacity": 1, "line": {"color": OUTLINE, "width": 0.6}},
                                   colorbar={"title": colorbar, "tickformat": tick, "thickness": 14},
                                   customdata=shown[["barrio_name", "distrito_name"]], hovertemplate=hover))
    fig.update_layout(height=height, margin={"l": 0, "r": 0, "t": 5, "b": 0}, paper_bgcolor="white",
                      map={"style": "white-bg", "center": cv.map_center(geo), "zoom": zoom})
    return fig


def view_header(title, limitation):
    st.subheader(title)
    st.markdown(f'<div class="limit">Limitation: {limitation}</div>', unsafe_allow_html=True)


def top_columns(value_column):
    """Fixed widths, so the value column stays visible next to the map."""
    return {"#": st.column_config.NumberColumn(width=30),
            "Neighbourhood": st.column_config.TextColumn(width=225),
            "District": st.column_config.TextColumn(width=125),
            value_column: st.column_config.TextColumn(width=85)}


def show(fig, key):
    st.plotly_chart(fig, width="stretch", key=key, config={"displaylogo": False, "scrollZoom": False})


tables = load()

# ------------------------------------------------------------------------------------------------
# Sidebar: general filters
# ------------------------------------------------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    st.caption("They apply to every view. The limitation under each title says when a filter cannot apply.")
    years = st.multiselect("Year", [2023, 2024, 2025], default=[2023, 2024, 2025], key="f_years")
    month_from, month_to = st.select_slider("Month range", options=list(range(1, 13)), value=(1, 12),
                                            format_func=lambda m: dd.MONTHS[m - 1], key="f_months")
    origins = st.multiselect("Visitor origin", dd.TRIP_ORIGINS, default=dd.VISITOR_ORIGINS, key="f_origins",
                             help="Residente exists only in trips, so it affects only the trips view (Q6).")
    types = st.multiselect("Visitor type", dd.VISITOR_TYPES, default=dd.VISITOR_TYPES, key="f_types",
                           help="Mobility data have no visitor type, so this does not affect the trips view (Q6).")
    day_type = st.radio("Days", dd.DAY_TYPES, index=0, key="f_days", horizontal=False,
                        help="Applies to the daily views (Q4) and to trips (Q6). Monthly files have no day detail.")
    st.subheader("Area")
    lookup = dd.barrio_lookup(tables)
    districts = st.multiselect("District", sorted(lookup["distrito_name"].unique()), key="f_districts",
                               help="Empty = the whole city.")
    choices = lookup[lookup["distrito_name"].isin(districts)] if districts else lookup
    barrios = st.multiselect("Neighbourhood", choices["barrio_name"].tolist(), key="f_barrios",
                             help="Empty = every neighbourhood of the selected districts.")
    st.divider()
    st.caption("2025 covers January to August. Regional visitors are always excursionists. With an area selected, "
               "visitor views use neighbourhood files and show presences (a person in two selected neighbourhoods counts twice).")

f = dd.Filters(sorted(years), month_from, month_to, origins, types, day_type, dd.area_codes(lookup, districts, barrios))
i3 = load_i3()

# ------------------------------------------------------------------------------------------------
# Header
# ------------------------------------------------------------------------------------------------
st.title("CONVIVE · Visitors and residents in Barcelona")
period = f"{dd.MONTHS[month_from - 1]} to {dd.MONTHS[month_to - 1]}" if month_from != month_to else dd.MONTHS[month_from - 1]
area_text = (", ".join(barrios) if barrios else ", ".join(districts)) if f.has_area else "whole city"
st.markdown(f"Iteration 3 dashboard · **{period}**, **{', '.join(map(str, f.years)) or 'no year selected'}** · "
            f"origin: **{', '.join(f.origins) or 'none'}** · type: **{', '.join(f.types) or 'none'}** · "
            f"days: **{f.day_type.lower()}** · area: **{area_text}**")

MEASURE = dd.measure_label(f)
Y_MONTH = "Presences per month (selected area)" if f.has_area else "Unique visitors per month"
Y_DAY = "Mean presences per day (selected area)" if f.has_area else "Mean unique visitors per day"

tab_q, tab_rq, tab_explore, tab_who, tab_nat, tab_quality = st.tabs(
    ["Q1–Q6 views", "Research answers Q1–Q20", "Neighbourhood explorer", "Who visits", "Nationalities", "Data quality"])

with tab_q:
    with st.expander("How to read this", expanded=True):
        st.markdown("""
- **Unique visitors** (Q1 to Q5) count people in a place and period. They cannot be added across months or neighbourhoods. A longer period is shown as a **monthly average**.
- **Trips** (Q6) count journeys between neighbourhoods. One person can make several. Trips and visitors are never combined.
- **0 or NA never means nobody:** below 15, a value is hidden for privacy and reads `<15`.
- With a district or neighbourhood selected, visitor views add up neighbourhoods and show **presences**, not people.
- The results describe **patterns, not causes**.
""")

    no_years = not f.years
    no_visitors = no_years or not f.visitor_origins or not f.types
    if no_years:
        st.warning("Select at least one year.")
    elif no_visitors:
        st.warning("The visitor views need at least one visitor origin (Internacional, Nacional or Regional) and one visitor type. The trips view (Q6) is still available below.")
    elif dd.kpis(tables, f) is None:
        no_visitors = True
        st.warning("This combination has no visitors in the data. Regional visitors are always excursionists, so Regional + Turista is empty. The trips view (Q6) is still available below.")
    gaps =dd.incomplete_months(tables, f) if not no_years else []
    if gaps:
        st.caption(f"Months with one missing day in the source, flagged and not imputed: {', '.join(gaps)}.")

    # ------------------------------------------------------------------------------------------------
    # Q3 KPI tiles
    # ------------------------------------------------------------------------------------------------
    if not no_visitors:
        with st.container(border=True):
            k = dd.kpis(tables, f)
            view_header("Q3 · Who visits? " + ("Presences in the selected area" if f.has_area else "Unique visitors") + " and their composition",
                        "regional visitors are always excursionists by definition, which raises the excursionist share.")
            if k is None:
                st.info("No visitor data for this selection.")
            else:
                label = (f"{MEASURE.capitalize()} in {k['single_month']}" if k["single_month"] else f"Monthly average ({k['n_months']} months)")
                columns = st.columns(5)
                columns[0].metric(label, dd.format_count(k["visitors"]))
                for column, origin in zip(columns[1:4], dd.VISITOR_ORIGINS):
                    value = k["origin_share"].get(origin)
                    column.metric(f"{origin} share", f"{value:.1%}" if value is not None else "not selected")
                columns[4].metric("Tourist share", f"{k['tourist_share']:.1%}")
                if not k["single_month"]:
                    st.caption("Several months are selected, so the first tile is a monthly average, never a sum of months. "
                               + ("With an area selected it comes from T4 and counts presences (a person in two selected neighbourhoods counts twice). "
                                  if f.has_area else "It comes from T1 (city unique visitors). ")
                               + "Shares are within the current selection.")
                segments = dd.segments_by_month(tables, f)
                fig = go.Figure()
                for (origin, tipo), g in segments.groupby(["origen", "tipo_visitante"], sort=False):
                    fig.add_bar(x=pd.to_datetime(g["mes"], format="%Y%m"), y=g["visitantes"], name=f"{origin} · {tipo}",
                                marker={"color": ORIGIN_COLORS[origin], "pattern": {"shape": "/" if tipo == "Excursionista" else ""},
                                        "line": {"color": "white", "width": 1}},
                                hovertemplate=f"{origin} · {tipo}<br>%{{x|%b %Y}}: %{{y:,.0f}}<extra></extra>")
                fig.update_layout(barmode="stack", bargap=0.25)
                show(base_layout(fig, 340, Y_MONTH, ",.0f"), "q3_bars")
                with st.expander("Table"):
                    st.dataframe(segments.assign(visitantes=segments["visitantes"].map(dd.format_count)), hide_index=True, width="stretch")

        # --------------------------------------------------------------------------------------------
        # Q2 and Q5
        # --------------------------------------------------------------------------------------------
        with st.container(border=True):
            view_header("Q2 · How does the number of visitors change from month to month, by origin?",
                        "2025 covers January to August only. Monthly values of months with a missing day are flagged above.")
            evolution = dd.monthly_evolution(tables, f)
            fig = go.Figure()
            for origin in dd.VISITOR_ORIGINS:
                g = evolution[evolution["origen"] == origin]
                if g.empty:
                    continue
                fig.add_scatter(x=g["date"], y=g["visitantes"], name=origin, mode="lines+markers",
                                line={"color": ORIGIN_COLORS[origin], "width": 2},
                                marker={"color": ORIGIN_COLORS[origin], "size": 8, "symbol": ORIGIN_SYMBOLS[origin], "line": {"color": "white", "width": 1}},
                                hovertemplate=f"{origin}<br>%{{x|%b %Y}}: %{{y:,.0f}}<extra></extra>")
                last = g.dropna(subset=["visitantes"]).iloc[-1]
                fig.add_annotation(x=last["date"], y=last["visitantes"], text=origin, showarrow=False, xanchor="left", xshift=9,
                                   font={"color": INK, "size": 12})
            base_layout(fig, 360, Y_MONTH, ",.0f")
            fig.update_xaxes(tickformat="%b %Y", hoverformat="%b %Y")
            fig.update_layout(margin={"r": 95})
            show(fig, "q2_lines")
            ratio = dd.peak_to_trough(evolution)
            with st.expander("Table: peak-to-trough ratio per origin and year"):
                st.dataframe(ratio, hide_index=True, width="stretch")

        with st.container(border=True):
            view_header("Q5 · Did visitors grow between equivalent periods?",
                        "only months present in every selected year are compared, as a mean per month. Very small neighbourhood bases are left out of the change map.")
            yoy, months = dd.yoy_city(tables, f)
            if len(f.years) < 2:
                st.info("Select at least two years to compare equivalent months.")
            elif yoy.empty:
                st.info("The selected years have no month in common. 2025 stops in August, so choose months up to August, or remove 2025.")
            else:
                st.caption("Equivalent months compared: " + ", ".join(dd.MONTHS[m - 1] for m in months))
                left, right = st.columns([1, 1])
                with left:
                    fig = go.Figure()
                    for year, g in yoy.groupby("year"):
                        labels = [("" if pd.isna(c) else f"{c:+.1%}") for c in g["change_vs_previous_year"]]
                        fig.add_bar(x=g["origen"], y=g["mean_monthly_visitors"], name=str(year), marker={"color": YEAR_COLORS[year]},
                                    text=labels, textposition="outside", textfont={"size": 11, "color": INK}, cliponaxis=False,
                                    hovertemplate=f"%{{x}} · {year}<br>%{{y:,.0f}} per month<extra></extra>")
                    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.06)
                    show(base_layout(fig, 420, "Mean unique visitors per month", ",.0f"), "q5_bars")
                    st.caption("Labels: change against the previous selected year.")
                table, first, last = dd.yoy_barrio(tables, f)
                with right:
                    if first is not None and first != last and table["change"].notna().any():
                        st.markdown(f"**Change per neighbourhood, {first} to {last}**")
                        fig = choropleth(table, "change", "Change", "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{z:+.1%}<extra></extra>",
                                         colorscale=DIVERGING, tick="+.0%", height=400, zlimits=(-0.5, 0.5), zoom=10.2)
                        show(fig, "q5_map")
                        st.caption("Colours stop at ±50%. Hover or see the table for the exact change. Grey: base below 1,000 visitors per month.")
                if first is not None and table["change"].notna().any():
                    ordered = table.dropna(subset=["change"]).sort_values("change", ascending=False)
                    ordered = ordered.assign(change=ordered["change"].map("{:+.1%}".format), base=ordered["base"].map(dd.format_count),
                                             latest=ordered["latest"].map(dd.format_count))
                    ordered = ordered[["barrio_name", "distrito_name", "base", "latest", "change"]].rename(
                        columns={"barrio_name": "Neighbourhood", "distrito_name": "District", "base": f"Per month, {first}", "latest": f"Per month, {last}", "change": "Change"})
                    with st.expander("Table: change per neighbourhood"):
                        st.dataframe(ordered, hide_index=True, width="stretch")

        # --------------------------------------------------------------------------------------------
        # Q4
        # --------------------------------------------------------------------------------------------
        with st.container(border=True):
            view_header("Q4 · Are daily visitors higher at weekends than on weekdays?",
                        "means per day. Daily values cannot be summed into weekly totals.")
            pattern = dd.weekday_pattern(tables, f)
            fig = go.Figure()
            for origin in dd.VISITOR_ORIGINS:
                g = pattern[pattern["origen"] == origin]
                if len(g):
                    fig.add_bar(x=g["weekday"].map(dd.WEEKDAYS_EN), y=g["mean_visitors"], name=origin, marker={"color": ORIGIN_COLORS[origin]},
                                customdata=g[["median_visitors", "n_days"]],
                                hovertemplate=f"{origin} · %{{x}}<br>Mean %{{y:,.0f}}<br>Median %{{customdata[0]:,.0f}}<br>%{{customdata[1]}} days<extra></extra>")
            fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06)
            fig.update_xaxes(categoryorder="array", categoryarray=list(dd.WEEKDAYS_EN.values()))
            show(base_layout(fig, 340, Y_DAY, ",.0f"), "q4_bars")
            difference = dd.weekend_difference(tables, f)
            if difference:
                st.caption("Weekend days against weekdays, mean per day: " + " · ".join(f"{o} {v:+.1%}" for o, v in difference.items()))
            with st.expander("Table"):
                st.dataframe(pattern.assign(weekday=pattern["weekday"].map(dd.WEEKDAYS_EN)).drop(columns="weekday_idx").round(0), hide_index=True, width="stretch")

        # --------------------------------------------------------------------------------------------
        # Q1
        # --------------------------------------------------------------------------------------------
        with st.container(border=True):
            view_header("Q1 · How concentrated are visitors across the 73 neighbourhoods?",
                        "neighbourhood values are not additive, because a person can visit several. The top-10 figure is a share of the ranking, not of the city total.")
            values = dd.barrio_values(tables, f)
            c = dd.concentration(values)
            left, right = st.columns([1, 1])
            with left:
                show(choropleth(values, "visitantes", "Visitors per month", "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{z:,.0f} visitors per month<extra></extra>"), "q1_map")
            with right:
                a, b = st.columns(2)
                a.metric("Top 10, share of ranking", f"{c['top10_share']:.1%}")
                b.metric("Gini across neighbourhoods", f"{c['gini']:.3f}")
                top = values.head(10).reset_index(drop=True)
                top = pd.DataFrame({"#": top.index + 1, "Neighbourhood": top["barrio_name"], "District": top["distrito_name"],
                                    "Per month": top["visitantes"].map(dd.format_count)})
                st.dataframe(top, hide_index=True, width="stretch", height=390, column_config=top_columns("Per month"))

    # ------------------------------------------------------------------------------------------------
    # Q6 (trips)
    # ------------------------------------------------------------------------------------------------
    if not no_years:
        with st.container(border=True):
            view_header("Q6 · Trips, not people: share of incoming trips by the selected origins",
                        "trips, not people. Trips inside a neighbourhood are excluded and flows below 15 appear as 0. Mobility data have no visitor type, so that filter does not apply here.")
            share = dd.trip_share(tables, f)
            if share.empty:
                st.info("Select at least one origin.")
            else:
                is_default = set(f.origins) == set(dd.VISITOR_ORIGINS)
                label = "Visitor share of trips" if is_default else "Selected origins, share of trips"
                left, right = st.columns([1, 1])
                with left:
                    show(choropleth(share, "share", "Share of trips", "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{z:.1%} of incoming trips<extra></extra>", tick=".0%"), "q6_map")
                with right:
                    a, b = st.columns(2)
                    a.metric(label, f"{dd.city_trip_share(share):.1%}")
                    b.metric("Neighbourhoods above 50%", f"{int((share['share'] > 0.5).sum())} of {len(share)}")
                    top = share.head(10).reset_index(drop=True)
                    top = pd.DataFrame({"#": top.index + 1, "Neighbourhood": top["barrio_name"], "District": top["distrito_name"],
                                        "Share": top["share"].map("{:.1%}".format)})
                    st.dataframe(top, hide_index=True, width="stretch", height=390, column_config=top_columns("Share"))
                st.caption(f"Selected: {', '.join(f.origins)}. The denominator always includes all four origins, residents among them.")

# ------------------------------------------------------------------------------------------------
# Iteration 3 (4.2.2): research answers with their decision rule and verdict
# ------------------------------------------------------------------------------------------------
HOLDS_ICON = {"Yes": "✅ Yes", "No": "❌ No", "Partly": "◐ Partly"}


with tab_rq:
    if not d3.available(i3):
        st.info("Run `python research_report.py` to build the Iteration 3 results.")
    else:
        answers = i3["answers"]
        st.subheader("Each question has a metric, a decision rule fixed in advance, an answer and a verdict")
        st.markdown('<div class="limit">Business Manager feedback of 9 Nov: every question must be quantified with an explicit threshold. '
                    'The rule decides the verdict, not the number. Q1–Q6 were shown at the Iteration 2 demo; Q7–Q20 are new in Iteration 3 (Q18–Q20: nationalities).</div>',
                    unsafe_allow_html=True)
        counts = answers["belief_holds"].value_counts()
        a, b, c, d = st.columns(4)
        a.metric("Questions answered", f"{len(answers)} of {len(answers)}")
        b.metric("Belief holds", int(counts.get("Yes", 0)))
        c.metric("Belief does not hold", int(counts.get("No", 0)))
        d.metric("Partly", int(counts.get("Partly", 0)))
        overview = answers[["id", "belief", "belief_holds", "verdict"]].rename(
            columns={"id": "ID", "belief": "Common belief", "belief_holds": "Holds?", "verdict": "Verdict from the data (decision rule applied)"})
        overview["Holds?"] = overview["Holds?"].map(HOLDS_ICON)
        st.dataframe(overview, hide_index=True, width="stretch", height=640,
                     column_config={"ID": st.column_config.TextColumn(width=45), "Holds?": st.column_config.TextColumn(width=85),
                                    "Common belief": st.column_config.TextColumn(width=330)})
        st.divider()
        options = [f"{r.id} · {r.question}" for r in answers.itertuples()]
        choice = st.selectbox("Question in detail", options, key="rq_choice")
        row = answers.iloc[options.index(choice)]
        with st.container(border=True):
            st.markdown(f"#### {row['id']} · {row['question']}")
            st.markdown(f"**Belief tested:** “{row['belief']}”  \n**Data:** {row['data']} · **Metric:** {row['metric']}")
            st.info(f"**Decision rule.** {row['decision_rule']}")
            st.markdown(f"**Answer.** {row['answer']}")
            message = f"**Verdict: {row['verdict']}.** Does the belief hold? **{row['belief_holds']}**"
            if row["belief_holds"] == "Yes":
                st.success(message)
            elif row["belief_holds"] == "No":
                st.error(message)
            else:
                st.warning(message)
            st.markdown(f'<div class="limit">Limitation: {row["limitation"]}</div>', unsafe_allow_html=True)
            figure = {"Q1": "q1_concentration", "Q2": "q2_seasonality", "Q3": "q3_origin_countries", "Q4": "q4_weekend_barrios",
                      "Q5": "q5_growth", "Q6": "q6_tourist_barris", "Q7": "q7_nights", "Q8": "q8_rank_season", "Q9": "q9_unusual_days",
                      "Q10": "q10_lq_maps", "Q11": "q3_origin_countries", "Q12": "q12_q13_residence", "Q13": "q12_q13_residence",
                      "Q14": "q14_profile", "Q15": "q15_rhythm", "Q16": "q1_concentration", "Q17": "q17_country_growth",
                      "Q18": "nat_season_heatmap", "Q19": "nat_lq_maps", "Q20": "nat_markets"}.get(row["id"])
            path = d3.FIGURES / f"{figure}.png"
            if figure and path.exists():
                st.image(str(path), width="stretch")
            st.caption("These answers use the whole period (Jan 2023–Aug 2025) and are not affected by the sidebar filters. "
                       "The Q1–Q6 views and the other tabs follow the filters.")

# ------------------------------------------------------------------------------------------------
# Iteration 3 (4.2.3): neighbourhood explorer
# ------------------------------------------------------------------------------------------------
with tab_explore:
    if not d3.available(i3) or no_years or not f.visitor_origins or not f.types:
        st.info("Select at least one year, one visitor origin and one visitor type, and run `python research_report.py`.")
    else:
        pool = lookup[lookup["cod_barrio"].isin(f.area)] if f.has_area else lookup
        names = pool["barrio_name"].tolist()
        default = names.index("el Barri Gòtic") if "el Barri Gòtic" in names else 0
        name = st.selectbox("Neighbourhood (limited to the area chosen in the sidebar)", names, index=default, key="ex_barrio")
        code = pool.loc[pool["barrio_name"] == name, "cod_barrio"].iloc[0]
        e = d3.explorer(i3, tables, code, f)
        st.subheader(f"{e['name']} · {pool.loc[pool['cod_barrio'] == code, 'distrito_name'].iloc[0]}")
        if e["low_data"]:
            st.warning(f"Low-data neighbourhood ({e['low_reason']}). Read its values with care: see the Data quality tab (issue I8).")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Visitors per month (mean)", dd.format_count(e["mean_monthly"]))
        k2.metric("Rank among 73", f"{int(e['rank'])}" if e["rank"] is not None and not pd.isna(e["rank"]) else "n/a")
        k3.metric("Visitor share of incoming trips", f"{e['visitor_share']:.1%}" if e["visitor_share"] is not None else "n/a")
        if e["lq"] is not None:
            top_origin = e["lq"].idxmax()
            k4.metric("Most over-represented origin (LQ)", f"{top_origin} {e['lq'].max():.2f}")
        left, right = st.columns(2)
        with left:
            fig = go.Figure()
            for origin in dd.VISITOR_ORIGINS:
                g = e["series"][e["series"]["origen"] == origin]
                if len(g):
                    fig.add_scatter(x=g["date"], y=g["visitantes"], name=origin, mode="lines+markers",
                                    line={"color": ORIGIN_COLORS[origin], "width": 2},
                                    marker={"color": ORIGIN_COLORS[origin], "size": 7, "symbol": ORIGIN_SYMBOLS[origin]},
                                    hovertemplate=f"{origin}<br>%{{x|%b %Y}}: %{{y:,.0f}}<extra></extra>")
            fig.update_xaxes(tickformat="%b %Y")
            st.markdown("**Unique visitors per month, by origin (T4)**")
            show(base_layout(fig, 320, "Unique visitors per month", ",.0f"), "ex_series")
        with right:
            st.markdown("**Mean daily visitors by weekday (T5)**")
            if e["weekday"] is not None:
                fig = go.Figure()
                for origin in dd.VISITOR_ORIGINS:
                    g = e["weekday"][e["weekday"]["origen"] == origin]
                    if len(g):
                        fig.add_bar(x=[dd.WEEKDAYS_EN[dd.WEEKDAYS[i]] for i in g["weekday_idx"]], y=g["visitantes"], name=origin,
                                    marker={"color": ORIGIN_COLORS[origin]}, hovertemplate=f"{origin} · %{{x}}: %{{y:,.0f}}<extra></extra>")
                fig.update_layout(barmode="group", bargap=0.25)
                show(base_layout(fig, 320, "Mean visitors per day", ",.0f"), "ex_weekday")
        left, right = st.columns(2)
        with left:
            st.markdown("**Incoming trips by origin (M1)**")
            tb = e["trip_by_origin"].reindex(dd.TRIP_ORIGINS).fillna(0)
            fig = go.Figure(go.Bar(x=tb.values, y=tb.index, orientation="h", marker={"color": [ORIGIN_COLORS[o] for o in tb.index]},
                                   text=[f"{v / tb.sum():.1%}" if tb.sum() else "" for v in tb.values], textposition="outside",
                                   hovertemplate="%{y}: %{x:,.0f} trips<extra></extra>", cliponaxis=False))
            fig = base_layout(fig, 260, "", None)
            fig.update_xaxes(tickformat=",.0f")
            show(fig, "ex_trips")
            st.caption("Trips, not people. Published zeros (fewer than 15 trips) add nothing.")
        with right:
            st.markdown("**Top countries of international visitors (T8, mean per month)**")
            c = e["countries"]
            if len(c):
                st.dataframe(pd.DataFrame({"Country": c.index, "Visitors per month": c.map(dd.format_count).values}),
                             hide_index=True, width="stretch", height=320)
            else:
                st.info("No country above the privacy threshold for this selection.")

# ------------------------------------------------------------------------------------------------
# Iteration 3 (4.2.2): who visits - countries, provinces, municipalities, profile
# ------------------------------------------------------------------------------------------------
with tab_who:
    if not d3.available(i3) or no_years:
        st.info("Select at least one year, and run `python research_report.py`.")
    else:
        st.markdown('<div class="limit">Shares of presences: each neighbourhood visit of a person counts once, so the shares are of '
                    'presences, not of people. Period filters apply; the area filter does not (city view).</div>', unsafe_allow_html=True)
        which = st.radio("Place of residence", list(d3.RESIDENCE), horizontal=True, key="who_level")
        ranking = d3.residence_ranking(i3, which, f, tipo=f.types)
        if ranking.empty:
            st.info("No data for this selection.")
        else:
            left, right = st.columns([1, 1])
            colour = {"Country (international, T8)": ORIGIN_COLORS["Internacional"], "Province (national, T7)": ORIGIN_COLORS["Nacional"],
                      "Municipality (regional, T6)": ORIGIN_COLORS["Regional"]}[which]
            with left:
                r15 = ranking.iloc[::-1]
                fig = go.Figure(go.Bar(x=r15["share"], y=r15["place"], orientation="h", marker={"color": colour},
                                       text=r15["share"].map("{:.1%}".format), textposition="outside", cliponaxis=False,
                                       hovertemplate="%{y}: %{x:.1%} of presences<extra></extra>"))
                fig = base_layout(fig, 470, "", None)
                fig.update_xaxes(tickformat=".0%")
                st.markdown(f"**Top 15 · {which}**")
                show(fig, "who_rank")
            with right:
                top5 = ranking["place"].head(5).tolist()
                trend = d3.residence_trend(i3, which, top5, tipo=f.types)
                fig = go.Figure()
                for i, place in enumerate(top5):
                    g = trend[trend["place"] == place]
                    fig.add_scatter(x=g["date"], y=g["share"], name=place, mode="lines",
                                    line={"width": 2, "color": ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#555555"][i],
                                          "dash": ["solid", "dash", "dot", "dashdot", "longdash"][i]},
                                    hovertemplate=f"{place}<br>%{{x|%b %Y}}: %{{y:.1%}}<extra></extra>")
                fig = base_layout(fig, 470, "Share of presences", ".0%")
                fig.update_xaxes(tickformat="%b %Y")
                st.markdown("**Monthly share of the top 5, whole period**")
                show(fig, "who_trend")
        st.divider()
        st.markdown("**Visitor profile (T9): age and income of national and regional visitors**")
        st.caption("T9 has no international visitors (issue I9), so the international filter has no effect here.")
        left, right = st.columns(2)
        for column, dimension, order, title in [(left, "edad", ["18-29", "30-39", "40-49", "50-59", "60-69", "70+"], "Age group"),
                                                (right, "nivel_renta", ["Bajo", "Medio", "Medio-Alto", "Alto"], "Income level")]:
            with column:
                prof = d3.profile(i3, f, dimension)
                if prof.empty:
                    st.info("Select national or regional visitors.")
                    continue
                fig = go.Figure()
                for origin in ["Nacional", "Regional"]:
                    g = prof[prof["origen"] == origin].set_index(dimension).reindex(order)
                    if g["share"].notna().any():
                        fig.add_bar(x=order, y=g["share"], name=origin, marker={"color": ORIGIN_COLORS[origin]},
                                    hovertemplate=f"{origin} · %{{x}}: %{{y:.1%}}<extra></extra>")
                fig.update_layout(barmode="group", bargap=0.25, title={"text": title, "font": {"size": 14}})
                show(base_layout(fig, 320, "Share of presences", ".0%"), f"who_{dimension}")

# ------------------------------------------------------------------------------------------------
# Iteration 3 (4.2.2): nationalities of international visitors (T8)
# ------------------------------------------------------------------------------------------------
with tab_nat:
    if not d3.available(i3) or no_years or i3["t8_city"] is None:
        st.info("Select at least one year, and run `python research_report.py`.")
    else:
        st.markdown('<div class="limit">Country of residence of international visitors (T8). Shares are of presences (person × neighbourhood), '
                    'not of people. Year, month and visitor-type filters apply; the area filter applies to the neighbourhood table. '
                    'Countries with fewer than 15 people in a neighbourhood are grouped by Telefónica as NA and left out.</div>',
                    unsafe_allow_html=True)
        ranking = d3.country_ranking(i3, f)
        if ranking.empty:
            st.info("No international visitors for this selection.")
        else:
            countries = ranking["country"].tolist()
            country = st.selectbox("Country of residence", countries, index=0, key="nat_country",
                                   format_func=lambda c: f"{c} ({ranking.set_index('country').loc[c, 'share']:.1%})")
            k = d3.country_card(i3, f, country, ranking)
            st.markdown(f"### {country} · {k['region']}")
            a, b, c, d, e = st.columns(5)
            a.metric("Share of international presences", f"{k['share']:.1%}", help="Selected years, months and visitor types.")
            b.metric("Rank among countries", f"{k['rank']} of {len(ranking)}")
            c.metric("Overnight tourists", f"{k['tourist_share']:.0%}" if pd.notna(k["tourist_share"]) else "–",
                     help="Share of the country's presences that are 'Turista' (at least one night). The rest are day-trippers.")
            d.metric("Jan–Aug 2023→2025", f"{k['growth_23_25']:+.0%}" if pd.notna(k["growth_23_25"]) else "–",
                     help="Change in January–August presences (equivalent months). Whole period, not affected by the filters.")
            e.metric("Peak month", k["peak_month"] or "–", help=f"Summer (Jun–Aug) / other months: {k['summer_ratio']:.2f}x (2023–2024).")
            left, right = st.columns([1.15, 1])
            with left:
                st.markdown("**Presences per month, overnight tourists and day-trippers**")
                series = d3.country_monthly(i3, f, country)
                fig = go.Figure()
                for tipo, colour, dash, label in [("Turista", "#0072B2", "solid", "Overnight tourists"), ("Excursionista", "#56B4E9", "dash", "Day-trippers")]:
                    if tipo in series:
                        fig.add_scatter(x=series.index, y=series[tipo], name=label, mode="lines+markers",
                                        line={"color": colour, "width": 2, "dash": dash}, marker={"size": 5},
                                        hovertemplate=f"{label}<br>%{{x|%b %Y}}: %{{y:,.0f}} presences<extra></extra>")
                fig = base_layout(fig, 330, "Presences per month")
                fig.update_xaxes(tickformat="%b %Y")
                show(fig, "nat_month")
            with right:
                st.markdown("**Seasonal index (mean month = 100), 2023–2024**")
                season = d3.country_season(i3, country)
                fig = go.Figure(go.Bar(x=season["month"], y=season["index"], marker={"color": ["#0072B2" if m in ("Jun", "Jul", "Aug") else "#9ab7d3" for m in season["month"]]},
                                       text=season["index"].round(0).astype(int), textposition="outside", cliponaxis=False,
                                       hovertemplate="%{x}: %{y:.0f}<extra></extra>"))
                fig.add_hline(y=100, line={"color": MUTED, "width": 1, "dash": "dot"})
                show(base_layout(fig, 330, "Index"), "nat_season")
            st.markdown(f"**Where {country} visitors are: location quotient by neighbourhood** "
                        "(share of the neighbourhood in this country's presences ÷ its share in all international presences; 1 = same mix)")
            lq = d3.country_lq(i3, f, country)
            left, right = st.columns([0.95, 1.15])
            with left:
                frame = lq[lq["reliable"]].assign(lq_shown=lambda x: x["lq"].clip(upper=2.5))
                show(choropleth(frame, "lq_shown", "LQ", "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>LQ %{z:.2f}<extra></extra>",
                                colorscale=[[0, "#2166ac"], [0.318, "#f7f7f7"], [1, "#b2182b"]], zlimits=(0.3, 2.5), height=470), "nat_map")
                st.caption("Grey: fewer than 1,000 presences per month of this country (ratio not stable). Colour capped at 2.5.")
            with right:
                top = lq.sort_values("mean_monthly", ascending=False)
                if f.has_area:
                    top = top[top["cod_barrio"].isin(f.area)]
                table = top.head(15)[["barrio_name", "distrito_name", "mean_monthly", "share_of_country", "lq"]].copy()
                table["mean_monthly"] = table["mean_monthly"].map(dd.format_count)
                table["share_of_country"] = table["share_of_country"].map("{:.1%}".format)
                table["lq"] = table["lq"].map("{:.2f}".format)
                st.dataframe(table.rename(columns={"barrio_name": "Neighbourhood", "distrito_name": "District", "mean_monthly": "Presences/month",
                                                   "share_of_country": "Share of country", "lq": "LQ"}), hide_index=True, width="stretch", height=470,
                             column_config={"Neighbourhood": st.column_config.TextColumn(width=210), "District": st.column_config.TextColumn(width=110),
                                            "LQ": st.column_config.TextColumn(width=50)})
        st.divider()
        st.markdown("**All nationalities (whole period): every indicator of the analysis (3.2.1, Q18–Q20)**")
        prof = i3.get("nat_profile")
        if prof is not None:
            view = prof[["rank", "country", "region", "share", "tourist_share", "growth_23_25", "summer_ratio", "peak_month", "top_barrio",
                         "distinctive_barrio", "distinctive_lq", "overlap_int_top10"]].head(60).copy()
            st.dataframe(view.rename(columns={"rank": "#", "country": "Country", "region": "Region", "share": "Share", "tourist_share": "Overnight",
                                              "growth_23_25": "Jan–Aug 23→25", "summer_ratio": "Summer / rest", "peak_month": "Peak",
                                              "top_barrio": "First neighbourhood", "distinctive_barrio": "Most over-represented",
                                              "distinctive_lq": "LQ", "overlap_int_top10": "Top-10 overlap"}),
                         hide_index=True, width="stretch", height=380,
                         column_config={"Share": st.column_config.NumberColumn(format="percent"),
                                        "Overnight": st.column_config.NumberColumn(format="percent"),
                                        "Jan–Aug 23→25": st.column_config.NumberColumn(format="percent"),
                                        "Summer / rest": st.column_config.NumberColumn(format="%.2f"),
                                        "LQ": st.column_config.NumberColumn(format="%.2f")})
        reg = i3.get("nat_regions")
        if reg is not None:
            st.markdown("**World regions, January–August share of international presences**")
            fig = go.Figure()
            for year, colour in [(2023, "#BDBDBD"), (2024, "#7F7F7F"), (2025, "#333333")]:
                fig.add_bar(x=reg["region"], y=reg[f"share_jan_aug_{year}"], name=f"Jan–Aug {year}", marker={"color": colour},
                            hovertemplate=f"%{{x}} · {year}: %{{y:.1%}}<extra></extra>")
            fig.update_layout(barmode="group", bargap=0.25)
            show(base_layout(fig, 340, "Share of international presences", ".0%"), "nat_regions")

# ------------------------------------------------------------------------------------------------
# Iteration 3: data quality - low-data neighbourhoods (I8) and validation log (2.2.2)
# ------------------------------------------------------------------------------------------------
with tab_quality:
    if not d3.available(i3):
        st.info("Run `python research_report.py` and `python validation.py`.")
    else:
        low = i3["low_data"]
        flagged = low[low["low_data"]]
        st.subheader(f"Neighbourhoods with very few data: {len(flagged)} of 73 (issue I8)")
        st.markdown('<div class="limit">Rule: mean monthly visitors below 10% of the median neighbourhood, or more than 15% of the rows of '
                    'T6–T8 grouped as NA by the privacy threshold. Residents\' trips (M1) show whether people move there normally.</div>',
                    unsafe_allow_html=True)
        left, right = st.columns([1, 1])
        with left:
            frame = low.rename(columns={"cod_barrio": "cod_barrio"}).assign(ratio=low["vs_median"])
            show(choropleth(frame, "ratio", "vs median", "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{z:.1%} of the median neighbourhood<extra></extra>",
                            tick=".0%", zlimits=(0, 2), height=470), "dq_map")
            st.caption("Colour stops at 200% of the median so the low end stays readable.")
        with right:
            table = flagged[["barrio_name", "distrito_name", "mean_monthly_visitors", "vs_median", "resident_trips_vs_median",
                             "visitor_share_trips", "reason"]].copy()
            table["mean_monthly_visitors"] = table["mean_monthly_visitors"].map(dd.format_count)
            table["vs_median"] = table["vs_median"].map("{:.1%}".format)
            table["resident_trips_vs_median"] = table["resident_trips_vs_median"].map("{:.2f}x".format)
            table["visitor_share_trips"] = table["visitor_share_trips"].map("{:.1%}".format)
            st.dataframe(table.rename(columns={"barrio_name": "Neighbourhood", "distrito_name": "District", "mean_monthly_visitors": "Visitors/month",
                                               "vs_median": "vs median", "resident_trips_vs_median": "Residents' trips vs median",
                                               "visitor_share_trips": "Visitor share of trips", "reason": "Reason"}),
                         hide_index=True, width="stretch", height=280)
            st.markdown("**Reading.** Residents' trips are normal, but visitors are almost absent in two independent products (T4 people, "
                        "M1 trips). Verdun also has a −83% step between July and August 2023 that no neighbour shows. The cause is upstream "
                        "of our pipeline; the question is sent to the Business Manager.")
        if i3["validation"] is not None:
            v = i3["validation"]
            st.subheader(f"Aggregated data validation (2.2.2): {int((v['result'] == 'PASS').sum())} of {len(v)} checks passed")
            st.dataframe(v[["#", "area", "check", "result", "evidence"]], hide_index=True, width="stretch", height=420,
                         column_config={"check": st.column_config.TextColumn(width=380), "evidence": st.column_config.TextColumn(width=380)})

# ------------------------------------------------------------------------------------------------
# Limits and footer
# ------------------------------------------------------------------------------------------------
with st.expander("Data & limits"):
    st.markdown("""
- **Trips are not visitors.** Mobility files (M1 to M3) count trips, and one person can make several. Tourism files (T1 to T9) count unique people. The two measures are never mixed in one indicator.
- **Unique visitors are not additive.** Adding days does not give the month, and adding neighbourhoods does not give the city. City totals come from T1 and T2, not from summing T4 and T5.
- **The privacy threshold applies.** In mobility, trips below 15 are published as 0. In tourism, segments below 15 people are grouped as NA. A 0 or an NA never means "nobody".
- **Residents appear only in mobility** (`origen = Residente`). Tourism files contain regional, national and international visitors only. Regional visitors are always excursionists.
- **Overnight stays (T3) exist at municipality level only**, for national and international visitors.
- **Patterns, not causes.** The answers describe differences and changes. They do not say that tourists cause anything.

**Data supplied under NDA.** Smart Steps data (Telefónica Tech) are confidential. This dashboard runs locally and reads only aggregated tables, with values below 15 shown as `<15`. Do not publish or upload it.
""")

st.markdown(f'<div class="footer">{FOOTER}</div>', unsafe_allow_html=True)
