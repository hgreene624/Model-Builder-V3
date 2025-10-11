from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import pandas as pd

from src.data.loader import MarketDataLoader, SymbolDiagnostics
from src.models.contracts import Portfolio


@dataclass
class PortfolioPreview:
    tickers: List[str]
    table: pd.DataFrame
    stats: Dict[str, float]
    diagnostics: List[SymbolDiagnostics] | None = None


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def normalize_symbols(symbols: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def apply_filters(
    symbols: Iterable[str],
    *,
    include_substring: str | None = None,
    exclude_substring: str | None = None,
) -> List[str]:
    include = include_substring.lower().strip() if include_substring else None
    exclude = exclude_substring.lower().strip() if exclude_substring else None

    filtered: List[str] = []
    for symbol in symbols:
        candidate = normalize_symbol(symbol)
        if include and include not in candidate.lower():
            continue
        if exclude and exclude in candidate.lower():
            continue
        filtered.append(candidate)
    return filtered


def compute_liquidity_table(
    loader: MarketDataLoader,
    symbols: Iterable[str],
    start: str,
    end: str,
    *,
    diagnostics: Optional[List[SymbolDiagnostics]] = None,
) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        try:
            if diagnostics is not None:
                frame, diag = loader.load_with_diagnostics(symbol, start, end, interval="1d", warmup_bars=0)
                diagnostics.append(diag)
                if diag.exception_message:
                    continue
            else:
                frame = loader.load(symbol, start, end, interval="1d", warmup_bars=0)
        except Exception:
            continue
        if frame.empty:
            continue
        median_price = float(frame["close"].median())
        median_dollar_volume = float((frame["close"] * frame["volume"]).median())
        rows.append(
            {
                "symbol": symbol,
                "median_price": median_price,
                "median_dollar_volume": median_dollar_volume,
                "observations": int(frame.shape[0]),
            }
        )
    return pd.DataFrame(rows)


def summarize_stats(table: pd.DataFrame) -> Dict[str, float]:
    if table.empty:
        return {
            "median_price": 0.0,
            "median_dollar_volume": 0.0,
            "symbols_covered": 0,
        }
    return {
        "median_price": float(table["median_price"].median()),
        "median_dollar_volume": float(table["median_dollar_volume"].median()),
        "symbols_covered": int(table.shape[0]),
    }


def build_portfolio(
    *,
    name: str,
    description: str | None,
    source: str,
    seed_reference: str | None,
    symbols: Iterable[str],
    max_count: int,
    coverage_start: str,
    coverage_end: str,
    loader: MarketDataLoader,
    notes: list[str] | None = None,
    filters: Dict[str, object] | None = None,
    debug: bool = False,
) -> tuple[Portfolio, PortfolioPreview]:
    normalized = normalize_symbols(symbols)[:max_count]
    diagnostics: List[SymbolDiagnostics] | None = [] if debug else None
    table = compute_liquidity_table(
        loader, normalized, coverage_start, coverage_end, diagnostics=diagnostics
    )
    stats = summarize_stats(table)

    portfolio = Portfolio(
        portfolio_id=str(uuid.uuid4()),
        name=name,
        description=description,
        source=source,
        seed_reference=seed_reference,
        filters=filters or {},
        coverage_window={"start": coverage_start, "end": coverage_end},
        tickers=normalized,
        liquidity_stats=stats,
        notes=notes or [],
    )

    preview = PortfolioPreview(tickers=normalized, table=table, stats=stats, diagnostics=diagnostics)
    return portfolio, preview
