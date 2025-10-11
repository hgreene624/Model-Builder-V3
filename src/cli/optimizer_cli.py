from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

import typer

from src.config.settings import AppSettings
from src.engine.atr_breakout import ATRBreakoutConfig, RiskSettings
from src.engine.backtest import CostModel
from src.optimizer.evolutionary import ConstraintGate, ObjectiveWeights
from src.optimizer.workflow import run_optimization
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout

optimizer_app = typer.Typer(help="Optimization workflows.")


@optimizer_app.command("run")
def optimize(
    portfolio_id: str = typer.Argument(..., help="Identifier of the portfolio to optimize."),
    model_id: str = typer.Option("models.atr_breakout", help="Model identifier to optimize."),
    sample_size: int = typer.Option(5, min=1, help="Number of symbols sampled from the portfolio."),
    atr_window: int = typer.Option(14, min=5, max=100, help="Base ATR window."),
    breakout_lookback: int = typer.Option(20, min=5, max=100, help="Base breakout lookback."),
    breakout_multiplier: float = typer.Option(2.0, min=0.5, max=5.0, help="Base breakout multiplier."),
    risk_fraction: float = typer.Option(0.02, min=0.001, max=0.2, help="Base risk fraction."),
    position_weight_range: Tuple[float, float] = typer.Option(
        (0.05, 0.25),
        help="Minimum and maximum position weights applied after risk sizing.",
        show_default=True,
    ),
    atr_window_range: Tuple[int, int] = typer.Option(
        (10, 30),
        help="Bounds for ATR window during optimisation.",
        show_default=True,
    ),
    breakout_lookback_range: Tuple[int, int] = typer.Option(
        (15, 45),
        help="Bounds for breakout lookback during optimisation.",
        show_default=True,
    ),
    breakout_multiplier_range: Tuple[float, float] = typer.Option(
        (1.5, 3.5),
        help="Bounds for breakout multiplier during optimisation.",
        show_default=True,
    ),
    risk_fraction_range: Tuple[float, float] = typer.Option(
        (0.01, 0.04),
        help="Bounds for risk fraction during optimisation.",
        show_default=True,
    ),
    population_size: int = typer.Option(9, min=3, help="Number of genomes per generation."),
    generations: int = typer.Option(3, min=1, help="Number of evolutionary generations."),
    max_workers: int = typer.Option(1, min=1, help="Process pool size for evaluation."),
    seed: Optional[int] = typer.Option(42, help="Deterministic random seed."),
    initial_capital: float = typer.Option(100_000.0, min=1_000.0, help="Initial capital for backtests."),
    objective_weights: Tuple[float, float, float] = typer.Option(
        (0.5, 0.3, 0.2),
        help="Weights for CAGR, Calmar, and Sharpe components respectively.",
        show_default=True,
    ),
    max_trade_rate: float = typer.Option(50.0, help="Constraint: maximum annualised trades."),
    min_hold_days: float = typer.Option(2.0, help="Constraint: minimum average hold days."),
    output: Optional[Path] = typer.Option(None, help="Optional JSON file path for summary output."),
    use_synthetic: bool = typer.Option(
        False,
        "--synthetic/--no-synthetic",
        help="Force synthetic price data instead of loading from providers.",
    ),
) -> None:
    """Run the ATR optimisation workflow via CLI."""
    cagr_weight, calmar_weight, sharpe_weight = objective_weights
    if cagr_weight + calmar_weight + sharpe_weight <= 0:
        raise typer.BadParameter("Objective weights must sum to a positive value.")

    settings = AppSettings.from_env()
    layout = StorageLayout(settings.data_dir)
    store = ArtifactStore(layout)

    portfolio = store.load_portfolio(portfolio_id)
    if portfolio is None:
        typer.echo(f"Portfolio '{portfolio_id}' was not found in storage.", err=True)
        raise typer.Exit(code=1)

    if not portfolio.tickers:
        typer.echo("Selected portfolio has no tickers to optimize.", err=True)
        raise typer.Exit(code=1)

    selected_symbols = portfolio.tickers[:sample_size]
    base_config = ATRBreakoutConfig(
        atr_window=int(atr_window),
        breakout_lookback=int(breakout_lookback),
        breakout_multiplier=float(breakout_multiplier),
    )
    min_weight, max_weight = position_weight_range
    base_risk = RiskSettings(
        enabled=True,
        risk_fraction=float(risk_fraction),
        min_weight=float(min_weight),
        max_weight=float(max_weight),
    )
    bounds = {
        "atr_window": (float(min(atr_window_range)), float(max(atr_window_range))),
        "breakout_lookback": (float(min(breakout_lookback_range)), float(max(breakout_lookback_range))),
        "breakout_multiplier": (
            float(min(breakout_multiplier_range)),
            float(max(breakout_multiplier_range)),
        ),
        "risk_fraction": (
            float(min(risk_fraction_range)),
            float(max(risk_fraction_range)),
        ),
    }

    objective = ObjectiveWeights(
        cagr=float(cagr_weight),
        calmar=float(calmar_weight),
        sharpe=float(sharpe_weight),
    )
    constraints = ConstraintGate(
        max_trade_rate=float(max_trade_rate),
        min_hold_days=float(min_hold_days),
        penalty=-1_000.0,
    )

    try:
        result = run_optimization(
            settings=settings,
            portfolio=portfolio,
            selected_symbols=selected_symbols,
            base_config=base_config,
            base_risk=base_risk,
            bounds=bounds,
            objective_weights=objective,
            constraint_gate=constraints,
            population_size=int(population_size),
            generations=int(generations),
            max_workers=int(max_workers),
            seed=seed,
            initial_capital=float(initial_capital),
            cost_model=CostModel(),
            model_id=model_id,
            session="cli",
            use_synthetic=use_synthetic,
        )
    except ValueError as exc:
        typer.echo(f"Optimization failed: {exc}", err=True)
        raise typer.Exit(code=1)

    # Update portfolio provenance notes
    portfolio_record = store.load_portfolio(portfolio_id)
    if portfolio_record is not None:
        note = (
            f"{datetime.now(tz=timezone.utc).isoformat()} · run {result.run_id} "
            f"saved parameter set {result.parameter_set.parameter_set_id}"
        )
        notes = list(portfolio_record.notes or [])
        notes.append(note)
        portfolio_record.notes = notes  # type: ignore[assignment]
        portfolio_record.touch()
        store.save_portfolio(portfolio_record)

    summary = {
        "run_id": result.run_id,
        "portfolio_id": portfolio_id,
        "model_id": model_id,
        "parameter_set_id": result.parameter_set.parameter_set_id,
        "best_parameters": result.parameter_set.parameters,
        "metrics": dict(result.parameter_set.fitness),
        "constraints": dict(result.parameter_set.constraints),
        "log_path": str(result.log_path),
        "parameter_path": str(result.parameter_path),
        "synthetic_data": result.synthetic,
        "issues": result.issues,
    }

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2))

    typer.echo(json.dumps(summary, indent=2))
