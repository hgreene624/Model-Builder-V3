from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


@dataclass
class HomeSummary:
    portfolios: list[tuple[str, str | None]]
    parameter_sets: list[tuple[str, str | None]]
    simulations: list[tuple[str, str | None]]
    logs: list[tuple[str, str | None]]


def collect_home_summary(data_dir: Path, limit: int = 5) -> HomeSummary:
    layout = StorageLayout(root=data_dir)
    store = ArtifactStore(layout=layout)

    portfolios = [(pf.name, pf.coverage_window.get("end")) for pf in store.list_portfolios(limit)]
    parameter_sets = [
        (ps.parameter_set_id, ps.created_at) for ps in store.list_parameter_sets(limit)
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
