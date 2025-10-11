from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Sequence

from src.models.contracts import ParameterSet
from src.optimizer.training_logger import TrainingLogger
from src.storage.layout import StorageLayout


@dataclass(frozen=True)
class ObjectiveWeights:
    cagr: float
    calmar: float
    sharpe: float

    def __post_init__(self) -> None:
        total = self.cagr + self.calmar + self.sharpe
        if total <= 0:
            raise ValueError("objective weights must sum to a positive value")
        object.__setattr__(self, "_normalized", {  # type: ignore[call-arg]
            "cagr": self.cagr / total,
            "calmar": self.calmar / total,
            "sharpe": self.sharpe / total,
        })

    @property
    def normalized(self) -> Dict[str, float]:
        return self._normalized  # type: ignore[attr-defined]

    def score(self, metrics: Dict[str, float]) -> float:
        return sum(metrics.get(name, 0.0) * weight for name, weight in self.normalized.items())


@dataclass(frozen=True)
class GateResult:
    passed: bool
    penalty: float
    reasons: List[str]


@dataclass(frozen=True)
class ConstraintGate:
    max_trade_rate: float
    min_hold_days: float
    penalty: float

    def evaluate(self, stats: Dict[str, float]) -> GateResult:
        reasons: List[str] = []
        trade_rate = stats.get("trade_rate")
        hold_days = stats.get("avg_hold_days")

        if trade_rate is not None and trade_rate > self.max_trade_rate:
            reasons.append(f"trade_rate {trade_rate:.2f} exceeds max {self.max_trade_rate:.2f}")
        if hold_days is not None and hold_days < self.min_hold_days:
            reasons.append(f"avg_hold_days {hold_days:.2f} below min {self.min_hold_days:.2f}")

        if reasons:
            return GateResult(passed=False, penalty=self.penalty, reasons=reasons)
        return GateResult(passed=True, penalty=0.0, reasons=[])


class EvolutionaryOptimizer:
    def __init__(
        self,
        objective_weights: ObjectiveWeights,
        constraint_gate: ConstraintGate,
        logger: TrainingLogger,
        layout: StorageLayout,
        population_size: int,
        generations: int,
    ) -> None:
        if population_size <= 0:
            raise ValueError("population_size must be positive")
        if generations <= 0:
            raise ValueError("generations must be positive")
        self.objective_weights = objective_weights
        self.constraint_gate = constraint_gate
        self.logger = logger
        self.layout = layout
        self.population_size = population_size
        self.generations = generations

    def run(
        self,
        run_id: str,
        model_id: str,
        portfolio_id: str,
        evaluator,
        initial_population: Sequence[Dict[str, float]],
        seed: int | None = None,
    ) -> ParameterSet:
        if len(initial_population) < self.population_size:
            raise ValueError("initial_population smaller than population_size")

        start_time = time.perf_counter()
        self._log_event(
            "session_start",
            run_id,
            {
                "model_id": model_id,
                "portfolio_id": portfolio_id,
                "objective_weights": self.objective_weights.normalized,
                "population_size": self.population_size,
                "generations": self.generations,
                "seed": seed,
            },
        )

        best_candidate: dict | None = None
        best_metrics: Dict[str, float] | None = None
        best_stats: Dict[str, float] | None = None
        best_score: float = float("-inf")
        best_penalty: float = 0.0
        infeasible_total = 0

        population = list(initial_population[: self.population_size])
        for generation in range(1, self.generations + 1):
            generation_records = []
            infeasible_total = 0
            for genome in population:
                outcome = evaluator(genome)
                metrics = dict(outcome.get("metrics") or {})
                stats = dict(outcome.get("stats") or {})

                score = self.objective_weights.score(metrics)
                gate = self.constraint_gate.evaluate(stats)
                if not gate.passed:
                    infeasible_total += 1
                adjusted_score = score + gate.penalty

                generation_records.append(
                    {
                        "genome": genome,
                        "metrics": metrics,
                        "stats": stats,
                        "score": score,
                        "adjusted_score": adjusted_score,
                        "penalty": gate.penalty,
                        "reasons": gate.reasons,
                    }
                )

                if adjusted_score > best_score:
                    best_candidate = genome
                    best_metrics = metrics
                    best_stats = stats
                    best_score = adjusted_score
                    best_penalty = gate.penalty

            assert best_candidate is not None
            assert best_metrics is not None
            assert best_stats is not None

            self._log_event(
                "generation_summary",
                run_id,
                {
                    "generation": generation,
                    "population_size": len(population),
                    "infeasible": infeasible_total,
                    "best_fitness": best_score,
                    "best_parameters": dict(best_candidate),
                    "best_metrics": best_metrics,
                    "best_constraints": best_stats,
                },
            )

        parameter_set = self._persist_best(
            run_id,
            model_id,
            portfolio_id,
            best_candidate,
            best_metrics,
            best_stats,
            best_score,
            best_penalty,
        )

        duration = time.perf_counter() - start_time
        self._log_event(
            "session_end",
            run_id,
            {
                "status": "completed",
                "best_parameter_set_id": parameter_set.parameter_set_id,
                "duration_seconds": duration,
            },
        )

        return parameter_set

    def _persist_best(
        self,
        run_id: str,
        model_id: str,
        portfolio_id: str,
        parameters: Dict[str, float],
        metrics: Dict[str, float],
        stats: Dict[str, float],
        score: float,
        penalty: float,
    ) -> ParameterSet:
        parameter_set_id = uuid.uuid4().hex
        payload = ParameterSet(
            parameter_set_id=parameter_set_id,
            model_id=model_id,
            portfolio_id=portfolio_id,
            run_id=run_id,
            parameters=dict(parameters),
            fitness={
                "score": score,
                **metrics,
            },
            constraints=dict(stats),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )

        path = self.layout.parameter_set_path(parameter_set_id)
        path.write_text(json.dumps(asdict(payload), indent=2, sort_keys=True))
        return payload

    def _log_event(self, event_type: str, run_id: str, payload: Dict[str, object]) -> None:
        self.logger.write(
            {
                "event_type": event_type,
                "run_id": run_id,
                "payload": payload,
            }
        )
