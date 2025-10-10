from __future__ import annotations

import json
from pathlib import Path

from src.home.dashboard import collect_home_summary


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_collect_home_summary(tmp_path: Path) -> None:
    write_json(
        tmp_path / "portfolios" / "pf-1.json",
        {
            "portfolio_id": "pf-1",
            "name": "Tech",
            "description": None,
            "source": "manual",
            "seed_reference": None,
            "filters": {},
            "coverage_window": {"start": "2020", "end": "2025"},
            "tickers": [],
            "liquidity_stats": {},
            "notes": [],
            "schema_version": "1.0.0",
        },
    )

    write_json(
        tmp_path / "parameters" / "ps-1.json",
        {
            "parameter_set_id": "ps-1",
            "model_id": "atr",
            "portfolio_id": "pf-1",
            "run_id": "run-1",
            "parameters": {},
            "fitness": {},
            "constraints": {},
            "created_at": "2025-10-10T00:00:00Z",
            "schema_version": "1.0.0",
        },
    )

    (tmp_path / "simulations" / "sim-1").mkdir(parents=True)
    (tmp_path / "simulations" / "sim-1" / "result.json").write_text("{}")

    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "logs" / "run-1.jsonl").write_text("{}\n")

    summary = collect_home_summary(tmp_path)

    assert summary.portfolios == [("Tech", "2025")]
    assert summary.parameter_sets[0][0] == "ps-1"
    assert summary.simulations == [("sim-1", None)]
    assert summary.logs == [("run-1", None)]
