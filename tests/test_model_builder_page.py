from datetime import date
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
src_path = str(PROJECT_ROOT / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)
else:
    sys.path.remove(src_path)
    sys.path.insert(0, src_path)

tests_path = str(PROJECT_ROOT / "tests")
if tests_path in sys.path:
    sys.path.remove(tests_path)
    sys.path.append(tests_path)

root_path = str(PROJECT_ROOT)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

import pytest

coverage_module = pytest.importorskip("model_builder.optimization.coverage")
profiles_module = pytest.importorskip("model_builder.profiles.models")
page_module = pytest.importorskip("model_builder.ui.pages.model_builder_page")

CoveragePlan = coverage_module.CoveragePlan
CoverageSlice = coverage_module.CoverageSlice
WarmupPlan = coverage_module.WarmupPlan
CoverageWindow = profiles_module.CoverageWindow
_create_timezone_aligner = page_module._create_timezone_aligner
_resolve_equity_column_names = page_module._resolve_equity_column_names
_split_equity_curve = page_module._split_equity_curve


def _build_coverage_plan() -> CoveragePlan:
    warmup_slice = CoverageSlice(start=date(2025, 5, 25), end=date(2025, 5, 31))
    train_slice = CoverageSlice(start=date(2025, 6, 1), end=date(2025, 6, 3))
    holdout_slice = CoverageSlice(start=date(2025, 6, 4), end=date(2025, 6, 6))

    window = CoverageWindow(
        portfolio_id="TEST",
        coverage_start=warmup_slice.start,
        coverage_end=holdout_slice.end,
        train_start=train_slice.start,
        train_end=train_slice.end,
        holdout_start=holdout_slice.start,
        holdout_end=holdout_slice.end,
        warmup_start=warmup_slice.start,
    )
    warmup_plan = WarmupPlan(slice=warmup_slice, required_days=7, deficit_days=0)

    return CoveragePlan(window=window, train=train_slice, holdout=holdout_slice, warmup=warmup_plan)


def test_split_equity_curve_with_equity_column() -> None:
    plan = _build_coverage_plan()
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-06-01", periods=6, freq="D"),
            "equity": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
        }
    )
    align = _create_timezone_aligner(frame["timestamp"])
    split = _split_equity_curve(
        frame,
        plan,
        x_field="timestamp",
        training_column="equity",
        holdout_column="equity",
        align=align,
    )

    assert list(split.training["equity"]) == [100.0, 101.0, 102.0]
    assert list(split.holdout["equity"]) == [103.0, 104.0, 105.0]
    assert split.expected_holdout_points == 3
    assert split.observed_holdout_points == 3


def test_resolve_equity_column_names_prefers_segment_specific_columns() -> None:
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-06-01", periods=4, freq="D"),
            "train_equity": [100.0, 101.0, 102.0, None],
            "holdout_equity": [None, None, None, 105.0],
            "equity": [200.0, 201.0, 202.0, 203.0],
        }
    )

    training_column, holdout_column = _resolve_equity_column_names(frame, x_field="timestamp")

    assert training_column == "train_equity"
    assert holdout_column == "holdout_equity"


def test_split_equity_curve_handles_missing_holdout_values() -> None:
    plan = _build_coverage_plan()
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-06-01", periods=6, freq="D"),
            "equity": [100.0, 101.0, 102.0, None, None, None],
        }
    )
    align = _create_timezone_aligner(frame["timestamp"])
    split = _split_equity_curve(
        frame,
        plan,
        x_field="timestamp",
        training_column="equity",
        holdout_column="equity",
        align=align,
    )

    assert split.expected_holdout_points == 3
    assert split.observed_holdout_points == 0
    assert split.holdout.empty


def test_split_equity_curve_supports_timezone_aware_timestamps() -> None:
    plan = _build_coverage_plan()
    frame = pd.DataFrame(
        {
            "timestamp": pd.date_range("2025-06-01", periods=6, freq="D", tz="UTC"),
            "equity": [100.0, 101.5, 102.5, 103.5, 104.5, 105.5],
        }
    )
    align = _create_timezone_aligner(frame["timestamp"])
    split = _split_equity_curve(
        frame,
        plan,
        x_field="timestamp",
        training_column="equity",
        holdout_column="equity",
        align=align,
    )

    assert split.train_end_ts.tzinfo is not None
    assert split.holdout_start_ts.tzinfo is not None
    assert list(split.training["timestamp"]) == list(frame["timestamp"].iloc[:3])
    assert list(split.holdout["timestamp"]) == list(frame["timestamp"].iloc[3:])
