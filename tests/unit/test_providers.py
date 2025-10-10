from __future__ import annotations

import pandas as pd

from src.data.providers.alpaca_client import AlpacaClient
from src.data.providers.yahoo_client import YahooClient


def _stub_fetch(*_, **__) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2024-01-01", periods=2, freq="D", tz="UTC"),
            "open": [1.0, 2.0],
            "high": [1.5, 2.5],
            "low": [0.5, 1.5],
            "close": [1.2, 2.2],
            "volume": [100, 200],
        }
    ).set_index("timestamp")


def test_alpaca_client_uses_fetcher() -> None:
    client = AlpacaClient(fetcher=_stub_fetch)
    frame = client.fetch_bars("AAPL", "2024-01-01", "2024-01-10", "1d")
    assert len(frame) == 2
    assert frame.index.tzinfo is not None


def test_yahoo_client_uses_fetcher() -> None:
    client = YahooClient(fetcher=_stub_fetch)
    frame = client.fetch_bars("MSFT", "2024-01-01", "2024-01-10", "1d")
    assert "close" in frame.columns
