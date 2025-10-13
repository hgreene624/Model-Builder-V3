"""Transform backtest trade records into timeline-friendly payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Sequence

import pandas as pd

from src.models.contracts import TradeRecord


@dataclass(frozen=True)
class TradeTimelinePoint:
    """Single entry representing a trade on the holdout timeline."""

    timestamp: str
    exit_timestamp: str | None
    symbol: str
    side: str
    notional: float
    pnl: float
    pnl_direction: str
    duration_days: float | None

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "exit_timestamp": self.exit_timestamp,
            "symbol": self.symbol,
            "side": self.side,
            "notional": self.notional,
            "pnl": self.pnl,
            "pnl_direction": self.pnl_direction,
            "duration_days": self.duration_days,
        }


@dataclass(frozen=True)
class TradeTimeline:
    """Aggregated trade timeline output."""

    points: List[TradeTimelinePoint]

    @property
    def wins(self) -> int:
        return sum(1 for point in self.points if point.pnl > 0)

    @property
    def losses(self) -> int:
        return sum(1 for point in self.points if point.pnl < 0)

    @property
    def flats(self) -> int:
        return sum(1 for point in self.points if point.pnl == 0)

    @property
    def total_notional(self) -> float:
        return sum(point.notional for point in self.points)

    def to_dict(self) -> dict[str, object]:
        return {
            "points": [point.to_dict() for point in self.points],
            "wins": self.wins,
            "losses": self.losses,
            "flats": self.flats,
            "total_notional": self.total_notional,
        }


def _to_mapping(trade: TradeRecord | Mapping[str, object]) -> Mapping[str, object]:
    if isinstance(trade, TradeRecord):
        return {
            "timestamp": trade.timestamp,
            "symbol": trade.symbol,
            "action": trade.action,
            "quantity": trade.quantity,
            "price": trade.price,
            "costs": dict(trade.costs),
            "exit_timestamp": trade.exit_timestamp,
            "pnl": trade.pnl,
        }
    if isinstance(trade, Mapping):
        return trade
    raise TypeError("trade entries must be TradeRecord instances or mapping payloads.")


def _parse_timestamp(value: object) -> pd.Timestamp:
    if value is None:
        raise ValueError("timestamp must be provided.")
    return pd.Timestamp(value)


def _determine_side(quantity: float, action: str | None) -> str:
    if quantity > 0:
        return "long"
    if quantity < 0:
        return "short"
    if action:
        upper = action.upper()
        if upper.startswith("BUY"):
            return "long"
        if upper.startswith("SELL"):
            return "short"
    return "flat"


def _pnl_direction(pnl: float) -> str:
    if pnl > 0:
        return "gain"
    if pnl < 0:
        return "loss"
    return "flat"


def _duration_days(entry: pd.Timestamp, exit_value: object) -> float | None:
    if not exit_value:
        return None
    exit_ts = pd.Timestamp(exit_value)
    delta = exit_ts - entry
    return float(delta / pd.Timedelta(days=1))


def build_trade_timeline(trades: Sequence[TradeRecord | Mapping[str, object]]) -> TradeTimeline:
    """Derive timeline metadata (side, notional, pnl direction) for plotting."""

    if not isinstance(trades, (list, tuple)):
        trades = list(trades)

    points: List[TradeTimelinePoint] = []

    for raw in trades:
        payload = dict(_to_mapping(raw))
        entry_ts = _parse_timestamp(payload.get("timestamp"))
        exit_ts = payload.get("exit_timestamp")

        quantity = float(payload.get("quantity", 0.0) or 0.0)
        price = float(payload.get("price", 0.0) or 0.0)
        pnl = float(payload.get("pnl", 0.0) or 0.0)
        action = payload.get("action")

        notional = abs(quantity * price)
        side = _determine_side(quantity, str(action) if action is not None else None)
        direction = _pnl_direction(pnl)
        duration = _duration_days(entry_ts, exit_ts)

        point = TradeTimelinePoint(
            timestamp=entry_ts.isoformat(),
            exit_timestamp=pd.Timestamp(exit_ts).isoformat() if exit_ts else None,
            symbol=str(payload.get("symbol", "")),
            side=side,
            notional=notional,
            pnl=pnl,
            pnl_direction=direction,
            duration_days=duration,
        )
        points.append(point)

    points.sort(key=lambda point: point.timestamp)
    return TradeTimeline(points=points)


__all__ = ["TradeTimeline", "TradeTimelinePoint", "build_trade_timeline"]
