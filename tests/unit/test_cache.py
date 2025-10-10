from __future__ import annotations

import pandas as pd
import pytest

from src.data.cache import MarketDataCache


def make_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
            "open": [1, 2, 3],
            "high": [2, 3, 4],
            "low": [0, 1, 2],
            "close": [1.5, 2.5, 3.5],
            "volume": [10, 20, 30],
        }
    ).set_index("timestamp")


def test_memory_cache_eviction(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=1)

    cache.store_memory("AAPL", "1d", make_frame())
    assert cache.get_memory("AAPL", "1d") is not None

    cache.store_memory("MSFT", "1d", make_frame())
    assert cache.get_memory("MSFT", "1d") is not None
    assert cache.get_memory("AAPL", "1d") is None  # evicted


def test_disk_roundtrip(tmp_path) -> None:
    cache = MarketDataCache(root=tmp_path, max_items=2)
    frame = make_frame()

    cache.store_disk("AAPL", "1d", "2024-01-01", "2024-01-03", frame)
    loaded = cache.load_disk("AAPL", "1d", "2024-01-01", "2024-01-03")

    assert loaded is not None
    pd.testing.assert_frame_equal(loaded, frame)
