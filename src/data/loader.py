from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable, Dict, List, Optional

import pandas as pd

from src.data.cache import MarketDataCache


@dataclass
class FetchAttempt:
    provider: str
    success: bool
    error: str | None = None


@dataclass
class SymbolDiagnostics:
    symbol: str
    start: str
    end: str
    interval: str
    warmup_start: str
    cache_hit: str | None = None
    final_provider: str | None = None
    rows_returned: int | None = None
    exception_message: str | None = None
    attempts: List[FetchAttempt] = field(default_factory=list)
    shard_path: str | None = None

    def to_summary(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "cache_hit": self.cache_hit or "",
            "provider": self.final_provider or "",
            "rows": self.rows_returned or 0,
            "error": self.exception_message or "",
        }


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

        frame, _, error = self._load_internal(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            warmup_start=warmup_start,
            provider_name=provider_name,
        )
        if error is not None:
            raise error
        return frame

    def load_with_diagnostics(
        self,
        symbol: str,
        start: str,
        end: str,
        *,
        interval: str = "1d",
        warmup_bars: int = 0,
        provider: str | None = None,
    ) -> tuple[pd.DataFrame, SymbolDiagnostics, Optional[Exception]]:
        provider_name = provider or self.default_provider
        warmup_start = self._apply_warmup(start, warmup_bars, interval)
        frame, diagnostics, error = self._load_internal(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            warmup_start=warmup_start,
            provider_name=provider_name,
            suppress_errors=True,
        )
        return frame, diagnostics, error

    def _load_internal(
        self,
        *,
        symbol: str,
        start: str,
        end: str,
        interval: str,
        warmup_start: str,
        provider_name: str,
        suppress_errors: bool = False,
    ) -> tuple[pd.DataFrame, SymbolDiagnostics, Optional[Exception]]:
        diagnostics = SymbolDiagnostics(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            warmup_start=warmup_start,
        )
        error: Exception | None = None

        memory = self.cache.get_memory(symbol, interval)
        if memory is not None and start >= warmup_start:
            subset = memory.loc[start:end]
            if not subset.empty:
                diagnostics.cache_hit = "memory"
                diagnostics.final_provider = "memory"
                diagnostics.rows_returned = int(subset.shape[0])
                return subset, diagnostics, None
            diagnostics.cache_hit = "memory-empty"
            self.cache.drop_memory(symbol, interval)

        disk = self.cache.load_disk(symbol, interval, warmup_start, end)
        if disk is not None:
            subset = disk.loc[start:end]
            if not subset.empty:
                self.cache.store_memory(symbol, interval, disk)
                diagnostics.cache_hit = "disk"
                diagnostics.final_provider = "disk"
                diagnostics.rows_returned = int(subset.shape[0])
                diagnostics.shard_path = str(self.cache._shard_file(symbol, interval, warmup_start, end))  # type: ignore[attr-defined]
                return subset, diagnostics, None
            diagnostics.cache_hit = "disk-empty"
            self.cache.delete_disk(symbol, interval, warmup_start, end)

        diagnostics.cache_hit = diagnostics.cache_hit or "miss"
        active_provider = provider_name
        fetcher = self._resolve_provider(active_provider)

        try:
            frame = fetcher(symbol, warmup_start, end, interval)
            diagnostics.attempts.append(FetchAttempt(provider=active_provider, success=True))
            diagnostics.final_provider = active_provider
        except Exception as exc:
            diagnostics.attempts.append(FetchAttempt(provider=active_provider, success=False, error=str(exc)))
            if active_provider != "yahoo" and "yahoo" in self.providers:
                active_provider = "yahoo"
                fetcher = self._resolve_provider(active_provider)
                try:
                    frame = fetcher(symbol, warmup_start, end, interval)
                    diagnostics.attempts.append(FetchAttempt(provider=active_provider, success=True))
                    diagnostics.final_provider = active_provider
                except Exception as fallback_exc:
                    diagnostics.attempts.append(
                        FetchAttempt(provider=active_provider, success=False, error=str(fallback_exc))
                    )
                    diagnostics.exception_message = str(fallback_exc)
                    error = fallback_exc
                    empty = pd.DataFrame()
                    diagnostics.rows_returned = 0
                    return empty, diagnostics, error
            else:
                diagnostics.exception_message = str(exc)
                error = exc
                empty = pd.DataFrame()
                diagnostics.rows_returned = 0
                return empty, diagnostics, error

        frame = frame.sort_index()
        if frame.index.tz is None:
            frame.index = frame.index.tz_localize("UTC")

        self.cache.store_memory(symbol, interval, frame)
        shard_path = self.cache.store_disk(symbol, interval, warmup_start, end, frame)
        if shard_path is not None:
            diagnostics.shard_path = str(shard_path)
        final_frame = frame.loc[start:end]
        diagnostics.rows_returned = int(final_frame.shape[0])
        return final_frame, diagnostics, error
