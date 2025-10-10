from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader


def stub_frame(start: str, periods: int = 5) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range(start, periods=periods, freq="D", tz="UTC"),
            "open": range(periods),
            "high": range(periods),
            "low": range(periods),
            "close": range(periods),
            "volume": [100] * periods,
        }
    ).set_index("timestamp")


def test_loader_expands_warmup(tmp_path: Path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=10)
    calls: list[tuple[str, str]] = []

    def fetch(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        calls.append((start, end))
        return stub_frame(start)

    loader = MarketDataLoader(
        cache=cache,
        providers={"alpaca": lambda: fetch},
        default_provider="alpaca",
    )

    loader.load("AAPL", "2024-01-10", "2024-01-15", interval="1d", warmup_bars=3)

    assert calls[0][0] == "2024-01-07"  # warmup applied
    assert cache.load_disk("AAPL", "1d", "2024-01-07", "2024-01-15") is not None


def test_loader_uses_cache(tmp_path: Path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=10)
    calls = 0

    def fetch(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        nonlocal calls
        calls += 1
        return stub_frame(start)

    loader = MarketDataLoader(
        cache=cache,
        providers={"alpaca": lambda: fetch},
        default_provider="alpaca",
    )

    loader.load("AAPL", "2024-01-01", "2024-01-05", interval="1d", warmup_bars=0)
    loader.load("AAPL", "2024-01-01", "2024-01-05", interval="1d", warmup_bars=0)

    assert calls == 1  # second call hit cache
