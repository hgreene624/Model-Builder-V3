from __future__ import annotations

import pytest

from src.optimizer.evolutionary import ConstraintGate, ObjectiveWeights


def test_objective_weights_normalize_and_score() -> None:
    weights = ObjectiveWeights(cagr=2.0, calmar=1.0, sharpe=1.0)
    metrics = {"cagr": 0.18, "calmar": 1.4, "sharpe": 1.1}

    score = weights.score(metrics)

    expected = (0.18 * 0.5) + (1.4 * 0.25) + (1.1 * 0.25)
    assert score == pytest.approx(expected, rel=1e-6)


def test_objective_weights_reject_all_zero() -> None:
    with pytest.raises(ValueError):
        ObjectiveWeights(cagr=0.0, calmar=0.0, sharpe=0.0)


def test_constraint_gate_pass() -> None:
    gate = ConstraintGate(max_trade_rate=6.0, min_hold_days=2.5, penalty=-1_000.0)
    stats = {"trade_rate": 5.5, "avg_hold_days": 3.1}

    result = gate.evaluate(stats)

    assert result.passed is True
    assert result.penalty == pytest.approx(0.0)
    assert result.reasons == []


def test_constraint_gate_flags_trade_rate_violation() -> None:
    gate = ConstraintGate(max_trade_rate=5.0, min_hold_days=2.5, penalty=-500.0)
    stats = {"trade_rate": 5.8, "avg_hold_days": 3.5}

    result = gate.evaluate(stats)

    assert result.passed is False
    assert any("trade_rate" in reason for reason in result.reasons)
    assert result.penalty == pytest.approx(-500.0)


def test_constraint_gate_flags_hold_period_violation() -> None:
    gate = ConstraintGate(max_trade_rate=6.0, min_hold_days=4.0, penalty=-750.0)
    stats = {"trade_rate": 5.0, "avg_hold_days": 3.0}

    result = gate.evaluate(stats)

    assert result.passed is False
    assert any("avg_hold_days" in reason for reason in result.reasons)
    assert result.penalty == pytest.approx(-750.0)
