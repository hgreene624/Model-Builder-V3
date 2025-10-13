from datetime import datetime, timezone

import pandas as pd
import pytest

from model_builder.analytics import TradeTimeline, build_trade_timeline
from src.models.contracts import TradeRecord


def _trade(
    *,
    timestamp: str,
    symbol: str,
    quantity: float,
    price: float,
    pnl: float,
    action: str = "BUY",
    exit_timestamp: str | None = None,
) -> TradeRecord:
    return TradeRecord(
        timestamp=timestamp,
        symbol=symbol,
        action=action,
        quantity=quantity,
        price=price,
        costs={"total": 0.0},
        exit_timestamp=exit_timestamp,
        pnl=pnl,
    )


def test_build_trade_timeline_from_trade_records() -> None:
    trades = [
        _trade(
            timestamp="2024-01-05T00:00:00+00:00",
            symbol="AAPL",
            quantity=100,
            price=150.0,
            pnl=500.0,
            action="BUY",
            exit_timestamp="2024-01-20T00:00:00+00:00",
        ),
        _trade(
            timestamp="2024-01-10T00:00:00+00:00",
            symbol="MSFT",
            quantity=-50,
            price=320.0,
            pnl=-250.0,
            action="SELL",
            exit_timestamp="2024-01-18T00:00:00+00:00",
        ),
    ]

    timeline = build_trade_timeline(trades)

    assert isinstance(timeline, TradeTimeline)
    assert timeline.wins == 1
    assert timeline.losses == 1
    assert timeline.flats == 0
    assert pytest.approx(timeline.total_notional) == 100 * 150 + 50 * 320

    point_one, point_two = timeline.points
    assert point_one.symbol == "AAPL"
    assert point_one.side == "long"
    assert point_one.pnl_direction == "gain"
    assert point_one.duration_days == pytest.approx(15.0)

    assert point_two.symbol == "MSFT"
    assert point_two.side == "short"
    assert point_two.pnl_direction == "loss"
    assert point_two.duration_days == pytest.approx(8.0)


def test_build_trade_timeline_accepts_mapping_payload() -> None:
    trades = [
        {
            "timestamp": "2024-02-01T00:00:00+00:00",
            "symbol": "TSLA",
            "quantity": 0,
            "price": 200.0,
            "pnl": 0.0,
        }
    ]

    timeline = build_trade_timeline(trades)

    assert len(timeline.points) == 1
    point = timeline.points[0]
    assert point.side == "flat"
    assert point.pnl_direction == "flat"
    assert point.notional == 0.0
    assert point.duration_days is None


def test_build_trade_timeline_requires_timestamp() -> None:
    trades = [{"symbol": "ABC", "quantity": 10, "price": 5.0, "pnl": 1.0}]

    with pytest.raises(ValueError):
        build_trade_timeline(trades)
