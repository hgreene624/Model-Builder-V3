from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from model_builder.optimization import EVENT_TYPE_CANDIDATE_EVALUATION  # noqa: E402
from model_builder.ui.components.live_evaluations import get_live_evaluations_state  # noqa: E402
from src.config.settings import AppSettings  # noqa: E402
from src.engine.atr_breakout import ATRBreakoutConfig, RiskSettings  # noqa: E402
from src.engine.backtest import CostModel  # noqa: E402
from src.models.contracts import Portfolio  # noqa: E402
from src.optimizer.evolutionary import ConstraintGate, ObjectiveWeights  # noqa: E402
from src.optimizer.workflow import OptimizationResult, resolve_coverage_window, run_optimization  # noqa: E402
from src.storage.artifacts import ArtifactStore  # noqa: E402
from src.storage.layout import StorageLayout  # noqa: E402

MAX_SYMBOLS = 10
SESSION_RESULTS_KEY = "model_builder_last_result"


def _portfolio_options(store: ArtifactStore, limit: int = 20) -> List[Portfolio]:
    try:
        return store.list_portfolios(limit=limit)
    except FileNotFoundError:
        return []


def _render_portfolio_summary(portfolio: Portfolio, selected_symbols: Sequence[str], used_synthetic: bool) -> None:
    st.subheader("Run Context")
    st.markdown(
        f"- **Portfolio**: `{portfolio.name}` (`{portfolio.portfolio_id}`)\n"
        f"- **Symbols sampled**: {len(selected_symbols)} / {len(portfolio.tickers)}\n"
        f"- **Synthetic data**: {'Yes' if used_synthetic else 'No'}"
    )


def _render_equity_curve(equity: pd.DataFrame) -> None:
    st.subheader("Equity Curve")
    if equity.empty:
        st.caption("Backtest produced no equity curve for the best genome.")
        return

    frame = equity.copy()
    if "timestamp" in frame.columns:
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        x_field = "timestamp"
    else:
        frame = frame.reset_index().rename(columns={"index": "timestamp"})
        frame["timestamp"] = pd.to_datetime(frame["timestamp"])
        x_field = "timestamp"

    if "equity" not in frame.columns:
        st.line_chart(frame.set_index(x_field))
        return

    fig = px.line(frame, x=x_field, y="equity")
    fig.update_traces(mode="lines", hovertemplate="%{x|%Y-%m-%d}<br>Equity=%{y:.2f}<extra></extra>")
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
        boundary = pd.Timestamp(year=year, month=1, day=1)
        fig.add_vline(
            x=boundary,
            line_dash="dash",
            line_color="rgba(0,0,0,0.25)",
            line_width=1,
        )
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, use_container_width=True)


def _render_live_evaluations(run_id: str, events: List[dict]) -> None:
    st.subheader("Live Holdout Evaluations")
    if not run_id:
        st.caption("Run identifier missing; unable to render candidate stream.")
        return

    state = get_live_evaluations_state(st.session_state)
    ingested = 0

    for envelope in events:
        if not isinstance(envelope, dict):
            continue
        if envelope.get("event_type") != EVENT_TYPE_CANDIDATE_EVALUATION:
            continue
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            continue
        try:
            state.ingest(run_id, payload)
        except (TypeError, ValueError):
            continue
        ingested += 1

    rows = state.rows
    if not rows:
        st.caption("No candidate evaluations captured yet.")
        return

    df = pd.DataFrame(list(rows))
    df_display = df[["candidate_id", "score", "score_delta", "timestamp"]].copy()
    df_display["score"] = df_display["score"].map(lambda value: round(value, 6))
    df_display["score_delta"] = df_display["score_delta"].map(lambda value: round(value, 6))
    st.dataframe(df_display, use_container_width=True)

    best_row = max(rows, key=lambda row: row["score"])
    st.caption(
        f"Best candidate: `{best_row['candidate_id']}` · "
        f"score {best_row['score']:.4f} (Δ {best_row['score_delta']:.4f})"
    )

    if ingested:
        st.caption(f"{ingested} new candidate event{'s' if ingested != 1 else ''} processed.")


def _format_bounds(
    atr_bounds: Tuple[int, int],
    lookback_bounds: Tuple[int, int],
    multiplier_bounds: Tuple[float, float],
    risk_fraction_bounds: Tuple[float, float],
) -> Dict[str, Tuple[float, float]]:
    return {
        "atr_window": (float(atr_bounds[0]), float(atr_bounds[1])),
        "breakout_lookback": (float(lookback_bounds[0]), float(lookback_bounds[1])),
        "breakout_multiplier": (float(multiplier_bounds[0]), float(multiplier_bounds[1])),
        "risk_fraction": (float(risk_fraction_bounds[0]), float(risk_fraction_bounds[1])),
    }


def _summarize_result(result: OptimizationResult) -> Dict[str, object]:
    fitness = dict(result.parameter_set.fitness)
    summary = {
        "run_id": result.run_id,
        "parameter_set_id": result.parameter_set.parameter_set_id,
        "portfolio_id": result.parameter_set.portfolio_id,
        "model_id": result.parameter_set.model_id,
        "best_parameters": result.parameter_set.parameters,
        "metrics": fitness,
        "constraints": result.parameter_set.constraints,
        "log_path": str(result.log_path),
        "evaluation_log_path": str(result.evaluation_log_path),
        "parameter_path": str(result.parameter_path),
        "synthetic_data": result.synthetic,
        "issues": result.issues,
    }
    return summary


def run_page() -> None:
    st.set_page_config(page_title="Model Builder", layout="wide")
    st.title("Model Builder")

    settings = AppSettings.from_env()
    store = ArtifactStore(StorageLayout(settings.data_dir))
    portfolios = _portfolio_options(store)

    if not portfolios:
        st.warning("Save a portfolio in the Portfolio Curator page before running the optimizer.")
        return

    portfolio_names = {f"{portfolio.name} ({len(portfolio.tickers)} symbols)": portfolio for portfolio in portfolios}
    selected_label = st.selectbox("Choose a portfolio", list(portfolio_names.keys()))
    if not selected_label:
        return
    portfolio = portfolio_names[selected_label]

    coverage_start, coverage_end = resolve_coverage_window(portfolio)
    max_symbols = min(MAX_SYMBOLS, len(portfolio.tickers))
    symbol_count = st.slider(
        "Symbols sampled per run",
        min_value=1,
        max_value=max_symbols,
        value=max(1, min(5, max_symbols)),
        help="Controls how many tickers from the selected portfolio are included in each run. Example: sampling 5 symbols keeps runs fast while still exercising diversification.",
    )
    selected_symbols = portfolio.tickers[:symbol_count]

    with st.expander("ATR & Risk Parameters", expanded=True):
        col1, col2, col3 = st.columns(3)
        atr_window = col1.number_input(
            "ATR Window",
            min_value=5,
            max_value=100,
            value=14,
            help="Number of sessions used when smoothing true range. Example: 14 mirrors the Wilder default and provides a balanced volatility estimate.",
        )
        breakout_lookback = col2.number_input(
            "Breakout Lookback",
            min_value=5,
            max_value=100,
            value=20,
            help="Lookback window for the prior high that defines the breakout threshold. Example: 20 sessions captures monthly highs.",
        )
        breakout_multiplier = col3.number_input(
            "Breakout Multiplier",
            min_value=0.5,
            max_value=5.0,
            value=2.0,
            step=0.1,
            help="Scales ATR when computing the breakout band. Example: increasing from 2.0 to 3.0 waits for more decisive moves.",
        )

        risk_cols = st.columns([1, 2])
        risk_enabled = risk_cols[0].checkbox(
            "Enable Risk-Aware Sizing",
            value=True,
            help="Toggle dynamic sizing. When enabled, position weights scale with ATR distance to the stop price.",
        )
        risk_fraction = risk_cols[1].number_input(
            "Risk Fraction (portfolio percent)",
            min_value=0.001,
            max_value=0.2,
            value=0.02,
            step=0.001,
            format="%.3f",
            help="Capital fraction risked per position. Example: 0.02 limits per-trade loss to ~2% of portfolio value.",
        )
        weight_cols = st.columns([2, 1])
        weight_range = weight_cols[0].slider(
            "Position Weight Range",
            min_value=0.0,
            max_value=1.0,
            value=(0.05, 0.25),
            step=0.01,
            help="Drag the handles to set minimum and maximum position weights after risk sizing. Example: (0.05, 0.25) keeps allocations between 5% and 25%.",
        )
        min_weight, max_weight = weight_range

    with st.expander("Optimizer Settings", expanded=True):
        col1, col2, col3 = st.columns(3)
        population_size = col1.number_input(
            "Population Size",
            min_value=3,
            max_value=30,
            value=9,
            step=1,
            help="Number of genomes evaluated per generation. Larger populations explore more combinations at the cost of compute.",
        )
        generations = col2.number_input(
            "Generations",
            min_value=1,
            max_value=20,
            value=3,
            step=1,
            help="How many evolution cycles to perform. Example: 5 generations offers more convergence while keeping runs interactive.",
        )
        max_workers = col3.number_input(
            "Max Workers",
            min_value=1,
            max_value=4,
            value=1,
            step=1,
            help="Process pool size for evaluations. Increase when running locally with multiple CPU cores.",
        )

        objective_cols = st.columns(3)
        objective_cagr = objective_cols[0].slider(
            "Objective Weight · CAGR",
            min_value=0.0,
            max_value=1.0,
            value=0.5,
            step=0.05,
            help="Emphasise annualised growth rate. Example: 0.5 gives CAGR half of the combined scoring weight.",
        )
        objective_calmar = objective_cols[1].slider(
            "Objective Weight · Calmar",
            min_value=0.0,
            max_value=1.0,
            value=0.3,
            step=0.05,
            help="Balance performance with drawdown control. Example: raising to 0.4 favours smoother equity curves.",
        )
        objective_sharpe = objective_cols[2].slider(
            "Objective Weight · Sharpe",
            min_value=0.0,
            max_value=1.0,
            value=0.2,
            step=0.05,
            help="Reward risk-adjusted returns. Example: increasing to 0.3 prioritises consistency over raw CAGR.",
        )
        weight_total = objective_cagr + objective_calmar + objective_sharpe
        if not math.isclose(weight_total, 1.0, rel_tol=1e-3):
            st.warning("Objective weights sum should be close to 1.0 for balanced scoring.")

        col4, col5 = st.columns(2)
        max_trade_rate = col4.number_input(
            "Constraint · Max Trades / Year",
            min_value=1.0,
            max_value=200.0,
            value=50.0,
            step=1.0,
            help="Hard cap on annualised trade count. Example: set to 30 to keep the strategy closer to swing-trading cadence.",
        )
        min_hold_days = col5.number_input(
            "Constraint · Min Hold Days",
            min_value=0.5,
            max_value=30.0,
            value=2.0,
            step=0.5,
            help="Minimum average holding period required for feasibility. Example: increase to 5 to discourage short-term churn.",
        )

        seed_capital_cols = st.columns(2)
        seed = seed_capital_cols[0].number_input(
            "Random Seed",
            min_value=0,
            max_value=10_000,
            value=42,
            step=1,
            help="Controls RNG for reproducible runs. Use different seeds to explore alternative optimisation paths.",
        )
        initial_capital = seed_capital_cols[1].number_input(
            "Initial Capital",
            min_value=10_000.0,
            max_value=1_000_000.0,
            value=100_000.0,
            step=10_000.0,
            help="Starting equity for backtests. Example: raising to 250k scales trades and commissions accordingly.",
        )

    with st.expander("Parameter Bounds", expanded=False):
        bounds_row_one = st.columns(2)
        atr_bounds = bounds_row_one[0].slider(
            "ATR Window Range",
            min_value=5,
            max_value=100,
            value=(max(5, atr_window - 10), min(100, atr_window + 10)),
            step=1,
            help="Lower and upper bounds for ATR window during optimisation. Example: (10, 30) lets the search explore slower or faster volatility estimates.",
        )
        lookback_bounds = bounds_row_one[1].slider(
            "Breakout Lookback Range",
            min_value=5,
            max_value=100,
            value=(max(5, breakout_lookback - 10), min(100, breakout_lookback + 10)),
            step=1,
            help="Range for the breakout lookback. Example: (15, 45) covers short to medium-term breakout horizons.",
        )

        bounds_row_two = st.columns(2)
        multiplier_bounds = bounds_row_two[0].slider(
            "Breakout Multiplier Range",
            min_value=0.5,
            max_value=5.0,
            value=(
                max(0.5, breakout_multiplier - 1.0),
                min(5.0, breakout_multiplier + 1.0),
            ),
            step=0.1,
            help="Range for the ATR multiplier applied to breakout bands. Example: (1.5, 3.5) balances sensitivity and noise rejection.",
        )
        risk_fraction_bounds = bounds_row_two[1].slider(
            "Risk Fraction Range",
            min_value=0.001,
            max_value=0.2,
            value=(
                max(0.001, risk_fraction * 0.5),
                min(0.2, risk_fraction * 1.5),
            ),
            step=0.001,
            format="%.3f",
            help="Bounds for risk-aware sizing during optimisation. Example: (0.010, 0.040) keeps risk per position between 1% and 4%.",
        )

    cost_model = CostModel()
    base_config = ATRBreakoutConfig(
        atr_window=int(atr_window),
        breakout_lookback=int(breakout_lookback),
        breakout_multiplier=float(breakout_multiplier),
    )
    base_risk = RiskSettings(
        enabled=risk_enabled,
        risk_fraction=float(risk_fraction),
        min_weight=float(min_weight),
        max_weight=float(max_weight),
    )
    bounds = _format_bounds(
        atr_bounds,
        lookback_bounds,
        multiplier_bounds,
        risk_fraction_bounds,
    )

    if st.button("Run Optimization", type="primary"):
        if weight_total <= 0:
            st.error("Objective weights must sum to a positive value before running the optimizer.")
            return
        objective = ObjectiveWeights(
            cagr=float(objective_cagr),
            calmar=float(objective_calmar),
            sharpe=float(objective_sharpe),
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
                seed=int(seed),
                initial_capital=float(initial_capital),
                cost_model=cost_model,
                model_id="models.atr_breakout",
                session="ui",
            )
        except ValueError as exc:
            st.error(str(exc))
            return

        _render_portfolio_summary(portfolio, selected_symbols, result.synthetic)
        if result.issues:
            with st.expander("Data Diagnostics", expanded=False):
                for issue in result.issues:
                    st.write(f"- {issue}")

        summary_col, metrics_col = st.columns([1, 1])
        parameter_set = result.parameter_set

        with summary_col:
            st.subheader("Best Parameters")
            st.write(
                {
                    "atr_window": result.best_config.atr_window,
                    "breakout_lookback": result.best_config.breakout_lookback,
                    "breakout_multiplier": round(result.best_config.breakout_multiplier, 3),
                    "risk_fraction": round(result.best_risk.risk_fraction, 4),
                }
            )
            st.write(f"Parameter Set ID: `{parameter_set.parameter_set_id}`")
            st.caption(f"Telemetry log saved at `{result.log_path}`")
            st.caption(f"Candidate replay log saved at `{result.evaluation_log_path}`")

        with metrics_col:
            st.subheader("Performance Snapshot")
            st.write({k: round(v, 4) for k, v in result.metrics.items()})
            st.write({k: round(v, 4) for k, v in result.stats.items()})

        _render_equity_curve(result.equity_curve)
        _render_live_evaluations(result.run_id, result.telemetry)

        st.success("Optimization complete. Best parameter set saved to storage.")
        st.session_state[SESSION_RESULTS_KEY] = _summarize_result(result)


if __name__ == "__main__":  # pragma: no cover
    run_page()
