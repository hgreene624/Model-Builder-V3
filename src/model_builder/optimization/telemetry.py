"""Telemetry JSONL writer used for optimization replay logs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, MutableSequence

from src.storage.layout import StorageLayout

TelemetryListener = Callable[[dict], None]
DEFAULT_EVENT_SCHEMA_VERSION = "1.0.0"


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


def _ensure_mapping(name: str, payload: Mapping[str, object]) -> dict:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{name} must be a mapping of primitive JSON values.")
    return dict(payload)


@dataclass
class TelemetryLogWriter:
    """Append structured telemetry envelopes to evaluation logs."""

    run_id: str
    layout: StorageLayout
    session: str = "app"
    schema_version: str = DEFAULT_EVENT_SCHEMA_VERSION
    _listeners: MutableSequence[TelemetryListener] = field(default_factory=list, init=False)
    _sequence: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._log_path = self.layout.evaluation_log_path(self.run_id)

    @property
    def log_path(self) -> Path:
        """Absolute path to the backing JSONL log."""
        return self._log_path

    @property
    def relative_log_path(self) -> Path:
        """Log path relative to the storage root for artifact references."""
        return self._log_path.relative_to(self.layout.root)

    def register(self, listener: TelemetryListener) -> None:
        """Subscribe to emitted envelopes (used by UI/CLI streaming hooks)."""
        self._listeners.append(listener)

    def emit(
        self,
        event_type: str,
        payload: Mapping[str, object],
        *,
        metadata: Mapping[str, object] | None = None,
    ) -> dict:
        """Create, persist, and broadcast a telemetry envelope."""
        if not event_type:
            raise ValueError("event_type must be a non-empty string.")

        self._sequence += 1
        envelope: dict[str, object] = {
            "schema_version": self.schema_version,
            "timestamp": _utc_now(),
            "event_type": event_type,
            "run_id": self.run_id,
            "session": self.session,
            "sequence": self._sequence,
            "payload": _ensure_mapping("payload", payload),
        }
        if metadata is not None:
            envelope["metadata"] = _ensure_mapping("metadata", metadata)

        self._append(envelope)
        for listener in list(self._listeners):
            listener(envelope)
        return envelope

    def extend(self, events: Iterable[Mapping[str, object]]) -> None:
        """Append pre-built telemetry envelopes (used for replay backfills)."""
        for event in events:
            envelope = dict(event)
            self._append(envelope)
            sequence = envelope.get("sequence")
            if isinstance(sequence, int):
                self._sequence = max(self._sequence, sequence)

    def _append(self, envelope: dict) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(payload + "\n")
