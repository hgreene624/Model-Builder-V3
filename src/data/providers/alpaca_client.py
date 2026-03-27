from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

import pandas as pd

from src.config.settings import AppSettings

FetchFunc = Callable[[str, str, str, str], pd.DataFrame]


class AlpacaClient:
    """Thin wrapper around Alpaca stock data with injectable fetcher for testing."""

    def __init__(self, fetcher: FetchFunc | None = None) -> None:
        self.settings = AppSettings.from_env()

        self._fetcher = fetcher or self._default_fetcher()

    def _default_fetcher(self) -> FetchFunc:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        if not self.settings.has_alpaca_credentials:
            raise RuntimeError("Alpaca credentials are required but were not provided.")

        client_kwargs = {
            "api_key": self.settings.alpaca_key_id,
            "secret_key": self.settings.alpaca_secret_key,
            "raw_data": True,
        }

        data_base = (
            self.settings.alpaca_data_base_url
            or os.getenv("APCA_DATA_API_BASE_URL")
            or "https://data.alpaca.markets"
        )
        client_kwargs["url_override"] = data_base

        client = StockHistoricalDataClient(**client_kwargs)

        def fetch(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
            timeframe = {"1d": TimeFrame.Day}.get(interval)
            if timeframe is None:
                raise ValueError(f"Unsupported interval for Alpaca: {interval}")

            start_dt = _to_utc(start)
            end_dt = _to_utc(end)

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=timeframe,
                start=start_dt,
                end=end_dt,
                feed=DataFeed.IEX,
                adjustment=Adjustment.RAW,
            )
            result = client.get_stock_bars(request)
            df = _alpaca_payload_to_frame(result, symbol)
            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index(level=0, drop=True)
            df = _normalize_alpaca_frame(df, symbol)
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


def _to_utc(value: str) -> datetime:
    ts = pd.Timestamp(value, tz="UTC")
    return ts.to_pydatetime()


def _alpaca_payload_to_frame(payload: Any, symbol: str) -> pd.DataFrame:
    """Convert various Alpaca SDK payload shapes into a Pandas DataFrame."""
    if hasattr(payload, "df"):
        return payload.df.copy()

    bars = getattr(payload, "bars", None)
    if bars is None and hasattr(payload, "data"):
        data = payload.data
        if isinstance(data, dict):
            bars = data.get("bars") or data.get(symbol)

    if bars is None and isinstance(payload, dict):
        bars = payload.get("bars") or payload.get(symbol)

    if bars is not None:
        records: list[dict[str, Any]] = []
        for bar in bars:
            if hasattr(bar, "dict"):
                records.append(bar.dict())
            elif hasattr(bar, "model_dump"):
                records.append(bar.model_dump())
            elif hasattr(bar, "__dict__"):
                records.append(vars(bar))
            elif isinstance(bar, dict):
                records.append(bar)
            else:
                records.append({"value": bar})
        if records:
            return pd.DataFrame(records)

    return pd.DataFrame(payload)


def _normalize_alpaca_frame(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Standardize Alpaca responses to a UTC-indexed OHLCV frame."""
    rename_map = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
        "o": "open",
        "h": "high",
        "l": "low",
        "c": "close",
        "v": "volume",
        "t": "timestamp",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")

    if "symbol" in df.columns:
        df = df.drop(columns=["symbol"])

    if isinstance(df.columns, pd.MultiIndex):
        if symbol in df.columns.get_level_values(0):
            df = df[symbol]
        elif symbol in df.columns.get_level_values(-1):
            df = df.xs(symbol, axis=1, level=-1)
        else:
            for level in range(df.columns.nlevels):
                level_values = df.columns.get_level_values(level)
                if {"open", "high", "low", "close", "volume"}.issubset(
                    {str(v).lower() for v in level_values}
                ):
                    df = df.droplevel(level, axis=1)
                    break
        df.columns = [str(c).lower() for c in df.columns]

    if df.index.name == "symbol":
        df = df.reset_index(drop=True)

    if isinstance(df.index, pd.DatetimeIndex):
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
    else:
        df.index = pd.to_datetime(df.index, utc=True)

    df = df.sort_index()
    return df
