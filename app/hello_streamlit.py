"""Minimal test page for the visualisation environment decision (WBS 4.1.3).

Run:  streamlit run app/hello_streamlit.py
It uses no project data: it checks that Streamlit, Plotly and a filter work on this computer, locally.
"""

import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="CONVIVE hello", page_icon="👋")
st.title("CONVIVE · Streamlit test page")
st.write("If you can read this and the chart reacts to the slider, the environment works. No real data here.")

n = st.slider("Number of points", 2, 20, 8)
fig = go.Figure(go.Scatter(x=list(range(n)), y=[i ** 2 for i in range(n)], mode="lines+markers", line={"color": "#0072B2", "width": 2}))
fig.update_layout(height=320, margin={"l": 10, "r": 10, "t": 10, "b": 10}, xaxis_title="x", yaxis_title="x squared")
st.plotly_chart(fig, width="stretch")
