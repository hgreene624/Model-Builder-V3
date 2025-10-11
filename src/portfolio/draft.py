from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Iterable, List, Sequence

import pandas as pd


def _normalize(symbol: str) -> str:
    return symbol.strip().upper()


def _current_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class DraftPortfolioState:
    universe_id: str
    selected_symbols: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=_current_timestamp)
    updated_at: str = field(default_factory=_current_timestamp)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "DraftPortfolioState":
        return cls(
            universe_id=str(payload.get("universe_id", "")),
            selected_symbols=[_normalize(sym) for sym in payload.get("selected_symbols", [])],
            created_at=str(payload.get("created_at") or _current_timestamp()),
            updated_at=str(payload.get("updated_at") or _current_timestamp()),
        )

    def add_symbols(self, symbols: Iterable[str]) -> None:
        normalized = [_normalize(symbol) for symbol in symbols if symbol]
        if not normalized:
            return
        existing = set(self.selected_symbols)
        for symbol in normalized:
            if symbol not in existing:
                self.selected_symbols.append(symbol)
                existing.add(symbol)
        self.updated_at = _current_timestamp()

    def remove_symbols(self, symbols: Iterable[str]) -> None:
        targets = {_normalize(symbol) for symbol in symbols if symbol}
        if not targets:
            return
        self.selected_symbols = [symbol for symbol in self.selected_symbols if symbol not in targets]
        self.updated_at = _current_timestamp()

    def limit(self, max_symbols: int) -> None:
        if max_symbols <= 0:
            self.selected_symbols = []
        elif len(self.selected_symbols) > max_symbols:
            self.selected_symbols = self.selected_symbols[:max_symbols]
        self.updated_at = _current_timestamp()


def ensure_state(payload: dict[str, object] | None, universe_id: str) -> DraftPortfolioState:
    if payload is None:
        return DraftPortfolioState(universe_id=universe_id)
    state = DraftPortfolioState.from_dict(payload)
    if state.universe_id != universe_id:
        return DraftPortfolioState(universe_id=universe_id)
    return state


def serialize_state(state: DraftPortfolioState) -> dict[str, object]:
    return state.to_dict()


def add_to_draft(state: DraftPortfolioState, symbols: Sequence[str], max_symbols: int | None = None) -> DraftPortfolioState:
    state.add_symbols(symbols)
    if max_symbols is not None:
        state.limit(max_symbols)
    return state


def remove_from_draft(state: DraftPortfolioState, symbols: Sequence[str]) -> DraftPortfolioState:
    state.remove_symbols(symbols)
    return state


def draft_stats(state: DraftPortfolioState, liquidity_frame: pd.DataFrame | None = None) -> dict[str, object]:
    total = len(state.selected_symbols)
    if total == 0 or liquidity_frame is None or liquidity_frame.empty:
        return {
            "symbol_count": total,
            "median_price": None,
            "median_dollar_volume": None,
            "coverage_start": None,
            "coverage_end": None,
            "coverage_gap_count": 0,
        }

    subset = liquidity_frame.loc[liquidity_frame.index.intersection(state.selected_symbols)]
    if subset.empty:
        return {
            "symbol_count": total,
            "median_price": None,
            "median_dollar_volume": None,
            "coverage_start": None,
            "coverage_end": None,
            "coverage_gap_count": 0,
        }

    median_price = float(subset["median_price"].median(skipna=True)) if "median_price" in subset else None
    median_dollar_volume = (
        float(subset["median_dollar_volume"].median(skipna=True)) if "median_dollar_volume" in subset else None
    )
    coverage_start = subset["coverage_start"].dropna().min() if "coverage_start" in subset else None
    coverage_end = subset["coverage_end"].dropna().max() if "coverage_end" in subset else None
    coverage_gap_count = 0
    if "coverage_status" in subset:
        coverage_gap_count = int((subset["coverage_status"].fillna("").str.lower() != "complete").sum())

    return {
        "symbol_count": total,
        "median_price": median_price,
        "median_dollar_volume": median_dollar_volume,
        "coverage_start": coverage_start,
        "coverage_end": coverage_end,
        "coverage_gap_count": coverage_gap_count,
    }
