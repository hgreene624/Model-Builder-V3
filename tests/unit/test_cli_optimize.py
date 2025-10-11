from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli.main import app
from src.models.contracts import Portfolio
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


def _create_portfolio(data_dir: Path) -> Portfolio:
    store = ArtifactStore(StorageLayout(data_dir))
    portfolio = Portfolio.from_dict(
        {
            "portfolio_id": "demo",
            "name": "Demo Portfolio",
            "description": None,
            "source": "cli",
            "seed_reference": None,
            "filters": {},
            "coverage_window": {"start": "2024-01-01", "end": "2024-06-30"},
            "tickers": ["AAA", "BBB", "CCC", "DDD", "EEE"],
            "liquidity_stats": {"symbol_count": 5},
            "notes": [],
            "coverage_summary": {},
            "shard_hints": {},
            "schema_version": "1.0.0",
        }
    )
    store.save_portfolio(portfolio)
    return portfolio


def test_cli_optimize_runs_with_synthetic_data(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(data_dir))

    portfolio = _create_portfolio(data_dir)
    runner = CliRunner()
    output_path = tmp_path / "summary.json"

    result = runner.invoke(
        app,
        [
            "optimize",
            "run",
            portfolio.portfolio_id,
            "--synthetic",
            "--sample-size",
            "3",
            "--population-size",
            "3",
            "--generations",
            "1",
            "--seed",
            "7",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    summary = json.loads(result.stdout.strip())

    assert summary["portfolio_id"] == portfolio.portfolio_id
    assert Path(summary["log_path"]).exists()
    assert Path(summary["parameter_path"]).exists()
    assert summary["synthetic_data"] is True
    assert summary["issues"]  # Synthetic message present

    saved_portfolio = ArtifactStore(StorageLayout(data_dir)).load_portfolio(portfolio.portfolio_id)
    assert saved_portfolio is not None
    assert saved_portfolio.notes
    assert summary["parameter_set_id"] in saved_portfolio.notes[-1]

    assert output_path.exists()
    exported = json.loads(output_path.read_text())
    assert exported["parameter_set_id"] == summary["parameter_set_id"]
