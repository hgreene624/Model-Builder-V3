"""Session utilities for streaming optimization candidate evaluations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Mapping, MutableSequence, Sequence

from .telemetry import TelemetryLogWriter

CandidateListener = Callable[[dict], None]
EVENT_TYPE_CANDIDATE_EVALUATION = "candidate_evaluation"


def _utc_now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _to_float_mapping(values: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(values, Mapping):
        raise TypeError("metrics must be a mapping.")
    converted: dict[str, float] = {}
    for key, value in values.items():
        converted[str(key)] = float(value)
    return converted


def _to_payload(mapping: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(mapping, Mapping):
        raise TypeError("parameter_payload must be a mapping.")
    return {str(key): value for key, value in mapping.items()}


def _normalize_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        raise TypeError("metadata must be a mapping.")
    return {str(key): value for key, value in metadata.items()}


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class CandidateEvaluation:
    candidate_id: str
    score: float
    score_delta: float
    metrics: dict[str, float]
    timestamp: str
    parameter_payload: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "score": self.score,
            "score_delta": self.score_delta,
            "metrics": dict(self.metrics),
            "timestamp": self.timestamp,
            "parameter_payload": dict(self.parameter_payload),
        }


@dataclass
class EvaluationAppender:
    """Append candidate evaluations, persist them, and fan out to listeners."""

    writer: TelemetryLogWriter
    clock: Callable[[], datetime] = _utc_now
    event_type: str = EVENT_TYPE_CANDIDATE_EVALUATION
    _best_score: float | None = field(default=None, init=False)
    _best_candidate_id: str | None = field(default=None, init=False)
    _history: list[CandidateEvaluation] = field(default_factory=list, init=False)
    _listeners: MutableSequence[CandidateListener] = field(default_factory=list, init=False)

    def register(self, listener: CandidateListener) -> None:
        """Subscribe to candidate payloads as they are appended."""
        self._listeners.append(listener)

    @property
    def best_candidate_id(self) -> str | None:
        return self._best_candidate_id

    @property
    def history(self) -> Sequence[CandidateEvaluation]:
        return tuple(self._history)

    def snapshot(self) -> list[dict[str, object]]:
        """Return a copy of session payloads for UI consumption."""
        return [record.to_dict() for record in self._history]

    def append(
        self,
        *,
        candidate_id: str,
        score: float,
        metrics: Mapping[str, float],
        parameter_payload: Mapping[str, object],
        timestamp: datetime | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> dict[str, object] | None:
        if not candidate_id:
            raise ValueError("candidate_id must be a non-empty string.")

        score_value = float(score)
        prior_best = self._best_score if self._best_score is not None else score_value
        score_delta = score_value - prior_best

        if timestamp is None:
            timestamp = self.clock()

        evaluation = CandidateEvaluation(
            candidate_id=str(candidate_id),
            score=score_value,
            score_delta=score_delta,
            metrics=_to_float_mapping(metrics),
            timestamp=_isoformat(timestamp),
            parameter_payload=_to_payload(parameter_payload),
        )

        if self._best_score is None or score_value > self._best_score:
            self._best_score = score_value
            self._best_candidate_id = evaluation.candidate_id

        self._history.append(evaluation)
        payload = evaluation.to_dict()

        metadata_payload = _normalize_metadata(metadata) or None

        envelope = self.writer.emit(self.event_type, payload, metadata=metadata_payload)

        for listener in list(self._listeners):
            listener(envelope)

        return envelope


__all__ = [
    "CandidateEvaluation",
    "CandidateListener",
    "EVENT_TYPE_CANDIDATE_EVALUATION",
    "EvaluationAppender",
]
