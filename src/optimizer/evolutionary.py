from __future__ import annotations

import json
import math
import random
import time
import uuid
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Sequence

from src.models.contracts import ParameterSet
from src.optimizer.telemetry import TelemetryPublisher
from src.storage.layout import StorageLayout

EvaluationFn = Callable[[Dict[str, float]], Dict[str, Dict[str, float]]]
MutateFn = Callable[[Dict[str, float], random.Random], Dict[str, float]]


@dataclass(frozen=True)
class ObjectiveWeights:
    cagr: float
    calmar: float
    sharpe: float

    def __post_init__(self) -> None:
        total = self.cagr + self.calmar + self.sharpe
        if total <= 0:
            raise ValueError("objective weights must sum to a positive value")
        normalised = {
            "cagr": self.cagr / total,
            "calmar": self.calmar / total,
            "sharpe": self.sharpe / total,
        }
        object.__setattr__(self, "_normalised", normalised)  # type: ignore[call-arg]

    @property
    def normalised(self) -> Dict[str, float]:
        return self._normalised  # type: ignore[attr-defined]

    def score(self, metrics: Dict[str, float]) -> float:
        return sum(metrics.get(name, 0.0) * weight for name, weight in self.normalised.items())


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


@dataclass(frozen=True)
class CandidateScore:
    parameters: Dict[str, float]
    metrics: Dict[str, float]
    stats: Dict[str, float]
    score: float
    adjusted_score: float
    penalty: float
    reasons: List[str]


class EvolutionaryOptimizer:
    """Evolutionary search over strategy parameters with telemetry integration."""

    def __init__(
        self,
        *,
        objective_weights: ObjectiveWeights,
        constraint_gate: ConstraintGate,
        publisher: TelemetryPublisher,
        layout: StorageLayout,
        population_size: int,
        generations: int,
        max_workers: int = 1,
        mutate_fn: MutateFn | None = None,
        candidate_event_sink: Callable[[dict], None] | None = None,
    ) -> None:
        if population_size <= 0:
            raise ValueError("population_size must be positive")
        if generations <= 0:
            raise ValueError("generations must be positive")
        if max_workers <= 0:
            raise ValueError("max_workers must be positive")

        self.objective_weights = objective_weights
        self.constraint_gate = constraint_gate
        self.publisher = publisher
        self.layout = layout
        self.population_size = population_size
        self.generations = generations
        self.max_workers = max_workers
        self.mutate_fn = mutate_fn
        self._candidate_event_sink = candidate_event_sink

    def run(
        self,
        *,
        run_id: str,
        model_id: str,
        portfolio_id: str,
        evaluator: EvaluationFn,
        initial_population: Sequence[Dict[str, float]],
        seed: int | None = None,
    ) -> ParameterSet:
        if len(initial_population) < self.population_size:
            raise ValueError("initial_population smaller than population_size")

        rng = random.Random(seed)
        population = [dict(genome) for genome in initial_population[: self.population_size]]
        population = self._apply_bounds(population)

        start_time = time.perf_counter()
        self.publisher.session_start(
            model_id=model_id,
            portfolio_id=portfolio_id,
            objective_weights=self.objective_weights.normalised,
            population_size=self.population_size,
            generations=self.generations,
            seed=seed,
        )

        best_record: CandidateScore | None = None

        for generation in range(1, self.generations + 1):
            records = self._evaluate_population(
                run_id=run_id,
                generation=generation,
                population=population,
                evaluator=evaluator,
            )
            records.sort(key=lambda item: item.adjusted_score, reverse=True)

            generation_best = records[0]
            if best_record is None or generation_best.adjusted_score > best_record.adjusted_score:
                best_record = generation_best
                self.publisher.checkpoint(
                    {
                        "generation": generation,
                        "best_parameters": generation_best.parameters,
                        "best_score": generation_best.adjusted_score,
                        "penalty": generation_best.penalty,
                        "reasons": generation_best.reasons,
                    }
                )

            self.publisher.generation_summary(
                generation=generation,
                population_size=len(population),
                infeasible=sum(1 for record in records if record.penalty != 0.0),
                best_fitness=generation_best.adjusted_score,
                average_fitness=_mean([record.adjusted_score for record in records]),
                best_parameters=generation_best.parameters,
                best_metrics=generation_best.metrics,
                best_constraints=generation_best.stats,
            )

            if generation < self.generations and self.mutate_fn is not None:
                population = self._next_population(records, rng)
            else:
                population = [dict(record.parameters) for record in records[: self.population_size]]

        assert best_record is not None

        parameter_set = self._persist_best(
            run_id=run_id,
            model_id=model_id,
            portfolio_id=portfolio_id,
            record=best_record,
        )

        duration = time.perf_counter() - start_time
        self.publisher.session_end(
            status="completed",
            duration_seconds=duration,
            best_parameter_set_id=parameter_set.parameter_set_id,
            best_score=best_record.adjusted_score,
        )

        return parameter_set

    def _evaluate_population(
        self,
        *,
        run_id: str,
        generation: int,
        population: Sequence[Dict[str, float]],
        evaluator: EvaluationFn,
    ) -> List[CandidateScore]:
        records: List[CandidateScore] = []

        if self.max_workers > 1:
            with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
                for index, (genome, outcome) in enumerate(
                    zip(population, executor.map(evaluator, population), strict=False), start=1
                ):
                    record = self._build_record(dict(genome), outcome)
                    records.append(record)
                    self._emit_candidate_event(
                        run_id=run_id,
                        generation=generation,
                        index=index,
                        record=record,
                    )
            return records

    # In sequential mode --------------------------------------------------
        for index, genome in enumerate(population, start=1):
            outcome = evaluator(genome)
            record = self._build_record(dict(genome), outcome)
            records.append(record)
            self._emit_candidate_event(
                run_id=run_id,
                generation=generation,
                index=index,
                record=record,
            )
        return records

    def _emit_candidate_event(
        self,
        *,
        run_id: str,
        generation: int,
        index: int,
        record: CandidateScore,
    ) -> None:
        if self._candidate_event_sink is None:
            return
        candidate_id = f"{run_id}-g{generation:03d}-c{index:03d}"
        payload = {
            "candidate_id": candidate_id,
            "score": record.adjusted_score,
            "raw_score": record.score,
            "metrics": record.metrics,
            "parameters": record.parameters,
            "stats": record.stats,
            "penalty": record.penalty,
            "generation": generation,
            "rank": index,
        }
        try:
            self._candidate_event_sink(payload)
        except Exception:  # pragma: no cover - defensive
            pass

    def _build_record(self, genome: Dict[str, float], outcome: Dict[str, Dict[str, float]]) -> CandidateScore:
        metrics = dict(outcome.get("metrics") or {})
        stats = dict(outcome.get("stats") or {})
        score = self.objective_weights.score(metrics)
        gate = self.constraint_gate.evaluate(stats)
        adjusted = score + gate.penalty
        return CandidateScore(
            parameters=dict(genome),
            metrics=metrics,
            stats=stats,
            score=score,
            adjusted_score=adjusted,
            penalty=gate.penalty,
            reasons=gate.reasons,
        )

    def _next_population(self, records: Sequence[CandidateScore], rng: random.Random) -> List[Dict[str, float]]:
        elite_count = max(1, self.population_size // 3)
        elites = [dict(records[i].parameters) for i in range(elite_count)]
        offspring: List[Dict[str, float]] = list(elites)

        while len(offspring) < self.population_size:
            parent = rng.choice(elites)
            child = dict(parent)
            if self.mutate_fn is not None:
                child = self.mutate_fn(child, rng)
            offspring.append(child)

        return self._apply_bounds(offspring[: self.population_size])

    def _apply_bounds(self, population: Iterable[Dict[str, float]]) -> List[Dict[str, float]]:
        adjusted: List[Dict[str, float]] = []
        for genome in population:
            adjusted.append({key: float(value) for key, value in genome.items()})
        return adjusted

    def _persist_best(
        self,
        *,
        run_id: str,
        model_id: str,
        portfolio_id: str,
        record: CandidateScore,
    ) -> ParameterSet:
        parameter_set_id = uuid.uuid4().hex
        payload = ParameterSet(
            parameter_set_id=parameter_set_id,
            model_id=model_id,
            portfolio_id=portfolio_id,
            run_id=run_id,
            parameters=dict(record.parameters),
            fitness={"score": record.adjusted_score, **record.metrics},
            constraints=dict(record.stats),
            created_at=datetime.now(tz=timezone.utc).isoformat(),
        )

        path = self.layout.parameter_set_path(parameter_set_id)
        path.write_text(json.dumps(asdict(payload), indent=2, sort_keys=True))
        return payload


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))
