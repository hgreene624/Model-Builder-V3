from __future__ import annotations

from datetime import timedelta
from typing import Callable, Dict

import pandas as pd

from src.data.cache import MarketDataCache


class MarketDataLoader:
    """Coordinate fetches between providers and cache with warmup handling."""

    def __init__(
        self,
        cache: MarketDataCache,
        providers: Dict[str, Callable[[], Callable[[str, str, str, str], pd.DataFrame]]],
        default_provider: str = "alpaca",
    ) -> None:
        self.cache = cache
        self.providers = providers
        self.default_provider = default_provider

    def _resolve_provider(self, name: str) -> Callable[[str, str, str, str], pd.DataFrame]:
        factory = self.providers.get(name)
        if factory is None:
            raise ValueError(f"Unknown provider: {name}")
        return factory()

    def _apply_warmup(self, start: str, warmup_bars: int, interval: str) -> str:
        if warmup_bars <= 0:
            return start
        start_ts = pd.Timestamp(start, tz="UTC")
        if interval == "1d":
            delta = timedelta(days=warmup_bars)
        else:
            delta = timedelta(minutes=warmup_bars)
        warmup_start = start_ts - delta
        return warmup_start.strftime("%Y-%m-%d")

    def load(
        self,
        symbol: str,
        start: str,
        end: str,
        *,
        interval: str = "1d",
        warmup_bars: int = 0,
        provider: str | None = None,
    ) -> pd.DataFrame:
        provider_name = provider or self.default_provider
        warmup_start = self._apply_warmup(start, warmup_bars, interval)

        memory = self.cache.get_memory(symbol, interval)
        if memory is not None and start >= warmup_start:
            return memory.loc[start:end]

        disk = self.cache.load_disk(symbol, interval, warmup_start, end)
        if disk is not None:
            self.cache.store_memory(symbol, interval, disk)
            return disk.loc[start:end]

        fetcher = self._resolve_provider(provider_name)
        frame = fetcher(symbol, warmup_start, end, interval)
        frame = frame.sort_index()
        if frame.index.tz is None:
            frame.index = frame.index.tz_localize("UTC")

        self.cache.store_memory(symbol, interval, frame)
        self.cache.store_disk(symbol, interval, warmup_start, end, frame)
        return frame.loc[start:end]
