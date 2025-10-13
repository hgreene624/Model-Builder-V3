from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Callable

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model_builder.optimization.coverage import CoveragePlan
from model_builder.profiles import ProfilesService, StrategyProfileRepository
from model_builder.ui.components import (
    build_best_candidate_view,
    load_best_candidate,
    render_best_candidate,
    store_best_candidate,
)
from model_builder.ui.components.profile_editor import ProfileEditorResult, render_profile_editor
from src.config.settings import AppSettings
from src.engine.atr_breakout import ATRBreakoutConfig, RiskSettings
from src.engine.backtest import CostModel
from src.models.contracts import Portfolio
from src.optimizer.evolutionary import ConstraintGate, ObjectiveWeights
from src.optimizer.workflow import OptimizationResult, run_optimization
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout

SESSION_RESULTS_KEY = "model_builder_last_result"


@dataclass(frozen=True)
class EquitySplit:
    training: pd.DataFrame
    holdout: pd.DataFrame
    training_column: str
    holdout_column: str
    expected_holdout_points: int
    observed_holdout_points: int
    train_end_ts: pd.Timestamp
    holdout_start_ts: pd.Timestamp


def _create_timezone_aligner(timestamp_series: pd.Series) -> Callable[[object], pd.Timestamp]:
    tz = timestamp_series.dt.tz

    def _align(value: object) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        if tz is not None:
            if ts.tz is None:
                ts = ts.tz_localize(tz)
            else:
                ts = ts.tz_convert(tz)
        elif ts.tz is not None:
            ts = ts.tz_convert(None)
        return ts

    return _align


def _resolve_equity_column_names(frame: pd.DataFrame, *, x_field: str) -> tuple[str, str]:
    candidate_columns = [col for col in frame.columns if col != x_field]
    if not candidate_columns:
        raise ValueError("Equity curve frame requires at least one value column.")

    def _pick(preferences: list[str]) -> str | None:
        for column in preferences:
            if column in frame.columns:
                return column
        return None

    training_column = _pick(["train_equity", "training_equity", "equity"])
    holdout_column = _pick(["holdout_equity", "equity"])

    if training_column is None:
        training_column = candidate_columns[0]
    if holdout_column is None:
        holdout_column = training_column

    return training_column, holdout_column


def _split_equity_curve(
    frame: pd.DataFrame,
    coverage: CoveragePlan,
    *,
    x_field: str,
    training_column: str,
    holdout_column: str,
    align: Callable[[object], pd.Timestamp],
) -> EquitySplit:
    timestamp_series = frame[x_field]
    train_end_ts = align(coverage.train.end)
    holdout_start_ts = align(coverage.holdout.start)

    normalized_series = timestamp_series.dt.normalize()
    training_mask = normalized_series <= train_end_ts
    holdout_mask = normalized_series >= holdout_start_ts
    if not holdout_mask.any():
        holdout_mask = timestamp_series >= holdout_start_ts

    training_frame = frame.loc[training_mask].copy()
    if training_column in training_frame.columns:
        training_frame = training_frame.dropna(subset=[training_column])

    holdout_frame = frame.loc[holdout_mask].copy()
    if holdout_column in holdout_frame.columns:
        holdout_frame = holdout_frame.dropna(subset=[holdout_column])

    expected_holdout_points = int((timestamp_series >= holdout_start_ts).sum())
    observed_holdout_points = len(holdout_frame)

    return EquitySplit(
        training=training_frame,
        holdout=holdout_frame,
        training_column=training_column,
        holdout_column=holdout_column,
        expected_holdout_points=expected_holdout_points,
        observed_holdout_points=observed_holdout_points,
        train_end_ts=train_end_ts,
        holdout_start_ts=holdout_start_ts,
    )


def _load_portfolios(store: ArtifactStore, limit: int = 50) -> list[Portfolio]:
    try:
        return store.list_portfolios(limit=limit)
    except FileNotFoundError:
        return []


def _select_symbols(portfolio: Portfolio, count: int) -> list[str]:
    tickers = list(portfolio.tickers or [])
    if not tickers:
        return []
    count = max(1, min(len(tickers), count))
    return tickers[:count]


def _coverage_table(result: OptimizationResult) -> pd.DataFrame:
    plan = result.coverage_plan
    warmup_slice = plan.warmup.slice
    rows = [
        {
            "Slice": "Coverage",
            "Start": plan.window.coverage_start.isoformat(),
            "End": plan.window.coverage_end.isoformat(),
            "Notes": "",
        },
        {
            "Slice": "Training",
            "Start": plan.train.start.isoformat(),
            "End": plan.train.end.isoformat(),
            "Notes": "",
        },
        {
            "Slice": "Holdout",
            "Start": plan.holdout.start.isoformat(),
            "End": plan.holdout.end.isoformat(),
            "Notes": "",
        },
        {
            "Slice": "Warmup",
            "Start": warmup_slice.start.isoformat(),
            "End": warmup_slice.end.isoformat(),
            "Notes": f"Deficit {plan.warmup.deficit_days} day(s)" if plan.warmup.deficit_days else "",
        },
    ]
    return pd.DataFrame(rows)


def _summarize_result(result: OptimizationResult) -> dict[str, Any]:
    summary = {
        "run_id": result.run_id,
        "parameter_set_id": result.parameter_set.parameter_set_id,
        "portfolio_id": result.parameter_set.portfolio_id,
        "log_path": str(result.log_path),
        "parameter_path": str(result.parameter_path),
        "metrics": result.metrics,
        "stats": result.stats,
        "best_parameters": result.parameter_set.parameters,
        "issues": result.issues,
        "coverage": {
            "train_start": result.coverage_plan.train.start.isoformat(),
            "train_end": result.coverage_plan.train.end.isoformat(),
            "holdout_start": result.coverage_plan.holdout.start.isoformat(),
            "holdout_end": result.coverage_plan.holdout.end.isoformat(),
            "warmup_start": result.coverage_plan.warmup.slice.start.isoformat(),
            "warmup_end": result.coverage_plan.warmup.slice.end.isoformat(),
        },
    }
    return summary


def _render_equity_curve(result: OptimizationResult) -> None:
    st.subheader("Holdout Equity Curve (Train + Holdout)")
    equity = result.equity_curve
    if equity.empty:
        st.caption("No equity curve returned for the optimisation run.")
        return

    frame = equity.copy()
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        x_field = "timestamp"
    else:
        frame = frame.reset_index().rename(columns={"index": "timestamp"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        x_field = "timestamp"

    candidate_columns = [col for col in frame.columns if col != x_field]
    if not candidate_columns:
        st.line_chart(frame.set_index(x_field))
        return

    try:
        training_y_field, holdout_y_field = _resolve_equity_column_names(frame, x_field=x_field)
    except ValueError:
        st.line_chart(frame.set_index(x_field))
        return

    frame = frame.sort_values(x_field).reset_index(drop=True)
    timestamp_series = frame[x_field]
    align = _create_timezone_aligner(timestamp_series)

    coverage = result.coverage_plan
    split = _split_equity_curve(
        frame,
        coverage,
        x_field=x_field,
        training_column=training_y_field,
        holdout_column=holdout_y_field,
        align=align,
    )

    warmup_ts = align(coverage.warmup.slice.start)
    train_start_ts = align(coverage.train.start)
    holdout_start_ts = split.holdout_start_ts

    training_frame = split.training
    holdout_frame = split.holdout
    holdout_warning: str | None = None
    if split.expected_holdout_points > 0 and split.observed_holdout_points == 0:
        holdout_warning = (
            "Holdout equity curve returned only missing values; nothing to plot in orange."
        )

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=training_frame[x_field],
            y=training_frame[split.training_column],
            mode="lines",
            name="Training",
            line=dict(color="#1f77b4"),
            hovertemplate="%{x|%Y-%m-%d}<br>Equity=%{y:.2f}<extra></extra>",
        )
    )
    if not holdout_frame.empty:
        fig.add_trace(
            go.Scatter(
                x=holdout_frame[x_field],
                y=holdout_frame[split.holdout_column],
                mode="lines",
                name="Holdout",
                line=dict(color="#ff7f0e"),
                hovertemplate="%{x|%Y-%m-%d}<br>Equity=%{y:.2f}<extra></extra>",
            )
        )
    elif split.expected_holdout_points > 0:
        holdout_warning = "Holdout equity curve returned only missing values; nothing to plot in orange."

    fig.update_xaxes(
        tickformat="%b %Y",
        dtick="M2",
        ticklabelmode="period",
        showline=True,
        linewidth=1,
        linecolor="rgba(0,0,0,0.4)",
        mirror=True,
    )
    years = sorted(frame[x_field].dt.year.unique())
    for year in years[1:]:
        boundary = align(pd.Timestamp(year=year, month=1, day=1)).to_pydatetime()
        fig.add_vline(
            x=boundary,
            line_dash="dash",
            line_color="rgba(0,0,0,0.25)",
            line_width=1,
        )
    fig.add_vrect(
        x0=warmup_ts,
        x1=train_start_ts,
        fillcolor="rgba(31, 119, 180, 0.05)",
        line_width=0,
    )
    fig.add_vline(
        x=holdout_start_ts,
        line_dash="dot",
        line_color="#ff7f0e",
        line_width=2,
    )

    warmup_midpoint = warmup_ts + (train_start_ts - warmup_ts) / 2
    fig.add_annotation(
        x=warmup_midpoint.to_pydatetime(),
        y=1.02,
        xref="x",
        yref="paper",
        text="Warmup",
        showarrow=False,
        align="left",
        xanchor="left",
        font=dict(color="rgba(31, 119, 180, 0.7)"),
    )
    fig.add_annotation(
        x=holdout_start_ts.to_pydatetime(),
        y=1.02,
        xref="x",
        yref="paper",
        text="Holdout Start",
        showarrow=False,
        align="left",
        xanchor="left",
        font=dict(color="#ff7f0e"),
    )

    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        f"Equity points · total {len(frame)} | training {len(training_frame)} | "
        f"holdout {split.observed_holdout_points}/{split.expected_holdout_points}"
    )
    if holdout_warning:
        st.caption(holdout_warning)


def _display_result(result: OptimizationResult) -> None:
    st.success(f"Run {result.run_id} completed. Parameter set `{result.parameter_set.parameter_set_id}` saved.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.caption("Best Parameters")
        st.json(result.parameter_set.parameters)
        st.caption("Best Config")
        st.json(
            {
                "atr_window": result.best_config.atr_window,
                "breakout_lookback": result.best_config.breakout_lookback,
                "breakout_multiplier": round(result.best_config.breakout_multiplier, 3),
                "risk_fraction": round(result.best_risk.risk_fraction, 4),
                "min_weight": result.best_risk.min_weight,
                "max_weight": result.best_risk.max_weight,
            }
        )

    with col_b:
        st.caption("Performance Metrics")
        metrics_frame = pd.DataFrame([result.metrics, result.stats]).T
        metrics_frame.columns = ["Score", "Stat"]
        st.dataframe(metrics_frame, use_container_width=True)
        st.caption("Artifacts")
        st.write(
            {
                "log_path": str(result.log_path),
                "parameter_path": str(result.parameter_path),
            }
        )

    st.caption("Coverage Plan")
    st.dataframe(_coverage_table(result), use_container_width=True)

    if result.issues:
        st.warning("\n".join(result.issues))

    _render_equity_curve(result)

    best_candidate = build_best_candidate_view(result)
    if best_candidate is not None:
        store_best_candidate(st.session_state, best_candidate)
        render_best_candidate(best_candidate)


def _build_objective(parameters: Dict[str, Any]) -> ObjectiveWeights:
    objective = parameters.get("objective_weights", {})
    return ObjectiveWeights(
        cagr=float(objective.get("cagr", 0.5)),
        calmar=float(objective.get("calmar", 0.3)),
        sharpe=float(objective.get("sharpe", 0.2)),
    )


def _build_bounds(parameters: Dict[str, Any]) -> Dict[str, tuple[float, float]]:
    bounds = parameters.get("bounds", {})
    return {
        "atr_window": (
            float(bounds.get("atr_window", [parameters.get("atr_window", 14) - 4, parameters.get("atr_window", 14) + 4])[0]),
            float(bounds.get("atr_window", [parameters.get("atr_window", 14) - 4, parameters.get("atr_window", 14) + 4])[1]),
        ),
        "breakout_lookback": (
            float(bounds.get("breakout_lookback", [parameters.get("breakout_lookback", 20) - 5, parameters.get("breakout_lookback", 20) + 5])[0]),
            float(bounds.get("breakout_lookback", [parameters.get("breakout_lookback", 20) - 5, parameters.get("breakout_lookback", 20) + 5])[1]),
        ),
        "breakout_multiplier": (
            float(bounds.get("breakout_multiplier", [parameters.get("breakout_multiplier", 2.0) - 0.5, parameters.get("breakout_multiplier", 2.0) + 0.5])[0]),
            float(bounds.get("breakout_multiplier", [parameters.get("breakout_multiplier", 2.0) - 0.5, parameters.get("breakout_multiplier", 2.0) + 0.5])[1]),
        ),
        "risk_fraction": (
            float(bounds.get("risk_fraction", [parameters.get("risk_fraction", 0.02) / 2, parameters.get("risk_fraction", 0.02) * 1.5])[0]),
            float(bounds.get("risk_fraction", [parameters.get("risk_fraction", 0.02) / 2, parameters.get("risk_fraction", 0.02) * 1.5])[1]),
        ),
    }


def _ensure_objective_positive(weights: ObjectiveWeights) -> None:
    total = weights.cagr + weights.calmar + weights.sharpe
    if total <= 0:
        raise ValueError("Objective weights must sum to a positive value.")


def _resolve_profile_portfolio(store: ArtifactStore, profile: dict[str, Any]) -> Portfolio | None:
    portfolio_id = profile.get("portfolio_id")
    if not portfolio_id:
        return None
    return store.load_portfolio(portfolio_id)


def run_page() -> None:
    st.set_page_config(page_title="Model Builder", layout="wide")
    st.title("Model Builder")

    settings = AppSettings.from_env()
    layout = StorageLayout(settings.data_dir)
    store = ArtifactStore(layout)
    portfolios = _load_portfolios(store)

    repository = StrategyProfileRepository(layout=layout)
    service = ProfilesService(repository=repository)

    editor_result = render_profile_editor(service=service, portfolios=portfolios)
    profile = editor_result.profile

    if editor_result.message:
        if editor_result.saved:
            st.info(editor_result.message)
        elif editor_result.deleted:
            st.info(editor_result.message)
        else:
            st.caption(editor_result.message)

    if not profile:
        st.stop()

    portfolio = _resolve_profile_portfolio(store, profile)
    if portfolio is None:
        st.error("Associated portfolio could not be found. Update the profile to reference a valid portfolio.")
        st.stop()

    parameters = dict(profile.get("parameters") or {})
    selected_symbols = _select_symbols(portfolio, int(parameters.get("symbol_count", 5)))
    if not selected_symbols:
        st.error("Selected portfolio has no tickers. Adjust the portfolio before running the optimizer.")
        st.stop()

    st.divider()
    st.subheader("Optimization")
    st.write(
        f"Portfolio **{portfolio.name}** (`{portfolio.portfolio_id}`) · Train percentage "
        f"{profile['train_percentage']:.0%} · Warmup {profile['atr_warmup_days']} day(s)"
    )

    run_clicked = st.button("Run Optimization", type="primary")
    if run_clicked:
        try:
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
            bounds = _build_bounds(parameters)
            objective_weights = _build_objective(parameters)
            _ensure_objective_positive(objective_weights)
            constraint_gate = ConstraintGate(
                max_trade_rate=float(parameters.get("max_trade_rate", 50.0)),
                min_hold_days=float(parameters.get("min_hold_days", 2.0)),
                penalty=-1_000.0,
            )
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
                session="ui",
                use_synthetic=bool(parameters.get("use_synthetic", False)),
                train_percentage=float(profile["train_percentage"]),
                warmup_days=int(profile["atr_warmup_days"]),
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            summary = _summarize_result(result)
            st.session_state[SESSION_RESULTS_KEY] = summary
            _display_result(result)
    elif SESSION_RESULTS_KEY in st.session_state:
        st.subheader("Most Recent Run")
        st.json(st.session_state[SESSION_RESULTS_KEY])
        stored_view = load_best_candidate(st.session_state)
        if stored_view is not None:
            render_best_candidate(stored_view)


__all__ = ["run_page"]
