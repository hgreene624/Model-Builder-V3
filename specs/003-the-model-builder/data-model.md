# Data Model — Model Builder Strategy Profiles

## Entities

### StrategyProfile
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `schema_version` | str | Semantic version of the artifact schema | Must equal latest supported major version |
| `profile_id` | str | Deterministic identifier (UUID4 hex) | Unique across all profiles |
| `name` | str | Human-friendly label shown in UI | 1–80 characters |
| `description` | str | Optional notes for researchers | ≤500 characters |
| `portfolio_id` | str | Reference to saved portfolio artifact | Must exist in `storage/portfolios/` |
| `train_percentage` | float | Portion of coverage dedicated to training (0–1) | Enforces ≥1 holdout day when applied |
| `atr_warmup_days` | int | Warmup length in trading days | ≥1; default 14 |
| `parameters` | dict[str, Any] | Strategy-specific knobs (ATR window, breakout, risk) | Validated via Pydantic model |
| `created_at` | str (ISO 8601) | Creation timestamp | Immutable |
| `updated_at` | str (ISO 8601) | Last updated timestamp | Monotonic |

**Relationships**: References one `Portfolio` artifact; linked to many `EvaluationRun` records through `profile_id`.

### CoverageWindow
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `portfolio_id` | str | Associated portfolio | Must match `StrategyProfile.portfolio_id` |
| `coverage_start` | str (ISO date) | Earliest available trading day | Derived from portfolio |
| `coverage_end` | str (ISO date) | Latest available trading day | Derived from portfolio |
| `train_start` | str (ISO date) | First training day | Calculated from slider |
| `train_end` | str (ISO date) | Final training day | < `holdout_start` |
| `holdout_start` | str (ISO date) | First holdout day | ≥ one day after `train_end` |
| `holdout_end` | str (ISO date) | Final holdout day | ≤ `coverage_end` |
| `warmup_start` | str (ISO date) | earliest day used for ATR warmup | May precede `train_start`; extends into holdout if needed |

### EvaluationRun
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `run_id` | str | Unique identifier per run | UUID4 hex |
| `profile_id` | str | Strategy profile used | Must match saved profile |
| `portfolio_id` | str | Portfolio context | Must match profile |
| `train_window` | CoverageWindow slice | Window applied to optimization | Non-empty |
| `holdout_window` | CoverageWindow slice | Window applied to stats | ≥1 trading day |
| `warmup_window` | CoverageWindow slice | Warmup dates used prior to holdout | Can overlap holdout |
| `evaluations` | list[CandidateEvaluation] | Chronological holdout measurements | At least 1 |
| `best_candidate_id` | str | Candidate promoted as leader | Must exist in `evaluations` |
| `artifact_paths` | dict[str, str] | References to persisted JSONL, equity curves, parameter sets | Paths relative to storage root |
| `created_at` | str (ISO 8601) | Run timestamp | Immutable |

### CandidateEvaluation
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `candidate_id` | str | Identifier of evaluated genome | Unique per run |
| `score` | float | Primary fitness metric | Higher is better |
| `score_delta` | float | Delta vs previous best | Calculated column |
| `metrics` | dict[str, float] | Additional fitness KPIs | Contains CAGR, Calmar, Sharpe |
| `timestamp` | str (ISO 8601) | When evaluation finished | Monotonic |
| `parameter_payload` | dict[str, Any] | Parameters submitted to backtest | Serializable |

### BestCandidateSnapshot
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `candidate_id` | str | Key of the leading candidate | Must match evaluation |
| `score` | float | Leader score | Equal to best `CandidateEvaluation.score` |
| `score_delta` | float | Improvement over prior leader | Non-negative |
| `parameters` | dict[str, Any] | Serialized parameters | Matches strategy schema |
| `equity_curve_path` | str | Location of holdout equity data | Points to parquet/CSV |
| `momentum_heatmap` | dict | Structured values for 5/10/20/60-day momentum | Derived at promotion time |
| `trade_timeline` | list[dict] | Trade records enriched with P&L and notional | Sorted chronologically |
| `session_cache_key` | str | Identifier for Streamlit session state | Unique per session |

### TelemetryLog
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `log_id` | str | Unique identifier per log file | Derived from `run_id` |
| `events` | list[dict] | Optimization lifecycle events | Append-only |
| `event_schema_version` | str | Versioning for telemetry format | Required for replay |
| `path` | str | Filesystem path to JSONL log | Must exist |

## Relationships Overview

- `StrategyProfile` **1—n** `EvaluationRun`
- `EvaluationRun` **1—n** `CandidateEvaluation`
- `EvaluationRun` **1—1** `BestCandidateSnapshot`
- `EvaluationRun` **1—1** `TelemetryLog`

## State Transitions

- **StrategyProfile**: `created` → `active` → (`updated`)* → `deleted` (physical delete removes artifact). Profiles are globally writable per clarification; no ownership state machine.
- **EvaluationRun**: `scheduled` → `running` → `completed`. A run only enters `completed` when best candidate artifacts and telemetry log are flushed.
- **BestCandidateSnapshot**: `unset` → `published`. Every promotion overrides the prior snapshot; Streamlit pins the latest within the session cache.

## Derived Data

- **Rolling-return heatmap**: computed from holdout equity using 5/10/20/60-day annualized returns, stored as four arrays plus descriptive blurb to support rehydration without recomputation.
- **Trade timeline**: derived by joining backtest trades with equity timestamps, enriching each trade with P&L classification and funded notional sizing for bubble charts.
- **Score deltas**: computed lazily when adding an evaluation to ensure accurate live table rendering.
