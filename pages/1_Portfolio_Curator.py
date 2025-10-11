from __future__ import annotations

from datetime import date, timedelta
from typing import List

import streamlit as st
import pandas as pd

from src.config.settings import AppSettings
from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader
from src.portfolio import services
from src.portfolio.seeds import SEED_COLLECTIONS
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


def _default_dates() -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=365 * 5)
    return start, end


def _create_loader(settings: AppSettings) -> MarketDataLoader:
    cache = MarketDataCache(root=settings.data_dir / "cache", max_items=16)

    from src.data.providers.alpaca_client import AlpacaClient
    from src.data.providers.yahoo_client import YahooClient

    def alpaca_factory():
        return AlpacaClient().fetch_bars

    def yahoo_factory():
        return YahooClient().fetch_bars

    providers = {
        "alpaca": alpaca_factory,
        "yahoo": yahoo_factory,
    }
    default = "alpaca" if settings.has_alpaca_credentials else "yahoo"
    return MarketDataLoader(cache=cache, providers=providers, default_provider=default)


def _write_preview(preview: services.PortfolioPreview) -> None:
    st.markdown("### Preview")
    st.caption(f"{len(preview.tickers)} symbols selected")
    if not preview.table.empty:
        st.dataframe(preview.table.set_index("symbol"))
    else:
        st.info(
            "Liquidity data unavailable for the selected universe. Preview limited to ticker list. "
            "Ensure you have network access or valid credentials."
        )
    _write_debug_panel(preview)


def _write_debug_panel(preview: services.PortfolioPreview) -> None:
    diagnostics = preview.diagnostics or []
    if not diagnostics:
        return

    summary_rows = [diag.to_summary() for diag in diagnostics]
    with st.expander("Debug diagnostics", expanded=False):
        st.caption(
            "Inspect cache hits, provider attempts, and errors captured while loading market data."
        )
        if summary_rows:
            summary_frame = pd.DataFrame(summary_rows)
            st.dataframe(summary_frame)
        error_symbols = [row["symbol"] for row in summary_rows if row.get("error")]
        if error_symbols:
            st.warning(
                f"Failed to load data for {len(error_symbols)} symbols: {', '.join(error_symbols[:10])}"
                + (" ..." if len(error_symbols) > 10 else "")
            )
        for diag in diagnostics:
            if not diag.attempts:
                continue
            attempt_rows = [
                {
                    "provider": attempt.provider,
                    "success": attempt.success,
                    "error": attempt.error or "",
                }
                for attempt in diag.attempts
            ]
            st.markdown(f"**{diag.symbol} attempts**")
            st.dataframe(pd.DataFrame(attempt_rows))


def main(settings: AppSettings) -> None:
    st.title("Portfolio Curator")
    st.write("Assemble a tradable universe by starting from a seed list or uploading tickers.")

    seeds = list(SEED_COLLECTIONS.keys())
    seed_choice = st.selectbox("Seed collection", options=seeds, index=0 if seeds else -1)
    manual_tickers = st.text_area("Additional tickers (comma-separated)", "")

    if seed_choice:
        seed_symbols = SEED_COLLECTIONS.get(seed_choice, [])
        st.caption(f"{len(seed_symbols)} tickers in {seed_choice}:")
        st.code(", ".join(seed_symbols))

    include_filter = st.text_input("Include symbols containing", "")
    exclude_filter = st.text_input("Exclude symbols containing", "")
    max_count = st.slider("Universe size cap", min_value=10, max_value=500, value=100, step=10)

    coverage_start, coverage_end = _default_dates()
    coverage_start = st.date_input("Coverage start", coverage_start)
    coverage_end = st.date_input("Coverage end", coverage_end)

    loader = _create_loader(settings)
    layout = StorageLayout(root=settings.data_dir)
    store = ArtifactStore(layout=layout)

    preview = None
    symbols: List[str] = []

    if seed_choice:
        symbols.extend(SEED_COLLECTIONS[seed_choice])
    if manual_tickers:
        symbols.extend([sym.strip() for sym in manual_tickers.split(",")])

    symbols = services.apply_filters(
        services.normalize_symbols(symbols),
        include_substring=include_filter or None,
        exclude_substring=exclude_filter or None,
    )

    debug_mode = st.toggle("Enable debug diagnostics", value=False, help="Capture provider and cache traces for troubleshooting.")

    if st.button("Preview universe"):
        with st.spinner("Loading market data..."):
            portfolio, preview = services.build_portfolio(
                name=f"{seed_choice} Universe" if seed_choice else "Custom Universe",
                description=None,
                source="seed" if seed_choice else "manual",
                seed_reference=seed_choice,
                symbols=symbols,
                max_count=max_count,
                coverage_start=str(coverage_start),
                coverage_end=str(coverage_end),
                loader=loader,
                filters={
                    "include": include_filter,
                    "exclude": exclude_filter,
                    "max_count": max_count,
                },
                debug=debug_mode,
            )
        st.session_state["portfolio_preview"] = preview
        st.session_state["portfolio_object"] = portfolio

    preview = st.session_state.get("portfolio_preview")
    if preview:
        _write_preview(preview)

    if st.session_state.get("portfolio_object") is not None:
        if st.button("Save portfolio"):
            portfolio = st.session_state["portfolio_object"]
            store.save_portfolio(portfolio)
            st.success(f"Portfolio saved: {portfolio.name} ({len(portfolio.tickers)} symbols)")
            st.session_state.pop("portfolio_object")
            st.session_state.pop("portfolio_preview")


if __name__ == "__main__":
    app_settings = AppSettings.from_env()
    main(app_settings)
