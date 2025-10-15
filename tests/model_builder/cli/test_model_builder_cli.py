from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner
import pytest

from model_builder.cli.model_builder import cli
from model_builder.optimization import EVENT_TYPE_CANDIDATE_EVALUATION, TelemetryLogWriter
from model_builder.profiles import ProfilesService, StrategyProfileRepository
from src.models.contracts import Portfolio
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


def _env(data_dir: Path) -> dict[str, str]:
    return {"DATA_DIR": str(data_dir)}


def test_profiles_list_returns_empty_array(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["profiles", "list"], env=_env(tmp_path))
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_profiles_save_and_delete_profile(tmp_path: Path) -> None:
    runner = CliRunner()

    save_result = runner.invoke(
        cli,
        [
            "profiles",
            "save",
            "--profile-id",
            "alpha",
            "--name",
            "Alpha Profile",
            "--portfolio-id",
            "portfolio-1",
            "--train-percentage",
            "0.6",
            "--atr-warmup-days",
            "14",
            "--parameters",
            '{"atr_window": 14}',
        ],
        env=_env(tmp_path),
    )
    assert save_result.exit_code == 0, save_result.output
    payload = json.loads(save_result.output)
    assert payload["profile_id"] == "alpha"
    assert payload["name"] == "Alpha Profile"
    assert payload["portfolio_id"] == "portfolio-1"

    list_result = runner.invoke(cli, ["profiles", "list"], env=_env(tmp_path))
    assert list_result.exit_code == 0
    summaries = json.loads(list_result.output)
    assert len(summaries) == 1
    assert summaries[0]["profile_id"] == "alpha"

    delete_result = runner.invoke(
        cli,
        ["profiles", "delete", "alpha", "--force"],
        env=_env(tmp_path),
    )
    assert delete_result.exit_code == 0
    assert json.loads(delete_result.output) == {"profile_id": "alpha", "deleted": True}

    second_delete = runner.invoke(
        cli,
        ["profiles", "delete", "alpha", "--force"],
        env=_env(tmp_path),
    )
    assert second_delete.exit_code != 0
    assert "was not found" in second_delete.output


def test_optimize_command_writes_metadata(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    store = ArtifactStore(layout)

    portfolio = Portfolio(
        portfolio_id="portfolio-1",
        name="Test Portfolio",
        description=None,
        source="tests",
        seed_reference=None,
        filters={},
        coverage_window={"start": "2024-01-01", "end": "2024-03-31"},
        tickers=["AAPL", "MSFT", "GOOG", "AMZN"],
        liquidity_stats={},
        notes=[],
    )
    store.save_portfolio(portfolio)

    service = ProfilesService(repository=StrategyProfileRepository(layout=layout))
    profile = service.save_profile(
        {
            "name": "CLI Profile",
            "portfolio_id": "portfolio-1",
            "train_percentage": 0.6,
            "atr_warmup_days": 14,
            "parameters": {
                "symbol_count": 2,
                "atr_window": 14,
                "breakout_lookback": 20,
                "breakout_multiplier": 2.0,
                "risk_fraction": 0.02,
                "min_weight": 0.05,
                "max_weight": 0.25,
                "population_size": 4,
                "generations": 1,
                "max_workers": 1,
                "seed": 7,
                "objective_weights": {"cagr": 0.5, "calmar": 0.3, "sharpe": 0.2},
                "bounds": {
                    "atr_window": [10, 20],
                    "breakout_lookback": [15, 25],
                    "breakout_multiplier": [1.5, 2.5],
                    "risk_fraction": [0.01, 0.04],
                },
                "max_trade_rate": 50.0,
                "min_hold_days": 2.0,
                "initial_capital": 100_000.0,
                "use_synthetic": True,
            },
        }
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "optimize",
            "--profile-id",
            profile["profile_id"],
            "--use-synthetic",
        ],
        env=_env(tmp_path),
    )
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    run_id = summary["run_id"]

    log_path = tmp_path / "evaluations" / f"{run_id}.jsonl"
    assert log_path.exists()
    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert log_lines, "telemetry log should contain at least one event"
    envelopes = [json.loads(line) for line in log_lines]
    run_completed = next((env for env in envelopes if env.get("event_type") == "run_completed"), None)
    assert run_completed is not None, "run_completed event missing from telemetry log"
    assert run_completed["payload"]["parameter_path"] == summary["parameter_path"]


def test_live_tail_streams_candidate_events(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    writer = TelemetryLogWriter(run_id="run-live", layout=layout, session="cli")
    writer.emit(
        "run_started",
        {"profile_id": "profile-1"},
    )
    writer.emit(
        EVENT_TYPE_CANDIDATE_EVALUATION,
        {
            "candidate_id": "cand-42",
            "score": 1.08,
            "score_delta": 0.03,
            "metrics": {"cagr": 0.14, "sharpe": 1.9},
            "timestamp": "2025-01-01T12:00:00.000Z",
            "parameter_payload": {"atr_window": 18},
        },
        metadata={"generation": 3},
    )
    writer.emit(
        "run_completed",
        {"profile_id": "profile-1"},
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["evaluations", "live-tail", "--run-id", "run-live", "--no-follow"],
        env=_env(tmp_path),
    )

    assert result.exit_code == 0, result.output
    lines = [json.loads(line) for line in result.output.strip().splitlines() if line.strip()]
    assert len(lines) == 1
    envelope = lines[0]
    assert envelope["event_type"] == EVENT_TYPE_CANDIDATE_EVALUATION
    assert envelope["payload"]["candidate_id"] == "cand-42"
    assert envelope["payload"]["score_delta"] == pytest.approx(0.03)
