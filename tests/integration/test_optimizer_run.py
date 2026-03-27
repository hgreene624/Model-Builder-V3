from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.models.contracts import ParameterSet
from src.optimizer.evolutionary import ConstraintGate, EvolutionaryOptimizer, ObjectiveWeights
from src.optimizer.telemetry import TelemetryPublisher
from src.optimizer.training_logger import TrainingLogger
from src.storage.layout import StorageLayout


def evaluation_function(genome: dict[str, float]) -> dict[str, dict[str, float]]:
    atr_window = genome["atr_window"]
    multiplier = genome["breakout_multiplier"]

    metrics = {
        "cagr": 0.12 + (20 - atr_window) * 0.005,
        "calmar": 1.0 + (2.5 - multiplier) * 0.2,
        "sharpe": 1.0 + multiplier * 0.1,
    }
    stats = {
        "trade_rate": 4.0 + (12 - atr_window) * 0.3,
        "avg_hold_days": 3.0 + atr_window * 0.1,
    }
    return {"metrics": metrics, "stats": stats}


def test_optimizer_run_emits_telemetry_and_saves_genome(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    layout = StorageLayout(storage_root)
    run_id = "run-001"
    log_path = layout.run_log_path(run_id)
    logger = TrainingLogger(log_path)
    publisher = TelemetryPublisher(run_id=run_id, logger=logger, session="test")
    captured: list[dict] = []
    publisher.register(captured.append)

    weights = ObjectiveWeights(cagr=0.5, calmar=0.3, sharpe=0.2)
    gate = ConstraintGate(max_trade_rate=5.0, min_hold_days=4.0, penalty=-1_000.0)

    optimizer = EvolutionaryOptimizer(
        objective_weights=weights,
        constraint_gate=gate,
        publisher=publisher,
        layout=layout,
        population_size=3,
        generations=1,
        max_workers=1,
    )

    population = [
        {"atr_window": 8, "breakout_multiplier": 3.0},
        {"atr_window": 12, "breakout_multiplier": 1.8},
        {"atr_window": 16, "breakout_multiplier": 1.2},
    ]

    best = optimizer.run(
        run_id=run_id,
        model_id="models.atr_breakout",
        portfolio_id="portfolio-123",
        evaluator=evaluation_function,
        initial_population=population,
        seed=42,
    )

    parameter_files = list(layout.parameter_sets_directory().glob("*.json"))
    assert len(parameter_files) == 1

    payload = json.loads(parameter_files[0].read_text())
    saved = ParameterSet(**payload)

    assert saved.parameter_set_id == best.parameter_set_id
    assert saved.parameters == {"atr_window": 16, "breakout_multiplier": 1.2}
    assert saved.fitness["score"] == pytest.approx(0.672, rel=1e-6)
    assert saved.fitness["cagr"] == pytest.approx(0.14, rel=1e-6)
    assert saved.fitness["calmar"] == pytest.approx(1.26, rel=1e-6)
    assert saved.fitness["sharpe"] == pytest.approx(1.12, rel=1e-6)
    assert saved.constraints == {"trade_rate": 2.8, "avg_hold_days": 4.6}
    assert saved.run_id == run_id
    assert saved.model_id == "models.atr_breakout"
    assert saved.portfolio_id == "portfolio-123"

    events = [json.loads(line) for line in log_path.read_text().splitlines()]
    assert events == captured

    event_types = [event["event_type"] for event in events]
    assert event_types == ["session_start", "checkpoint", "generation_summary", "session_end"]

    for event in events:
        assert event["run_id"] == run_id
        assert event["schema_version"] == "1.0.0"
        assert "timestamp" in event
        assert event["session"] == "test"

    checkpoint = events[1]
    assert checkpoint["event_type"] == "checkpoint"
    assert checkpoint["payload"]["best_score"] == pytest.approx(0.672, rel=1e-6)
    assert checkpoint["payload"]["generation"] == 1

    summary = events[2]
    payload = summary["payload"]
    assert payload["generation"] == 1
    assert payload["population_size"] == 3
    assert payload["infeasible"] == 1
    assert payload["best_fitness"] == pytest.approx(0.672, rel=1e-6)
    assert payload["average_fitness"] == pytest.approx(-332.683333, rel=1e-6)
    assert payload["best_parameters"] == {"atr_window": 16.0, "breakout_multiplier": 1.2}
    assert payload["best_metrics"]["cagr"] == pytest.approx(0.14, rel=1e-6)
    assert payload["best_metrics"]["calmar"] == pytest.approx(1.26, rel=1e-6)
    assert payload["best_metrics"]["sharpe"] == pytest.approx(1.12, rel=1e-6)

    session_end = events[3]
    assert session_end["payload"]["best_score"] == pytest.approx(0.672, rel=1e-6)
