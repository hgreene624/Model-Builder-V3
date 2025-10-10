from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


@dataclass
class HomeSummary:
    portfolios: List[Tuple[str, str | None]]
    parameter_sets: List[Tuple[str, str | None]]
    simulations: List[Tuple[str, str | None]]
    logs: List[Tuple[str, str | None]]


def collect_home_summary(data_dir: Path, limit: int = 5) -> HomeSummary:
    layout = StorageLayout(root=data_dir)
    store = ArtifactStore(layout=layout)

    portfolios = [(pf.name, pf.coverage_window.get("end")) for pf in store.list_portfolios(limit)]
    parameter_sets = [
        (ps.parameter_set_id, ps.created_at)
        for ps in store.list_parameter_sets(limit)
    ]
    simulations = []
    for result_path in store.list_simulations(limit):
        simulation_id = result_path.parent.name
        simulations.append((simulation_id, None))

    logs = []
    for log_path in store.list_run_logs(limit):
        logs.append((log_path.stem, None))

    return HomeSummary(
        portfolios=portfolios,
        parameter_sets=parameter_sets,
        simulations=simulations,
        logs=logs,
    )
