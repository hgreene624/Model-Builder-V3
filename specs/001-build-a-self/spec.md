# Feature Specification: Self-Hosted Strategy Research Dashboard

**Feature Branch**: `[001-build-a-self]`  
**Created**: 2025-10-10  
**Status**: Draft  
**Input**: User description: "/specify Build a self-hosted research dashboard…"

## User Scenarios & Testing *(mandatory)*

## Clarifications

### Session 2025-10-10

- Q: When premium credentials are absent we need a default public data pipeline. Which fallback source should the dashboard ship with? → A: Yahoo Finance
- Q: CLI parity is critical, but we need to lock how results (optimizer runs, simulations) should be emitted for headless workflows. What is the default presentation? → A: JSON files written to disk plus brief console summary
- Q: To size storage and defaults we need the standard historical lookback for new portfolios. What window should the app propose when coverage allows? → A: 5 years of daily bars

### User Story 1 - Resume Research from Home Overview (Priority: P1)

A quantitative researcher opens the workspace and instantly sees which data sources are available plus recently saved portfolios, parameter sets, and simulations so work can resume without hunting through folders.

**Why this priority**: Every other journey depends on clear entry points and awareness of saved artifacts; without it users waste time reassembling context.

**Independent Test**: With existing artifacts in storage, launch the app and confirm the Home view lists them with timestamps and clearly indicates whether premium or fallback market data will be used.

**Acceptance Scenarios**:

1. **Given** at least one saved portfolio, **When** the Home page loads, **Then** the portfolio appears with name, last edited date, and an action to open it.
2. **Given** premium market credentials are missing, **When** the Home page loads, **Then** the page shows a warning and explains that a public data source will be used instead while keeping functionality available.

---

### User Story 2 - Curate and Save a Portfolio (Priority: P1)

A researcher assembles a stock universe from common indexes or imported lists, filters by naming, sector, and liquidity thresholds, reviews summary stats, caps the size, normalizes ticker symbols, and saves the resulting portfolio with provenance.

**Why this priority**: A curated universe is required before any optimization or simulation can start.

**Independent Test**: Start from a seed list, apply filters, preview liquidity stats, cap the ticker count, save the portfolio, and reload it later to confirm filters and coverage details persist.

**Acceptance Scenarios**:

1. **Given** a selected seed list, **When** the user applies liquidity and sector filters, **Then** the preview updates with the filtered tickers and displays median price and dollar volume for the configured window.
2. **Given** the filtered universe, **When** the user saves the portfolio, **Then** the saved record includes applied filters, data coverage dates, ticker count, and a normalized ticker file.
3. **Given** network or credential issues during preview, **When** the user enables diagnostics, **Then** the UI surfaces per-symbol fetch attempts (cache hit state, provider used, and error text) so remediation steps are clear.

---

### User Story 3 - Configure and Optimize the ATR Baseline (Priority: P1)

A researcher chooses the default ATR breakout model, adjusts its parameters and risk-aware sizing rails, launches an evolutionary optimization run, monitors live progress, and saves the best-performing parameter sets for later use.

**Why this priority**: Demonstrates the full modeling loop and delivers the baseline strategy expected by stakeholders.

**Independent Test**: Load a portfolio, start optimization, observe progress updates, inspect the holdout equity curve, save the top genome, and confirm it appears in stored parameter sets with summary metrics.

**Acceptance Scenarios**:

1. **Given** a curated portfolio and selected ATR model, **When** optimization begins, **Then** the workspace streams generation-by-generation metrics including fitness scores and equity snapshots.
2. **Given** optimization completes, **When** the user saves a genome, **Then** it is stored with parameter values, performance metrics, and links to the portfolio and model.
3. **Given** the researcher adjusts train percentage or warmup values in the Model Builder profile editor, **When** the optimization workspace renders coverage details, **Then** the summary banner, coverage table, and holdout equity preview immediately reflect the active (unsaved) form state without requiring a profile save.

---

### User Story 4 - Add and Use a New Model Module (Priority: P2)

A developer drops a new strategy into the models directory; the workspace auto-discovers it, renders its tunable parameters in the Model Studio, and allows optimization using the same workflow as the ATR baseline without additional wiring.

**Why this priority**: Modularity is a core promise; failure here blocks future strategy innovation.

**Independent Test**: Add a “Buy-the-Dip + ATR overlay” module following the defined contract, reboot the app, confirm it appears in the selector, run optimization, and verify the outputs are stored with standard metadata.

**Acceptance Scenarios**:

1. **Given** a contract-compliant model module is added, **When** the workspace loads, **Then** the model appears in the selector with its parameter controls and descriptions.
2. **Given** the new model is selected, **When** optimization completes, **Then** saved genomes and logs use the same structure as the baseline model with no schema errors.

---

### User Story 5 - Inspect Optimizer Logs and Compare Benchmarks (Priority: P2)

An engineer or PM loads optimizer logs, scrubs through generations, compares strategy equity to a total-return benchmark, reviews cost drag and trade counts, and opens a detailed debug panel when results look suspicious.

**Why this priority**: Decision makers need trustworthy diagnostics before promoting a strategy.

**Independent Test**: Import a log file, navigate generations, confirm equity vs benchmark charts render, inspect cost and trade summaries, open debug metadata for a single generation, and export findings.

**Acceptance Scenarios**:

1. **Given** a stored optimizer log, **When** it is loaded, **Then** the interface shows a selectable generation timeline with benchmark comparison and cost metrics for each step.
2. **Given** a generation is flagged, **When** the debug view opens, **Then** it displays the configuration snapshot, errors (if any), and relevant breadcrumbs for diagnosis.

---

### User Story 6 - Simulate and Export Results (Priority: P3)

A researcher selects a stored parameter set, runs a fresh simulation, reviews KPIs such as Sharpe, CAGR, drawdown, and hit rate, and exports the run as a bundle the headless app can consume later.

**Why this priority**: Produces decision-ready artifacts and ensures future portability toward automated trading.

**Independent Test**: Load a saved genome, execute simulation, confirm KPIs and charts render, export a bundle, and validate the bundle contents are complete.

**Acceptance Scenarios**:

1. **Given** a saved parameter set, **When** simulation is run, **Then** the workspace returns KPIs, equity curves, trade counts, and benchmark comparisons within the same session.
2. **Given** the simulation finishes, **When** the user exports the bundle, **Then** the exported package contains model metadata, parameter values, provenance, and passes validation for headless re-use.

### Edge Cases

- Marketplace credentials unavailable or invalid: the system must fall back to Yahoo Finance data, label the session accordingly, and block actions that require premium-only coverage.
- Sparse or missing historical bars for selected tickers: portfolio builder must flag coverage gaps from the five-year default window, allow removal or substitution, and ensure downstream runs record the gaps.
- Model module fails contract validation: the workspace must reject it with actionable guidance and keep existing models available.
- Long-running optimization interrupted (app closes or connection drops): progress must be checkpointed so the run can resume without data loss.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Home view must summarize credential status, indicate when Yahoo Finance fallback is active, and list the most recent portfolios, parameter sets, models, simulations, and logs with quick actions.
- **FR-002**: The portfolio builder must ingest seed lists, support filtering by name, sector, liquidity, and cap the universe size with real-time previews of coverage stats.
- **FR-003**: Each saved portfolio must capture provenance including filters applied, data window, ticker count, and normalized identifiers so it can be restored consistently.
- **FR-004**: The system must enforce a shared model contract defining required inputs, outputs, and parameter metadata, and auto-discover compliant models placed in the designated directory.
- **FR-005**: The ATR breakout model must expose tunable parameters for ATR window, breakout multiplier, lookback period, risk-aware sizing toggle, and minimum/maximum sizing rails.
- **FR-006**: Optimization runs must support configurable parameter bounds, deterministic seeds, pause/resume controls, live progress updates, and holdout equity visualization.
- **FR-006a**: Coverage summaries and holdout graphs on the optimization page must derive from the in-session editor state, applying unsaved adjustments (e.g., train percentage, warmup days) before persistence so previews stay aligned with the next run configuration.
- **FR-007**: The platform must compute and display benchmark comparisons, trade counts, cost drag, and rolling performance for each optimization run and simulation.
- **FR-008**: Saved parameter sets must remain reusable across UI and CLI experiences, including fitness metrics, references to source portfolio/model, and timestamps.
- **FR-009**: The log inspector must parse stored logs into per-generation records, support filtering and bookmarking, and surface detailed metadata for debugging.
- **FR-010**: Simulation workflows must accept any combination of portfolio, model, and parameter set, producing standardized KPIs, equity curves, and trade ledgers.
- **FR-011**: Users must be able to export model bundles containing the strategy description, tuned parameters, provenance, and compatibility metadata for future headless execution.
- **FR-012**: Core actions (optimize, inspect logs, simulate, validate bundles) must also be executable through a CLI using the same contracts and storage locations as the UI, writing JSON results to disk and emitting a brief console summary.
- **FR-013**: All artifacts must be stored under a predictable local folder hierarchy with naming conventions that make them discoverable by type, date, and user-supplied labels.
- **FR-014**: The system must surface user-friendly error messages with remediation steps whenever data coverage, credentials, or model contracts prevent progression.
- **FR-015**: The workspace must record audit trails for key actions (portfolio saved, model added, optimization completed, bundle exported) to support later review.

### Key Entities *(include if feature involves data)*

- **Portfolio**: Named collection of tickers with recorded filters, liquidity stats, coverage window, capped size, and storage reference.
- **Model Module**: Strategy definition containing metadata, parameter schema, contract compliance flag, and version notes.
- **Parameter Set (Genome)**: Captured parameter values from optimization runs alongside performance metrics, source portfolio/model IDs, and creation timestamps.
- **Optimizer Run**: Time-stamped record linking portfolio, model, parameter bounds, random seed, progress snapshots, logs, and winning genomes.
- **Simulation Report**: Result package capturing KPIs, equity curve, trade ledger, benchmark comparison, and links to source inputs.
- **Model Bundle**: Portable artifact combining a model module, selected parameter sets, compatibility metadata, and verification checksum.
- **Credential Profile**: Stored indication of available market data credentials, their status, and fallback notes for data sourcing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Researchers can curate and save a portfolio with provenance in under 5 minutes using only the workspace UI.
- **SC-002**: Optimization of the ATR baseline on a 200-ticker, five-year dataset completes within 10 minutes while streaming progress updates without UI freezes.
- **SC-003**: Newly added model modules that follow the contract appear in the Model Studio and run end-to-end without manual wiring in at least 95% of onboarding attempts.
- **SC-004**: Benchmark comparison, KPI summary, and trade metrics become available within 30 seconds after a simulation finishes, with less than 5% variance from reference calculations.
- **SC-005**: Exported model bundles pass validation through both UI and CLI on the first attempt at least 90% of the time during acceptance testing.
- **SC-006**: At least 90% of usability test participants report they can understand whether a strategy beats the benchmark, including drawdown and trade cost impacts, after a single review session.

## Assumptions

- Researchers work on single-user local environments where filesystem access is available and storage quotas are sufficient for historical data.
- Premium market data credentials, when provided, are handled outside the scope of this feature; the app only verifies their presence and status.
- Evolutionary optimization is the primary tuning approach; additional optimization methods will be evaluated later if needed.
