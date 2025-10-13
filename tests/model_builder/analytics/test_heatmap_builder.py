import pandas as pd
import pytest

from model_builder.analytics import MomentumHeatmap, build_momentum_heatmap


def _build_series(values: list[float], start: str = "2024-01-01") -> pd.Series:
    index = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(values, index=index)


def test_build_momentum_heatmap_positive_trend() -> None:
    series = _build_series([100 * 1.002**i for i in range(80)])

    heatmap = build_momentum_heatmap(series)

    assert isinstance(heatmap, MomentumHeatmap)
    assert heatmap.windows == [5, 10, 20, 60]
    assert len(heatmap.dates) > 0
    assert len(heatmap.matrix) == len(heatmap.windows)
    assert all(len(row) == len(heatmap.dates) for row in heatmap.matrix)
    assert "positive" in heatmap.narrative.lower()

    # Validate the 5-day reading matches the expected annualised return.
    last = float(series.iloc[-1])
    prior = float(series.iloc[-6])
    expected = ((last / prior) ** (252 / 5) - 1) * 100
    five_day_row = heatmap.matrix[0]
    last_value = next(value for value in reversed(five_day_row) if value is not None)
    assert last_value == pytest.approx(expected, rel=1e-6)


def test_build_momentum_heatmap_negative_trend() -> None:
    series = _build_series([120 * 0.998**i for i in range(90)])

    heatmap = build_momentum_heatmap(series)

    assert len(heatmap.dates) > 0
    assert "negative" in heatmap.narrative.lower()
    for row in heatmap.matrix:
        values = [value for value in row if value is not None]
        assert values, "expected non-empty momentum row"
        assert all(value < 0 for value in values)


def test_build_momentum_heatmap_mixed_trend() -> None:
    values = []
    for i in range(65):
        if i < 10:
            values.append(100 + i)  # early rise
        elif i < 50:
            values.append(110 - (i - 10) * 0.8)  # gradual drawdown
        else:
            values.append(78 + (i - 50) * 1.5)  # recovery but still below start
    series = _build_series(values)

    heatmap = build_momentum_heatmap(series)

    short_row = [value for value in heatmap.matrix[0] if value is not None]
    long_row = [value for value in heatmap.matrix[-1] if value is not None]
    assert short_row and long_row
    short_term = short_row[-1]
    long_term = long_row[-1]
    assert short_term > 0 and long_term < 0
    assert "mixed" in heatmap.narrative.lower()


def test_build_momentum_heatmap_insufficient_data() -> None:
    series = _build_series([100])

    heatmap = build_momentum_heatmap(series)

    assert heatmap.matrix == []
    assert heatmap.dates == []
    assert "too short" in heatmap.narrative.lower()
