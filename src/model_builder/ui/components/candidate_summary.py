"""Best-candidate presenter combining callout, equity, momentum heatmap, and trade timeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, MutableMapping, Sequence

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from model_builder.analytics import build_momentum_heatmap, build_trade_timeline

BEST_CANDIDATE_STATE_KEY = "model_builder_best_candidate"

POSITIVE_COLOR = "#2ca02c"
NEGATIVE_COLOR = "#d62728"
NEUTRAL_COLOR = "#7f7f7f"
TRAINING_COLOR = "#1f77b4"
HOLDOUT_COLOR = "#ff7f0e"


@dataclass(frozen=True)
class BestCandidateView:
    run_id: str
    candidate_id: str | None
    score: float
    score_delta: float
    parameters: Dict[str, Any]
    metrics: Dict[str, float]
    stats: Dict[str, float]
    training_equity: List[Dict[str, float]]
    holdout_equity: List[Dict[str, float]]
    coverage: Dict[str, str]
    heatmap: Dict[str, Any]
    timeline: Dict[str, Any]
    all_trades: List[Any]  # Store all trades for dynamic timeline building

    def to_session(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "candidate_id": self.candidate_id,
            "score": self.score,
            "score_delta": self.score_delta,
            "parameters": self.parameters,
            "metrics": self.metrics,
            "stats": self.stats,
            "training_equity": self.training_equity,
            "holdout_equity": self.holdout_equity,
            "coverage": self.coverage,
            "heatmap": self.heatmap,
            "timeline": self.timeline,
            "all_trades": self.all_trades,
        }

    @classmethod
    def from_session(cls, payload: Mapping[str, Any]) -> "BestCandidateView":
        return cls(
            run_id=str(payload["run_id"]),
            candidate_id=payload.get("candidate_id"),
            score=float(payload.get("score", 0.0)),
            score_delta=float(payload.get("score_delta", 0.0)),
            parameters=dict(payload.get("parameters") or {}),
            metrics={str(k): float(v) for k, v in dict(payload.get("metrics") or {}).items()},
            stats={str(k): float(v) for k, v in dict(payload.get("stats") or {}).items()},
            training_equity=[
                {"timestamp": str(point["timestamp"]), "equity": float(point["equity"])}
                for point in payload.get("training_equity", [])
            ],
            holdout_equity=[
                {"timestamp": str(point["timestamp"]), "equity": float(point["equity"])}
                for point in payload.get("holdout_equity", [])
            ],
            coverage=dict(payload.get("coverage") or {}),
            heatmap=dict(payload.get("heatmap") or {}),
            timeline=dict(payload.get("timeline") or {}),
            all_trades=list(payload.get("all_trades") or []),
        )


def _align_timestamp(value: str, sample: pd.Series | None = None) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if sample is not None and not sample.empty:
        tz = sample.dt.tz  # type: ignore[attr-defined]
        if tz is not None:
            if ts.tz is None:
                ts = ts.tz_localize(tz)
            else:
                ts = ts.tz_convert(tz)
    return ts


def _normalize_equity_frame(equity_frame: pd.DataFrame) -> pd.DataFrame:
    frame = equity_frame.copy()
    if frame.empty:
        return frame
    if "timestamp" not in frame.columns:
        frame = frame.reset_index().rename(columns={"index": "timestamp"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    value_columns = [col for col in frame.columns if col != "timestamp"]
    if not value_columns:
        raise ValueError("Equity curve payload must include at least one value column.")
    value_column = value_columns[0]
    frame = frame[["timestamp", value_column]].sort_values("timestamp")
    frame = frame.rename(columns={value_column: "equity"})
    frame["equity"] = frame["equity"].astype(float)
    return frame


def _split_training_holdout(
    frame: pd.DataFrame,
    *,
    train_end: str,
    holdout_start: str,
    warmup_start: str,
    train_start: str,
) -> tuple[List[Dict[str, float]], List[Dict[str, float]], Dict[str, str]]:
    if frame.empty:
        coverage = {
            "warmup_start": warmup_start,
            "train_start": train_start,
            "train_end": train_end,
            "holdout_start": holdout_start,
        }
        return [], [], coverage

    timestamps = frame["timestamp"]
    train_end_ts = _align_timestamp(train_end, timestamps)
    holdout_start_ts = _align_timestamp(holdout_start, timestamps)

    training_mask = timestamps <= train_end_ts
    holdout_mask = timestamps >= holdout_start_ts

    training_points = [
        {"timestamp": ts.isoformat(), "equity": float(eq)}
        for ts, eq in zip(frame.loc[training_mask, "timestamp"], frame.loc[training_mask, "equity"], strict=False)
    ]
    holdout_points = [
        {"timestamp": ts.isoformat(), "equity": float(eq)}
        for ts, eq in zip(frame.loc[holdout_mask, "timestamp"], frame.loc[holdout_mask, "equity"], strict=False)
    ]

    coverage = {
        "warmup_start": warmup_start,
        "train_start": train_start,
        "train_end": train_end,
        "holdout_start": holdout_start,
    }
    return training_points, holdout_points, coverage


def _select_candidate_event(history: Sequence[Mapping[str, Any]], candidate_id: str | None) -> Mapping[str, Any] | None:
    if not history:
        return None
    if candidate_id:
        for entry in reversed(history):
            if str(entry.get("candidate_id")) == candidate_id:
                return entry
    return history[-1]




def build_best_candidate_view(result) -> BestCandidateView | None:  # type: ignore[valid-type]
    """Derive best-candidate artefacts from an optimisation result."""

    equity_frame = _normalize_equity_frame(result.equity_curve)
    if equity_frame.empty and not result.candidate_history:
        return None

    coverage_plan = result.coverage_plan
    history = list(result.candidate_history or [])
    candidate_id = result.best_candidate_id
    candidate_event = _select_candidate_event(history, candidate_id)

    score = float(result.parameter_set.fitness.get("score", 0.0))
    score_delta = 0.0
    if candidate_event:
        candidate_id = str(candidate_event.get("candidate_id") or candidate_id)
        score = float(candidate_event.get("score", score))
        score_delta = float(candidate_event.get("score_delta", 0.0))

    training_points, holdout_points, coverage = _split_training_holdout(
        equity_frame,
        train_end=coverage_plan.train.end.isoformat(),
        holdout_start=coverage_plan.holdout.start.isoformat(),
        warmup_start=coverage_plan.warmup.slice.start.isoformat(),
        train_start=coverage_plan.train.start.isoformat(),
    )

    holdout_series = pd.Series(dtype=float)
    if holdout_points:
        holdout_series = pd.Series(
            data=[point["equity"] for point in holdout_points],
            index=pd.to_datetime([point["timestamp"] for point in holdout_points]),
            dtype=float,
        )
    heatmap = build_momentum_heatmap(holdout_series)

    window_start = coverage_plan.holdout.start.isoformat()
    window_end = coverage_plan.holdout.end.isoformat()
    trade_timeline = build_trade_timeline(
        result.trades,
        window_start=window_start,
        window_end=window_end,
    )

    return BestCandidateView(
        run_id=result.run_id,
        candidate_id=candidate_id,
        score=score,
        score_delta=score_delta,
        parameters=dict(result.parameter_set.parameters),
        metrics=dict(result.metrics),
        stats=dict(result.stats),
        training_equity=training_points,
        holdout_equity=holdout_points,
        coverage=coverage,
        heatmap=heatmap.to_dict(),
        timeline=trade_timeline.to_dict(),
         all_trades=result.trades,
    )


def _build_equity_figure(view: BestCandidateView) -> go.Figure:
    fig = go.Figure()
    training_df = pd.DataFrame(view.training_equity)
    holdout_df = pd.DataFrame(view.holdout_equity)

    if not training_df.empty:
        training_df["timestamp"] = pd.to_datetime(training_df["timestamp"])
        fig.add_trace(
            go.Scatter(
                x=training_df["timestamp"],
                y=training_df["equity"],
                mode="lines",
                name="Training",
                line=dict(color=TRAINING_COLOR),
                hovertemplate="%{x|%Y-%m-%d}<br>Equity=%{y:,.2f}<extra></extra>",
            )
        )
    if not holdout_df.empty:
        holdout_df["timestamp"] = pd.to_datetime(holdout_df["timestamp"])
        fig.add_trace(
            go.Scatter(
                x=holdout_df["timestamp"],
                y=holdout_df["equity"],
                mode="lines",
                name="Holdout",
                line=dict(color=HOLDOUT_COLOR),
                hovertemplate="%{x|%Y-%m-%d}<br>Equity=%{y:,.2f}<extra></extra>",
            )
        )

    warmup_start = pd.Timestamp(view.coverage["warmup_start"])
    train_start = pd.Timestamp(view.coverage["train_start"])
    holdout_start = pd.Timestamp(view.coverage["holdout_start"])

    fig.add_vrect(
        x0=warmup_start,
        x1=train_start,
        fillcolor="rgba(31, 119, 180, 0.05)",
        line_width=0,
        layer="below",
    )
    fig.add_vline(
        x=holdout_start,
        line_dash="dot",
        line_color=HOLDOUT_COLOR,
        line_width=2,
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", x=0, y=1.1),
    )
    fig.update_xaxes(
        tickformat="%b %Y",
        dtick="M2",
        ticklabelmode="period",
        showline=True,
        linewidth=1,
        linecolor="rgba(0,0,0,0.4)",
        mirror=True,
    )
    return fig


def _build_heatmap_figure(heatmap: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    windows = heatmap.get("windows") or []
    dates = heatmap.get("dates") or []
    matrix = heatmap.get("matrix") or []
    if not windows or not dates or not matrix:
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        return fig

    labels = [f"{int(window)}d" for window in windows]
    x_values = [pd.to_datetime(value) for value in dates]
    z_values = [
        [None if value is None else float(value) for value in row] for row in matrix
    ]

    fig.add_trace(
        go.Heatmap(
            x=x_values,
            y=labels,
            z=z_values,
            colorscale=heatmap.get("colorscale", "RdYlGn"),
            zmid=heatmap.get("zmid", 0.0),
            colorbar=dict(title="% annualised"),
            hovertemplate="Window=%{y}<br>Date=%{x|%Y-%m-%d}<br>Momentum=%{z:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        title="Rolling performance heatmap",
        showlegend=False,
    )
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="Window")
    return fig


def _build_timeline_figure(timeline: Dict[str, Any]) -> go.Figure:
    fig = go.Figure()
    points = timeline.get("points") or []
    if not points:
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        fig.update_xaxes(title="Date", type="date")
        fig.update_yaxes(title="Symbol")
        window_start = timeline.get("window_start")
        window_end = timeline.get("window_end")
        if window_start and window_end:
            fig.update_xaxes(range=[pd.to_datetime(window_start), pd.to_datetime(window_end)])
        return fig

    frame = pd.DataFrame(points)
    from plotly import colors as plotly_colors
    frame["entry"] = pd.to_datetime(frame["entry"])
    frame["exit"] = pd.to_datetime(frame["exit"])
    frame["return_pct"] = frame["return_pct"].astype(float)
    frame["size_fraction"] = frame.get("size_fraction", pd.Series(0.0, index=frame.index)).astype(float)
    frame["duration_days"] = frame.get("duration_days", pd.Series(0.0, index=frame.index)).astype(float)

    return_series = frame["return_pct"].fillna(0.0)
    color_domain = timeline.get("color_domain")
    if color_domain is None or color_domain <= 0:
        color_domain = max(1.0, return_series.abs().max())
    color_scale = timeline.get("color_scale", "RdYlGn")

    symbols = list(dict.fromkeys(frame["symbol"]))
    symbol_to_idx = {symbol: idx for idx, symbol in enumerate(symbols)}

    def _height(fraction: float) -> float:
        fraction = float(fraction if pd.notna(fraction) else 0.0)
        return max(0.2, min(0.9, fraction * 0.8 + 0.2))

    def _color(value: float) -> str:
        normalized = 0.5 if color_domain == 0 else (value + color_domain) / (2 * color_domain)
        normalized = max(0.0, min(1.0, normalized))
        return plotly_colors.sample_colorscale(color_scale, [normalized])[0]

    for row in frame.itertuples():
        metadata = row.metadata or {}
        formatted_return = "n/a" if pd.isna(row.return_pct) else f"{row.return_pct:.2f}%"
        actual_entry = (
            row.metadata.get("entry_actual", row.entry.isoformat())
            if isinstance(row.metadata, dict)
            else row.entry.isoformat()
        )
        actual_exit = (
            row.metadata.get("exit_actual", row.exit.isoformat())
            if isinstance(row.metadata, dict)
            else row.exit.isoformat()
        )
        hover_lines = [
            f"Symbol={row.symbol}",
            f"Entry (holdout)={row.entry:%Y-%m-%d %H:%M:%S}",
            f"Exit (holdout)={row.exit:%Y-%m-%d %H:%M:%S}",
            f"Entry (actual)={pd.Timestamp(actual_entry):%Y-%m-%d %H:%M:%S}",
            f"Exit (actual)={pd.Timestamp(actual_exit):%Y-%m-%d %H:%M:%S}",
            f"Return={formatted_return}",
            f"Duration={row.duration_days:.1f} days",
            f"Quantity={row.quantity:,.2f}",
            f"P&L={row.pnl:,.2f}",
            f"Notional={row.notional:,.2f}",
        ]
        if row.portfolio_notional is not None:
            hover_lines.append(f"Portfolio Notional={row.portfolio_notional:,.2f}")
        weight_pct = metadata.get("portfolio_weight_pct")
        if weight_pct is not None:
            hover_lines.append(f"Weight={float(weight_pct):.2f}%")
        weight_fraction = metadata.get("portfolio_weight")
        if weight_fraction is not None:
            hover_lines.append(f"Weight Fraction={float(weight_fraction):.4f}")
        risk_reward = metadata.get("risk_reward")
        if risk_reward is not None:
            hover_lines.append(f"Risk/Reward={risk_reward}")
        mae = metadata.get("max_adverse_excursion")
        if mae is not None:
            hover_lines.append(f"Max Adverse Excursion={mae}")
        mfe = metadata.get("max_favorable_excursion")
        if mfe is not None:
            hover_lines.append(f"Max Favorable Excursion={mfe}")
        size_fraction = metadata.get("size_fraction")
        if size_fraction is not None:
            hover_lines.append(f"Size Fraction={float(size_fraction):.2f}")
        hover_text = "<br>".join(hover_lines)

        center = symbol_to_idx[row.symbol]
        height = _height(row.size_fraction)
        y0 = center - height / 2
        y1 = center + height / 2
        color = _color(0.0 if pd.isna(row.return_pct) else float(row.return_pct))

        fig.add_trace(
            go.Scatter(
                x=[row.entry, row.exit, row.exit, row.entry, row.entry],
                y=[y0, y0, y1, y1, y0],
                mode="lines",
                fill="toself",
                line=dict(width=0),
                fillcolor=color,
                hovertext=hover_text,
                hoverinfo="text",
                showlegend=False,
            )
        )

    # Invisible marker to keep colorscale legend
    fig.add_trace(
        go.Scatter(
            x=[frame["exit"].max()],
            y=[symbol_to_idx[symbols[0]] if symbols else 0],
            mode="markers",
            marker=dict(
                size=0.1,
                color=[color_domain],
                colorscale=color_scale,
                cmin=-color_domain,
                cmax=color_domain,
                showscale=True,
                colorbar=dict(title="Return (%)"),
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    window_start = timeline.get("window_start")
    window_end = timeline.get("window_end")
    xaxis_kwargs: Dict[str, Any] = {"title": "Date", "type": "date"}
    if window_start and window_end:
        start_ts = pd.to_datetime(window_start)
        end_ts = pd.to_datetime(window_end)
        xaxis_kwargs["range"] = [start_ts, end_ts]

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        title="Holdout trade timeline",
        showlegend=False,
    )
    fig.update_xaxes(**xaxis_kwargs)
    fig.update_yaxes(
        title="Symbol",
        tickmode="array",
        tickvals=list(symbol_to_idx.values()),
        ticktext=symbols,
        autorange="reversed",
    )

    return fig


def render_best_candidate(view: BestCandidateView) -> None:
    if view is None:
        return

    st.subheader("Best Candidate")
    score_delta_display = f"{view.score_delta:+.3f}"
    col_a, col_b = st.columns([1, 1])
    with col_a:
        st.metric("Score", f"{view.score:.3f}", delta=score_delta_display)
        st.caption(f"Run {view.run_id} · Candidate {view.candidate_id or '—'}")
        st.json(view.parameters)
    with col_b:
        metrics_frame = pd.DataFrame(
            {"Metric": list(view.metrics.keys()), "Value": [float(v) for v in view.metrics.values()]}
        )
        stats_frame = pd.DataFrame(
            {"Stat": list(view.stats.keys()), "Value": [float(v) for v in view.stats.values()]}
        )
        st.caption("Performance Metrics")
        st.dataframe(metrics_frame.set_index("Metric"), use_container_width=True)
        st.caption("Run Stats")
        st.dataframe(stats_frame.set_index("Stat"), use_container_width=True)

    # Toggle for window selection
    show_full_window = st.toggle("Show Full Training + Holdout Window", value=False, key=f"window_toggle_{view.run_id}")

    # Determine window boundaries
    if show_full_window:
        # Full training + holdout
        window_start = view.coverage.get("warmup_start") or view.coverage.get("train_start")
        window_end = view.coverage.get("holdout_start")
        # Get holdout end from last equity point if available
        if view.holdout_equity:
            window_end = view.holdout_equity[-1]["timestamp"]
        # Combine training and holdout equity for analytics
        all_equity_points = view.training_equity + view.holdout_equity
        equity_series = pd.Series(dtype=float)
        if all_equity_points:
            equity_series = pd.Series(
                data=[point["equity"] for point in all_equity_points],
                index=pd.to_datetime([point["timestamp"] for point in all_equity_points]),
                dtype=float,
            )
    else:
        # Holdout only (default)
        window_start = view.coverage.get("holdout_start")
        window_end = None
        if view.holdout_equity:
            window_end = view.holdout_equity[-1]["timestamp"]
        equity_series = pd.Series(dtype=float)
        if view.holdout_equity:
            equity_series = pd.Series(
                data=[point["equity"] for point in view.holdout_equity],
                index=pd.to_datetime([point["timestamp"] for point in view.holdout_equity]),
                dtype=float,
            )

    equity_fig = _build_equity_figure(view)
    if show_full_window and window_start and window_end:
        equity_fig.update_xaxes(range=[pd.to_datetime(window_start), pd.to_datetime(window_end)])
    elif not show_full_window and window_start and window_end:
        equity_fig.update_xaxes(range=[pd.to_datetime(window_start), pd.to_datetime(window_end)])
    st.plotly_chart(equity_fig, use_container_width=True)

    st.write("")  # Add vertical spacing

    # Rebuild heatmap with selected window
    from model_builder.analytics import build_momentum_heatmap, build_trade_timeline
    heatmap_data = build_momentum_heatmap(equity_series)
    heatmap_fig = _build_heatmap_figure(heatmap_data.to_dict())
    st.plotly_chart(heatmap_fig, use_container_width=True)
    st.caption(heatmap_data.to_dict().get("narrative", ""))

    st.write("")  # Add vertical spacing

    # Rebuild timeline with selected window using all trades
    timeline_data = build_trade_timeline(
        view.all_trades,
        window_start=window_start,
        window_end=window_end,
    )
    timeline_fig = _build_timeline_figure(timeline_data.to_dict())
    st.plotly_chart(timeline_fig, use_container_width=True)
    timeline_dict = timeline_data.to_dict()
    if not timeline_dict.get("points"):
        st.caption("No trades executed within the selected window.")
    else:
        st.caption(
            f"Trades · wins {timeline_dict.get('wins', 0)} | losses {timeline_dict.get('losses', 0)} "
            f"| flats {timeline_dict.get('flats', 0)} · total notional {timeline_dict.get('total_notional', 0):,.0f}"
        )


def store_best_candidate(session_state: MutableMapping[str, Any], view: BestCandidateView) -> None:
    session_state[BEST_CANDIDATE_STATE_KEY] = view.to_session()


def load_best_candidate(session_state: MutableMapping[str, Any]) -> BestCandidateView | None:
    payload = session_state.get(BEST_CANDIDATE_STATE_KEY)
    if not isinstance(payload, Mapping):
        return None
    try:
        return BestCandidateView.from_session(payload)
    except (KeyError, TypeError, ValueError):
        return None


__all__ = [
    "BEST_CANDIDATE_STATE_KEY",
    "BestCandidateView",
    "build_best_candidate_view",
    "render_best_candidate",
    "store_best_candidate",
    "load_best_candidate",
]
