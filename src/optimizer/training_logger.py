from __future__ import annotations

import json
from pathlib import Path


class TrainingLogger:
    """Append JSON events to a log file with simple size-based rotation."""

    def __init__(self, path: Path, max_bytes: int = 5_000_000) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: dict) -> None:
        payload = json.dumps(event, separators=(",", ":")) + "\n"
        self._rotate_if_needed(len(payload))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(payload)

    def _rotate_if_needed(self, incoming_bytes: int) -> None:
        if not self.path.exists():
            return
        size = self.path.stat().st_size + incoming_bytes
        if size <= self.max_bytes:
            return
        idx = 1
        rotated = self.path.with_suffix(self.path.suffix + f".{idx}")
        while rotated.exists():
            idx += 1
            rotated = self.path.with_suffix(self.path.suffix + f".{idx}")
        self.path.replace(rotated)
