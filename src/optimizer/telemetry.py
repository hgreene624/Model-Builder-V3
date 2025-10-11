from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

from src.optimizer.training_logger import TrainingLogger


Listener = Callable[[dict], None]


def _utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="milliseconds")


@dataclass
class TelemetryPublisher:
    run_id: str
    logger: TrainingLogger
    session: str = "cli"
    schema_version: str = "1.0.0"

    def __post_init__(self) -> None:
        self._listeners: List[Listener] = []

    def register(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def emit(self, event_type: str, payload: Dict[str, object]) -> dict:
        event = {
            "schema_version": self.schema_version,
            "timestamp": _utc_now(),
            "event_type": event_type,
            "run_id": self.run_id,
            "session": self.session,
            "payload": payload,
        }
        self.logger.write(event)
        for listener in list(self._listeners):
            listener(event)
        return event

    # Convenience helpers -------------------------------------------------
    def session_start(
        self,
        *,
        model_id: str,
        portfolio_id: str,
        objective_weights: Dict[str, float],
        population_size: int,
        generations: int,
        seed: Optional[int],
    ) -> dict:
        return self.emit(
            "session_start",
            {
                "model_id": model_id,
                "portfolio_id": portfolio_id,
                "objective_weights": objective_weights,
                "population_size": population_size,
                "generations": generations,
                "seed": seed,
            },
        )

    def generation_summary(
        self,
        *,
        generation: int,
        population_size: int,
        infeasible: int,
        best_fitness: float,
        average_fitness: float,
        best_parameters: Dict[str, float],
        best_metrics: Dict[str, float],
        best_constraints: Dict[str, float],
    ) -> dict:
        return self.emit(
            "generation_summary",
            {
                "generation": generation,
                "population_size": population_size,
                "infeasible": infeasible,
                "best_fitness": best_fitness,
                "average_fitness": average_fitness,
                "best_parameters": best_parameters,
                "best_metrics": best_metrics,
                "best_constraints": best_constraints,
            },
        )

    def checkpoint(self, payload: Dict[str, object]) -> dict:
        return self.emit("checkpoint", payload)

    def session_end(
        self,
        *,
        status: str,
        duration_seconds: float,
        best_parameter_set_id: str,
        best_score: float,
    ) -> dict:
        return self.emit(
            "session_end",
            {
                "status": status,
                "duration_seconds": duration_seconds,
                "best_parameter_set_id": best_parameter_set_id,
                "best_score": best_score,
            },
        )
