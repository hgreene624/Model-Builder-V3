from __future__ import annotations

from typing import Iterable

import pandas as pd
import pytest

from src.engine.atr_breakout import (
    ATRBreakoutConfig,
    RiskSettings,
    atr_breakout_signals,
    compute_wilder_atr,
)


@pytest.fixture
def sample_bars() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [99.0, 100.0, 100.8, 101.5, 102.2, 102.7, 103.1, 104.5, 105.0, 110.0],
            "high": [100.5, 101.9, 102.6, 103.8, 104.5, 105.2, 106.4, 107.9, 109.6, 121.0],
            "low": [98.9, 99.5, 100.0, 100.8, 101.2, 101.8, 102.4, 103.9, 104.6, 109.5],
            "close": [100.1, 101.2, 102.0, 103.5, 103.9, 104.6, 106.0, 107.5, 109.2, 120.5],
            "volume": [1_000_000] * 10,
        },
        index=index,
    )


def manual_wilder_atr(bars: pd.DataFrame, window: int) -> pd.Series:
    highs = bars["high"].to_list()
    lows = bars["low"].to_list()
    closes = bars["close"].to_list()
    true_ranges: list[float] = []
    previous_close: float | None = None

    for high, low, close in zip(highs, lows, closes):
        if previous_close is None:
            true_range = high - low
        else:
            true_range = max(high - low, abs(high - previous_close), abs(low - previous_close))
        true_ranges.append(true_range)
        previous_close = close

    index = bars.index
    tr_series = pd.Series(true_ranges, index=index, dtype=float)
    atr_series = tr_series.rolling(window).mean()
    for i in range(window, len(tr_series)):
        atr_series.iloc[i] = (atr_series.iloc[i - 1] * (window - 1) + tr_series.iloc[i]) / window
    return atr_series


def clamp(value: float, bounds: Iterable[float]) -> float:
    lower, upper = bounds
    return max(lower, min(upper, value))


def test_compute_wilder_atr_matches_reference(sample_bars: pd.DataFrame) -> None:
    window = 3
    expected = manual_wilder_atr(sample_bars, window).round(6).rename("atr")
    actual = compute_wilder_atr(sample_bars, window).round(6)
    pd.testing.assert_series_equal(actual, expected)


def test_breakout_generates_trade_intents(sample_bars: pd.DataFrame) -> None:
    config = ATRBreakoutConfig(atr_window=3, breakout_lookback=3, breakout_multiplier=1.5)
    risk = RiskSettings(enabled=True, risk_fraction=0.02, min_weight=0.1, max_weight=0.4)

    signals = atr_breakout_signals("XYZ", sample_bars, config, risk)

    assert list(signals.columns) == ["timestamp", "symbol", "action", "weight", "metadata"]
    assert set(signals["action"].iloc[:-1]) == {"flat"}

    atr_series = compute_wilder_atr(sample_bars, config.atr_window)
    breakout_high = sample_bars["high"].shift(1).rolling(config.breakout_lookback).max()
    breakout_level = breakout_high + atr_series * config.breakout_multiplier

    final_row = signals.iloc[-1]
    expected_weight = clamp(
        risk.risk_fraction
        * sample_bars["close"].iloc[-1]
        / (atr_series.iloc[-1] * config.breakout_multiplier),
        (risk.min_weight, risk.max_weight),
    )

    assert final_row["action"] == "buy"
    assert final_row["weight"] == pytest.approx(expected_weight, rel=1e-6)
    metadata = final_row["metadata"]
    assert metadata["atr"] == pytest.approx(atr_series.iloc[-1], rel=1e-6)
    assert metadata["breakout_level"] == pytest.approx(breakout_level.iloc[-1], rel=1e-6)


def test_risk_sizing_respects_bounds(sample_bars: pd.DataFrame) -> None:
    config = ATRBreakoutConfig(atr_window=3, breakout_lookback=3, breakout_multiplier=1.5)
    low_risk = RiskSettings(enabled=True, risk_fraction=0.005, min_weight=0.1, max_weight=0.4)
    high_risk = RiskSettings(enabled=True, risk_fraction=0.08, min_weight=0.1, max_weight=0.4)

    low_signals = atr_breakout_signals("XYZ", sample_bars, config, low_risk)
    high_signals = atr_breakout_signals("XYZ", sample_bars, config, high_risk)

    assert low_signals.iloc[-1]["weight"] == pytest.approx(low_risk.min_weight, rel=1e-6)
    assert high_signals.iloc[-1]["weight"] == pytest.approx(high_risk.max_weight, rel=1e-6)
