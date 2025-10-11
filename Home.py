from __future__ import annotations

import streamlit as st

from src.config.settings import AppSettings
from src.home.dashboard import HomeSummary, collect_home_summary

APP_TITLE = "Model Builder V3 — Research Dashboard"


def render_header() -> None:
    st.title(APP_TITLE)
    st.write(
        "Welcome! Use the navigation menu or the quick links below to curate portfolios, evolve models, "
        "inspect optimizer logs, and review simulations."
    )


def render_credential_banner(settings: AppSettings) -> None:
    if settings.has_alpaca_credentials:
        st.success("✅ Alpaca credentials detected. Yahoo Finance fallback remains available.")
    else:
        st.warning(
            "⚠️ Alpaca credentials not found. The workspace will fall back to Yahoo Finance daily bars until credentials are provided."
        )


def render_storage_summary(settings: AppSettings) -> None:
    st.subheader("Storage Root")
    st.code(str(settings.data_dir))
    st.caption(
        "Override with the `DATA_DIR` environment variable. Directories are created on demand the first time you save an artifact."
    )


def _render_section(title: str, items: list[tuple[str, str | None]], empty_message: str, page: str) -> None:
    st.subheader(title)
    if not items:
        st.caption(empty_message)
        return

    for name, timestamp in items:
        label = f"{name}" if not timestamp else f"{name} · {timestamp}"
        st.page_link(page, label=label, icon="➡️")


def render_sections(summary: HomeSummary) -> None:
    sections = [
        (
            "Recent Portfolios",
            summary.portfolios,
            "No portfolios saved yet.",
            "pages/1_Portfolio_Curator.py",
        ),
        (
            "Recent Parameter Sets",
            summary.parameter_sets,
            "No parameter sets saved yet.",
            "pages/2_Model_Builder.py",
        ),
        (
            "Recent Simulations",
            summary.simulations,
            "No simulation runs recorded yet.",
            "pages/4_Simulation_Review.py",
        ),
        (
            "Optimizer Logs",
            summary.logs,
            "No optimizer logs available yet.",
            "pages/3_Log_Inspector.py",
        ),
    ]

    for title, items, empty, page in sections:
        _render_section(title, items, empty, page)


def render_next_steps() -> None:
    st.subheader("Next Steps")
    st.markdown(
        "- Go to **Portfolio Curator** to build or import a ticker universe.\n"
        "- Visit **Model Builder** to tune the ATR breakout baseline or other strategies.\n"
        "- Open **Log Inspector** to review optimization telemetry and benchmarks.\n"
        "- Use **Simulation Review** to validate tuned parameter sets and export bundles."
    )


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    settings = AppSettings.from_env()
    summary = collect_home_summary(settings.data_dir)

    render_header()
    render_credential_banner(settings)
    render_storage_summary(settings)
    render_sections(summary)
    render_next_steps()


if __name__ == "__main__":
    main()
