from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Portfolio:
    portfolio_id: str
    name: str
    description: str | None
    source: str
    seed_reference: str | None
    filters: Dict[str, Any]
    coverage_window: Dict[str, str]
    tickers: List[str]
    liquidity_stats: Dict[str, Any]
    notes: List[str]
    schema_version: str = field(default="1.0.0")


@dataclass
class ParameterSet:
    parameter_set_id: str
    model_id: str
    portfolio_id: str
    run_id: str
    parameters: Dict[str, Any]
    fitness: Dict[str, float]
    constraints: Dict[str, Any]
    created_at: str
    schema_version: str = field(default="1.0.0")


@dataclass
class TradeRecord:
    timestamp: str
    symbol: str
    action: str
    quantity: float
    price: float
    costs: Dict[str, float]
    exit_timestamp: Optional[str]
    pnl: float


@dataclass
class BacktestResult:
    equity_curve: List[Dict[str, Any]]
    trades: List[TradeRecord]
    benchmarks: List[Dict[str, Any]]
    kpis: Dict[str, float]
    risk_notes: List[str]
    schema_version: str = field(default="1.0.0")
