from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from src.data.universe_loader import IndexUniverse, UniverseSymbol


def _normalize(text: str | None) -> str:
    return (text or "").strip().lower()


@dataclass(frozen=True)
class FilterStats:
    total_symbols: int
    matched_symbols: int
    limited_symbols: int


def _passes_search(symbol: UniverseSymbol, search: str) -> bool:
    if not search:
        return True
    search_lower = search.lower()
    text_segments = [
        symbol.ticker.lower(),
        (symbol.name or "").lower(),
        (symbol.sector or "").lower(),
        (symbol.industry or "").lower(),
    ]
    return any(search_lower in segment for segment in text_segments if segment)


def _passes_sector(symbol: UniverseSymbol, sectors: Sequence[str]) -> bool:
    if not sectors:
        return True
    sector_value = _normalize(symbol.sector)
    requested = {_normalize(sector) for sector in sectors}
    return sector_value in requested


def filter_universe(
    universe: IndexUniverse,
    *,
    search: str | None = None,
    sectors: Sequence[str] | None = None,
    max_symbols: int | None = None,
) -> tuple[pd.DataFrame, FilterStats]:
    search_term = (search or "").strip().lower()
    selected_sectors = [sector for sector in (sectors or []) if sector]

    matched: list[UniverseSymbol] = []
    for symbol in universe.symbols:
        if not _passes_search(symbol, search_term):
            continue
        if not _passes_sector(symbol, selected_sectors):
            continue
        matched.append(symbol)

    limited_count = len(matched)
    if max_symbols and max_symbols > 0:
        limited_count = min(max_symbols, limited_count)
        limited_symbols = matched[:limited_count]
    else:
        limited_symbols = matched

    records = [
        {
            "ticker": symbol.ticker,
            "name": symbol.name or "",
            "sector": symbol.sector or "",
            "industry": symbol.industry or "",
        }
        for symbol in limited_symbols
    ]
    frame = pd.DataFrame.from_records(records)
    if not frame.empty:
        frame = frame.set_index("ticker")

    stats = FilterStats(
        total_symbols=len(universe.symbols),
        matched_symbols=len(matched),
        limited_symbols=len(limited_symbols),
    )
    return frame, stats


def available_sectors(universe: IndexUniverse) -> list[str]:
    sectors = {symbol.sector for symbol in universe.symbols if symbol.sector}
    return sorted(sectors)
