from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from src.data.loader import MarketDataLoader, SymbolDiagnostics
from src.models.contracts import Portfolio


@dataclass
class PortfolioPreview:
    tickers: list[str]
    table: pd.DataFrame
    stats: dict[str, float]
    diagnostics: list[SymbolDiagnostics] | None = None


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def normalize_symbols(symbols: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def normalize_portfolio_id(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower())
    slug = slug.strip("-")
    return slug or "portfolio"


def _clean_filters(filters: dict[str, object] | None) -> dict[str, object]:
    if not filters:
        return {}
    cleaned: dict[str, object] = {}
    for key, value in filters.items():
        if value is None:
            continue
        if key == "thresholds":
            thresholds = {
                threshold_key: threshold_value
                for threshold_key, threshold_value in (value or {}).items()
                if threshold_value is not None
            }
            if thresholds:
                cleaned[key] = thresholds
            continue
        if key == "sectors":
            sectors = [sector for sector in (value or []) if sector]
            if sectors:
                cleaned[key] = sectors
            continue
        cleaned[key] = value
    return cleaned


def apply_filters(
    symbols: Iterable[str],
    *,
    include_substring: str | None = None,
    exclude_substring: str | None = None,
) -> list[str]:
    include = include_substring.lower().strip() if include_substring else None
    exclude = exclude_substring.lower().strip() if exclude_substring else None

    filtered: list[str] = []
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
    diagnostics: list[SymbolDiagnostics] | None = None,
) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        try:
            if diagnostics is not None:
                frame, diag, error = loader.load_with_diagnostics(
                    symbol, start, end, interval="1d", warmup_bars=0
                )
                diagnostics.append(diag)
                if error is not None or diag.exception_message:
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


def summarize_stats(table: pd.DataFrame) -> dict[str, float]:
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
    filters: dict[str, object] | None = None,
    debug: bool = False,
) -> tuple[Portfolio, PortfolioPreview]:
    normalized = normalize_symbols(symbols)[:max_count]
    diagnostics: list[SymbolDiagnostics] | None = [] if debug else None
    table = compute_liquidity_table(
        loader, normalized, coverage_start, coverage_end, diagnostics=diagnostics
    )
    stats = summarize_stats(table)
    stats.setdefault("coverage_gap_count", 0)

    coverage_summary = {
        "start": coverage_start,
        "end": coverage_end,
        "coverage_gap_count": stats.get("coverage_gap_count", 0),
    }

    timestamp = datetime.now(tz=UTC).isoformat()

    portfolio = Portfolio(
        portfolio_id=normalize_portfolio_id(name or "portfolio"),
        name=name,
        description=description,
        source=source,
        seed_reference=seed_reference,
        filters=_clean_filters(filters),
        coverage_window={"start": coverage_start, "end": coverage_end},
        tickers=normalized,
        liquidity_stats=stats,
        notes=notes or [],
        coverage_summary=coverage_summary,
        shard_hints={},
        created_at=timestamp,
        updated_at=timestamp,
    )

    preview = PortfolioPreview(
        tickers=normalized, table=table, stats=stats, diagnostics=diagnostics
    )
    return portfolio, preview
