# Model Builder Parameters

This guide explains the primary knobs exposed on the **Model Builder** page and how changing them affects ATR breakout optimisation results. Each section includes example scenarios to illustrate the trade-offs.

## ATR Strategy Configuration

| Parameter | Description | Typical Range | Example Adjustment |
|-----------|-------------|----------------|--------------------|
| `ATR Window` | Number of sessions used when smoothing the Average True Range. Larger windows respond more slowly to volatility changes. | 10–30 | Increase from 14 to 21 if recent volatility spikes should be damped. |
| `Breakout Lookback` | Lookback window for the prior high that defines the breakout trigger. | 10–60 | Drop from 40 to 20 to react to shorter-term breakouts. |
| `Breakout Multiplier` | Scales ATR when computing the breakout band above the lookback high. | 1.5–3.5 | Raise from 2.0 to 2.75 to demand stronger momentum confirmation. |

## Risk Sizing Controls

| Parameter | Description | Typical Range | Example Adjustment |
|-----------|-------------|----------------|--------------------|
| `Enable Risk-Aware Sizing` | Toggles ATR-based position sizing. Disable for equal-weight exposure. | On/Off | Turn off when testing signal quality without risk heuristics. |
| `Risk Fraction` | Fraction of portfolio value risked per position. | 0.5–5% | Reduce from 2% to 1% to limit drawdowns during exploratory runs. |
| `Minimum Position Weight` | Floor applied after risk sizing to avoid negligible allocations. | 2–10% | Set to 0.08 to ensure meaningful contributions from each holding. |
| `Maximum Position Weight` | Cap applied after risk sizing to enforce diversification. | 15–30% | Lower to 0.20 when a portfolio contains concentrated themes. |

## Optimiser Settings

| Parameter | Description | Guidance | Example Adjustment |
|-----------|-------------|----------|--------------------|
| `Population Size` | Number of candidate genomes per generation. | Increase for broader search, decrease for faster iterations. | Move from 9 to 15 to explore more combinations when CPU headroom allows. |
| `Generations` | Count of evolutionary cycles. | Use 3–6 for rapid feedback, 8+ for convergence. | Extend to 6 once initial parameter bounds look promising. |
| `Max Workers` | Process pool size for parallel fitness evaluation. | Match available CPU cores. | Raise to 4 on a workstation to shorten run time. |

### Objective Weights

- **CAGR** emphasises raw growth. Example: weight 0.5 gives CAGR half of the composite score.
- **Calmar** balances return with drawdown depth. Example: increase to 0.4 to favour smoother equity.
- **Sharpe** rewards risk-adjusted consistency. Example: lift to 0.3 for lower-volatility portfolios.

Ensure weights sum to ~1.0 for interpretable scoring.

### Constraint Gate

- **Max Trades / Year** caps annualised turnover. Lower values encourage swing-style behaviour, while higher limits allow more reactive strategies.
- **Min Hold Days** enforces a minimum average holding period. Increase when transaction costs or tax considerations make short holds undesirable.

## Workflow Tips

1. Start with tighter bounds around the default ATR settings and a modest population to validate data quality.
2. Review the telemetry table after each run—large infeasible counts usually indicate constraint settings that conflict with the sampled parameter ranges.
3. Save promising parameter sets via the CLI or artifacts browser; re-run with higher generations to confirm stability before promoting to bundles.
