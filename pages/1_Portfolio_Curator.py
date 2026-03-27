from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from src.config.settings import AppSettings
from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader
from src.data.universe_loader import (
    UniverseNotFoundError,
    UniverseSummary,
    list_universes,
    load_universe,
)
from src.models.contracts import Portfolio
from src.portfolio.draft import (
    DraftPortfolioState,
    add_to_draft,
    draft_stats,
    ensure_state,
    remove_from_draft,
    serialize_state,
)
from src.portfolio.filters import FilterStats, available_sectors, filter_universe
from src.portfolio.liquidity import fetch_liquidity
from src.portfolio.services import normalize_portfolio_id
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout

SESSION_KEYS = {
    "universe_summary": "portfolio_universe_summary",
    "filters": "portfolio_filters",
    "priors_window": "portfolio_priors_window",
    "filtered_symbols": "portfolio_filtered_symbols",
    "filter_stats": "portfolio_filter_stats",
    "liquidity": "portfolio_liquidity_data",
    "thresholds": "portfolio_thresholds",
    "draft": "portfolio_draft",
    "liquidity_symbols": "portfolio_liquidity_symbols",
    "table_data": "portfolio_table_data",
    "draft_name": "portfolio_draft_name",
    "overwrite_confirm": "portfolio_overwrite_confirm",
    "selected_portfolio": "portfolio_selected_saved",
}

_STORE_SESSION_KEY = "_portfolio_artifact_store"
SAVE_DESCRIPTION_KEY = "portfolio_save_description"
SAVE_NOTES_KEY = "portfolio_save_notes"


def _universe_directory(settings: AppSettings) -> Path:
    return (settings.data_dir / "index_universes").resolve()


def _create_loader(settings: AppSettings) -> MarketDataLoader:
    cache = MarketDataCache(root=settings.data_dir / "cache", max_items=16)

    from src.data.providers.alpaca_client import AlpacaClient
    from src.data.providers.yahoo_client import YahooClient

    providers = {
        "alpaca": lambda: AlpacaClient().fetch_bars,
        "yahoo": lambda: YahooClient().fetch_bars,
    }
    default = "alpaca" if settings.has_alpaca_credentials else "yahoo"
    return MarketDataLoader(cache=cache, providers=providers, default_provider=default)


def _artifact_store(settings: AppSettings) -> ArtifactStore:
    store = st.session_state.get(_STORE_SESSION_KEY)
    if store is None:
        layout = StorageLayout(root=settings.data_dir)
        store = ArtifactStore(layout=layout)
        st.session_state[_STORE_SESSION_KEY] = store
    return store


def _aggregate_shard_hints(frame: pd.DataFrame | None) -> dict[str, Any]:
    if frame is None or frame.empty or "shard_hints" not in frame:
        return {}
    aggregated: dict[str, dict[str, Any]] = {}
    for hints in frame["shard_hints"]:
        if not isinstance(hints, dict):
            continue
        cache_key = hints.get("cacheKey")
        if not cache_key:
            continue
        entry = aggregated.setdefault(cache_key, {"cacheKey": cache_key, "segments": []})
        segments = hints.get("segments") or []
        if not isinstance(segments, list):
            continue
        existing_signatures = {
            (segment.get("start"), segment.get("end"), segment.get("symbolCount"))
            for segment in entry["segments"]
        }
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            signature = (
                segment.get("start"),
                segment.get("end"),
                segment.get("symbolCount"),
            )
            if signature in existing_signatures:
                continue
            entry["segments"].append(
                {
                    "symbolCount": int(segment.get("symbolCount", 0)),
                    "start": segment.get("start"),
                    "end": segment.get("end"),
                }
            )
            existing_signatures.add(signature)
    if not aggregated:
        return {}
    return {"cacheKeys": list(aggregated.values())}


def _build_portfolio_document(
    *,
    name: str,
    description: str | None,
    universe_summary: UniverseSummary,
    draft_state: DraftPortfolioState,
    liquidity_frame: pd.DataFrame,
    filters: dict[str, object],
    thresholds: dict[str, float],
    priors_window: dict[str, date],
    notes: list[str],
) -> Portfolio:
    stats = draft_stats(draft_state, liquidity_frame)
    subset = liquidity_frame.loc[
        liquidity_frame.index.intersection(draft_state.selected_symbols)
    ].copy()

    priors_start = priors_window["start"].isoformat()
    priors_end = priors_window["end"].isoformat()
    coverage_start = stats.get("coverage_start") or priors_start
    coverage_end = stats.get("coverage_end") or priors_end

    liquidity_stats = {
        "symbol_count": stats.get("symbol_count", 0),
        "median_price": stats.get("median_price"),
        "median_dollar_volume": stats.get("median_dollar_volume"),
        "coverage_gap_count": stats.get("coverage_gap_count", 0),
    }
    liquidity_stats = {key: value for key, value in liquidity_stats.items() if value is not None}

    filters_payload: dict[str, Any] = dict(filters or {})
    if thresholds:
        filters_payload["thresholds"] = thresholds
    filters_payload["universe"] = {
        "identifier": universe_summary.identifier,
        "name": universe_summary.name,
    }
    filters_payload["priors_window"] = {"start": priors_start, "end": priors_end}

    coverage_summary = {
        "start": coverage_start,
        "end": coverage_end,
        "coverage_gap_count": stats.get("coverage_gap_count", 0),
    }

    shard_hints = _aggregate_shard_hints(subset)
    return Portfolio(
        portfolio_id=normalize_portfolio_id(name),
        name=name,
        description=description,
        source="streamlit",
        seed_reference=universe_summary.identifier,
        filters=filters_payload,
        coverage_window={"start": coverage_start, "end": coverage_end},
        tickers=list(draft_state.selected_symbols),
        liquidity_stats=liquidity_stats,
        notes=notes,
        coverage_summary=coverage_summary,
        shard_hints=shard_hints,
    )


def _default_priors_window() -> tuple[date, date]:
    prev_close = date.today() - timedelta(days=1)
    start = prev_close - timedelta(days=365 * 5)
    return start, prev_close


def _initialize_priors_window() -> dict[str, date]:
    if SESSION_KEYS["priors_window"] not in st.session_state:
        start, end = _default_priors_window()
        st.session_state[SESSION_KEYS["priors_window"]] = {"start": start, "end": end}
    return st.session_state[SESSION_KEYS["priors_window"]]


def _prepare_filters(total_symbols: int) -> dict[str, object]:
    filters: dict[str, object] = st.session_state.get(SESSION_KEYS["filters"], {})
    filters.setdefault("search", "")
    filters.setdefault("sectors", [])
    filters.setdefault("max_symbols", min(100, total_symbols) if total_symbols else 0)
    # Clamp max_symbols to available universe size
    max_symbols = int(filters["max_symbols"]) if total_symbols else 0
    filters["max_symbols"] = min(max_symbols or total_symbols, total_symbols)
    st.session_state[SESSION_KEYS["filters"]] = filters
    return filters


def _get_draft_state(universe_summary: UniverseSummary) -> DraftPortfolioState:
    raw_state = st.session_state.get(SESSION_KEYS["draft"])
    state = ensure_state(raw_state, universe_summary.identifier)
    st.session_state[SESSION_KEYS["draft"]] = serialize_state(state)
    return state


def _update_draft_state(state: DraftPortfolioState) -> None:
    st.session_state[SESSION_KEYS["draft"]] = serialize_state(state)


def _render_filters(
    universe_summary: UniverseSummary,
) -> tuple[dict[str, object], FilterStats, pd.DataFrame]:
    universe = load_universe(
        universe_summary.identifier, directory=universe_summary.source_path.parent
    )
    filters = _prepare_filters(len(universe.symbols))
    draft_state = _get_draft_state(universe_summary)

    st.subheader("Filter universe")
    filter_cols = st.columns((3, 3, 1))
    with filter_cols[0]:
        search_value = st.text_input(
            "Search tickers or names",
            value=str(filters.get("search", "")),
            placeholder="e.g. energy, mega cap, technology",
        )
    filters["search"] = search_value

    with filter_cols[1]:
        sector_options = available_sectors(universe)
        default_sectors = [
            sector for sector in filters.get("sectors", []) if sector in sector_options
        ]
        selected_sectors = st.multiselect(
            "Sectors", options=sector_options, default=default_sectors
        )
    filters["sectors"] = selected_sectors

    total_symbols = len(universe.symbols)
    if total_symbols == 0:
        st.warning("Selected universe contains no symbols.")
        return filters, FilterStats(total_symbols=0, matched_symbols=0, limited_symbols=0)

    max_limit = max(1, total_symbols)
    raw_max = int(filters.get("max_symbols") or min(100, max_limit))
    with filter_cols[2]:
        max_symbols_value = st.number_input(
            "Max symbols",
            min_value=1,
            max_value=max_limit,
            value=min(raw_max, max_limit),
            step=1,
            help="Limit the working universe to this many symbols after filters.",
        )
    filters["max_symbols"] = max_symbols_value
    st.session_state[SESSION_KEYS["filters"]] = filters

    frame, stats = filter_universe(
        universe,
        search=search_value,
        sectors=selected_sectors,
        max_symbols=max_symbols_value,
    )
    previous_symbols = st.session_state.get(SESSION_KEYS["filtered_symbols"])
    current_symbols = frame.index.tolist()
    st.session_state[SESSION_KEYS["filtered_symbols"]] = current_symbols
    st.session_state[SESSION_KEYS["filter_stats"]] = stats

    if previous_symbols != current_symbols:
        st.session_state.pop(SESSION_KEYS["liquidity"], None)
        st.session_state.pop(SESSION_KEYS["liquidity_symbols"], None)
        draft_state = DraftPortfolioState(universe_summary.identifier)
        _update_draft_state(draft_state)

    draft_state.limit(max_symbols_value)
    _update_draft_state(draft_state)

    cols = st.columns(3)
    cols[0].metric("Available symbols", stats.total_symbols)
    cols[1].metric("Matched", stats.matched_symbols)
    cols[2].metric("In view", stats.limited_symbols)

    display_frame = frame.reset_index().rename(
        columns={
            "ticker": "Ticker",
            "name": "Name",
            "sector": "Sector",
            "industry": "Industry",
        }
    )
    base_columns = ["Ticker", "Name", "Sector", "Industry"]
    metrics_columns = [
        "Median Price",
        "Median $ Volume",
        "Coverage Start",
        "Coverage End",
        "Coverage Status",
        "Missing %",
    ]
    if display_frame.empty:
        display_frame = pd.DataFrame(columns=base_columns)
    else:
        display_frame = display_frame[base_columns]
    for column in metrics_columns:
        display_frame[column] = pd.NA
    display_frame = display_frame[base_columns + metrics_columns]
    st.session_state[SESSION_KEYS["table_data"]] = display_frame

    if frame.empty:
        st.warning("No symbols match the current filters. Adjust filters to continue.")

    return filters, stats, frame


def _render_selection_panel(
    universe_summary: UniverseSummary,
    max_symbols: int,
    available_symbols: list[str],
    liquidity_frame: pd.DataFrame | None,
) -> None:
    if not available_symbols:
        st.warning("Fetch liquidity to populate the draft selection list.")
        return

    draft_state = _get_draft_state(universe_summary)
    st.subheader("Draft portfolio selection")

    add_selection = st.multiselect(
        "Select symbols to add",
        options=available_symbols,
        key="draft_add_symbols",
    )
    if st.button(
        "Add to draft",
        key="draft_add_button",
        disabled=len(add_selection) == 0,
    ):
        add_to_draft(draft_state, add_selection, max_symbols=max_symbols)
        _update_draft_state(draft_state)
        st.success(f"Added {len(add_selection)} symbol(s) to the draft portfolio.")

    remove_selection = st.multiselect(
        "Symbols currently in draft",
        options=draft_state.selected_symbols,
        key="draft_remove_symbols",
    )
    if st.button(
        "Remove selected",
        key="draft_remove_button",
        disabled=len(remove_selection) == 0,
    ):
        remove_from_draft(draft_state, remove_selection)
        _update_draft_state(draft_state)
        st.info(f"Removed {len(remove_selection)} symbol(s) from the draft portfolio.")


def _render_draft_table(
    universe_summary: UniverseSummary,
    liquidity_frame: pd.DataFrame | None,
) -> None:
    draft_state = _get_draft_state(universe_summary)
    if not draft_state.selected_symbols:
        st.info("Draft portfolio has no symbols yet.")
        return

    stats = draft_stats(draft_state, liquidity_frame)
    st.subheader("Draft portfolio summary")
    cols = st.columns(4)
    cols[0].metric("Tickers", stats["symbol_count"])
    cols[1].metric(
        "Median price",
        f"{stats['median_price']:.2f}" if stats["median_price"] is not None else "—",
    )
    cols[2].metric(
        "Median $ volume",
        f"{stats['median_dollar_volume'] / 1_000_000:.1f}M"
        if stats["median_dollar_volume"] is not None
        else "—",
    )
    cols[3].metric(
        "Coverage gaps",
        str(stats.get("coverage_gap_count", 0)),
    )
    if stats["coverage_start"] and stats["coverage_end"]:
        st.caption(f"Coverage window: {stats['coverage_start']} → {stats['coverage_end']}")
    else:
        st.caption("Coverage window: —")
    frame = pd.DataFrame({"Ticker": draft_state.selected_symbols})
    st.dataframe(frame, use_container_width=True)


def _render_persistence_controls(
    settings: AppSettings,
    universe_summary: UniverseSummary,
    filters: dict[str, object],
    liquidity_frame: pd.DataFrame | None,
) -> None:
    draft_state = _get_draft_state(universe_summary)
    if not draft_state.selected_symbols:
        return

    if liquidity_frame is None or liquidity_frame.empty:
        st.info("Fetch liquidity before saving the draft portfolio.")
        return

    subset = liquidity_frame.loc[liquidity_frame.index.intersection(draft_state.selected_symbols)]
    if subset.empty:
        st.info("Run liquidity fetch for the selected symbols before saving.")
        return

    priors_window = st.session_state.get(SESSION_KEYS["priors_window"])
    if not priors_window:
        st.info("Define a priors window before saving the portfolio.")
        return

    st.subheader("Save portfolio")
    default_name = (
        st.session_state.get(SESSION_KEYS["draft_name"]) or f"{universe_summary.name} Draft"
    )
    if SESSION_KEYS["draft_name"] not in st.session_state:
        st.session_state[SESSION_KEYS["draft_name"]] = default_name
    name_value = st.text_input("Portfolio name", key=SESSION_KEYS["draft_name"])
    name = name_value.strip()
    description_value = st.text_area("Description (optional)", key=SAVE_DESCRIPTION_KEY)
    description = description_value.strip() or None
    notes_value = st.text_area("Notes (optional)", key=SAVE_NOTES_KEY, height=80)
    notes = [line.strip() for line in notes_value.splitlines() if line.strip()]

    thresholds = st.session_state.get(SESSION_KEYS["thresholds"], {})
    if not name:
        st.error("Provide a portfolio name to enable saving.")
        return

    store = _artifact_store(settings)
    portfolio_id = normalize_portfolio_id(name)
    existing = store.load_portfolio(portfolio_id)
    overwrite_confirmed = True
    confirm_key = f"{SESSION_KEYS['overwrite_confirm']}_{portfolio_id}"
    if existing is not None:
        st.warning(
            f"Portfolio '{name}' already exists and will be overwritten when you save.",
        )
        overwrite_confirmed = st.checkbox("Confirm overwrite", key=confirm_key)

    save_allowed = overwrite_confirmed and not subset.empty
    save_clicked = st.button("Save portfolio", type="primary", disabled=not save_allowed)
    if not save_clicked:
        return

    portfolio = _build_portfolio_document(
        name=name,
        description=description,
        universe_summary=universe_summary,
        draft_state=draft_state,
        liquidity_frame=liquidity_frame,
        filters=filters,
        thresholds=thresholds,
        priors_window=priors_window,
        notes=notes,
    )
    store.save_portfolio(portfolio)
    st.session_state[SESSION_KEYS["selected_portfolio"]] = name
    if confirm_key in st.session_state:
        st.session_state.pop(confirm_key)
    if hasattr(st, "toast"):
        st.toast(f"Saved portfolio '{name}'.")
    st.success(f"Portfolio '{name}' saved to storage.")


def _render_saved_portfolios(settings: AppSettings) -> None:
    st.subheader("Saved portfolios")
    store = _artifact_store(settings)
    portfolios = store.list_portfolios(limit=50)
    if not portfolios:
        st.caption("No portfolios saved yet.")
        return

    table_rows = []
    for portfolio in portfolios:
        table_rows.append(
            {
                "Name": portfolio.name,
                "Symbols": len(portfolio.tickers),
                "Coverage gaps": portfolio.liquidity_stats.get("coverage_gap_count", 0),
                "Updated": portfolio.updated_at,
            }
        )
    display = pd.DataFrame(table_rows)
    st.dataframe(display, use_container_width=True, hide_index=True)

    names = [portfolio.name for portfolio in portfolios]
    default_index = 0
    stored_selection = st.session_state.get(SESSION_KEYS["selected_portfolio"])
    if stored_selection in names:
        default_index = names.index(stored_selection)
    selected_name = st.selectbox(
        "Select a portfolio to delete",
        options=names,
        index=default_index,
        key=SESSION_KEYS["selected_portfolio"],
    )

    selected_portfolio = next(
        (portfolio for portfolio in portfolios if portfolio.name == selected_name), None
    )
    if selected_portfolio is None:
        return

    confirm_key = f"delete_confirm_{selected_portfolio.portfolio_id}"
    confirm_delete = st.checkbox("Confirm delete", key=confirm_key)
    if st.button("Delete selected portfolio", disabled=not confirm_delete):
        store.delete_portfolio(selected_portfolio.portfolio_id)
        if hasattr(st, "toast"):
            st.toast(f"Deleted portfolio '{selected_portfolio.name}'.")
        st.success(f"Portfolio '{selected_portfolio.name}' deleted.")
        st.session_state.pop(confirm_key, None)
        st.session_state.pop(SESSION_KEYS["selected_portfolio"], None)


def _render_table_view() -> None:
    table = st.session_state.get(SESSION_KEYS["table_data"])
    if table is None or (hasattr(table, "empty") and table.empty):
        st.info("No symbols to display; adjust filters or fetch liquidity.")
        return
    st.dataframe(table, use_container_width=True)


def _ensure_thresholds() -> dict[str, float]:
    thresholds = st.session_state.get(SESSION_KEYS["thresholds"])
    if thresholds is None:
        thresholds = {"price_floor": 5.0, "volume_floor": 1_000_000.0}
        st.session_state[SESSION_KEYS["thresholds"]] = thresholds
    return thresholds


def _render_liquidity_panel(
    universe_summary: UniverseSummary,
    base_frame: pd.DataFrame,
    loader: MarketDataLoader,
) -> tuple[list[str], pd.DataFrame]:
    symbols = st.session_state.get(SESSION_KEYS["filtered_symbols"], [])
    base_display = base_frame.reset_index().rename(
        columns={
            "ticker": "Ticker",
            "name": "Name",
            "sector": "Sector",
            "industry": "Industry",
        }
    )
    st.session_state[SESSION_KEYS["table_data"]] = base_display

    if not symbols:
        st.info("Adjust filters to populate symbols before fetching liquidity.")
        st.session_state[SESSION_KEYS["liquidity_symbols"]] = []
        st.session_state.pop(SESSION_KEYS["liquidity"], None)
        return [], base_frame

    st.subheader("Liquidity & Coverage")
    thresholds = _ensure_thresholds()

    thresh_cols = st.columns((1, 1, 1))
    with thresh_cols[0]:
        price_floor = st.number_input(
            "Median price floor",
            min_value=0.0,
            value=float(thresholds.get("price_floor", 5.0)),
            step=1.0,
            help="Symbols below this price are filtered out after fetching liquidity data.",
        )
    with thresh_cols[1]:
        volume_floor = st.number_input(
            "Median dollar volume floor",
            min_value=0.0,
            value=float(thresholds.get("volume_floor", 1_000_000.0)),
            step=100000.0,
            help="Filter out symbols that do not meet minimum liquidity thresholds.",
            format="%.0f",
        )

    thresholds.update({"price_floor": float(price_floor), "volume_floor": float(volume_floor)})
    st.session_state[SESSION_KEYS["thresholds"]] = thresholds

    window_state = _initialize_priors_window()
    date_cols = st.columns((1, 1, 1))
    with date_cols[0]:
        start_input = st.date_input(
            "Priors window start",
            value=window_state["start"],
            key="liquidity_priors_start",
        )
    with date_cols[1]:
        end_input = st.date_input(
            "Priors window end",
            value=window_state["end"],
            key="liquidity_priors_end",
        )
    if start_input > end_input:
        date_cols[2].error("Priors start must be on or before end.")
        fetch_start = start_input
        fetch_end = end_input
    else:
        st.session_state[SESSION_KEYS["priors_window"]] = {"start": start_input, "end": end_input}
        fetch_start = start_input
        fetch_end = end_input

    with thresh_cols[2]:
        fetch_clicked = st.button("Fetch liquidity", type="primary")

    if fetch_clicked:
        with st.spinner("Fetching liquidity metrics..."):
            try:
                frame, summary, errors = fetch_liquidity(
                    loader,
                    symbols,
                    fetch_start.isoformat(),
                    fetch_end.isoformat(),
                )
            except Exception as exc:  # pragma: no cover - defensive
                st.error(f"Liquidity fetch failed: {exc}")
            else:
                st.session_state[SESSION_KEYS["liquidity"]] = {
                    "frame": frame,
                    "summary": summary,
                    "errors": errors,
                }
                st.success(f"Liquidity refreshed for {summary.retrieved} symbols.")

    liquidity_state = st.session_state.get(SESSION_KEYS["liquidity"])
    if not liquidity_state:
        st.caption("Run a liquidity fetch to inspect coverage and apply thresholds.")
        st.session_state[SESSION_KEYS["liquidity_symbols"]] = []
        return [], base_frame

    frame = liquidity_state["frame"].copy()
    summary = liquidity_state["summary"]
    errors = liquidity_state["errors"]

    cols = st.columns(4)
    cols[0].metric("Requested", summary.requested)
    cols[1].metric("Retrieved", summary.retrieved)
    cols[2].metric("Complete", summary.complete)
    cols[3].metric("Partial", summary.partial)
    st.caption(f"Coverage ratio: {summary.coverage_ratio:.0%}")

    if errors:
        error_preview = ", ".join(f"{err['symbol']}: {err['error']}" for err in errors[:5])
        st.warning(
            f"{len(errors)} symbols had fetch issues."
            + (f" Details: {error_preview}" if error_preview else "")
        )

    if frame.empty:
        st.info("No liquidity data available for the selected window.")
        st.session_state[SESSION_KEYS["liquidity_symbols"]] = []
        st.session_state[SESSION_KEYS["table_data"]] = base_display
        return [], base_frame

    filtered = frame.copy()
    filtered = filtered[filtered["median_price"].fillna(0) >= thresholds["price_floor"]]
    filtered = filtered[filtered["median_dollar_volume"].fillna(0) >= thresholds["volume_floor"]]

    if filtered.empty:
        st.info("No symbols pass the current liquidity thresholds.")
        st.session_state[SESSION_KEYS["liquidity_symbols"]] = []
        st.session_state[SESSION_KEYS["table_data"]] = base_display
        return [], base_frame

    missing_threshold = 0.05
    coverage_mask = filtered["coverage_status"] != "complete"
    significant_mask = filtered["missing_fraction"].fillna(1.0) >= missing_threshold
    flagged = filtered[coverage_mask & significant_mask].index.tolist()
    if flagged:
        st.warning(
            "Insufficient coverage for: "
            + ", ".join(flagged[:10])
            + (" ..." if len(flagged) > 10 else "")
        )
    elif coverage_mask.any():
        st.caption("Minor coverage gaps detected (<5% missing); review before finalizing.")

    universe_filtered_symbols = filtered.index.tolist()
    st.session_state[SESSION_KEYS["liquidity_symbols"]] = universe_filtered_symbols

    draft_state = _get_draft_state(universe_summary)
    invalid_symbols = [
        symbol for symbol in draft_state.selected_symbols if symbol not in universe_filtered_symbols
    ]
    if invalid_symbols:
        remove_from_draft(draft_state, invalid_symbols)
        _update_draft_state(draft_state)

    base_subset = base_frame.loc[universe_filtered_symbols].copy()
    merged = base_subset.join(filtered, how="left")
    display_frame = merged.reset_index().rename(
        columns={
            "ticker": "Ticker",
            "name": "Name",
            "sector": "Sector",
            "industry": "Industry",
            "median_price": "Median Price",
            "median_dollar_volume": "Median $ Volume",
            "coverage_start": "Coverage Start",
            "coverage_end": "Coverage End",
            "observations": "Observations",
            "missing_fraction": "Missing Fraction",
            "coverage_status": "Coverage Status",
        }
    )
    display_frame["Missing %"] = (display_frame.pop("Missing Fraction") * 100).round(1)
    st.session_state[SESSION_KEYS["table_data"]] = display_frame

    return universe_filtered_symbols, merged


def main(settings: AppSettings) -> None:
    st.title("Portfolio Curator")
    st.write(
        "Start from a published index universe, refine it with filters, and prepare it for modeling."
    )

    universe_dir = _universe_directory(settings)
    summaries = list_universes(universe_dir)
    if not summaries:
        st.warning(
            "No index universes found. Add JSON files to `storage/index_universes/` to continue."
        )
        return

    loader = _create_loader(settings)

    default_summary = st.session_state.get(SESSION_KEYS["universe_summary"]) or summaries[0]
    try:
        default_index = summaries.index(default_summary)  # type: ignore[arg-type]
    except ValueError:
        default_index = 0

    selected_summary = st.selectbox(
        "Index universe",
        options=summaries,
        format_func=lambda summary: f"{summary.name} ({summary.symbol_count} symbols)",
        index=default_index,
    )
    st.session_state[SESSION_KEYS["universe_summary"]] = selected_summary

    try:
        filters, _, base_frame = _render_filters(selected_summary)
    except UniverseNotFoundError as exc:
        st.error(str(exc))
        return

    max_symbols = int(filters.get("max_symbols", 0)) if filters else 0
    if max_symbols <= 0:
        max_symbols = 1
    liquidity_symbols, liquidity_frame = _render_liquidity_panel(
        selected_summary,
        base_frame,
        loader,
    )
    _render_table_view()
    _render_selection_panel(selected_summary, max_symbols, liquidity_symbols, liquidity_frame)
    _render_draft_table(selected_summary, liquidity_frame)
    _render_persistence_controls(settings, selected_summary, filters, liquidity_frame)
    _render_saved_portfolios(settings)


if __name__ == "__main__":
    app_settings = AppSettings.from_env()
    main(app_settings)
