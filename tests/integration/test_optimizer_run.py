from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest

from src.models.contracts import ParameterSet
from src.optimizer.evolutionary import ConstraintGate, EvolutionaryOptimizer, ObjectiveWeights
from src.optimizer.training_logger import TrainingLogger
from src.storage.layout import StorageLayout


def evaluation_function(genome: Dict[str, float]) -> Dict[str, Dict[str, float]]:
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
    logger = TrainingLogger(layout.run_log_path(run_id), max_bytes=1024)

    weights = ObjectiveWeights(cagr=0.5, calmar=0.3, sharpe=0.2)
    gate = ConstraintGate(max_trade_rate=5.0, min_hold_days=4.0, penalty=-1_000.0)

    optimizer = EvolutionaryOptimizer(
        objective_weights=weights,
        constraint_gate=gate,
        logger=logger,
        layout=layout,
        population_size=3,
        generations=1,
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

    log_path = layout.run_log_path(run_id)
    events = [json.loads(line) for line in log_path.read_text().splitlines()]
    event_types = [event["event_type"] for event in events]

    assert event_types[0] == "session_start"
    assert "generation_summary" in event_types
    assert event_types[-1] == "session_end"

    summary = next(event for event in events if event["event_type"] == "generation_summary")
    payload = summary["payload"]
    assert payload["generation"] == 1
    assert payload["population_size"] == 3
    assert payload["infeasible"] == 1
    assert payload["best_fitness"] == pytest.approx(0.672, rel=1e-6)
    assert payload["best_parameters"] == {"atr_window": 16, "breakout_multiplier": 1.2}
    assert payload["best_metrics"]["cagr"] == pytest.approx(0.14, rel=1e-6)
    assert payload["best_metrics"]["calmar"] == pytest.approx(1.26, rel=1e-6)
    assert payload["best_metrics"]["sharpe"] == pytest.approx(1.12, rel=1e-6)
