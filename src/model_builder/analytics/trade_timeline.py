"""Transform backtest trade records into timeline-friendly payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Sequence

import pandas as pd

from src.models.contracts import TradeRecord

MAX_TIMELINE_TRADES = 200
MIN_WIDTH = 0.35
MAX_WIDTH = 0.9
DEFAULT_COLOR_SCALE = "RdYlGn"


@dataclass(frozen=True)
class TradeTimelinePoint:
    """Single timeline element describing a closed trade."""

    symbol: str
    entry: str
    exit: str
    quantity: float
    price: float
    notional: float
    portfolio_notional: float | None
    pnl: float
    return_pct: float | None
    duration_days: float
    display_duration_days: float
    size_fraction: float
    bar_width: float
    metadata: Dict[str, Any]

    def to_dict(self) -> dict[str, object]:
        payload = {
            "symbol": self.symbol,
            "entry": self.entry,
            "exit": self.exit,
            "quantity": self.quantity,
            "price": self.price,
            "notional": self.notional,
            "portfolio_notional": self.portfolio_notional,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
            "duration_days": self.duration_days,
            "display_duration_days": self.display_duration_days,
            "size_fraction": self.size_fraction,
            "bar_width": self.bar_width,
            "metadata": dict(self.metadata),
        }
        return payload


@dataclass(frozen=True)
class TradeTimeline:
    """Aggregated trade timeline output."""

    points: List[TradeTimelinePoint]
    color_scale: str = DEFAULT_COLOR_SCALE
    color_mid: float = 0.0
    color_domain: float | None = None
    window_start: str | None = None
    window_end: str | None = None

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
            "color_scale": self.color_scale,
            "color_mid": self.color_mid,
            "color_domain": self.color_domain,
            "window_start": self.window_start,
            "window_end": self.window_end,
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


def _parse_timestamp(value: object) -> pd.Timestamp | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tz is not None:
        ts = ts.tz_convert(None)
    return ts


def _normalize_metadata(payload: Mapping[str, Any]) -> dict[str, Any]:
    metadata_keys = [
        "portfolio_weight",
        "portfolio_weight_pct",
        "risk_reward",
        "max_adverse_excursion",
        "max_favorable_excursion",
        "size_fraction",
    ]
    metadata: dict[str, Any] = {}
    for key in metadata_keys:
        if key in payload:
            metadata[key] = payload[key]
    return metadata


def _size_fraction(values: List[float]) -> List[float]:
    if not values:
        return []
    max_value = max(values)
    if max_value <= 0:
        return [0.0 for _ in values]
    return [value / max_value for value in values]


def _calc_bar_width(fractions: Iterable[float]) -> List[float]:
    widths: List[float] = []
    span = MAX_WIDTH - MIN_WIDTH
    for fraction in fractions:
        clamped = max(0.0, min(1.0, fraction))
        widths.append(MIN_WIDTH + clamped * span)
    return widths


def _compute_return_pct(pnl: float, preferred_notional: float | None, fallback_notional: float) -> float | None:
    basis = preferred_notional if preferred_notional and preferred_notional > 0 else fallback_notional
    if basis <= 0:
        return None
    return (pnl / basis) * 100.0


def build_trade_timeline(
    trades: Sequence[TradeRecord | Mapping[str, object]],
    *,
    window_start: str,
    window_end: str,
) -> TradeTimeline:
    """Derive timeline metadata for horizontal trade bars."""

    if not isinstance(trades, (list, tuple)):
        trades = list(trades)

    start_ts = _parse_timestamp(window_start)
    end_ts = _parse_timestamp(window_end)
    if start_ts is None or end_ts is None:
        raise ValueError("window_start and window_end must be valid timestamps")

    normalized_trades: List[dict[str, Any]] = []
    for raw in trades:
        payload = dict(_to_mapping(raw))
        entry_ts = _parse_timestamp(payload.get("timestamp"))
        exit_ts = _parse_timestamp(payload.get("exit_timestamp"))
        if entry_ts is None or exit_ts is None:
            continue
        if exit_ts is None:
            continue

        if exit_ts <= entry_ts:
            continue

        if exit_ts < start_ts or entry_ts > end_ts:
            continue

        entry_plot = max(entry_ts, start_ts)
        exit_plot = min(exit_ts, end_ts)
        if exit_plot <= entry_plot:
            continue

        quantity = float(payload.get("quantity", 0.0) or 0.0)
        price = float(payload.get("price", 0.0) or 0.0)
        pnl = float(payload.get("pnl", 0.0) or 0.0)

        notional = abs(quantity * price)
        portfolio_notional = payload.get("portfolio_notional")
        if isinstance(portfolio_notional, str):
            try:
                portfolio_notional = float(portfolio_notional)
            except ValueError:
                portfolio_notional = None
        elif isinstance(portfolio_notional, (int, float)):
            portfolio_notional = float(portfolio_notional)
        else:
            portfolio_notional = None

        return_pct = _compute_return_pct(pnl, portfolio_notional, notional)
        duration_days = float((exit_ts - entry_ts) / pd.Timedelta(days=1))
        display_duration_days = float((exit_plot - entry_plot) / pd.Timedelta(days=1))

        normalized_trades.append(
            {
                "symbol": str(payload.get("symbol", "")),
                "entry": entry_ts,
                "exit": exit_ts,
                "entry_plot": entry_plot,
                "exit_plot": exit_plot,
                "quantity": quantity,
                "price": price,
                "notional": notional,
                "portfolio_notional": portfolio_notional,
                "pnl": pnl,
                "return_pct": return_pct,
                "duration_days": duration_days,
                "display_duration_days": display_duration_days,
                "metadata": _normalize_metadata(payload),
            }
        )

    if not normalized_trades:
        return TradeTimeline(points=[], window_start=window_start, window_end=window_end)

    normalized_trades.sort(key=lambda item: item["entry"])
    if len(normalized_trades) > MAX_TIMELINE_TRADES:
        normalized_trades = normalized_trades[-MAX_TIMELINE_TRADES:]

    size_basis = [
        trade["portfolio_notional"] if trade["portfolio_notional"] and trade["portfolio_notional"] > 0 else trade["notional"]
        for trade in normalized_trades
    ]
    fractions = _size_fraction(size_basis)
    widths = _calc_bar_width(fractions)

    max_abs_return = max(
        (abs(trade["return_pct"]) for trade in normalized_trades if trade["return_pct"] is not None),
        default=None,
    )

    points: List[TradeTimelinePoint] = []
    for trade, fraction, width in zip(normalized_trades, fractions, widths, strict=False):
        metadata = dict(trade["metadata"])
        metadata["size_fraction"] = fraction
        metadata["entry_actual"] = trade["entry"].isoformat()
        metadata["exit_actual"] = trade["exit"].isoformat()
        point = TradeTimelinePoint(
            symbol=trade["symbol"],
            entry=trade["entry_plot"].isoformat(),
            exit=trade["exit_plot"].isoformat(),
            quantity=trade["quantity"],
            price=trade["price"],
            notional=trade["notional"],
            portfolio_notional=trade["portfolio_notional"],
            pnl=trade["pnl"],
            return_pct=trade["return_pct"],
            duration_days=trade["duration_days"],
            display_duration_days=trade["display_duration_days"],
            size_fraction=fraction,
            bar_width=width,
            metadata=metadata,
        )
        points.append(point)

    return TradeTimeline(
        points=points,
        color_domain=max_abs_return,
        window_start=window_start,
        window_end=window_end,
    )


__all__ = ["TradeTimeline", "TradeTimelinePoint", "build_trade_timeline"]
