# Data Model — Self-Hosted Strategy Research Dashboard

## Overview

All persisted artifacts live under `storage/` with JSON/JSONL documents and parquet shards. Metadata includes a `schema_version` string to enable non-breaking upgrades. Timestamps are recorded in ISO 8601 UTC with millisecond precision.

## Entities

### Portfolio
- `portfolio_id` (UUID string) — primary identifier.
- `name` (string) — user-friendly label.
- `description` (string, optional) — summary of filters or intended use.
- `created_at` / `updated_at` (ISO UTC).
- `source` (enum) — e.g., `index`, `csv_import`, `manual`.
- `seed_reference` (string, optional) — origin list identifier.
- `filters` (object) — applied criteria (sector, liquidity thresholds, ticker patterns).
- `coverage_window` (object) — `{start: ISO, end: ISO}`; defaults to 5-year lookback when coverage allows.
- `tickers` (array of normalized symbols).
- `liquidity_stats` (object) — median price, median dollar volume, observation count.
- `notes` (array of strings) — user annotations.

Stored at `storage/portfolios/<portfolio_id>.json`.

### MarketShard
- `symbol` (string).
- `interval` (enum: `1d`, future `1h`).
- `start` / `end` (ISO UTC).
- `rows` (parquet dataset) — columns: `timestamp`, `open`, `high`, `low`, `close`, `volume`, optional corporate-action fields.
- `provider` (enum: `alpaca`, `yahoo`).
- `retrieved_at` (ISO UTC).

Stored as `storage/ohlcv/<symbol>/<interval>/<start>_<end>.parquet`.

### ModelModule
- `model_id` (string) — dotted module path.
- `name` (string).
- `version` (semver).
- `description` (string).
- `parameters` (array of ParameterSpec).
- `supports_risk_sizing` (bool).
- `contract_version` (string).
- `entry_point` (string) — Python callable path.
- `checksum` (string SHA256).

Registered within `storage/models/registry.json`.

### ParameterSpec
- `key` (string).
- `display_name` (string).
- `type` (enum: `int`, `float`, `bool`, `enum`).
- `range` (object) — min/max or allowed values.
- `default` (typed value).
- `step` (float, optional).
- `description` (string).

### ParameterSet (Genome)
- `parameter_set_id` (UUID).
- `model_id` (string).
- `portfolio_id` (string).
- `run_id` (UUID reference to optimizer run).
- `parameters` (key/value map).
- `fitness` (object) — weighted score, CAGR, Sharpe, Calmar.
- `constraints` (object) — trade rate, holding period compliance flags.
- `created_at` (ISO UTC).
- `schema_version`.

Stored at `storage/parameters/<parameter_set_id>.json`.

### OptimizerRun
- `run_id` (UUID).
- `model_id` / `portfolio_id`.
- `bounds` (map) — parameter limits.
- `objective_weights` (CAGR, Calmar, Sharpe).
- `seed` (int).
- `status` (enum: `running`, `paused`, `completed`, `failed`).
- `started_at` / `completed_at`.
- `best_parameter_set_id` (UUID optional until completion).
- `artifact_paths` (object) — references to JSONL logs, saved genomes, temporary checkpoints.

Run log appended at `storage/logs/<run_id>.jsonl`.

### TrainingEvent (JSONL row)
- `timestamp` (ISO UTC).
- `event_type` (enum: `generation_summary`, `holdout_update`, `checkpoint`, `warning`, `error`).
- `generation` (int, optional).
- `payload` (object) — includes sample genome, best fitness, telemetry metrics.

### SimulationRun
- `simulation_id` (UUID).
- `parameter_set_id`.
- `portfolio_id`.
- `benchmark_symbol` (string).
- `config` (object) — cost assumptions, execution settings.
- `results` (BacktestResult snapshot).
- `created_at`.

Stored under `storage/simulations/<simulation_id>/result.json` with supporting files (Plotly JSON, PNG).

### BacktestResult (embedded)
- `equity_curve` (array of `{timestamp, equity}`).
- `trades` (array of `{timestamp, symbol, action, quantity, price, costs, exit_timestamp, pnl}`).
- `benchmarks` (array per benchmark symbol).
- `kpis` (object) — CAGR, Sharpe, Calmar, max drawdown, hit rate, turnover, cost drag.
- `risk_notes` (array of strings).

### Bundle
- `bundle_id` (UUID).
- `model_id`.
- `parameter_sets` (array of ParameterSet snapshots).
- `created_at`.
- `compatibility` (object) — contract version, required Python version.
- `checksum`.

Serialized as ZIP at `storage/bundles/<bundle_id>.zip` with manifest `bundle.json`.

### CredentialProfile
- `provider` (enum).
- `status` (enum: `valid`, `missing`, `invalid`, `rate_limited`).
- `checked_at`.
- `message` (string).

Cached in `storage/credentials/status.json`.

## Relationships
- Portfolio ↔ MarketShard: many-to-many via tickers and coverage window.
- OptimizerRun references ModelModule, Portfolio, ParameterSet.
- SimulationRun references ParameterSet and Portfolio, consumes MarketShard data indirectly.
- Bundle aggregates ModelModule metadata and one or more ParameterSet snapshots.

## Versioning
- `schema_version` increments semantically per entity (major/minor/patch).
- Migration rules live in `storage/migrations.py`; on load, outdated artifacts upgrade in-memory then rewrite atomically.

## Data Volume Assumptions
- Portfolios: tens to hundreds of tickers per run.
- Market shards: five years of daily bars (~1,260 rows per ticker).
- Optimizer logs: thousands of JSONL entries per run; rotate every 10 MB by default.
