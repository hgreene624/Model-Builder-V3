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


def _filter_holdout_trades(
    trades: Sequence[Any],
    holdout_start: str,
) -> List[Any]:
    holdout_start_ts = pd.Timestamp(holdout_start)
    holdout_start_norm = holdout_start_ts.tz_convert(None) if holdout_start_ts.tz is not None else holdout_start_ts

    filtered: List[Any] = []
    for trade in trades:
        payload = trade
        timestamp = pd.Timestamp(payload.timestamp if hasattr(payload, "timestamp") else payload.get("timestamp"))
        exit_value = getattr(payload, "exit_timestamp", None)
        if exit_value is None and isinstance(payload, Mapping):
            exit_value = payload.get("exit_timestamp")

        entry_norm = timestamp.tz_convert(None) if timestamp.tz is not None else timestamp
        exit_norm = None
        if exit_value:
            exit_ts = pd.Timestamp(exit_value)
            exit_norm = exit_ts.tz_convert(None) if exit_ts.tz is not None else exit_ts

        include = entry_norm >= holdout_start_norm
        if not include and exit_norm is not None:
            include = exit_norm >= holdout_start_norm
        if include:
            filtered.append(trade)
    return filtered


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

    holdout_trades = _filter_holdout_trades(result.trades, coverage_plan.holdout.start.isoformat())
    trade_timeline = build_trade_timeline(holdout_trades)

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
        return fig

    frame = pd.DataFrame(points)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame["pnl"] = frame["pnl"].astype(float)
    frame["notional"] = frame["notional"].astype(float)
    frame["marker_color"] = frame["pnl_direction"].apply(
        lambda direction: POSITIVE_COLOR if direction == "gain" else NEGATIVE_COLOR if direction == "loss" else NEUTRAL_COLOR
    )

    max_notional = frame["notional"].max()
    if max_notional > 0:
        sizeref = 2 * max_notional / (40**2)
        sizes = frame["notional"]
    else:
        sizeref = 1
        sizes = pd.Series([12.0] * len(frame))

    hover_text = []
    for row in frame.itertuples():
        duration = f"{row.duration_days:.1f}d" if row.duration_days is not None else "open"
        hover_text.append(
            f"{row.symbol} | Notional {row.notional:,.0f} | P&L {row.pnl:,.2f} | Duration {duration}"
        )

    fig.add_trace(
        go.Scatter(
            x=frame["timestamp"],
            y=frame["pnl"],
            mode="markers",
            marker=dict(
                size=sizes,
                sizemode="area",
                sizeref=sizeref,
                sizemin=8,
                color=frame["marker_color"],
                line=dict(width=0.6, color="rgba(0,0,0,0.4)"),
            ),
            hovertemplate="%{text}<extra></extra>",
            text=hover_text,
        )
    )

    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(
        title="P&L",
        zeroline=True,
        zerolinewidth=1,
        zerolinecolor="rgba(0,0,0,0.3)",
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

    equity_fig = _build_equity_figure(view)
    st.plotly_chart(equity_fig, use_container_width=True)

    col_heatmap, col_timeline = st.columns(2)
    with col_heatmap:
        heatmap_fig = _build_heatmap_figure(view.heatmap)
        st.plotly_chart(heatmap_fig, use_container_width=True)
        st.caption(view.heatmap.get("narrative", ""))
    with col_timeline:
        timeline_fig = _build_timeline_figure(view.timeline)
        st.plotly_chart(timeline_fig, use_container_width=True)
        st.caption(
            f"Trades · wins {view.timeline.get('wins', 0)} | losses {view.timeline.get('losses', 0)} "
            f"| flats {view.timeline.get('flats', 0)} · total notional {view.timeline.get('total_notional', 0):,.0f}"
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
