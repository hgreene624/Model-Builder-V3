from __future__ import annotations

from datetime import date, timedelta

from model_builder.optimization.coverage import derive_plan


def _date_range(start: date, days: int) -> list[date]:
    return [start + timedelta(days=offset) for offset in range(days)]


def test_coverage_plan_enforces_windows_and_extends_warmup() -> None:
    start = date(2025, 1, 1)
    dates = _date_range(start, 8)  # eight sequential trading days

    plan = derive_plan(
        portfolio_id="portfolio-123",
        coverage_dates=dates,
        train_percentage=0.5,
        warmup_days=5,
    )

    # Training slice consumes first four days (rounded), leaving room for holdout.
    assert plan.train.start == start
    assert plan.train.end == start + timedelta(days=3)

    # Warmup requires five days; only four exist pre-holdout, so it extends one day forward.
    assert plan.warmup.required_days == 5
    assert plan.warmup.deficit_days == 1
    assert plan.warmup.slice.start == start
    assert plan.warmup.slice.end == start + timedelta(days=4)
    assert not plan.warmup.satisfied

    # Holdout shifts forward by the deficit and remains within overall coverage.
    assert plan.holdout.start == start + timedelta(days=5)
    assert plan.holdout.end == dates[-1]
    assert plan.holdout.days == 3

    # Coverage window reflects each derived slice and enforces warmup start.
    window = plan.window
    assert window.portfolio_id == "portfolio-123"
    assert window.coverage_start == dates[0]
    assert window.coverage_end == dates[-1]
    assert window.train_start == plan.train.start
    assert window.train_end == plan.train.end
    assert window.holdout_start == plan.holdout.start
    assert window.holdout_end == plan.holdout.end
    assert window.warmup_start == plan.warmup.slice.start
