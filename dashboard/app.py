"""CONVIVE - "hello world" dashboard (Iteration 2, P2: visualisation environment).

Runs locally only (NDA). From the repo root:
    streamlit run dashboard/app.py

Data source: environment variable CONVIVE_DATA_MODE ("auto", "synthetic" or "real"),
default "auto", same meaning as DATA_MODE in the notebook.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for convive.py
import convive as cv

DATA_MODE = os.environ.get("CONVIVE_DATA_MODE", "auto")


@st.cache_data
def load_t4(mode):
    """Monthly unique visitors per neighbourhood (T4), with the same fallback as the notebook."""
    df, source = cv.load("T4", mode)
    if df is None and mode != "real":
        cv.make_synthetic_data()
        df, source = cv.load("T4", mode)
    if df is not None:
        df["visitantes"] = df["visitantes"].astype(float)   # NA (anonymised, < 15) stays NaN
    return df, source


st.set_page_config(page_title="CONVIVE dashboard", layout="wide")
st.title("CONVIVE · Visitors per neighbourhood")

with st.spinner("Loading data (the first run creates the synthetic files)..."):
    t4, source = load_t4(DATA_MODE)
if t4 is None:
    st.error(f"No T4 file found (CONVIVE_DATA_MODE={DATA_MODE}).")
    st.stop()

if source == "synthetic":
    st.warning("SYNTHETIC DATA. All numbers and patterns are made up.")
else:
    st.error("REAL DATA (Telefónica, NDA). Local use only: do not share screenshots or exports.")

_, barris = cv.load_barris()
names = dict(zip(barris["cod_barrio"], barris["barrio_name"]))
code = st.selectbox("Neighbourhood", barris["cod_barrio"], format_func=names.get)

# One neighbourhood only: unique visitors are never added across neighbourhoods.
# Turista + Excursionista are added within the same month and origin, as in the notebook.
one = t4[t4["cod_barrio"] == code]
monthly = one.groupby(["mes", "origen"])["visitantes"].sum(min_count=1).unstack()
monthly.index = pd.to_datetime(monthly.index, format="%Y%m")
monthly = monthly.reindex(columns=[o for o in cv.VISITOR_ORIGINS if o in monthly.columns])

st.subheader(f"Monthly unique visitors by origin · {names[code]}")
st.line_chart(monthly)
st.caption(f"Source: T4 ({source}). Gaps = anonymised values (< 15 people), not zero.")
