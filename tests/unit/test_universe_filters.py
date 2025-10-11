from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.universe_loader import IndexUniverse, UniverseSymbol
from src.portfolio.filters import FilterStats, available_sectors, filter_universe


def make_universe() -> IndexUniverse:
    symbols = (
        UniverseSymbol(ticker="AAA", name="Alpha Corp", sector="Tech", industry="Software"),
        UniverseSymbol(ticker="BBB", name="Beta Labs", sector="Health", industry="Biotech"),
        UniverseSymbol(ticker="AAC", name="Alpha Capital", sector="Finance", industry="Banks"),
    )
    return IndexUniverse(
        name="Sample",
        as_of="2025-10-01",
        metadata={"record_count": len(symbols)},
        symbols=symbols,
        source_path=Path(__file__),
    )


def test_filter_universe_search() -> None:
    universe = make_universe()
    frame, stats = filter_universe(universe, search="Alpha")
    assert isinstance(stats, FilterStats)
    assert stats.matched_symbols == 2
    assert "AAA" in frame.index
    assert "AAC" in frame.index
    assert "BBB" not in frame.index


def test_filter_universe_sectors_with_limit() -> None:
    universe = make_universe()
    frame, stats = filter_universe(universe, sectors=["Tech", "Finance"], max_symbols=1)
    assert stats.matched_symbols == 2
    assert stats.limited_symbols == 1
    assert len(frame.index) == 1
    assert frame.index[0] in {"AAA", "AAC"}


def test_available_sectors_sorted() -> None:
    universe = make_universe()
    assert available_sectors(universe) == ["Finance", "Health", "Tech"]
