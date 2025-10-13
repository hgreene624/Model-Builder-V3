"""Utilities for deriving rolling momentum heatmap summaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence

import numpy as np
import pandas as pd

DEFAULT_INTERVALS: tuple[int, ...] = (5, 10, 20, 60)
TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class MomentumHeatmap:
    """Rolling-return summary used by the best-candidate module."""

    windows: List[int]
    dates: List[str]
    matrix: List[List[float | None]]
    narrative: str
    colorscale: str = "RdYlGn"
    zmid: float = 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "windows": list(self.windows),
            "dates": list(self.dates),
            "matrix": [
                [None if value is None or pd.isna(value) else float(value) for value in row] for row in self.matrix
            ],
            "narrative": self.narrative,
            "colorscale": self.colorscale,
            "zmid": self.zmid,
        }


def _normalize_series(series: pd.Series) -> pd.Series:
    if not isinstance(series, pd.Series):
        raise TypeError("series must be a pandas Series.")
    normalized = series.dropna()
    if normalized.empty:
        return normalized
    index = pd.to_datetime(normalized.index)
    if hasattr(index, "tz") and index.tz is not None:
        index = index.tz_convert(None)
    normalized = normalized.copy()
    normalized.index = index
    normalized = normalized.sort_index()
    return normalized.astype(float)


def _build_narrative(values_by_interval: dict[int, float]) -> str:
    if not values_by_interval:
        return "Holdout window is too short to derive momentum readings."

    positives = {k: v for k, v in values_by_interval.items() if v > 0}
    negatives = {k: v for k, v in values_by_interval.items() if v < 0}

    if positives and not negatives:
        strongest = max(positives.items(), key=lambda item: item[1])
        return (
            "Momentum is positive across all tracked windows; "
            f"strongest over {strongest[0]}-day at {strongest[1]:.1%} annualized."
        )

    if negatives and not positives:
        weakest = min(negatives.items(), key=lambda item: item[1])
        return (
            "Momentum is negative across all tracked windows; "
            f"weakest over {weakest[0]}-day at {weakest[1]:.1%} annualized."
        )

    if positives and negatives:
        strongest = max(positives.items(), key=lambda item: item[1])
        weakest = min(negatives.items(), key=lambda item: item[1])
        return (
            "Momentum is mixed: "
            f"{strongest[0]}-day prints {strongest[1]:.1%}, "
            f"while {weakest[0]}-day sits at {weakest[1]:.1%}."
        )

    # All zero returns; treat as flat.
    return "Momentum is flat across tracked windows."


def build_momentum_heatmap(
    series: pd.Series,
    *,
    intervals: Sequence[int] = DEFAULT_INTERVALS,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
) -> MomentumHeatmap:
    """Compute annualized momentum readings and narrative for the holdout window."""

    normalized = _normalize_series(series)
    if normalized.empty or len(normalized) < 2:
        return MomentumHeatmap(
            windows=list(intervals),
            dates=[],
            matrix=[],
            narrative="Holdout window is too short to derive momentum readings.",
        )

    returns = normalized.pct_change().dropna()
    if returns.empty:
        return MomentumHeatmap(
            windows=list(intervals),
            dates=[],
            matrix=[],
            narrative="Holdout window is too short to derive momentum readings.",
        )

    percent_frame = pd.DataFrame(index=returns.index)
    decimal_frame = pd.DataFrame(index=returns.index)
    for window in intervals:
        window = int(window)
        if window <= 0:
            continue
        rolling_product = (1 + returns).rolling(window=window, min_periods=window).apply(np.prod, raw=True)
        if rolling_product.empty:
            continue
        rolling_product = rolling_product.where(rolling_product > 0)
        annualized = rolling_product.pow(trading_days_per_year / window) - 1
        decimal_frame[window] = annualized
        percent_frame[window] = annualized * 100

    percent_frame = percent_frame.dropna(how="all").sort_index()
    if percent_frame.empty:
        return MomentumHeatmap(
            windows=list(intervals),
            dates=[],
            matrix=[],
            narrative="Holdout window is too short to derive momentum readings.",
        )

    decimal_frame = decimal_frame.loc[percent_frame.index]

    windows_order = [int(window) for window in intervals if int(window) in percent_frame.columns]
    dates = [timestamp.isoformat() for timestamp in percent_frame.index]
    matrix: List[List[float | None]] = []
    for window in windows_order:
        row = percent_frame[window]
        matrix.append([None if pd.isna(value) else float(value) for value in row])

    latest_values: dict[int, float] = {}
    latest_frame = decimal_frame.dropna(how="all")
    if not latest_frame.empty:
        latest_row = latest_frame.iloc[-1]
        latest_values = {
            int(window): float(value)
            for window, value in latest_row.items()
            if not pd.isna(value)
        }

    narrative = _build_narrative(latest_values)
    return MomentumHeatmap(windows=windows_order, dates=dates, matrix=matrix, narrative=narrative)


__all__ = ["MomentumHeatmap", "build_momentum_heatmap"]
