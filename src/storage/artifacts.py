from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List

from src.models.contracts import ParameterSet, Portfolio
from src.storage.layout import StorageLayout


class ArtifactStore:
    def __init__(self, layout: StorageLayout) -> None:
        self.layout = layout

    # Portfolios ------------------------------------------------------
    def save_portfolio(self, portfolio: Portfolio) -> Path:
        portfolio.touch()
        path = self.layout.portfolio_path(portfolio.portfolio_id)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(asdict(portfolio), indent=2, sort_keys=True))
        tmp.replace(path)
        return path

    def load_portfolio(self, portfolio_id: str) -> Portfolio | None:
        path = self.layout.portfolio_path(portfolio_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Portfolio.from_dict(data)

    def list_portfolios(self, limit: int = 5) -> List[Portfolio]:
        directory = self.layout.portfolios_directory()
        files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        portfolios: List[Portfolio] = []
        for path in files[:limit]:
            payload = json.loads(path.read_text())
            portfolios.append(Portfolio.from_dict(payload))
        return portfolios

    def delete_portfolio(self, portfolio_id: str) -> bool:
        path = self.layout.portfolio_path(portfolio_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    # Parameter Sets --------------------------------------------------
    def list_parameter_sets(self, limit: int = 5) -> List[ParameterSet]:
        directory = self.layout.parameter_sets_directory()
        files = sorted(directory.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        items: List[ParameterSet] = []
        for path in files[:limit]:
            items.append(ParameterSet(**json.loads(path.read_text())))
        return items

    # Logs ------------------------------------------------------------
    def append_log(self, run_id: str, event: Dict[str, Any]) -> Path:
        path = self.layout.run_log_path(run_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, separators=(",", ":")))
            handle.write("\n")
        return path

    def list_run_logs(self, limit: int = 5) -> List[Path]:
        directory = self.layout.logs_directory()
        files = sorted(directory.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        return files[:limit]

    # Simulations -----------------------------------------------------
    def list_simulations(self, limit: int = 5) -> List[Path]:
        directory = self.layout.simulations_directory()
        sims = sorted(directory.glob("*/result.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        return sims[:limit]
