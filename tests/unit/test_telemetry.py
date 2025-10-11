from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.optimizer.telemetry import TelemetryPublisher
from src.optimizer.training_logger import TrainingLogger


def test_telemetry_publisher_writes_events(tmp_path: Path) -> None:
    log_path = tmp_path / "run.jsonl"
    logger = TrainingLogger(log_path)
    publisher = TelemetryPublisher(run_id="run-1", logger=logger, session="ui")

    captured: list[dict] = []
    publisher.register(captured.append)

    publisher.session_start(
        model_id="models.atr_breakout",
        portfolio_id="portfolio-1",
        objective_weights={"cagr": 0.5, "calmar": 0.3, "sharpe": 0.2},
        population_size=4,
        generations=2,
        seed=123,
    )

    publisher.generation_summary(
        generation=1,
        population_size=4,
        infeasible=1,
        best_fitness=0.6,
        average_fitness=0.4,
        best_parameters={"atr_window": 12.0},
        best_metrics={"cagr": 0.14},
        best_constraints={"trade_rate": 5.5},
    )

    publisher.session_end(
        status="completed",
        duration_seconds=12.5,
        best_parameter_set_id="ps-001",
        best_score=0.6,
    )

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 3
    events = [json.loads(line) for line in lines]

    assert events == captured
    for event in events:
        assert event["schema_version"] == "1.0.0"
        assert event["run_id"] == "run-1"
        assert event["session"] == "ui"
        assert "timestamp" in event
        assert isinstance(event["payload"], dict)
