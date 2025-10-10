"""Streamlit page scaffold for simulation review and bundle export."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Simulation Review", layout="wide")

st.title("Simulation Review")
st.info(
    "This page will allow you to run fresh simulations, review KPIs, and export bundles."
)
