"""Streamlit page scaffold for optimizer log inspection."""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Log Inspector", layout="wide")

st.title("Log Inspector")
st.info(
    "This page will help you load optimizer logs, scrub generations, and review benchmarks."
)
