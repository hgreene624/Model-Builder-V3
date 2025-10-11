from __future__ import annotations

from time import sleep

import pandas as pd

from src.portfolio.draft import (
    DraftPortfolioState,
    add_to_draft,
    draft_stats,
    ensure_state,
    remove_from_draft,
    serialize_state,
)


def test_ensure_state_initializes_for_universe() -> None:
    state = ensure_state(None, "sp500")
    assert state.universe_id == "sp500"
    assert state.selected_symbols == []


def test_ensure_state_resets_on_universe_change() -> None:
    existing = DraftPortfolioState(universe_id="nasdaq", selected_symbols=["AAPL"])
    payload = serialize_state(existing)
    state = ensure_state(payload, "sp500")
    assert state.universe_id == "sp500"
    assert state.selected_symbols == []


def test_add_to_draft_removes_duplicates_and_limits() -> None:
    state = DraftPortfolioState(universe_id="sp500")
    add_to_draft(state, ["aapl", "msft", "AAPL"], max_symbols=2)
    assert state.selected_symbols == ["AAPL", "MSFT"]


def test_remove_from_draft() -> None:
    state = DraftPortfolioState(universe_id="sp500", selected_symbols=["AAPL", "MSFT", "GOOGL"])
    remove_from_draft(state, ["msft"])
    assert state.selected_symbols == ["AAPL", "GOOGL"]


def test_draft_stats_with_liquidity() -> None:
    state = DraftPortfolioState(universe_id="sp500", selected_symbols=["AAPL", "MSFT"])
    liquidity = pd.DataFrame(
        {
            "median_price": [150.0, 320.0],
            "median_dollar_volume": [1.2e9, 2.1e9],
            "coverage_start": ["2024-01-01", "2024-01-01"],
            "coverage_end": ["2024-03-01", "2024-03-01"],
            "coverage_status": ["complete", "partial"],
        },
        index=["AAPL", "MSFT"],
    )
    stats = draft_stats(state, liquidity)
    assert stats["symbol_count"] == 2
    assert stats["median_price"] == 235.0
    assert stats["coverage_start"] == "2024-01-01"
    assert stats["coverage_end"] == "2024-03-01"
    assert stats["coverage_gap_count"] == 1
