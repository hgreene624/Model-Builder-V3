from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli.main import app


def test_cli_commands_exist() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "status" in result.stdout
    assert "portfolio" in result.stdout
    assert "optimize" in result.stdout


def test_cli_status_counts(tmp_path: Path) -> None:
    runner = CliRunner()
    storage = tmp_path / "storage"
    (storage / "portfolios").mkdir(parents=True)
    (storage / "parameters").mkdir(parents=True)
    (storage / "simulations" / "sim-1").mkdir(parents=True)
    (storage / "logs").mkdir(parents=True)

    (storage / "portfolios" / "pf.json").write_text(
        json.dumps(
            {
                "portfolio_id": "pf",
                "name": "Sample",
                "description": None,
                "source": "manual",
                "seed_reference": None,
                "filters": {},
                "coverage_window": {"start": "2020", "end": "2025"},
                "tickers": [],
                "liquidity_stats": {},
                "notes": [],
                "schema_version": "1.0.0",
            }
        )
    )
    (storage / "parameters" / "ps.json").write_text(
        json.dumps(
            {
                "parameter_set_id": "ps",
                "model_id": "atr",
                "portfolio_id": "pf",
                "run_id": "run",
                "parameters": {},
                "fitness": {},
                "constraints": {},
                "created_at": "2025-10-10T00:00:00Z",
                "schema_version": "1.0.0",
            }
        )
    )
    (storage / "simulations" / "sim-1" / "result.json").write_text("{}")
    (storage / "logs" / "run.jsonl").write_text("{}\n")

    result = runner.invoke(app, ["status"], env={"DATA_DIR": str(storage)})
    assert result.exit_code == 0
    assert "Portfolios: 1" in result.stdout
