from __future__ import annotations

from typing import Callable

import pandas as pd

FetchFunc = Callable[[str, str, str, str], pd.DataFrame]


class YahooClient:
    """Wrapper around Yahoo Finance downloads with injectable fetcher."""

    def __init__(self, fetcher: FetchFunc | None = None) -> None:
        self._fetcher = fetcher or self._default_fetcher()

    def _default_fetcher(self) -> FetchFunc:
        import yfinance as yf

        def fetch(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
            data = yf.download(symbol, start=start, end=end, interval=interval, progress=False)
            data = data.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Adj Close": "adj_close",
                    "Volume": "volume",
                }
            )
            data.index = pd.to_datetime(data.index, utc=True)
            return data[["open", "high", "low", "close", "volume"]]

        return fetch

    def fetch_bars(self, symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        df = self._fetcher(symbol, start, end, interval)
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Dataframe missing required columns: {missing}")
        return df[required].sort_index()
