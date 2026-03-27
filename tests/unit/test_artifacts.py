from __future__ import annotations

import json
from pathlib import Path

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
        coverage_summary={"start": "2020-01-01", "end": "2025-01-01", "coverage_gap_count": 0},
        shard_hints={"entries": []},
    )

    store.save_portfolio(portfolio)
    loaded = store.load_portfolio("pf-1")

    assert loaded is not None
    assert loaded.name == "Tech"
    assert loaded.coverage_summary["start"] == "2020-01-01"
    assert "coverage_gap_count" in loaded.liquidity_stats
    assert loaded.schema_version == "1.1.0"
    assert (tmp_path / "portfolios" / "pf-1.json").exists()

    assert store.delete_portfolio("pf-1") is True
    assert store.load_portfolio("pf-1") is None


def test_append_log(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    store = ArtifactStore(layout=layout)
    store.append_log("run-1", {"foo": "bar"})
    path = layout.run_log_path("run-1")
    assert path.exists()
    content = path.read_text().strip()
    assert content.endswith("}")


def test_list_helpers(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    store = ArtifactStore(layout=layout)

    portfolio = Portfolio(
        portfolio_id="pf-1",
        name="Sample",
        description=None,
        source="manual",
        seed_reference=None,
        filters={},
        coverage_window={"start": "2020", "end": "2025"},
        tickers=[],
        liquidity_stats={},
        notes=[],
        coverage_summary={"start": "2020", "end": "2025", "coverage_gap_count": 0},
        shard_hints={},
    )
    store.save_portfolio(portfolio)

    ps_path = layout.parameter_set_path("ps-1")
    ps_path.parent.mkdir(parents=True, exist_ok=True)
    ps_path.write_text(
        json.dumps(
            {
                "parameter_set_id": "ps-1",
                "model_id": "m",
                "portfolio_id": "pf-1",
                "run_id": "run-1",
                "parameters": {},
                "fitness": {},
                "constraints": {},
                "created_at": "2025-10-10T00:00:00Z",
                "schema_version": "1.0.0",
            }
        )
    )

    layout.run_log_path("run-2").write_text("{}\n")
    (layout.simulation_directory("sim-1") / "result.json").write_text("{}")

    assert store.list_portfolios()
    assert store.list_parameter_sets()
    assert store.list_run_logs()
    assert store.list_simulations()
