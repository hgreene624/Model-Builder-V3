from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from model_builder.ui.components.live_evaluations import (
    LIVE_EVALUATIONS_STATE_KEY,
    LiveEvaluationsState,
    get_live_evaluations_state,
)


def _sample_evaluation(
    candidate_id: str,
    score: float,
    score_delta: float,
    *,
    metrics: Dict[str, float] | None = None,
    payload: Dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "score": score,
        "score_delta": score_delta,
        "metrics": metrics or {"cagr": 0.12},
        "timestamp": timestamp
        or datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(timespec="milliseconds"),
        "parameter_payload": payload or {"atr_window": 14},
    }


def test_get_live_evaluations_state_caches_instance() -> None:
    session_state: dict[str, object] = {}

    first = get_live_evaluations_state(session_state)
    second = get_live_evaluations_state(session_state)

    assert isinstance(first, LiveEvaluationsState)
    assert first is second
    assert session_state[LIVE_EVALUATIONS_STATE_KEY] is first


def test_live_evaluations_state_resets_on_new_run() -> None:
    session_state: dict[str, object] = {}
    state = get_live_evaluations_state(session_state)

    assert state.columns == (
        "candidate_id",
        "score",
        "score_delta",
        "timestamp",
        "metrics",
        "parameter_payload",
    )

    event_a = _sample_evaluation("cand-1", 1.05, 0.0)
    event_b = _sample_evaluation("cand-2", 1.08, 0.03, metrics={"cagr": 0.15, "sharpe": 1.8})

    state.ingest("run-1", event_a)
    state.ingest("run-1", event_b)

    assert state.run_id == "run-1"
    rows = state.rows
    assert [row["candidate_id"] for row in rows] == ["cand-1", "cand-2"]
    assert rows[1]["metrics"] == {"cagr": 0.15, "sharpe": 1.8}

    event_c = _sample_evaluation("cand-3", 0.98, -0.1)
    state.ingest("run-2", event_c)

    assert state.run_id == "run-2"
    assert [row["candidate_id"] for row in state.rows] == ["cand-3"]


def test_ingest_requires_candidate_id() -> None:
    state = LiveEvaluationsState()
    with pytest.raises(ValueError):
        state.ingest("run-1", _sample_evaluation("", 1.0, 0.0))


def test_ingest_ignores_duplicates_within_run() -> None:
    state = LiveEvaluationsState()
    event = _sample_evaluation("cand-4", 1.11, 0.02)

    state.ingest("run-1", event)
    state.ingest("run-1", event)  # duplicate should be ignored

    assert len(state.rows) == 1
