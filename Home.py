"""Streamlit entrypoint for the Model Builder V3 research workspace."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import streamlit as st

APP_TITLE = "Model Builder V3 — Research Dashboard"


def resolve_data_dir() -> Path:
    """Return the root directory for persisted artifacts."""
    root = Path(os.getenv("DATA_DIR", "storage"))
    return root if root.is_absolute() else (Path.cwd() / root).resolve()


def credential_status() -> tuple[Literal["valid", "missing"], str]:
    """Detect whether Alpaca credentials are present."""
    key = os.getenv("ALPACA_KEY_ID")
    secret = os.getenv("ALPACA_SECRET_KEY")
    status: Literal["valid", "missing"] = "valid" if key and secret else "missing"
    return status, "Alpaca credentials detected." if status == "valid" else "Alpaca credentials missing."


def render_header() -> None:
    st.title(APP_TITLE)
    st.write(
        "Welcome! Use the navigation menu to curate portfolios, evolve models, "
        "inspect optimizer logs, and review simulations."
    )


def render_credential_banner(status: Literal["valid", "missing"]) -> None:
    if status == "valid":
        st.success("✅ Using Alpaca market data. Yahoo Finance fallback remains available.")
    else:
        st.warning(
            "⚠️ Alpaca credentials were not found. The workspace will fall back to "
            "Yahoo Finance daily bars until credentials are provided."
        )


def render_storage_summary() -> None:
    data_dir = resolve_data_dir()
    st.subheader("Storage")
    st.write(
        "Artifacts will be stored under the following directory. "
        "You can override this path with the `DATA_DIR` environment variable."
    )
    st.code(str(data_dir))
    st.info(
        "The storage directory is created on-demand when you save a portfolio, "
        "run an optimizer session, or export a bundle."
    )


def render_next_steps() -> None:
    st.subheader("Next Steps")
    st.markdown(
        "- Navigate to **Portfolio Curator** to build a ticker universe.\n"
        "- Visit **Model Builder** to tune the ATR breakout baseline.\n"
        "- Use **Log Inspector** to review training telemetry.\n"
        "- Open **Simulation Review** to evaluate tuned parameter sets."
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    render_header()

    status, message = credential_status()
    st.caption(message)
    render_credential_banner(status)

    render_storage_summary()
    render_next_steps()


if __name__ == "__main__":
    main()
