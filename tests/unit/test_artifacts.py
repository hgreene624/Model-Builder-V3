from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.models.contracts import Portfolio
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


def test_save_and_load_portfolio(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    store = ArtifactStore(layout=layout)
    portfolio = Portfolio(
        portfolio_id="pf-1",
        name="Tech",
        description="Sample",
        source="manual",
        seed_reference=None,
        filters={"sector": ["Technology"]},
        coverage_window={"start": "2020-01-01", "end": "2025-01-01"},
        tickers=["AAPL", "MSFT"],
        liquidity_stats={"median_price": 100.0},
        notes=[],
    )

    store.save_portfolio(portfolio)
    loaded = store.load_portfolio("pf-1")

    assert loaded is not None
    assert loaded.name == "Tech"
    assert (tmp_path / "portfolios" / "pf-1.json").exists()


def test_append_log(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    store = ArtifactStore(layout=layout)
    store.append_log("run-1", {"foo": "bar"})
    path = layout.run_log_path("run-1")
    assert path.exists()
    content = path.read_text().strip()
    assert content.endswith("}")
