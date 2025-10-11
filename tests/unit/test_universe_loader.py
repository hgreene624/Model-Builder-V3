from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.data.universe_loader import (
    IndexUniverse,
    UniverseNotFoundError,
    UniverseValidationError,
    list_universes,
    load_universe,
)


def test_load_universe_by_identifier() -> None:
    universe = load_universe("sp500")
    assert isinstance(universe, IndexUniverse)
    assert universe.name == "S&P 500"
    assert universe.metadata["record_count"] == len(universe.symbols) > 100
    assert len(set(universe.tickers)) == len(universe.symbols)


def test_load_universe_by_display_name() -> None:
    universe = load_universe("S&P 500")
    assert universe.name == "S&P 500"


def test_list_universes_sorted(tmp_path: Path) -> None:
    payload_a = {
        "name": "Beta 50",
        "symbols": [{"ticker": "AAA"}],
    }
    payload_b = {
        "name": "Alpha 10",
        "symbols": [{"ticker": "BBB"}],
    }
    (tmp_path / "beta_50.json").write_text(json.dumps(payload_a))
    (tmp_path / "alpha_10.json").write_text(json.dumps(payload_b))

    summaries = list_universes(tmp_path)
    assert [summary.name for summary in summaries] == ["Alpha 10", "Beta 50"]


def test_load_universe_duplicate_tickers(tmp_path: Path) -> None:
    payload = {
        "name": "Duplicate Test",
        "symbols": [
            {"ticker": "ABC"},
            {"ticker": "ABC"},
        ],
    }
    path = tmp_path / "duplicate.json"
    path.write_text(json.dumps(payload))

    with pytest.raises(UniverseValidationError):
        load_universe("duplicate", directory=tmp_path)


def test_missing_universe_raises() -> None:
    with pytest.raises(UniverseNotFoundError):
        load_universe("missing-universe-123")
