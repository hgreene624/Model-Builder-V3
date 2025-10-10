# Telemetry Schema — TrainingLogger & CLI Inspector

## Purpose
Standardize JSONL events emitted during optimization and simulation so both Streamlit UI and CLI tools can parse progress, warnings, and outcomes.

## Event Envelope
Each JSONL line adheres to:

```json
{
  "schema_version": "1.0.0",
  "timestamp": "2025-10-10T12:00:00.000Z",
  "event_type": "generation_summary",
  "run_id": "4b3b2f0a-...",
  "session": "ui" | "cli",
  "payload": { ... }
}
```

- `schema_version`: semantic version of telemetry schema.
- `timestamp`: ISO 8601 UTC with millisecond precision.
- `event_type`: one of the defined categories below.
- `run_id`: UUID referencing OptimizerRun.
- `session`: originator (`ui` or `cli`).
- `payload`: event-specific body.

## Events

### `session_start`
Indicates optimizer or simulation run started.
- `payload`:
  - `model_id` (string)
  - `portfolio_id` (string)
  - `objective_weights` (object)
  - `bounds_snapshot` (object)

### `generation_summary`
Emitted per generation (optimizer only).
- `payload`:
  - `generation` (int)
  - `population_size` (int)
  - `best_fitness` (float)
  - `avg_fitness` (float)
  - `worst_fitness` (float)
  - `best_metrics` (object: `cagr`, `sharpe`, `calmar`, `drawdown`, `trade_rate`)
  - `best_parameters` (object key/value)

### `holdout_update`
Provides incremental holdout equity/benchmark snapshots.
- `payload`:
  - `equity` (array of `{timestamp, value}`)
  - `benchmark` (array of `{timestamp, value}`)
  - `generation` (int)

### `checkpoint`
Checkpoint saved.
- `payload`:
  - `path` (string)
  - `best_parameter_set_id` (string)

### `warning`
- `payload`:
  - `code` (string enum: `rate_limit`, `data_gap`, `contract_violation`, etc.)
  - `message` (string)
  - `details` (object, optional)

### `error`
- `payload`:
  - `code` (string)
  - `message` (string)
  - `trace` (string optional, sanitized)

### `session_end`
Final event when run completes or aborts.
- `payload`:
  - `status` (`completed`, `failed`, `aborted`)
  - `best_parameter_set_id` (string, optional)
  - `duration_seconds` (float)

### `simulation_summary`
Used during standalone simulation.
- `payload`:
  - `simulation_id` (string)
  - `parameter_set_id` (string)
  - `kpis` (object: `cagr`, `sharpe`, `calmar`, `hit_rate`, `drawdown`, `cost_drag`)
  - `trade_counts` (object: `long`, `short`, `total`)

## Validation
- All events validated against pydantic models in `optimizer/telemetry.py`.
- Unknown event types rejected; logged as errors in CLI/UI.

## Rotation & Retention
- Logger rotates files after 10 MB; rotated files share schema.
- Inspector accepts glob patterns (e.g., `{run_id}.jsonl*`) and merges events chronologically.
