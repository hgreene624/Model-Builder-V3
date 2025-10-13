from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from model_builder.optimization.runner import (
    EVENT_TYPE_CANDIDATE_EVALUATION,
    EvaluationAppender,
)
from model_builder.optimization.telemetry import TelemetryLogWriter
from src.storage.layout import StorageLayout


def _clock_factory(timestamps: list[datetime]) -> tuple[callable, list[datetime]]:
    items = list(timestamps)

    def _clock() -> datetime:
        if not items:
            raise AssertionError("Clock exhausted.")
        return items.pop(0)

    return _clock, items


def test_append_streams_to_log_and_tracks_best(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    writer = TelemetryLogWriter(run_id="run-abc", layout=layout, session="ui")
    clock, remaining = _clock_factory(
        [
            datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 12, 1, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 12, 2, tzinfo=timezone.utc),
        ]
    )
    appender = EvaluationAppender(writer=writer, clock=clock)

    captured: list[dict] = []
    appender.register(captured.append)

    first_env = appender.append(
        candidate_id="cand-001",
        score=1.0,
        metrics={"cagr": 0.12, "sharpe": 1.5},
        parameter_payload={"atr_window": 14, "seed": 1},
        metadata={"generation": 1, "rank": 1},
    )
    second_env = appender.append(
        candidate_id="cand-002",
        score=0.95,
        metrics={"cagr": 0.1},
        parameter_payload={"atr_window": 10},
        metadata={"generation": 1, "rank": 2},
    )
    third_env = appender.append(
        candidate_id="cand-003",
        score=1.15,
        metrics={"cagr": 0.15, "calmar": 1.2},
        parameter_payload={"atr_window": 18},
        metadata={"generation": 1, "rank": 3},
    )

    assert first_env is not None
    assert second_env is not None
    assert third_env is not None

    first = first_env["payload"]
    second = second_env["payload"]
    third = third_env["payload"]

    assert first_env["event_type"] == EVENT_TYPE_CANDIDATE_EVALUATION
    assert first_env["metadata"]["generation"] == 1
    assert third_env["metadata"]["rank"] == 3

    assert not remaining  # clock consumed expected timestamps

    assert captured == [first_env, second_env, third_env]

    assert first["score_delta"] == pytest.approx(0.0)
    assert second["score_delta"] == pytest.approx(-0.05)
    assert third["score_delta"] == pytest.approx(0.15)
    assert appender.best_candidate_id == "cand-003"
    assert appender.snapshot() == [first, second, third]

    log_lines = writer.log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 3
    envelopes = [json.loads(line) for line in log_lines]
    assert [env["payload"] for env in envelopes] == [first, second, third]
    assert all(env["event_type"] == EVENT_TYPE_CANDIDATE_EVALUATION for env in envelopes)


def test_append_rejects_blank_candidate_id(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    writer = TelemetryLogWriter(run_id="run-xyz", layout=layout)
    appender = EvaluationAppender(writer=writer, clock=lambda: datetime.now(tz=timezone.utc))

    with pytest.raises(ValueError):
        appender.append(
            candidate_id="",
            score=0.5,
            metrics={},
            parameter_payload={},
        )
