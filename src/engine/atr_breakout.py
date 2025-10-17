from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("high", "low", "close")


@dataclass(frozen=True)
class ATRBreakoutConfig:
    atr_window: int
    breakout_lookback: int
    breakout_multiplier: float

    def __post_init__(self) -> None:
        if self.atr_window <= 0:
            raise ValueError("atr_window must be positive")
        if self.breakout_lookback <= 0:
            raise ValueError("breakout_lookback must be positive")
        if self.breakout_multiplier <= 0:
            raise ValueError("breakout_multiplier must be positive")

    @property
    def warmup(self) -> int:
        return max(self.atr_window, self.breakout_lookback) + 1


@dataclass(frozen=True)
class RiskSettings:
    enabled: bool
    risk_fraction: float
    min_weight: float
    max_weight: float
    fallback_weight: float | None = None

    def __post_init__(self) -> None:
        if self.min_weight < 0 or self.max_weight < 0:
            raise ValueError("weights must be non-negative")
        if self.min_weight > self.max_weight:
            raise ValueError("min_weight cannot exceed max_weight")
        if self.enabled and self.risk_fraction <= 0:
            raise ValueError("risk_fraction must be positive when risk sizing is enabled")
        if (self.fallback_weight is not None) and not (
            self.min_weight <= self.fallback_weight <= self.max_weight
        ):
            raise ValueError("fallback_weight must lie between min_weight and max_weight")

    def clamp(self, value: float) -> float:
        return max(self.min_weight, min(self.max_weight, value))

    def fallback(self) -> float:
        if self.fallback_weight is not None:
            return self.fallback_weight
        return self.clamp(self.max_weight if not self.enabled else self.min_weight)


def _validate_bars(bars: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in bars.columns]
    if missing:
        raise KeyError(f"bars frame missing required columns: {', '.join(missing)}")


def compute_true_range(bars: pd.DataFrame) -> pd.Series:
    _validate_bars(bars)
    high = bars["high"]
    low = bars["low"]
    close = bars["close"]
    previous_close = close.shift(1)

    ranges = pd.concat(
        [high - low, (high - previous_close).abs(), (low - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    return ranges.rename("true_range")


def compute_wilder_atr(bars: pd.DataFrame, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be positive")

    true_range = compute_true_range(bars)
    atr = true_range.rolling(window).mean()

    values = atr.to_numpy()
    tr_values = true_range.to_numpy()
    for idx in range(window, len(tr_values)):
        prev = values[idx - 1]
        values[idx] = (prev * (window - 1) + tr_values[idx]) / window

    return pd.Series(values, index=true_range.index, name="atr")


def _risk_weight(
    close_price: float, atr_value: float, config: ATRBreakoutConfig, risk: RiskSettings
) -> float:
    if not risk.enabled:
        return risk.fallback()
    if not np.isfinite(atr_value) or atr_value <= 0:
        return 0.0
    exposure = risk.risk_fraction * close_price / (atr_value * config.breakout_multiplier)
    return risk.clamp(exposure)


def atr_breakout_signals(
    symbol: str,
    bars: pd.DataFrame,
    config: ATRBreakoutConfig,
    risk: RiskSettings,
) -> pd.DataFrame:
    _validate_bars(bars)
    atr = compute_wilder_atr(bars, config.atr_window)

    breakout_high = bars["high"].shift(1).rolling(config.breakout_lookback).max()
    breakout_level = breakout_high + atr * config.breakout_multiplier

    records: list[dict[str, object]] = []
    close_series = bars["close"]

    for timestamp, close_price, atr_value, level in zip(
        bars.index, close_series, atr, breakout_level, strict=False
    ):
        if not np.isfinite(level) or not np.isfinite(close_price):
            action = "flat"
            weight = 0.0
        elif close_price > level:
            action = "buy"
            weight = _risk_weight(float(close_price), float(atr_value), config, risk)
        else:
            action = "flat"
            weight = 0.0

        metadata = {
            "atr": float(atr_value) if np.isfinite(atr_value) else None,
            "breakout_level": float(level) if np.isfinite(level) else None,
        }
        records.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "action": action,
                "weight": float(weight),
                "metadata": metadata,
            }
        )

    return pd.DataFrame.from_records(
        records,
        columns=["timestamp", "symbol", "action", "weight", "metadata"],
    )
