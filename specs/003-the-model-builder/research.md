# Phase 0 Research — Model Builder Strategy Profiles

## Decision Log

### 1. Strategy profile persistence format
- **Decision**: Persist strategy profiles as JSON artifacts stored under `storage/strategy_profiles/` with a `schema_version`, `profile_id`, and full parameter payload.
- **Rationale**: JSON keeps parity with existing portfolio artifacts, enables schema versioning required by the constitution, and is easily consumed by both Streamlit and CLI flows without extra dependencies.
- **Alternatives considered**:
  - **YAML**: More human-readable but adds a new parser dependency and complicates schema enforcement.
  - **SQLite**: Provides richer querying but introduces migration overhead and exceeds the lightweight storage needs for ≤20 profiles.

### 2. Warmup handling when history is short
- **Decision**: Extend the ATR warmup window into the testing range when insufficient pre-test history exists, then start holdout statistics only after the warmup slice completes.
- **Rationale**: Aligns with clarification outcome, guarantees training starts at the desired test boundary, and avoids blocking runs for sparse datasets.
- **Alternatives considered**:
  - **Reject the run**: Prevents misaligned stats but harms usability when minor gaps exist.
  - **Shrink warmup length**: Keeps testing untouched but undermines the strategy requirements tied to ATR smoothing.

### 3. Live evaluations retention model
- **Decision**: Reset the live evaluations table at the beginning of each evolutionary run while preserving all candidate rows generated during that run.
- **Rationale**: Matches clarified scope, prevents cross-run contamination, and keeps session memory bounded for long-running research days.
- **Alternatives considered**:
  - **Session-wide accumulation**: Provides more history but complicates interpreting current run performance.
  - **Persist to disk automatically**: Useful for audits but unnecessary for the immediate UX and increases I/O during hot loops.

### 4. Visualization toolkit for best-candidate insights
- **Decision**: Use Plotly to render the holdout equity curve, rolling-return heatmap, and trade timeline.
- **Rationale**: Plotly is already bundled, supports synchronized hover interactions across visuals, and handles momentum heatmaps plus timeline sizing without bespoke D3 work.
- **Alternatives considered**:
  - **Altair**: Declarative and concise, but adds another dependency and struggles with large scatter timelines.
  - **Matplotlib static images**: Lightweight yet fails the interactive exploration expectations for holdout analysis.

### 5. Telemetry and replay logging
- **Decision**: Emit structured JSONL logs per run containing candidate evaluations, coverage windows, and profile metadata, stored under `storage/evaluations/`.
- **Rationale**: Satisfies the spec’s replay requirement (FR-016), keeps artifacts append-only for auditability, and lets CLI tooling reconstruct runs without re-simulation.
- **Alternatives considered**:
  - **In-memory session cache only**: Simple but prevents post-run analysis and breaks CLI parity.
  - **Database-backed event store**: Powerful yet disproportionate for the current single-user scope.
