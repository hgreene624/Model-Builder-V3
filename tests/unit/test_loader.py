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
    disk_frame = cache.load_disk("AAPL", "1d", "2024-01-07", "2024-01-15")
    if cache.parquet_available:
        assert disk_frame is not None
    else:
        assert disk_frame is None


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


def test_loader_falls_back_to_yahoo(tmp_path: Path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=10)

    def fail(*args, **kwargs):
        raise RuntimeError("alpaca unavailable")

    def succeed(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        return stub_frame(start)

    loader = MarketDataLoader(
        cache=cache,
        providers={"alpaca": lambda: fail, "yahoo": lambda: succeed},
        default_provider="alpaca",
    )

    frame = loader.load("AAPL", "2024-01-01", "2024-01-05", interval="1d", warmup_bars=0)
    assert not frame.empty


def test_loader_diagnostics_tracks_fallback(tmp_path: Path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=10)

    def fail(*args, **kwargs):
        raise RuntimeError("fail-first")

    def succeed(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        return stub_frame(start)

    loader = MarketDataLoader(
        cache=cache,
        providers={"alpaca": lambda: fail, "yahoo": lambda: succeed},
        default_provider="alpaca",
    )

    frame, diagnostics, error = loader.load_with_diagnostics("AAPL", "2024-01-01", "2024-01-05", interval="1d")

    assert not frame.empty
    assert error is None
    assert diagnostics.cache_hit == "miss"
    assert diagnostics.final_provider == "yahoo"
    assert len(diagnostics.attempts) == 2
    assert diagnostics.attempts[0].provider == "alpaca"
    assert not diagnostics.attempts[0].success
    assert diagnostics.attempts[1].provider == "yahoo"
    assert diagnostics.attempts[1].success
