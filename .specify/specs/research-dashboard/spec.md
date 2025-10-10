# Feature Specification: Self-Hosted Strategy Research Dashboard

**Feature Branch**: `[001-research-dashboard-workspace]`  
**Created**: 2025-10-10  
**Status**: Draft  
**Input**: User description captured in `/specify` request (“Build a self-hosted research dashboard…ATR-breakout baseline…”).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resume Research From Home Overview (Priority: P1)

As a quant researcher, I open the dashboard and immediately see recent portfolios, models, and runs plus data-source status so I can jump back into work without digging through folders.

**Why this priority**: Provides the re-entry point for every workflow; without it, the workspace feels opaque.

**Independent Test**: Launch app with saved artifacts; verify cards render with metadata and missing credentials trigger a fallback indicator while remaining usable.

**Acceptance Scenarios**:

1. **Given** at least one saved portfolio, **When** I load Home, **Then** the portfolio appears with last-edited timestamp and open button.
2. **Given** no credentials in config, **When** Home loads, **Then** I see a warning that public data will be used and the app remains functional.

---

### User Story 2 - Curate and Persist a Portfolio (Priority: P1)

As a researcher, I assemble a stock universe from seed lists, apply filters, preview liquidity stats, cap size, and save it with provenance so future runs use the same selection.

**Why this priority**: Portfolio definition is prerequisite for every strategy run.

**Independent Test**: Start with index constituents, apply filters, save universe, reload it later, and confirm filters/coverage metadata persist.

**Acceptance Scenarios**:

1. **Given** a seed list, **When** I filter by sector and liquidity, **Then** the preview updates with tickers and liquidity stats.
2. **Given** the filtered list, **When** I save the portfolio, **Then** the artifact includes the applied filters, data window, and ticker count.

---

### User Story 3 - Configure and Optimize ATR Breakout (Priority: P1)

As a researcher, I select the ATR breakout model, adjust its parameters and risk-aware sizing bounds, run evolutionary search, track progress, and save top genomes.

**Why this priority**: Establishes the baseline strategy and optimization loop.

**Independent Test**: Run optimization on sample data, confirm progress stream, inspect holdout equity, save best parameter set, and reload it.

**Acceptance Scenarios**:

1. **Given** a saved portfolio and default ATR model, **When** I start optimization, **Then** progress UI streams generations with fitness metrics.
2. **Given** optimization completes, **When** I save the top genome, **Then** it appears in saved parameter sets with summary stats.

---

### User Story 4 - Add and Use a New Model Module (Priority: P2)

As a developer, I drop a new model package into the models directory, have it auto-discovered with parameters rendered in the UI, and optimize it without touching core code.

**Why this priority**: Ensures modular extensibility, a core success metric.

**Independent Test**: Add “Buy-the-Dip + ATR” module, reload app, confirm contract validation, run optimizer, and save/export outputs.

**Acceptance Scenarios**:

1. **Given** a valid model module placed in the models folder, **When** the app boots, **Then** the model appears in the Model Studio selector with its param controls.
2. **Given** the new model selected, **When** I run optimization, **Then** results produce standardized trade intents and export without schema errors.

---

### User Story 5 - Inspect Logs and Benchmark Performance (Priority: P2)

As an engineer/PM, I load optimizer logs, scrub generations, compare equity vs benchmark, and surface cost drag, trade counts, and anomalies.

**Why this priority**: Enables auditing decisions and validating optimizer behavior.

**Independent Test**: Import a log file, navigate generations, view benchmark overlay, open debug metadata panel, and export a report.

**Acceptance Scenarios**:

1. **Given** a log file, **When** I load it, **Then** the timeline displays per-generation metrics and benchmark comparison.
2. **Given** a generation with suspicious metrics, **When** I open debug view, **Then** I see raw telemetry (e.g., config, errors) for root-cause analysis.

---

### User Story 6 - Run and Export Simulation Reports (Priority: P3)

As a researcher, I take a stored genome, run a fresh simulation, review KPIs, and export a model bundle for future headless use.

**Why this priority**: Delivers decision-ready results and portable artifacts.

**Independent Test**: Load saved parameter set, simulate, confirm KPIs and charts render, export bundle, and validate schema via CLI.

**Acceptance Scenarios**:

1. **Given** a saved parameter set, **When** I run simulation, **Then** I receive KPIs (Sharpe, CAGR, drawdown, hit rate) alongside equity and trade charts.
2. **Given** simulation completes, **When** I export the model bundle, **Then** the file includes model metadata, tuned params, and passes CLI validation.

### Edge Cases

- What happens when market credentials are invalid or rate-limited? System MUST fall back to public data and label outputs accordingly.
- How does system handle missing or sparse historical bars for tickers in the universe? Universe builder MUST flag coverage gaps and allow exclusion or interpolation rules.
- What if an imported model omits required contract fields (e.g., missing params metadata)? Auto-discovery MUST reject the module with actionable error messages.
- How are long optimizer runs handled if the UI session drops? Progress MUST persist to disk and resume without corrupting partial runs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a Home view summarizing credentials status and recent portfolios, parameter sets, models, and simulation runs.
- **FR-002**: Portfolio builder MUST support seeding from predefined lists (indexes, CSV imports) and filtering by ticker, sector, and liquidity metrics.
- **FR-003**: Portfolio saves MUST include provenance: filters applied, data coverage window, ticker count, and storage path.
- **FR-004**: Models directory MUST support plug-and-play discovery of Python 3.12 modules implementing the platform contract (`inputs`, `outputs`, `params`, metadata).
- **FR-005**: ATR breakout model MUST expose parameters for ATR window, breakout multiplier, lookback, risk sizing toggle, and min/max sizing rails.
- **FR-006**: Optimizer MUST support evolutionary search with adjustable bounds, deterministic random seeds, pause/resume, and live progress streaming.
- **FR-007**: Holdout evaluation MUST compare equity to a total-return benchmark and surface drawdown, trade counts, cost drag, and rollups.
- **FR-008**: Saved genomes MUST be reusable across UI and CLI, storing parameter values, optimizer stats, and associated portfolio/model IDs.
- **FR-009**: Log inspector MUST parse optimizer logs, surface per-generation metrics, benchmark overlays, and provide raw debug metadata.
- **FR-010**: Simulation engine MUST accept any model + portfolio + parameter set triad, produce standardized KPIs, charts, and trade summaries.
- **FR-011**: Export flow MUST create portable model bundles (model module reference, parameter set, schema version, checksum) suitable for future headless apps.
- **FR-012**: CLI tooling MUST mirror key UI workflows (optimize, inspect logs, run simulation, validate bundles) for headless operation.
- **FR-013**: System MUST persist artifacts in a predictable directory structure (e.g., `data/portfolios/`, `data/models/`, `data/logs/`, `data/runs/`).
- **FR-014**: UI and services MUST follow Python 3.12 best practices: type-annotated services, dataclass-based configs, async-friendly IO when streaming progress.
- **FR-015**: Error handling MUST provide user-facing alerts with remediation steps (credentials missing, data gaps, contract violations).

### Key Entities *(include if feature involves data)*

- **Portfolio**: Named universe containing tickers, filters applied, liquidity stats, data coverage summary, storage path.
- **Model Module**: Python package specifying metadata, parameter schema, strategy logic, and output contract version.
- **Parameter Set (Genome)**: Snapshot of model parameters with fitness metrics, provenance (optimizer config, date), and serialization format.
- **Optimizer Run**: Execution record linking portfolio, model, parameter bounds, seed, progress snapshots, logs, and final genomes.
- **Simulation Report**: Aggregated KPIs, equity curves, trade ledger, benchmark comparison, exportable artifacts.
- **Model Bundle**: Portable package bundling model module reference, tuned parameter sets, contract version, and checksum for headless use.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can curate and save a portfolio with provenance in under 5 minutes using only UI controls.
- **SC-002**: ATR optimization completes on a 200-ticker universe (5-year window) within 10 minutes on a modern laptop, emitting live progress without UI freeze.
- **SC-003**: Newly added model modules are auto-discovered and usable without modifying core code in ≥95% of trials during acceptance testing.
- **SC-004**: Benchmark comparison and KPI report are available within 30 seconds after simulation completion with <5% discrepancy against reference calculations.
- **SC-005**: Exported model bundles pass CLI validation and reload successfully in the UI on the first attempt at least 9 out of 10 times during QA.
