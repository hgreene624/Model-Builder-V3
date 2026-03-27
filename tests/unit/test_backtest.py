from __future__ import annotations

import pandas as pd
import pytest

from src.engine.backtest import CostModel, run_backtest


@pytest.fixture
def price_series() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=4, freq="D", tz="UTC")
    return pd.DataFrame({"XYZ": [100.0, 102.0, 106.0, 104.0]}, index=index)


@pytest.fixture
def signal_frame(price_series: pd.DataFrame) -> pd.DataFrame:
    records = []
    for timestamp, weight, action in zip(
        price_series.index,
        [0.0, 1.0, 1.0, 0.0],
        ["flat", "buy", "hold", "sell"],
        strict=False,
    ):
        records.append(
            {
                "timestamp": timestamp,
                "symbol": "XYZ",
                "action": action,
                "weight": weight,
                "metadata": {},
            }
        )
    return pd.DataFrame.from_records(records)


def test_backtest_produces_equity_and_trades(
    price_series: pd.DataFrame, signal_frame: pd.DataFrame
) -> None:
    result = run_backtest(
        prices=price_series,
        signals=signal_frame,
        initial_capital=100_000.0,
    )

    assert len(result.equity_curve) == len(price_series)
    assert result.equity_curve[-1]["equity"] == pytest.approx(101_960.78431372548, rel=1e-6)

    assert len(result.trades) == 2
    assert result.trades[0].action == "buy"
    assert result.trades[1].action == "sell"
    assert result.trades[1].pnl == pytest.approx(1_960.0, rel=1e-2)

    kpis = result.kpis
    assert kpis["cagr"] > 0
    assert kpis["max_drawdown"] <= 0
    assert kpis["hit_rate"] == pytest.approx(1.0, rel=1e-6)
    assert kpis["trade_rate"] == pytest.approx(63.0, rel=1e-6)
    assert kpis["avg_hold_days"] == pytest.approx(2.0, rel=1e-6)


def test_backtest_applies_cost_model(
    price_series: pd.DataFrame, signal_frame: pd.DataFrame
) -> None:
    baseline = run_backtest(
        prices=price_series,
        signals=signal_frame,
        initial_capital=50_000.0,
    )

    cost_model = CostModel(commission=5.0, slippage_bps=25.0)
    result = run_backtest(
        prices=price_series,
        signals=signal_frame,
        initial_capital=50_000.0,
        cost_model=cost_model,
    )

    sell_trades = [trade for trade in result.trades if trade.action == "sell"]
    assert sell_trades, "expected at least one sell trade"
    last_sell = sell_trades[-1]

    assert last_sell.costs["commission"] == pytest.approx(5.0, rel=1e-6)
    expected_slippage = abs(last_sell.quantity * last_sell.price) * 0.0025
    assert last_sell.costs["slippage"] == pytest.approx(expected_slippage, rel=1e-6)
    assert last_sell.costs["total"] == pytest.approx(5.0 + expected_slippage, rel=1e-6)
    assert last_sell.exit_timestamp is not None
    assert result.equity_curve[-1]["equity"] < baseline.equity_curve[-1]["equity"]
    assert result.kpis["trade_rate"] == pytest.approx(baseline.kpis["trade_rate"], rel=1e-6)
    assert result.kpis["avg_hold_days"] == pytest.approx(baseline.kpis["avg_hold_days"], rel=1e-6)
