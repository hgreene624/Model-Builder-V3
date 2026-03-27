from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _current_timestamp() -> str:
    return datetime.now(tz=UTC).isoformat()


@dataclass
class Portfolio:
    portfolio_id: str
    name: str
    description: str | None
    source: str
    seed_reference: str | None
    filters: dict[str, Any]
    coverage_window: dict[str, str]
    tickers: list[str]
    liquidity_stats: dict[str, Any]
    notes: list[str]
    coverage_summary: dict[str, Any] = field(default_factory=dict)
    shard_hints: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_current_timestamp)
    updated_at: str = field(default_factory=_current_timestamp)
    schema_version: str = field(default="1.1.0")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Portfolio:
        payload = dict(data)
        liquidity_stats = dict(payload.get("liquidity_stats") or {})
        liquidity_stats.setdefault(
            "coverage_gap_count", liquidity_stats.get("coverage_gap_count", 0)
        )
        created_at = payload.get("created_at") or _current_timestamp()
        portfolio = cls(
            portfolio_id=payload["portfolio_id"],
            name=payload["name"],
            description=payload.get("description"),
            source=payload["source"],
            seed_reference=payload.get("seed_reference"),
            filters=dict(payload.get("filters") or {}),
            coverage_window=dict(payload.get("coverage_window") or {}),
            tickers=list(payload.get("tickers") or []),
            liquidity_stats=liquidity_stats,
            notes=list(payload.get("notes") or []),
            coverage_summary=dict(payload.get("coverage_summary") or {}),
            shard_hints=dict(payload.get("shard_hints") or {}),
            created_at=created_at,
            updated_at=payload.get("updated_at") or created_at,
            schema_version=payload.get("schema_version", "1.0.0"),
        )
        return portfolio

    def touch(self) -> None:
        self.updated_at = _current_timestamp()


@dataclass
class ParameterSet:
    parameter_set_id: str
    model_id: str
    portfolio_id: str
    run_id: str
    parameters: dict[str, Any]
    fitness: dict[str, float]
    constraints: dict[str, Any]
    created_at: str
    schema_version: str = field(default="1.0.0")


@dataclass
class TradeRecord:
    timestamp: str
    symbol: str
    action: str
    quantity: float
    price: float
    costs: dict[str, float]
    exit_timestamp: str | None
    pnl: float
    entry_timestamp: str | None = None


@dataclass
class BacktestResult:
    equity_curve: list[dict[str, Any]]
    trades: list[TradeRecord]
    benchmarks: list[dict[str, Any]]
    kpis: dict[str, float]
    risk_notes: list[str]
    schema_version: str = field(default="1.0.0")
