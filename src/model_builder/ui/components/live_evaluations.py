"""State manager for the live evaluations Streamlit component."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Sequence, Tuple

LIVE_EVALUATIONS_STATE_KEY = "model_builder_live_evaluations"
_COLUMNS: Tuple[str, ...] = (
    "candidate_id",
    "score",
    "score_delta",
    "timestamp",
    "metrics",
    "parameter_payload",
)


def _normalize_metrics(metrics: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(metrics, Mapping):
        raise TypeError("metrics must be a mapping of metric name to numeric value.")
    normalized: dict[str, float] = {}
    for key, value in metrics.items():
        normalized[str(key)] = float(value)
    return normalized


def _normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise TypeError("parameter_payload must be a mapping.")
    return {str(key): value for key, value in payload.items()}


@dataclass
class LiveEvaluationsState:
    """Track candidate evaluations for the current run and expose table rows."""

    _run_id: str | None = None
    _rows: list[dict[str, Any]] = field(default_factory=list)
    _event_keys: set[tuple[str, str, float]] = field(default_factory=set)

    @property
    def columns(self) -> Tuple[str, ...]:
        return _COLUMNS

    @property
    def run_id(self) -> str | None:
        return self._run_id

    @property
    def rows(self) -> Tuple[dict[str, Any], ...]:
        return tuple(self._rows)

    def ingest(self, run_id: str, evaluation: Mapping[str, Any]) -> dict[str, Any]:
        if not run_id:
            raise ValueError("run_id must be a non-empty string.")

        if not isinstance(evaluation, Mapping):
            raise TypeError("evaluation must be a mapping.")

        candidate_id = str(evaluation.get("candidate_id", "")).strip()
        if not candidate_id:
            raise ValueError("candidate_id must be a non-empty string.")

        score = float(evaluation["score"])
        score_delta = float(evaluation["score_delta"])
        timestamp = str(evaluation["timestamp"])
        metrics = _normalize_metrics(evaluation.get("metrics", {}))
        payload = _normalize_payload(evaluation.get("parameter_payload", {}))

        if self._run_id != run_id:
            self._run_id = run_id
            self._rows.clear()
            self._event_keys.clear()

        event_key = (candidate_id, timestamp, score)
        if event_key in self._event_keys:
            return {
                "candidate_id": candidate_id,
                "score": score,
                "score_delta": score_delta,
                "timestamp": timestamp,
                "metrics": metrics,
                "parameter_payload": payload,
            }

        row = {
            "candidate_id": candidate_id,
            "score": score,
            "score_delta": score_delta,
            "timestamp": timestamp,
            "metrics": metrics,
            "parameter_payload": payload,
        }
        self._rows.append(row)
        self._event_keys.add(event_key)
        return row


def get_live_evaluations_state(
    session_state: MutableMapping[str, Any],
    *,
    key: str = LIVE_EVALUATIONS_STATE_KEY,
) -> LiveEvaluationsState:
    """Fetch or initialize the session-scoped evaluations state."""

    state = session_state.get(key)
    if not isinstance(state, LiveEvaluationsState):
        state = LiveEvaluationsState()
        session_state[key] = state
    return state


__all__ = [
    "LIVE_EVALUATIONS_STATE_KEY",
    "LiveEvaluationsState",
    "get_live_evaluations_state",
]
