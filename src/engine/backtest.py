from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Dict, Iterable, List, Sequence

import numpy as np
import pandas as pd

from src.models.contracts import BacktestResult, TradeRecord


@dataclass(frozen=True)
class CostModel:
    commission: float = 0.0
    slippage_bps: float = 0.0
    borrow_bps: float = 0.0

    def breakdown(self, notional: float, side: str) -> Dict[str, float]:
        absolute = abs(notional)
        commission = self.commission if absolute > 0 else 0.0
        slippage = absolute * (self.slippage_bps / 10_000)
        borrow = 0.0
        if side == "sell" and notional < 0 and self.borrow_bps:
            borrow = absolute * (self.borrow_bps / 10_000)
        total = commission + slippage + borrow
        return {
            "commission": commission,
            "slippage": slippage,
            "borrow": borrow,
            "total": total,
        }


def _close_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if isinstance(prices.columns, pd.MultiIndex):
        if "close" not in prices.columns.get_level_values(-1):
            raise KeyError("prices DataFrame missing 'close' level for MultiIndex columns")
        close = prices.xs("close", axis=1, level=-1)
    else:
        close = prices
    return close.astype(float)


def _prepare_weights(signals: pd.DataFrame, index: pd.Index, symbols: Sequence[str]) -> pd.DataFrame:
    if signals.empty:
        weights = pd.DataFrame(0.0, index=index, columns=symbols)
    else:
        pivot = signals.pivot_table(index="timestamp", columns="symbol", values="weight", aggfunc="last")
        weights = pivot.reindex(index).sort_index().ffill().fillna(0.0)
        missing_columns = set(symbols) - set(weights.columns)
        for symbol in missing_columns:
            weights[symbol] = 0.0
        weights = weights[symbols]
    return weights


def run_backtest(
    *,
    prices: pd.DataFrame,
    signals: pd.DataFrame,
    initial_capital: float,
    trading_days_per_year: int = 252,
    benchmark: pd.Series | None = None,
    cost_model: CostModel | None = None,
) -> BacktestResult:
    if initial_capital <= 0:
        raise ValueError("initial_capital must be positive")

    close = _close_prices(prices)
    close = close.sort_index()
    symbols = list(close.columns)
    weights = _prepare_weights(signals, close.index, symbols)
    cost_model = cost_model or CostModel()

    positions: Dict[str, float] = {symbol: 0.0 for symbol in symbols}
    cost_basis: Dict[str, float] = {symbol: 0.0 for symbol in symbols}
    open_timestamps: Dict[str, pd.Timestamp | None] = {symbol: None for symbol in symbols}
    cash = float(initial_capital)

    equity_points: List[tuple[pd.Timestamp, float]] = []
    benchmark_points: List[tuple[pd.Timestamp, float]] = []
    trades: List[TradeRecord] = []
    total_notional = 0.0
    closing_trades: List[TradeRecord] = []
    hold_durations: List[float] = []

    for timestamp in close.index:
        prices_row = close.loc[timestamp]
        portfolio_value = cash + sum(positions[symbol] * prices_row[symbol] for symbol in symbols)

        weight_row = weights.loc[timestamp]
        for symbol in symbols:
            price = float(prices_row[symbol])
            if not np.isfinite(price) or price <= 0:
                continue

            target_value = float(weight_row[symbol]) * portfolio_value
            current_value = positions[symbol] * price
            delta_value = target_value - current_value

            if abs(delta_value) < 1e-9:
                continue

            delta_units = delta_value / price
            action = "buy" if delta_units > 0 else "sell"
            notional = delta_units * price
            costs = cost_model.breakdown(notional, action)
            total_notional += abs(notional)

            cash -= notional
            cash -= costs["total"]

            realised_pnl = -costs["total"]
            previous_position = positions[symbol]

            exit_timestamp: str | None = None
            closed_position = False

            entry_timestamp_value: str | None = None

            if delta_units > 0:
                positions[symbol] += delta_units
                cost_basis[symbol] += delta_units * price
                if previous_position <= 1e-9 and positions[symbol] > 1e-9:
                    open_timestamps[symbol] = pd.Timestamp(timestamp)
            else:
                sell_units = abs(delta_units)
                position_before = positions[symbol]
                if position_before <= 0:
                    realised_pnl = -costs["total"]
                else:
                    average_cost = cost_basis[symbol] / position_before
                    realised = sell_units * (price - average_cost)
                    realised_pnl = realised - costs["total"]
                    cost_basis[symbol] -= min(cost_basis[symbol], sell_units * average_cost)
                positions[symbol] += delta_units
                if positions[symbol] <= 1e-9:
                    positions[symbol] = 0.0
                    cost_basis[symbol] = 0.0
                    closed_position = True
                    entry = open_timestamps.get(symbol)
                    if entry is not None:
                        duration = max(
                            (pd.Timestamp(timestamp) - entry) / pd.Timedelta(days=1),
                            1.0,
                        )
                        hold_durations.append(float(duration))
                        entry_timestamp_value = entry.isoformat()
                    open_timestamps[symbol] = None
                    exit_timestamp = pd.Timestamp(timestamp).isoformat()

            trade = TradeRecord(
                timestamp=pd.Timestamp(timestamp).isoformat(),
                symbol=symbol,
                action=action,
                quantity=float(delta_units),
                price=price,
                costs=costs,
                exit_timestamp=exit_timestamp,
                pnl=float(realised_pnl),
                entry_timestamp=entry_timestamp_value,
            )
            trades.append(trade)
            if closed_position:
                closing_trades.append(trade)

        portfolio_value = cash + sum(positions[symbol] * prices_row[symbol] for symbol in symbols)
        equity_points.append((pd.Timestamp(timestamp), float(portfolio_value)))

        if benchmark is not None:
            if timestamp in benchmark.index:
                benchmark_points.append((pd.Timestamp(timestamp), float(benchmark.loc[timestamp])))

    equity_series = pd.Series(
        {ts: value for ts, value in equity_points}, name="equity"
    ).sort_index()
    returns = equity_series.pct_change().fillna(0.0)

    years = max(len(equity_series) / trading_days_per_year, 1e-9)
    start_value = float(initial_capital)
    end_value = float(equity_series.iloc[-1])

    cagr = (end_value / start_value) ** (1 / years) - 1 if start_value > 0 else 0.0
    std_dev = returns.std()
    sharpe = (returns.mean() / std_dev * sqrt(trading_days_per_year)) if std_dev > 0 else 0.0

    rolling_max = equity_series.cummax()
    drawdown_series = equity_series / rolling_max - 1
    max_drawdown = float(drawdown_series.min())
    if max_drawdown < 0:
        calmar = cagr / abs(max_drawdown) if max_drawdown != 0 else float("inf")
    else:
        calmar = cagr if cagr > 0 else 0.0

    realised_trades = closing_trades
    wins = sum(1 for trade in realised_trades if trade.pnl > 0)
    hit_rate = wins / len(realised_trades) if realised_trades else 0.0
    trade_rate = len(realised_trades) / years if years > 0 else 0.0
    avg_hold_days = sum(hold_durations) / len(hold_durations) if hold_durations else 0.0

    average_equity = equity_series.mean()
    turnover = total_notional / average_equity if average_equity > 0 else 0.0

    risk_notes: List[str] = []
    if max_drawdown < -0.2:
        risk_notes.append(f"Max drawdown exceeded 20% ({max_drawdown:.2%}).")
    if turnover > 4.0:
        risk_notes.append(f"Turnover {turnover:.2f} indicates high trading activity.")

    equity_curve = [
        {"timestamp": ts.isoformat(), "equity": float(value)} for ts, value in equity_points
    ]
    benchmark_curve = [
        {"timestamp": ts.isoformat(), "value": value} for ts, value in benchmark_points
    ]

    kpis = {
        "cagr": float(cagr),
        "sharpe": float(sharpe),
        "calmar": float(calmar),
        "max_drawdown": float(max_drawdown),
        "hit_rate": float(hit_rate),
        "turnover": float(turnover),
        "trade_rate": float(trade_rate),
        "avg_hold_days": float(avg_hold_days),
    }

    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        benchmarks=benchmark_curve,
        kpis=kpis,
        risk_notes=risk_notes,
    )
