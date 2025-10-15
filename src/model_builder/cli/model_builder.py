from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import click

from model_builder.profiles import ProfileNotFoundError, ProfilesService, StrategyProfileRepository
from model_builder.optimization import EVENT_TYPE_CANDIDATE_EVALUATION
from model_builder.optimization.telemetry import TelemetryLogWriter
from src.config.settings import AppSettings
from src.engine.atr_breakout import ATRBreakoutConfig, RiskSettings
from src.engine.backtest import CostModel
from src.optimizer.evolutionary import ConstraintGate, ObjectiveWeights
from src.optimizer.workflow import run_optimization
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


def _build_profiles_service() -> ProfilesService:
    settings = AppSettings.from_env()
    layout = StorageLayout(settings.data_dir)
    repository = StrategyProfileRepository(layout=layout)
    return ProfilesService(repository=repository)


def _build_context() -> tuple[AppSettings, StorageLayout, ProfilesService, ArtifactStore]:
    settings = AppSettings.from_env()
    layout = StorageLayout(settings.data_dir)
    repository = StrategyProfileRepository(layout=layout)
    service = ProfilesService(repository=repository)
    store = ArtifactStore(layout)
    return settings, layout, service, store


def _load_payload_from_file(path: Optional[Path]) -> dict[str, Any]:
    if path is None:
        return {}
    text = path.read_text(encoding="utf-8")
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise click.ClickException(f"Failed to parse JSON from '{path}': {exc}") from exc
    if not isinstance(loaded, Mapping):
        raise click.ClickException(f"Profile payload in '{path}' must be a JSON object.")
    return dict(loaded)


def _merge_payload(
    base: dict[str, Any],
    *,
    profile_id: Optional[str],
    name: Optional[str],
    description: Optional[str],
    portfolio_id: Optional[str],
    train_percentage: Optional[float],
    atr_warmup_days: Optional[int],
    parameters: Optional[str],
) -> dict[str, Any]:
    payload = dict(base)
    if profile_id is not None:
        payload["profile_id"] = profile_id
    if name is not None:
        payload["name"] = name
    if description is not None:
        payload["description"] = description
    if portfolio_id is not None:
        payload["portfolio_id"] = portfolio_id
    if train_percentage is not None:
        payload["train_percentage"] = train_percentage
    if atr_warmup_days is not None:
        payload["atr_warmup_days"] = atr_warmup_days
    if parameters is not None:
        try:
            parsed = json.loads(parameters)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"Parameters must be valid JSON: {exc}") from exc
        if not isinstance(parsed, Mapping):
            raise click.ClickException("Parameters payload must be a JSON object.")
        payload["parameters"] = dict(parsed)
    return payload


def _stream_candidate_events(
    log_path: Path,
    *,
    follow: bool,
    payload_only: bool,
    poll_interval: float = 0.5,
) -> None:
    """Stream candidate evaluation envelopes from a telemetry log."""

    if not log_path.exists():
        raise click.ClickException(f"Telemetry log was not found at '{log_path}'.")

    try:
        with log_path.open("r", encoding="utf-8") as handle:
            while True:
                line = handle.readline()
                if line:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        envelope = json.loads(line)
                    except json.JSONDecodeError as exc:
                        click.echo(f"Skipping malformed telemetry line: {exc}", err=True)
                        continue

                    if envelope.get("event_type") != EVENT_TYPE_CANDIDATE_EVALUATION:
                        continue

                    output_obj = envelope.get("payload") if payload_only else envelope
                    if output_obj is None:
                        continue

                    click.echo(json.dumps(output_obj, separators=(",", ":"), ensure_ascii=True))
                else:
                    if not follow:
                        break
                    time.sleep(poll_interval)
    except KeyboardInterrupt:
        raise SystemExit(0)


def _objective_weights(parameters: Mapping[str, Any]) -> ObjectiveWeights:
    weights = parameters.get("objective_weights", {})
    return ObjectiveWeights(
        cagr=float(weights.get("cagr", 0.5)),
        calmar=float(weights.get("calmar", 0.3)),
        sharpe=float(weights.get("sharpe", 0.2)),
    )


def _ensure_objective_positive(weights: ObjectiveWeights) -> None:
    total = weights.cagr + weights.calmar + weights.sharpe
    if total <= 0:
        raise click.ClickException("Objective weights must sum to a positive value.")


def _bounds(parameters: Mapping[str, Any]) -> dict[str, tuple[float, float]]:
    defaults = {
        "atr_window": (float(parameters.get("atr_window", 14) - 4), float(parameters.get("atr_window", 14) + 4)),
        "breakout_lookback": (
            float(parameters.get("breakout_lookback", 20) - 5),
            float(parameters.get("breakout_lookback", 20) + 5),
        ),
        "breakout_multiplier": (
            float(parameters.get("breakout_multiplier", 2.0) - 0.5),
            float(parameters.get("breakout_multiplier", 2.0) + 0.5),
        ),
        "risk_fraction": (
            float(parameters.get("risk_fraction", 0.02) / 2),
            float(parameters.get("risk_fraction", 0.02) * 1.5),
        ),
    }
    raw_bounds = parameters.get("bounds", {})
    resolved: dict[str, tuple[float, float]] = {}
    for key, fallback in defaults.items():
        values = raw_bounds.get(key, fallback)
        resolved[key] = (float(values[0]), float(values[1]))
    return resolved


def _symbol_count(parameters: Mapping[str, Any], tickers: Sequence[str]) -> int:
    count = int(parameters.get("symbol_count", 5))
    if not tickers:
        raise click.ClickException("Selected portfolio has no tickers to optimize.")
    return max(1, min(len(tickers), count))


def _summarize_result(result: Any, profile_id: str, portfolio_id: str) -> dict[str, Any]:
    coverage = result.coverage_plan
    return {
        "run_id": result.run_id,
        "profile_id": profile_id,
        "portfolio_id": portfolio_id,
        "parameter_set_id": result.parameter_set.parameter_set_id,
        "parameter_path": str(result.parameter_path),
        "log_path": str(result.log_path),
        "metrics": result.metrics,
        "stats": result.stats,
        "coverage": {
            "train_start": coverage.train.start.isoformat(),
            "train_end": coverage.train.end.isoformat(),
            "holdout_start": coverage.holdout.start.isoformat(),
            "holdout_end": coverage.holdout.end.isoformat(),
            "warmup_start": coverage.warmup.slice.start.isoformat(),
            "warmup_end": coverage.warmup.slice.end.isoformat(),
            "warmup_deficit_days": coverage.warmup.deficit_days,
        },
    }


@click.group()
def cli() -> None:
    """Model Builder utilities."""


@cli.group()
def profiles() -> None:
    """Manage strategy profiles."""


@cli.group()
def evaluations() -> None:
    """Inspect evaluation telemetry."""


@evaluations.command("live-tail")
@click.option("--run-id", required=True, help="Evaluation run identifier.")
@click.option(
    "--follow/--no-follow",
    default=True,
    show_default=True,
    help="Continue streaming new events until interrupted.",
)
@click.option(
    "--payload-only",
    is_flag=True,
    help="Emit only the candidate payload instead of the full telemetry envelope.",
)
def evaluations_live_tail(run_id: str, follow: bool, payload_only: bool) -> None:
    """Stream candidate evaluation telemetry for a run."""

    settings = AppSettings.from_env()
    layout = StorageLayout(settings.data_dir)
    log_path = layout.evaluations_directory() / f"{run_id}.jsonl"
    _stream_candidate_events(log_path, follow=follow, payload_only=payload_only)


@profiles.command("list")
@click.option("--output", type=click.Choice(["json", "table"]), default="json", show_default=True)
def profiles_list(output: str) -> None:
    """List available strategy profiles."""

    service = _build_profiles_service()
    profiles = service.list_profiles()
    if output == "json":
        click.echo(json.dumps(profiles, indent=2))
        return

    if not profiles:
        click.echo("No strategy profiles found.")
        return

    headers = ["Profile ID", "Name", "Portfolio", "Updated"]
    click.echo("\t".join(headers))
    for entry in profiles:
        click.echo(
            "\t".join(
                [
                    str(entry.get("profile_id", "")),
                    str(entry.get("name", "")),
                    str(entry.get("portfolio_id", "")),
                    str(entry.get("updated_at", "")),
                ]
            )
        )


@profiles.command("save")
@click.option("--file", "file_path", type=click.Path(path_type=Path, exists=True))
@click.option("--profile-id", help="Override profile identifier when updating.")
@click.option("--name", help="Profile display name.")
@click.option("--description", help="Optional description.")
@click.option("--portfolio-id", help="Associated portfolio identifier.")
@click.option("--train-percentage", type=float, help="Fraction of coverage assigned to training (0-1).")
@click.option("--atr-warmup-days", type=int, help="ATR warmup days.")
@click.option(
    "--parameters",
    help="JSON object describing strategy parameters (e.g. '{\"atr_window\": 14}').",
)
def profiles_save(
    file_path: Optional[Path],
    profile_id: Optional[str],
    name: Optional[str],
    description: Optional[str],
    portfolio_id: Optional[str],
    train_percentage: Optional[float],
    atr_warmup_days: Optional[int],
    parameters: Optional[str],
) -> None:
    """Create or update a strategy profile."""

    payload = _load_payload_from_file(file_path)
    payload = _merge_payload(
        payload,
        profile_id=profile_id,
        name=name,
        description=description,
        portfolio_id=portfolio_id,
        train_percentage=train_percentage,
        atr_warmup_days=atr_warmup_days,
        parameters=parameters,
    )

    service = _build_profiles_service()
    try:
        result = service.save_profile(payload)
    except KeyError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(json.dumps(result, indent=2))


@profiles.command("delete")
@click.argument("profile_id")
@click.option("--force", is_flag=True, help="Skip confirmation prompt.")
def profiles_delete(profile_id: str, force: bool) -> None:
    """Delete a strategy profile."""

    if not force:
        if not click.confirm(f"Delete strategy profile '{profile_id}'?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    service = _build_profiles_service()
    removed = service.delete_profile(profile_id)
    if not removed:
        raise click.ClickException(f"Strategy profile '{profile_id}' was not found.")

    click.echo(json.dumps({"profile_id": profile_id, "deleted": True}))


@cli.command("optimize")
@click.option("--profile-id", "profile_id", required=True, help="Strategy profile identifier.")
@click.option("--train-percent", "train_percent", type=float, help="Override training percentage (0-1).")
@click.option("--warmup-days", type=int, help="Override ATR warmup days.")
@click.option("--symbol-count", type=int, help="Override symbol sampling count.")
@click.option("--seed", type=int, help="Override RNG seed.")
@click.option(
    "--use-synthetic/--no-synthetic",
    "use_synthetic",
    default=None,
    help="Force optimisation to use synthetic OHLCV data.",
)
@click.option("--output", type=click.Path(path_type=Path), help="Optional file path for JSON summary output.")
def optimize(  # noqa: PLR0915
    profile_id: str,
    train_percent: Optional[float],
    warmup_days: Optional[int],
    symbol_count: Optional[int],
    seed: Optional[int],
    use_synthetic: Optional[bool],
    output: Optional[Path],
) -> None:
    """Run an optimisation using a saved strategy profile."""

    settings, layout, service, store = _build_context()
    try:
        profile = service.load_profile(profile_id)
    except ProfileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    if train_percent is not None:
        profile["train_percentage"] = train_percent
    if warmup_days is not None:
        profile["atr_warmup_days"] = warmup_days

    parameters = dict(profile.get("parameters") or {})
    if symbol_count is not None:
        parameters["symbol_count"] = symbol_count
    if seed is not None:
        parameters["seed"] = seed
    if use_synthetic is not None:
        parameters["use_synthetic"] = use_synthetic

    portfolio_id = profile.get("portfolio_id")
    if not portfolio_id:
        raise click.ClickException("Profile is missing an associated portfolio.")

    portfolio = store.load_portfolio(portfolio_id)
    if portfolio is None:
        raise click.ClickException(f"Portfolio '{portfolio_id}' was not found in storage.")

    tickers = list(portfolio.tickers or [])
    count = _symbol_count(parameters, tickers)
    selected_symbols = tickers[:count]

    base_config = ATRBreakoutConfig(
        atr_window=int(parameters.get("atr_window", 14)),
        breakout_lookback=int(parameters.get("breakout_lookback", 20)),
        breakout_multiplier=float(parameters.get("breakout_multiplier", 2.0)),
    )
    risk_settings = RiskSettings(
        enabled=True,
        risk_fraction=float(parameters.get("risk_fraction", 0.02)),
        min_weight=float(parameters.get("min_weight", 0.05)),
        max_weight=float(parameters.get("max_weight", 0.25)),
    )
    bounds = _bounds(parameters)
    objective_weights = _objective_weights(parameters)
    _ensure_objective_positive(objective_weights)
    constraint_gate = ConstraintGate(
        max_trade_rate=float(parameters.get("max_trade_rate", 50.0)),
        min_hold_days=float(parameters.get("min_hold_days", 2.0)),
        penalty=-1_000.0,
    )

    try:
        result = run_optimization(
            settings=settings,
            portfolio=portfolio,
            selected_symbols=selected_symbols,
            base_config=base_config,
            base_risk=risk_settings,
            bounds=bounds,
            objective_weights=objective_weights,
            constraint_gate=constraint_gate,
            population_size=int(parameters.get("population_size", 9)),
            generations=int(parameters.get("generations", 3)),
            max_workers=int(parameters.get("max_workers", 1)),
            seed=int(parameters.get("seed", 42)),
            initial_capital=float(parameters.get("initial_capital", 100_000.0)),
            cost_model=CostModel(),
            model_id=str(parameters.get("model_id", "models.atr_breakout")),
            session="cli",
            use_synthetic=bool(parameters.get("use_synthetic", False)),
            train_percentage=float(profile["train_percentage"]),
            warmup_days=int(profile["atr_warmup_days"]),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    writer = TelemetryLogWriter(run_id=result.run_id, layout=layout, session="cli")
    writer.emit(
        "run_completed",
        {
            "profile_id": profile_id,
            "portfolio_id": portfolio_id,
            "parameter_path": str(result.parameter_path),
            "log_path": str(result.log_path),
        },
    )

    summary = _summarize_result(result, profile_id, portfolio_id)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    click.echo(json.dumps(summary, indent=2))


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
