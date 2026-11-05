"""CONVIVE preliminary dashboard (WBS 4.2.0), with the first version of the interactive maps (WBS 4.2.1).

Run locally:  streamlit run app/dashboard.py
Data input:   only deliverables/iteration2/3.1.6_stats/*.csv and the neighbourhood GeoJSON. Nothing leaves this computer.
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

# Okabe-Ito, colour-blind safe (validated). The same colour per origin everywhere, plus legends, line markers,
# direct labels and a table under each view, so identity never depends on colour alone.
ORIGIN_COLORS = {"Internacional": "#0072B2", "Nacional": "#E69F00", "Regional": "#009E73", "Residente": "#CC79A7"}
ORIGIN_SYMBOLS = {"Internacional": "circle", "Nacional": "square", "Regional": "diamond", "Residente": "triangle-up"}
YEAR_COLORS = {2023: "#BDBDBD", 2024: "#7F7F7F", 2025: "#333333"}
SEQUENTIAL = "Purples"
DIVERGING = "RdBu"
INK, MUTED, GRID, OUTLINE = "#1f1f1f", "#5f5f5f", "#e6e6e6", "#a9a9a9"
FOOTER = "CONVIVE · Team 102_A · Preliminary dashboard, Iteration 2 · Smart Steps data supplied under NDA · aggregated, threshold 15"

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
    st.divider()
    st.caption("2025 covers January to August. Regional visitors are always excursionists.")

f = dd.Filters(sorted(years), month_from, month_to, origins, types)

# ------------------------------------------------------------------------------------------------
# Header
# ------------------------------------------------------------------------------------------------
st.title("CONVIVE · Visitors and residents in Barcelona")
period = f"{dd.MONTHS[month_from - 1]} to {dd.MONTHS[month_to - 1]}" if month_from != month_to else dd.MONTHS[month_from - 1]
st.markdown(f"Preliminary dashboard · **{period}**, **{', '.join(map(str, f.years)) or 'no year selected'}** · "
            f"origin: **{', '.join(f.origins) or 'none'}** · type: **{', '.join(f.types) or 'none'}**")

with st.expander("How to read this", expanded=True):
    st.markdown("""
- **Unique visitors** (Q1 to Q5) count people in a place and period. They cannot be added across months or neighbourhoods. A longer period is shown as a **monthly average**.
- **Trips** (Q6) count journeys between neighbourhoods. One person can make several. Trips and visitors are never combined.
- **0 or NA never means nobody:** below 15, a value is hidden for privacy and reads `<15`.
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
        view_header("Q3 · Who visits? Unique visitors and their composition",
                    "regional visitors are always excursionists by definition, which raises the excursionist share.")
        if k is None:
            st.info("No visitor data for this selection.")
        else:
            label = f"Unique visitors in {k['single_month']}" if k["single_month"] else f"Monthly average ({k['n_months']} months)"
            columns = st.columns(5)
            columns[0].metric(label, dd.format_count(k["visitors"]))
            for column, origin in zip(columns[1:4], dd.VISITOR_ORIGINS):
                value = k["origin_share"].get(origin)
                column.metric(f"{origin} share", f"{value:.1%}" if value is not None else "not selected")
            columns[4].metric("Tourist share", f"{k['tourist_share']:.1%}")
            if not k["single_month"]:
                st.caption("Several months are selected, so the first tile is the monthly average from T1. Monthly unique visitors are not summed. Shares are within the current selection.")
            segments = dd.segments_by_month(tables, f)
            fig = go.Figure()
            for (origin, tipo), g in segments.groupby(["origen", "tipo_visitante"], sort=False):
                fig.add_bar(x=pd.to_datetime(g["mes"], format="%Y%m"), y=g["visitantes"], name=f"{origin} · {tipo}",
                            marker={"color": ORIGIN_COLORS[origin], "pattern": {"shape": "/" if tipo == "Excursionista" else ""},
                                    "line": {"color": "white", "width": 1}},
                            hovertemplate=f"{origin} · {tipo}<br>%{{x|%b %Y}}: %{{y:,.0f}}<extra></extra>")
            fig.update_layout(barmode="stack", bargap=0.25)
            show(base_layout(fig, 340, "Unique visitors per month", ",.0f"), "q3_bars")
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
        base_layout(fig, 360, "Unique visitors per month", ",.0f")
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
        show(base_layout(fig, 340, "Mean unique visitors per day", ",.0f"), "q4_bars")
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
