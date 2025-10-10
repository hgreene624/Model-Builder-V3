from __future__ import annotations

from dataclasses import is_dataclass

from src.models.contracts import BacktestResult, Portfolio, ParameterSet, TradeRecord


def test_contracts_are_dataclasses() -> None:
    assert is_dataclass(Portfolio)
    assert is_dataclass(ParameterSet)
    assert is_dataclass(BacktestResult)
    assert is_dataclass(TradeRecord)
