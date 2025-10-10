from __future__ import annotations

import json
from pathlib import Path

from src.optimizer.training_logger import TrainingLogger


def test_training_logger_writes_jsonl(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "run.jsonl"
    logger = TrainingLogger(log_path, max_bytes=1024)

    logger.write({"event": "test", "value": 1})
    logger.write({"event": "test", "value": 2})

    lines = log_path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["event"] == "test" for line in lines)


def test_training_logger_rotates(tmp_path: Path) -> None:
    log_path = tmp_path / "logs" / "run.jsonl"
    logger = TrainingLogger(log_path, max_bytes=50)

    for i in range(10):
        logger.write({"event": "run", "value": i})

    rotated = list(log_path.parent.glob("run.jsonl*"))
    assert len(rotated) >= 2
