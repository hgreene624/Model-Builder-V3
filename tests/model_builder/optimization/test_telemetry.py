from __future__ import annotations

import json
from pathlib import Path

from model_builder.optimization.telemetry import (
    DEFAULT_EVENT_SCHEMA_VERSION,
    TelemetryLogWriter,
)
from src.storage.layout import StorageLayout


def test_emit_writes_envelope_and_notifies_listeners(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    writer = TelemetryLogWriter(run_id="run-123", layout=layout, session="ui")

    captured: list[dict] = []
    writer.register(captured.append)

    event = writer.emit(
        "candidate_appended",
        {"score": 1.2, "score_delta": 0.3},
        metadata={"portfolio_id": "portfolio-1"},
    )

    assert event["schema_version"] == DEFAULT_EVENT_SCHEMA_VERSION
    assert event["run_id"] == "run-123"
    assert event["session"] == "ui"
    assert event["event_type"] == "candidate_appended"
    assert event["sequence"] == 1
    assert event["payload"] == {"score": 1.2, "score_delta": 0.3}
    assert event["metadata"] == {"portfolio_id": "portfolio-1"}
    assert captured == [event]

    log_path = writer.log_path
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == event

    assert writer.relative_log_path == Path("evaluations/run-123.jsonl")


def test_extend_preserves_sequence_and_appends(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    writer = TelemetryLogWriter(run_id="run-456", layout=layout)

    seed_event = {
        "schema_version": DEFAULT_EVENT_SCHEMA_VERSION,
        "timestamp": "2025-01-01T00:00:00.000Z",
        "event_type": "seed_event",
        "run_id": "run-456",
        "session": "app",
        "sequence": 5,
        "payload": {"note": "seed"},
    }
    writer.extend([seed_event])

    emitted = writer.emit("next_event", {"foo": "bar"})
    assert emitted["sequence"] == 6

    log_path = writer.log_path
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0]) == seed_event
    assert json.loads(lines[1]) == emitted
