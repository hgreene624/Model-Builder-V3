# Data Model — Model Builder Strategy Profiles

## Entities

### StrategyProfile
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `schema_version` | str | Semantic version for the strategy profile artifact | Must match supported major version |
| `profile_id` | str | Unique identifier (UUID4 hex) | Unique across profiles |
| `name` | str | Display name shown in UI/CLI | 1–80 characters |
| `description` | str | Optional notes | ≤500 characters |
| `portfolio_id` | str | Reference to saved portfolio | Portfolio artifact must exist |
| `train_percentage` | float | Fraction of coverage assigned to training (0–1) | Enforces ≥1 holdout day post-derivation |
| `atr_warmup_days` | int | ATR warmup length in trading days | ≥1; default 14 |
| `parameters` | dict[str, object] | Strategy-specific knobs (ATR window, breakout settings, risk controls) | Validated by profile schema |
| `created_at` | str (ISO 8601) | Creation timestamp | Immutable |
| `updated_at` | str (ISO 8601) | Last modified timestamp | Monotonic |

**Relationships**: References one `Portfolio` artifact; multiple evaluation runs may point to a single profile.

### CoverageWindow
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `portfolio_id` | str | Portfolio providing coverage | Must equal `StrategyProfile.portfolio_id` |
| `coverage_start` | str (ISO date) | Earliest trading day in portfolio data | Derived |
| `coverage_end` | str (ISO date) | Latest trading day | Derived |
| `train_start` | str (ISO date) | Training window start | Derived from slider |
| `train_end` | str (ISO date) | Training window end | < `holdout_start` |
| `holdout_start` | str (ISO date) | Holdout window start | ≥ one trading day after `train_end` |
| `holdout_end` | str (ISO date) | Holdout window end | ≤ `coverage_end` |
| `warmup_start` | str (ISO date) | Warmup start (may precede train window) | Extends into holdout if pre-history insufficient |

### EvaluationRun
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `run_id` | str | Unique run identifier | UUID4 hex |
| `profile_id` | str | Associated strategy profile | Must match saved profile |
| `portfolio_id` | str | Portfolio context | Must match profile |
| `train_window` | CoverageWindow slice | Training segment applied to optimization | Non-empty |
| `holdout_window` | CoverageWindow slice | Testing segment for holdout stats | ≥1 trading day |
| `warmup_window` | CoverageWindow slice | Warmup periods used before holdout | Can overlap holdout |
| `evaluations` | list[CandidateEvaluation] | Chronological candidate records | ≥1 entry |
| `best_candidate_id` | str | Current leader identifier | Must exist in `evaluations` |
| `artifact_paths` | dict[str, str] | References to persisted parity artifacts (parameters, telemetry, visuals) | Relative to storage root |
| `created_at` | str (ISO 8601) | Run creation timestamp | Immutable |

### CandidateEvaluation
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `candidate_id` | str | Genome identifier | Unique per run |
| `score` | float | Fitness score | Higher is better |
| `score_delta` | float | Difference vs prior best | Calculated |
| `metrics` | dict[str, float] | Additional KPIs (CAGR, Calmar, Sharpe) | Required keys |
| `timestamp` | str (ISO 8601) | Evaluation completion time | Monotonic |
| `parameter_payload` | dict[str, object] | Serialized parameter values | Serializable to JSON |

### BestCandidateSnapshot
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `candidate_id` | str | Identifier of leading candidate | Must match evaluation |
| `score` | float | Leader score | ≥ previous best |
| `score_delta` | float | Improvement vs previous leader | ≥0 |
| `parameters` | dict[str, object] | Parameter payload | Mirror evaluation payload |
| `equity_curve_path` | str | Path to holdout equity dataset (CSV/parquet) | File must exist |
| `momentum_heatmap` | dict | 5/10/20/60-day annualized momentum values + narrative | Derived |
| `trade_timeline` | list[dict] | Trade records with P&L classification and funded notional | Chronological |
| `session_cache_key` | str | Identifier for pinned visuals in session state | Unique per browser session |

### TelemetryLog
| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `log_id` | str | Unique log identifier | Derived from `run_id` |
| `event_schema_version` | str | Version of telemetry payloads | Required |
| `events` | list[dict] | Append-only optimization events | Chronological |
| `path` | str | Filesystem path to JSONL log | File must exist |

## Relationships

- `StrategyProfile` → `EvaluationRun` (1-to-many)
- `EvaluationRun` → `CandidateEvaluation` (1-to-many)
- `EvaluationRun` → `BestCandidateSnapshot` (1-to-1)
- `EvaluationRun` → `TelemetryLog` (1-to-1)

## State Transitions

- **StrategyProfile**: `created` → (`updated`)* → `deleted` (physical deletion removes artifact; open access per clarification).
- **EvaluationRun**: `scheduled` → `running` → `completed`; completion requires persistence of telemetry, best candidate snapshot, and artifacts.
- **BestCandidateSnapshot**: `unset` → `published`; updates overwrite prior session snapshot but persist to storage for replay.

## Derived Data Notes

- Rolling-return heatmap derives 5/10/20/60-day annualized momentum arrays plus a narrative string explaining observed trend.
- Trade timeline aggregates holdout trades, annotating each with P&L direction and funded notional to drive bubble sizes.
- Score deltas computed at append time to keep live table rendering constant complexity.
