from __future__ import annotations

from pathlib import Path
import sys

from model_builder.ui.components.candidate_summary import (
    build_best_candidate_view,
    load_best_candidate,
    store_best_candidate,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
src_path = PROJECT_ROOT / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from src.config.settings import AppSettings  # noqa: E402
from src.engine.atr_breakout import ATRBreakoutConfig, RiskSettings  # noqa: E402
from src.engine.backtest import CostModel  # noqa: E402
from src.models.contracts import Portfolio  # noqa: E402
from src.optimizer.evolutionary import ConstraintGate, ObjectiveWeights  # noqa: E402
from src.optimizer.workflow import run_optimization  # noqa: E402


def _build_synthetic_portfolio() -> Portfolio:
    return Portfolio(
        portfolio_id="TEST",
        name="Synthetic Portfolio",
        description="synthetic",
        source="synthetic",
        seed_reference=None,
        filters={},
        coverage_window={"start": "2023-01-01", "end": "2025-12-31"},
        tickers=["AAA", "BBB", "CCC"],
        liquidity_stats={},
        notes=[],
    )


def test_best_candidate_view_roundtrip() -> None:
    portfolio = _build_synthetic_portfolio()
    settings = AppSettings.from_env()
    result = run_optimization(
        settings=settings,
        portfolio=portfolio,
        selected_symbols=portfolio.tickers,
        base_config=ATRBreakoutConfig(atr_window=14, breakout_lookback=20, breakout_multiplier=2.0),
        base_risk=RiskSettings(enabled=True, risk_fraction=0.02, min_weight=0.05, max_weight=0.25),
        bounds={
            "atr_window": (14, 14),
            "breakout_lookback": (20, 20),
            "breakout_multiplier": (2.0, 2.0),
            "risk_fraction": (0.02, 0.02),
        },
        objective_weights=ObjectiveWeights(cagr=0.5, calmar=0.3, sharpe=0.2),
        constraint_gate=ConstraintGate(max_trade_rate=50.0, min_hold_days=2.0, penalty=-1000.0),
        population_size=1,
        generations=1,
        max_workers=1,
        seed=42,
        initial_capital=100_000.0,
        cost_model=CostModel(),
        model_id="models.atr_breakout",
        session="test",
        use_synthetic=True,
        train_percentage=0.8,
        warmup_days=10,
    )

    view = build_best_candidate_view(result)
    assert view is not None
    assert view.run_id == result.run_id
    assert isinstance(view.training_equity, list)
    assert isinstance(view.holdout_equity, list)
    assert "windows" in view.heatmap and "matrix" in view.heatmap
    assert len(view.heatmap["windows"]) > 0
    assert "points" in view.timeline
    if view.timeline["points"]:
        timeline_point = view.timeline["points"][0]
        assert "entry" in timeline_point and "exit" in timeline_point
        assert "return_pct" in timeline_point

    session_state: dict[str, object] = {}
    store_best_candidate(session_state, view)
    restored = load_best_candidate(session_state)
    assert restored is not None
    assert restored.run_id == view.run_id
    assert restored.candidate_id == view.candidate_id
