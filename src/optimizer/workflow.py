from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from functools import partial

import numpy as np
import pandas as pd

from src.config.settings import AppSettings
from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader
from src.engine.atr_breakout import ATRBreakoutConfig, RiskSettings, atr_breakout_signals
from src.engine.backtest import CostModel, run_backtest
from src.models.contracts import ParameterSet, Portfolio
from src.optimizer.evolutionary import ConstraintGate, ObjectiveWeights, EvolutionaryOptimizer
from src.optimizer.telemetry import TelemetryPublisher
from src.optimizer.training_logger import TrainingLogger
from src.storage.layout import StorageLayout

from model_builder.optimization import EvaluationAppender, TelemetryLogWriter
from model_builder.optimization.coverage import CoveragePlan, derive_plan


@dataclass(frozen=True)
class OptimizationContext:
    bars_by_symbol: Dict[str, pd.DataFrame]
    price_matrix: pd.DataFrame
    base_config: ATRBreakoutConfig
    base_risk: RiskSettings
    initial_capital: float
    cost_model: CostModel


@dataclass(frozen=True)
class OptimizationResult:
    parameter_set: ParameterSet
    telemetry: List[dict]
    metrics: Dict[str, float]
    stats: Dict[str, float]
    equity_curve: pd.DataFrame
    issues: List[str]
    synthetic: bool
    run_id: str
    log_path: Path
    evaluation_log_path: Path
    parameter_path: Path
    best_config: ATRBreakoutConfig
    best_risk: RiskSettings
    coverage_plan: CoveragePlan


def build_loader(settings: AppSettings) -> MarketDataLoader | None:
    """Instantiate the market data loader with available providers."""
    try:
        from src.data.providers.alpaca_client import AlpacaClient
        from src.data.providers.yahoo_client import YahooClient
    except Exception:
        return None

    cache = MarketDataCache(root=settings.data_dir / "cache", max_items=32)
    providers = {
        "alpaca": lambda: AlpacaClient().fetch_bars,
        "yahoo": lambda: YahooClient().fetch_bars,
    }
    default = "alpaca" if settings.has_alpaca_credentials else "yahoo"
    return MarketDataLoader(cache=cache, providers=providers, default_provider=default)


def generate_synthetic_frames(symbols: Iterable[str], periods: int = 365) -> Dict[str, pd.DataFrame]:
    """Produce deterministic synthetic OHLCV frames for offline optimisation."""
    end = datetime.now(tz=timezone.utc).date()
    index = pd.date_range(end=end, periods=periods, freq="D", tz="UTC")
    frames: Dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(symbols, start=1):
        rng = np.random.default_rng(seed=offset)
        base = rng.uniform(80, 120)
        drift = rng.normal(0.0005, 0.0002)
        shocks = rng.normal(0, 0.015, size=len(index))
        close = base * np.exp(np.cumsum(drift + shocks))
        high = close * (1 + rng.uniform(0.0, 0.015, size=len(index)))
        low = close * (1 - rng.uniform(0.0, 0.015, size=len(index)))
        open_ = close * (1 + rng.normal(0, 0.002, size=len(index)))
        volume = rng.integers(250_000, 1_000_000, size=len(index))
        frames[symbol] = pd.DataFrame(
            {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
            index=index,
        )
    return frames


def _filter_frame_by_dates(frame: pd.DataFrame, *, start: date, end: date) -> pd.DataFrame:
    """Restrict a bars frame to the inclusive [start, end] date range."""

    if frame.empty:
        return frame

    index = frame.index
    try:
        dates = index.date  # pandas DatetimeIndex
    except AttributeError:
        return frame

    mask = (dates >= start) & (dates <= end)
    return frame.loc[mask]


def resolve_coverage_window(portfolio: Portfolio) -> Tuple[str, str]:
    coverage = portfolio.coverage_window or {}
    end = coverage.get("end")
    start = coverage.get("start")
    if not end:
        end = datetime.now(tz=timezone.utc).date().isoformat()
    if not start:
        start_dt = datetime.fromisoformat(end).date() - timedelta(days=365 * 5)
        start = start_dt.isoformat()
    return start, end


def load_portfolio_bars(
    portfolio: Portfolio,
    loader: MarketDataLoader | None,
    symbols: Sequence[str],
    start: str,
    end: str,
    warmup_bars: int,
    *,
    use_synthetic: bool = False,
    synthetic_periods: int = 365,
) -> tuple[Dict[str, pd.DataFrame], List[str], bool]:
    frames: Dict[str, pd.DataFrame] = {}
    issues: List[str] = []
    synthetic_used = False

    if use_synthetic or loader is None:
        synthetic_used = True
        issues.append("Market data unavailable; using synthetic price series for all symbols.")
        return generate_synthetic_frames(symbols, periods=synthetic_periods), issues, synthetic_used

    for symbol in symbols:
        try:
            frame = loader.load(
                symbol=symbol,
                start=start,
                end=end,
                warmup_bars=warmup_bars,
                interval="1d",
            )
            if frame.empty:
                raise ValueError("no data returned")
            frames[symbol] = frame[["open", "high", "low", "close", "volume"]].copy()
        except Exception as exc:  # pragma: no cover - exercised via synthetic fallback
            issues.append(f"{symbol}: {exc}")

    missing = [symbol for symbol in symbols if symbol not in frames]
    if missing:
        synthetic_used = True
        issues.append(f"Synthetic data generated for symbols with missing history: {', '.join(missing)}.")
        frames.update(generate_synthetic_frames(missing, periods=synthetic_periods))

    return frames, issues, synthetic_used


def build_price_matrix(bars_by_symbol: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    close_frames = [
        frame["close"].rename(symbol) for symbol, frame in bars_by_symbol.items()
    ]
    if not close_frames:
        return pd.DataFrame()
    matrix = pd.concat(close_frames, axis=1).sort_index()
    return matrix.ffill().dropna(how="all")


def config_from_genome(genome: Dict[str, float], base: ATRBreakoutConfig) -> ATRBreakoutConfig:
    window = max(1, int(round(genome.get("atr_window", base.atr_window))))
    lookback = max(1, int(round(genome.get("breakout_lookback", base.breakout_lookback))))
    multiplier = float(genome.get("breakout_multiplier", base.breakout_multiplier))
    return ATRBreakoutConfig(
        atr_window=window,
        breakout_lookback=lookback,
        breakout_multiplier=max(0.1, multiplier),
    )


def risk_from_genome(genome: Dict[str, float], template: RiskSettings) -> RiskSettings:
    fraction = max(1e-6, float(genome.get("risk_fraction", template.risk_fraction)))
    return RiskSettings(
        enabled=template.enabled,
        risk_fraction=fraction,
        min_weight=template.min_weight,
        max_weight=template.max_weight,
        fallback_weight=template.fallback_weight,
    )


def evaluate_genome(genome: Dict[str, float], context: OptimizationContext) -> Dict[str, Dict[str, float]]:
    config = config_from_genome(genome, context.base_config)
    risk = risk_from_genome(genome, context.base_risk)
    frames = [
        atr_breakout_signals(symbol, frame, config, risk)
        for symbol, frame in context.bars_by_symbol.items()
    ]
    signals = (
        pd.concat(frames, ignore_index=True).sort_values("timestamp")
        if frames
        else pd.DataFrame(columns=["timestamp", "symbol", "action", "weight", "metadata"])
    )

    backtest = run_backtest(
        prices=context.price_matrix,
        signals=signals,
        initial_capital=context.initial_capital,
        cost_model=context.cost_model,
    )
    metrics = {key: float(backtest.kpis.get(key, 0.0)) for key in ("cagr", "calmar", "sharpe")}
    stats = {
        "trade_rate": float(backtest.kpis.get("trade_rate", 0.0)),
        "avg_hold_days": float(backtest.kpis.get("avg_hold_days", 0.0)),
    }
    return {"metrics": metrics, "stats": stats}


def backtest_best(
    genome: Dict[str, float],
    context: OptimizationContext,
) -> Tuple[ATRBreakoutConfig, RiskSettings, pd.DataFrame, Dict[str, float], Dict[str, float]]:
    config = config_from_genome(genome, context.base_config)
    risk = risk_from_genome(genome, context.base_risk)
    frames = [
        atr_breakout_signals(symbol, frame, config, risk)
        for symbol, frame in context.bars_by_symbol.items()
    ]
    signals = (
        pd.concat(frames, ignore_index=True).sort_values("timestamp")
        if frames
        else pd.DataFrame(columns=["timestamp", "symbol", "action", "weight", "metadata"])
    )

    backtest = run_backtest(
        prices=context.price_matrix,
        signals=signals,
        initial_capital=context.initial_capital,
        cost_model=context.cost_model,
    )
    metrics = {
        key: float(backtest.kpis.get(key, 0.0))
        for key in ("cagr", "calmar", "sharpe", "max_drawdown")
    }
    stats = {
        "trade_rate": float(backtest.kpis.get("trade_rate", 0.0)),
        "avg_hold_days": float(backtest.kpis.get("avg_hold_days", 0.0)),
        "turnover": float(backtest.kpis.get("turnover", 0.0)),
    }
    equity = pd.DataFrame(backtest.equity_curve)
    return config, risk, equity, metrics, stats


def generate_population(
    base: Dict[str, float],
    bounds: Dict[str, Tuple[float, float]],
    size: int,
    seed: Optional[int],
    int_fields: Iterable[str],
) -> List[Dict[str, float]]:
    generator = np.random.default_rng(seed or 0)
    population: List[Dict[str, float]] = [dict(base)]
    int_field_set = set(int_fields)

    while len(population) < size:
        genome: Dict[str, float] = {}
        for key, (low, high) in bounds.items():
            if key in int_field_set:
                value = generator.integers(int(low), int(high) + 1)
            else:
                value = generator.uniform(low, high)
            genome[key] = float(value)
        population.append(genome)

    return population[:size]


def build_mutate_fn(
    bounds: Dict[str, Tuple[float, float]],
    int_fields: Iterable[str],
) -> callable:
    int_field_set = set(int_fields)

    def mutate(genome: Dict[str, float], rng: np.random.Generator) -> Dict[str, float]:
        mutated = dict(genome)
        for key, (low, high) in bounds.items():
            span = high - low
            if span <= 0:
                continue
            jitter = span * 0.1
            candidate = mutated.get(key, low) + rng.uniform(-jitter, jitter)
            candidate = max(low, min(high, candidate))
            if key in int_field_set:
                mutated[key] = float(int(round(candidate)))
            else:
                mutated[key] = float(candidate)
        return mutated

    def mutate_wrapper(genome: Dict[str, float], random_state) -> Dict[str, float]:
        if isinstance(random_state, np.random.RandomState):  # pragma: no cover - compatibility branch
            generator = np.random.default_rng(random_state.randint(0, 1_000_000))
        else:
            generator = random_state
        return mutate(genome, generator)

    return mutate_wrapper


def run_optimization(
    *,
    settings: AppSettings,
    portfolio: Portfolio,
    selected_symbols: Sequence[str],
    base_config: ATRBreakoutConfig,
    base_risk: RiskSettings,
    bounds: Dict[str, Tuple[float, float]],
    objective_weights: ObjectiveWeights,
    constraint_gate: ConstraintGate,
    population_size: int,
    generations: int,
    max_workers: int,
    seed: Optional[int],
    initial_capital: float,
    cost_model: CostModel,
    model_id: str,
    session: str,
    run_id: Optional[str] = None,
    use_synthetic: bool = False,
    train_percentage: float | None = None,
    warmup_days: Optional[int] = None,
) -> OptimizationResult:
    if not selected_symbols:
        raise ValueError("Selected symbol list is empty; provide at least one ticker.")

    train_fraction = float(train_percentage) if train_percentage is not None else 0.7
    if not (0 < train_fraction < 1):
        raise ValueError("train_percentage must be between 0 and 1 (exclusive).")

    warmup_allocation = int(warmup_days) if warmup_days is not None else base_config.warmup
    if warmup_allocation < 1:
        raise ValueError("warmup_days must be ≥ 1.")

    layout = StorageLayout(settings.data_dir)
    loader = None if use_synthetic else build_loader(settings)
    start, end = resolve_coverage_window(portfolio)

    bars_by_symbol, issues, synthetic_used = load_portfolio_bars(
        portfolio,
        loader,
        selected_symbols,
        start,
        end,
        warmup_bars=max(base_config.warmup, warmup_allocation),
        use_synthetic=use_synthetic,
    )

    price_matrix = build_price_matrix(bars_by_symbol)
    if price_matrix.empty:
        raise ValueError("Unable to assemble price data for the selected symbols.")

    coverage_dates = [timestamp.date() for timestamp in price_matrix.index]
    coverage_plan = derive_plan(
        portfolio_id=portfolio.portfolio_id,
        coverage_dates=coverage_dates,
        train_percentage=train_fraction,
        warmup_days=warmup_allocation,
    )

    warmup_start = coverage_plan.warmup.slice.start
    train_end = coverage_plan.train.end

    filtered_bars: Dict[str, pd.DataFrame] = {}
    for symbol, frame in bars_by_symbol.items():
        sliced = _filter_frame_by_dates(frame, start=warmup_start, end=train_end)
        if sliced.empty:
            raise ValueError(
                f"No price data available for symbol '{symbol}' within training window "
                f"{warmup_start} to {train_end}."
            )
        filtered_bars[symbol] = sliced
    bars_by_symbol = filtered_bars

    price_matrix = _filter_frame_by_dates(price_matrix, start=warmup_start, end=train_end)
    if price_matrix.empty:
        raise ValueError("Training price data unavailable after applying coverage plan.")

    if coverage_plan.warmup.deficit_days > 0:
        issues.append(
            f"Warmup extended into holdout by {coverage_plan.warmup.deficit_days} day(s) "
            "to satisfy warmup requirement."
        )

    context = OptimizationContext(
        bars_by_symbol=bars_by_symbol,
        price_matrix=price_matrix,
        base_config=base_config,
        base_risk=base_risk,
        initial_capital=initial_capital,
        cost_model=cost_model,
    )

    base_genome = {
        "atr_window": float(base_config.atr_window),
        "breakout_lookback": float(base_config.breakout_lookback),
        "breakout_multiplier": float(base_config.breakout_multiplier),
        "risk_fraction": float(base_risk.risk_fraction),
    }
    int_fields = {"atr_window", "breakout_lookback"}

    population = generate_population(base_genome, bounds, population_size, seed, int_fields)
    mutate_fn = build_mutate_fn(bounds, int_fields)

    actual_run_id = run_id or uuid.uuid4().hex

    telemetry_events: List[dict] = []
    publisher = TelemetryPublisher(
        run_id=actual_run_id,
        logger=TrainingLogger(layout.run_log_path(actual_run_id)),
        session=session,
    )
    publisher.register(telemetry_events.append)

    telemetry_writer = TelemetryLogWriter(run_id=actual_run_id, layout=layout, session=session)
    evaluation_appender = EvaluationAppender(writer=telemetry_writer)

    def _record_candidate(event: Dict[str, object]) -> None:
        metadata = {
            "generation": event.get("generation"),
            "rank": event.get("rank"),
            "raw_score": event.get("raw_score"),
            "penalty": event.get("penalty"),
            "stats": event.get("stats"),
        }
        metadata = {key: value for key, value in metadata.items() if value is not None}
        envelope = evaluation_appender.append(
            candidate_id=str(event["candidate_id"]),
            score=float(event["score"]),
            metrics=event.get("metrics", {}),
            parameter_payload=event.get("parameters", {}),
            metadata=metadata,
        )
        if envelope is not None:
            telemetry_events.append(envelope)

    optimizer = EvolutionaryOptimizer(
        objective_weights=objective_weights,
        constraint_gate=constraint_gate,
        publisher=publisher,
        layout=layout,
        population_size=population_size,
        generations=generations,
        max_workers=max_workers,
        mutate_fn=mutate_fn,
        candidate_event_sink=_record_candidate,
    )

    parameter_set = optimizer.run(
        run_id=actual_run_id,
        model_id=model_id,
        portfolio_id=portfolio.portfolio_id,
        evaluator=partial(evaluate_genome, context=context),
        initial_population=population,
        seed=seed,
    )

    best_config, best_risk, equity_curve, metrics, stats = backtest_best(parameter_set.parameters, context)

    return OptimizationResult(
        parameter_set=parameter_set,
        telemetry=telemetry_events,
        metrics=metrics,
        stats=stats,
        equity_curve=equity_curve,
        issues=issues,
        synthetic=synthetic_used,
        run_id=actual_run_id,
        log_path=layout.run_log_path(actual_run_id),
        evaluation_log_path=telemetry_writer.log_path,
        parameter_path=layout.parameter_set_path(parameter_set.parameter_set_id),
        best_config=best_config,
        best_risk=best_risk,
        coverage_plan=coverage_plan,
    )
