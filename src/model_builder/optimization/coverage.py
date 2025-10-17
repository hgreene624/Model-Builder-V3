"""Utilities for deriving training, holdout, and warmup window slices."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from model_builder.profiles.constants import MIN_HOLDOUT_DAYS
from model_builder.profiles.models import CoverageWindow


@dataclass(frozen=True)
class CoverageSlice:
    """Simple inclusive date slice."""

    start: date
    end: date

    def validate(self) -> None:
        if self.end < self.start:
            raise ValueError("Coverage slice end must be on or after the start date.")

    @property
    def days(self) -> int:
        """Inclusive day count."""
        return (self.end - self.start).days + 1


@dataclass(frozen=True)
class WarmupPlan:
    """Metadata for warmup allocation."""

    slice: CoverageSlice
    required_days: int
    deficit_days: int

    @property
    def satisfied(self) -> bool:
        return self.deficit_days == 0


@dataclass(frozen=True)
class CoveragePlan:
    """Full breakdown of coverage slices."""

    window: CoverageWindow
    train: CoverageSlice
    holdout: CoverageSlice
    warmup: WarmupPlan


def _to_date(value: date | str) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def _normalize_dates(dates: Sequence[date | str]) -> list[date]:
    normalized = sorted({_to_date(value) for value in dates})
    if not normalized:
        raise ValueError("Coverage requires at least one trading day.")
    return normalized


def _compute_partition(total_days: int, train_percentage: float) -> int:
    if not (0 < train_percentage < 1):
        raise ValueError("train_percentage must be between 0 and 1 (exclusive).")

    # Base training allocation using round-to-nearest for stability.
    suggested_train = max(1, int(round(total_days * train_percentage)))
    max_train = max(1, total_days - MIN_HOLDOUT_DAYS)
    train_count = min(suggested_train, max_train)

    # Ensure holdout allocation never violates the minimum requirement.
    holdout_count = total_days - train_count
    if holdout_count < MIN_HOLDOUT_DAYS:
        holdout_count = MIN_HOLDOUT_DAYS
        train_count = total_days - holdout_count

    if train_count <= 0 or holdout_count <= 0:
        raise ValueError(
            "Coverage range is too small to satisfy training and holdout requirements."
        )

    return train_count


def derive_plan(
    *,
    portfolio_id: str,
    coverage_dates: Sequence[date | str],
    train_percentage: float,
    warmup_days: int,
) -> CoveragePlan:
    """Derive coverage slices enforcing warmup and holdout constraints."""

    if warmup_days < 1:
        raise ValueError("warmup_days must be >= 1.")

    dates = _normalize_dates(coverage_dates)
    total_days = len(dates)
    if total_days < MIN_HOLDOUT_DAYS + 1:
        raise ValueError("Coverage range must include at least two trading days.")

    train_count = _compute_partition(total_days, train_percentage)
    pre_holdout_dates = dates[:train_count]
    train_slice = CoverageSlice(start=pre_holdout_dates[0], end=pre_holdout_dates[-1])
    train_slice.validate()

    # Warmup handling: allocate as many days as possible before holdout, then spill into holdout.
    warmup_pre_holdout = min(len(pre_holdout_dates), warmup_days)
    warmup_deficit = warmup_days - warmup_pre_holdout

    holdout_start_index = train_count + warmup_deficit
    if holdout_start_index >= total_days:
        raise ValueError(
            "Coverage range cannot satisfy warmup requirements while leaving holdout data."
        )

    holdout_slice = CoverageSlice(start=dates[holdout_start_index], end=dates[-1])
    holdout_slice.validate()

    if holdout_slice.days < MIN_HOLDOUT_DAYS:
        raise ValueError(
            "Holdout window does not contain the minimum required trading days after warmup."
        )

    warmup_start_index = 0
    warmup_end_index = holdout_start_index - 1
    warmup_slice = CoverageSlice(start=dates[warmup_start_index], end=dates[warmup_end_index])
    warmup_slice.validate()

    window = CoverageWindow(
        portfolio_id=portfolio_id,
        coverage_start=dates[0],
        coverage_end=dates[-1],
        train_start=train_slice.start,
        train_end=train_slice.end,
        holdout_start=holdout_slice.start,
        holdout_end=holdout_slice.end,
        warmup_start=warmup_slice.start,
    )
    window.validate()

    warmup_plan = WarmupPlan(
        slice=warmup_slice,
        required_days=warmup_days,
        deficit_days=warmup_deficit,
    )

    return CoveragePlan(window=window, train=train_slice, holdout=holdout_slice, warmup=warmup_plan)
