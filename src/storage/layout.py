from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StorageLayout:
    """Resolve canonical artifact paths under the configured storage root."""

    root: Path

    def _ensure_parent(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def portfolio_path(self, portfolio_id: str) -> Path:
        return self._ensure_parent(self.root / "portfolios" / f"{portfolio_id}.json")

    def parameter_set_path(self, parameter_set_id: str) -> Path:
        return self._ensure_parent(self.root / "parameters" / f"{parameter_set_id}.json")

    def run_log_path(self, run_id: str) -> Path:
        return self._ensure_parent(self.root / "logs" / f"{run_id}.jsonl")

    def logs_directory(self) -> Path:
        path = self.root / "logs"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def parameter_sets_directory(self) -> Path:
        path = self.root / "parameters"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def portfolios_directory(self) -> Path:
        path = self.root / "portfolios"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def run_directory(self, run_id: str) -> Path:
        path = self.root / "runs" / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def simulation_directory(self, simulation_id: str) -> Path:
        path = self.root / "simulations" / simulation_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def simulations_directory(self) -> Path:
        path = self.root / "simulations"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def bundle_path(self, bundle_id: str) -> Path:
        return self._ensure_parent(self.root / "bundles" / f"{bundle_id}.zip")

    def benchmark_path(self, symbol: str) -> Path:
        return self._ensure_parent(self.root / "benchmarks" / f"{symbol}.parquet")

    def market_shard_path(self, symbol: str, interval: str, start: str, end: str) -> Path:
        safe_symbol = symbol.upper()
        filename = f"{start}_{end}.parquet"
        return self._ensure_parent(self.root / "ohlcv" / safe_symbol / interval / filename)

    # --- Strategy profiles & evaluation runs -------------------------------------------------

    def strategy_profiles_directory(self) -> Path:
        path = self.root / "strategy_profiles"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def strategy_profile_path(self, profile_id: str) -> Path:
        return self._ensure_parent(self.strategy_profiles_directory() / f"{profile_id}.json")

    def evaluations_directory(self) -> Path:
        path = self.root / "evaluations"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def evaluation_log_path(self, run_id: str) -> Path:
        return self._ensure_parent(self.evaluations_directory() / f"{run_id}.jsonl")
