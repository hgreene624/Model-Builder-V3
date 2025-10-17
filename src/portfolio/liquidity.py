from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from src.data.loader import MarketDataLoader, SymbolDiagnostics

COVERAGE_COMPLETENESS_THRESHOLD = 0.9


@dataclass(frozen=True)
class LiquiditySummary:
    requested: int
    retrieved: int
    complete: int
    partial: int
    missing: int

    @property
    def coverage_ratio(self) -> float:
        return (self.retrieved / self.requested) if self.requested else 0.0


def _expected_observations(start: str, end: str) -> int:
    if start > end:
        return 0
    return len(pd.bdate_range(start=start, end=end))


def _business_window(start: str, end: str) -> tuple[str | None, str | None]:
    if start > end:
        return None, None
    window = pd.bdate_range(start=start, end=end)
    if window.empty:
        return None, None
    return window[0].date().isoformat(), window[-1].date().isoformat()


def _exclusive_end(end: str) -> str:
    return (pd.Timestamp(end) + pd.Timedelta(days=1)).date().isoformat()


def _coverage_status(
    observations: int,
    expected: int,
    required_start: str | None,
    required_end: str | None,
    coverage_start: str | None,
    coverage_end: str | None,
) -> str:
    if observations == 0:
        return "missing"
    if expected <= 0:
        return "partial"
    coverage_ratio = observations / expected
    if coverage_ratio >= COVERAGE_COMPLETENESS_THRESHOLD:
        start_ok = required_start is None or (
            coverage_start is not None and coverage_start <= required_start
        )
        end_ok = required_end is None or (coverage_end is not None and coverage_end >= required_end)
        if start_ok and end_ok:
            return "complete"
    return "partial"


def fetch_liquidity(
    loader: MarketDataLoader,
    symbols: Iterable[str],
    start: str,
    end: str,
) -> tuple[pd.DataFrame, LiquiditySummary, list[dict[str, str]]]:
    records: list[dict[str, object]] = []
    errors: list[dict[str, str]] = []

    normalized_symbols = [symbol.strip().upper() for symbol in symbols if symbol]
    for symbol in normalized_symbols:
        frame = pd.DataFrame()
        diagnostics: SymbolDiagnostics | None = None
        error_message: str | None = None
        requested_end = end

        try:
            frame, diagnostics, error = loader.load_with_diagnostics(
                symbol,
                start,
                _exclusive_end(end),
                interval="1d",
                warmup_bars=0,
            )
            if error is not None:
                error_message = str(error)
        except Exception as exc:  # pragma: no cover - defensive
            diagnostics = SymbolDiagnostics(
                symbol=symbol,
                start=start,
                end=end,
                interval="1d",
                warmup_start=start,
            )
            error_message = str(exc)
            frame = pd.DataFrame()

        if not frame.empty:
            frame = frame.loc[start:requested_end]

        observations = int(frame.shape[0])
        expected = _expected_observations(start, requested_end)
        coverage_start = frame.index.min().date().isoformat() if observations else None
        coverage_end = frame.index.max().date().isoformat() if observations else None

        if expected <= 0:
            missing_fraction = 1.0 if observations == 0 else 0.0
        else:
            missing_fraction = 1.0 - min(1.0, observations / expected)

        required_start, required_end = _business_window(start, end)
        status = _coverage_status(
            observations,
            expected,
            required_start,
            required_end,
            coverage_start,
            coverage_end,
        )

        if diagnostics is not None and diagnostics.exception_message and not error_message:
            error_message = diagnostics.exception_message

        if error_message:
            errors.append({"symbol": symbol, "error": error_message})

        shard_hints: dict[str, object] | None = None
        if diagnostics is not None and diagnostics.shard_path:
            shard_hints = {
                "cacheKey": diagnostics.shard_path,
                "segments": [
                    {
                        "symbolCount": 1,
                        "start": coverage_start or start,
                        "end": coverage_end or end,
                    }
                ],
            }

        median_price = None
        if "close" in frame:
            price_value = frame["close"].median()
            if pd.notna(price_value):
                median_price = float(price_value)

        median_dollar_volume = None
        if {"close", "volume"}.issubset(frame.columns):
            dv_value = (frame["close"] * frame["volume"]).median()
            if pd.notna(dv_value):
                median_dollar_volume = float(dv_value)

        records.append(
            {
                "ticker": symbol,
                "median_price": median_price,
                "median_dollar_volume": median_dollar_volume,
                "coverage_start": coverage_start,
                "coverage_end": coverage_end,
                "observations": observations,
                "expected_observations": expected,
                "missing_fraction": missing_fraction,
                "coverage_status": status,
                "shard_hints": shard_hints,
                "error": error_message,
            }
        )

    frame = pd.DataFrame.from_records(records).set_index("ticker") if records else pd.DataFrame()

    summary = LiquiditySummary(
        requested=len(normalized_symbols),
        retrieved=int((frame["coverage_status"] != "missing").sum()) if not frame.empty else 0,
        complete=int((frame["coverage_status"] == "complete").sum()) if not frame.empty else 0,
        partial=int((frame["coverage_status"] == "partial").sum()) if not frame.empty else 0,
        missing=int((frame["coverage_status"] == "missing").sum())
        if not frame.empty
        else len(normalized_symbols),
    )

    return frame, summary, errors
