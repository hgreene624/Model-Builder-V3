# Model Contract — Strategy Plugins

## Purpose
Define the interface every strategy module must implement so UI, optimizer, backtest engine, and CLI can work interchangeably without custom wiring.

## Module Structure
- Python package located under `src/models/<strategy_name>/`.
- Exports a callable `register()` returning a `StrategyModel` instance (dataclass or pydantic model) defined in `src/models/contracts.py`.
- Must be importable without side effects beyond lightweight configuration.

## StrategyModel Fields
- `model_id`: unique dotted path (`models.atr_breakout`).
- `name`: human-readable label.
- `version`: semantic version of the strategy.
- `description`: concise summary of behavior and intended use.
- `parameters`: list of `ParameterSpec`.
- `supports_risk_sizing`: boolean (true enables risk/reward toggle).
- `warmup_period`: integer bars required before first trade signal.
- `run`: callable with signature `run(context: StrategyContext) -> TradeIntentFrame`.

## ParameterSpec Requirements
- `key`: Python identifier (snake_case).
- `display_name`: UI label.
- `type`: `int`, `float`, `bool`, `enum`.
- `default`: valid value.
- `bounds`:
  - Numeric (`min`, `max`, optional `step`).
  - Enum (`choices` list).
- `description`: user-facing explanation.

## StrategyContext
- `bars`: pandas DataFrame indexed by UTC timestamp with columns `open`, `high`, `low`, `close`, `volume`.
- `features`: dict of precomputed series (ATR, moving averages).
- `portfolio_meta`: metadata for current portfolio (tickers, liquidity stats).
- `params`: parameter values typed according to spec.
- `options`: execution hints (e.g., allow_short, cost assumptions).

## TradeIntentFrame Output
- pandas DataFrame with required columns:
  - `timestamp` (UTC).
  - `symbol`.
  - `action` (`buy`, `sell`, `flat`).
  - `weight` (float -1..1 representing target exposure per symbol).
  - `confidence` (float 0..1, optional).
  - `stop` / `target` (optional price levels).
  - `metadata` (JSON-serializable dict).
- Must align index with input bars for consumed timeframe.
- No network calls or disk writes from within `run`; rely on provided data.

## Validation Rules
- Model registry validates:
  - Parameter defaults within bounds.
  - Warmup period non-negative.
  - Output DataFrame contains required columns and dtype constraints.
- Failing validation raises `ModelContractError` and prevents registration.

## Lifecycle Hooks (optional)
- `post_registration(config)` — adjust defaults based on global settings.
- `pre_run(context)` — mutate context features before evaluation (must be deterministic).
- `on_evaluation(result)` — inject metadata into optimizer logs (no side effects outside telemetry).

## Logging & Determinism
- Strategies may emit structured logs via provided logger; no print statements.
- Runs must be deterministic given identical inputs and random seeds supplied through context.

## Versioning & Compatibility
- Increase `version` when parameters or outputs change materially.
- Update `contract_version` in registry if the interface evolves; maintain backward compatibility via adapters in `models/registry.py`.
