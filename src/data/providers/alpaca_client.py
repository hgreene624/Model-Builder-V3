from __future__ import annotations

from typing import Callable

import pandas as pd


FetchFunc = Callable[[str, str, str, str], pd.DataFrame]


class AlpacaClient:
    """Thin wrapper around Alpaca stock data with injectable fetcher for testing."""

    def __init__(self, fetcher: FetchFunc | None = None) -> None:
        self._fetcher = fetcher or self._default_fetcher()

    def _default_fetcher(self) -> FetchFunc:
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient()

        def fetch(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
            timeframe = {"1d": TimeFrame.Day}.get(interval)
            if timeframe is None:
                raise ValueError(f"Unsupported interval for Alpaca: {interval}")

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=timeframe,
                start=start,
                end=end,
            )
            result = client.get_stock_bars(request)
            df = result.df
            if isinstance(df.index, pd.MultiIndex):
                # Flatten multi-index (symbol, timestamp)
                df = df.reset_index(level=0, drop=True)
            df = df.sort_index()
            df.index = pd.to_datetime(df.index, utc=True)
            df.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                },
                inplace=True,
            )
            return df[["open", "high", "low", "close", "volume"]]

        return fetch

    def fetch_bars(self, symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
        df = self._fetcher(symbol, start, end, interval)
        if "timestamp" in df.columns:
            df = df.set_index("timestamp")
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        df = df.sort_index()
        required = ["open", "high", "low", "close", "volume"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Dataframe missing required columns: {missing}")
        return df[required]
