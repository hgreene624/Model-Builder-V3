from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from src.data.loader import MarketDataLoader
from src.data.cache import MarketDataCache
from src.portfolio.services import (
    apply_filters,
    build_portfolio,
    compute_liquidity_table,
    normalize_symbols,
)


def frame(start: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start, periods=5, freq="D", tz="UTC"),
            "open": [1, 2, 3, 4, 5],
            "high": [2, 3, 4, 5, 6],
            "low": [0, 1, 2, 3, 4],
            "close": [1.5, 2.5, 3.5, 4.5, 5.5],
            "volume": [10, 20, 30, 40, 50],
        }
    ).set_index("timestamp")


def test_normalize_and_filter() -> None:
    symbols = normalize_symbols([" aapl", "AAPL", "msft "])
    assert symbols == ["AAPL", "MSFT"]
    filtered = apply_filters(symbols, include_substring="ap")
    assert filtered == ["AAPL"]


def test_compute_liquidity_table(tmp_path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=4)

    def provider(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        return frame(start)

    loader = MarketDataLoader(cache=cache, providers={"alpaca": lambda: provider})
    table = compute_liquidity_table(loader, ["AAPL"], "2024-01-01", "2024-01-05")
    assert not table.empty
    assert table.loc[0, "symbol"] == "AAPL"
    assert table.loc[0, "median_price"] == pytest.approx(3.5)


def test_build_portfolio(tmp_path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=4)

    def provider(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        return frame(start)

    loader = MarketDataLoader(cache=cache, providers={"alpaca": lambda: provider})
    portfolio, preview = build_portfolio(
        name="Sample",
        description="desc",
        source="manual",
        seed_reference="seed",
        symbols=["AAPL", "MSFT", "GOOGL"],
        max_count=2,
        coverage_start="2024-01-01",
        coverage_end="2024-01-05",
        loader=loader,
        filters={"include": ""},
    )

    assert len(portfolio.tickers) == 2
    assert preview.table.shape[0] == 2
    assert "median_price" in portfolio.liquidity_stats
    assert portfolio.portfolio_id == "sample"
    assert portfolio.coverage_summary["start"] == "2024-01-01"
    assert portfolio.coverage_summary["coverage_gap_count"] == 0
    assert portfolio.shard_hints == {}
    assert portfolio.schema_version == "1.1.0"


def test_build_portfolio_debug(tmp_path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=4)

    def provider(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        return frame(start)

    loader = MarketDataLoader(cache=cache, providers={"alpaca": lambda: provider})
    portfolio, preview = build_portfolio(
        name="Sample",
        description=None,
        source="manual",
        seed_reference=None,
        symbols=["AAPL", "MSFT"],
        max_count=2,
        coverage_start="2024-01-01",
        coverage_end="2024-01-05",
        loader=loader,
        debug=True,
    )

    assert preview.diagnostics is not None
    assert len(preview.diagnostics) == len(preview.tickers)
    assert all(diag.final_provider == "alpaca" for diag in preview.diagnostics)
