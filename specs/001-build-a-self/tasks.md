# Tasks: Self-Hosted Strategy Research Dashboard

**Input**: Specification, plan, research, data model, and contracts in `specs/001-build-a-self/`  
**Prerequisites**: `spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/`

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 [P] Establish Python 3.12 virtualenv and install pinned `requirements.txt` / `requirements-dev.txt`
- [x] T002 [P] Scaffold Streamlit entrypoint `Home.py` and `pages/` directory structure per plan
- [x] T003 [P] Configure linting/formatting (`ruff.toml`, `pyproject` or `black` config) and add pre-commit hooks if desired
- [x] T004 Define `requirements.txt` and `requirements-dev.txt` pins for Streamlit, pandas, numpy, plotly, yfinance, alpaca-py, pytest, ruff, black

---

## Phase 2: Foundational (Blocking Prerequisites)

- [x] T010 Implement configuration module `src/config/settings.py` resolving `DATA_DIR`, provider preference, Alpaca credentials
- [x] T011 [P] Build storage layout helpers in `src/storage/layout.py` with atomic write utilities and schema version constants
- [x] T012 [P] Implement data cache (`src/data/cache.py`) with in-memory LRU and parquet shard management
- [x] T013 [P] Implement provider clients `src/data/providers/alpaca_client.py` and `src/data/providers/yahoo_client.py` with unified interface
- [x] T014 Create market data loader `src/data/loader.py` that integrates cache tiers, warmup logic, and provider fallback
- [x] T015 Define shared contracts/dataclasses in `src/models/contracts.py` (Portfolio, ParameterSet, BacktestResult, Telemetry events)
- [x] T016 Implement `src/storage/artifacts.py` for portfolios/parameters/simulations/logs CRUD respecting schema versions
- [x] T017 Set up CLI shell `src/cli/main.py` with command group scaffolding (no business logic yet)
- [x] T018 Configure pytest (`pytest.ini`, fixtures folder) and add smoke tests covering provider failover + cache stub
- [x] T019 Set up observability base: `TrainingLogger` class writing JSONL with rotation under `storage/logs/`

**Checkpoint**: Core infrastructure ready; user story implementation can proceed in parallel.

---

## Phase 3: User Story 1 — Resume Research from Home Overview (Priority: P1) 🎯

**Goal**: Home screen shows credential status, summary cards for recent artifacts, and Yahoo fallback indicator.  
**Independent Test**: Launch Home in Streamlit with seeded artifacts; verify listings and status banners render correctly.

### Tests (Recommended)
- [x] T101 [P] Add integration test `tests/integration/test_home_dashboard.py` using Streamlit testing utilities to verify artifact listings and fallback banner

### Implementation
- [x] T102 [US1] Implement `Home.py` sections: credential check (Alpaca vs Yahoo), recent portfolios/parameters/simulations/logs overview
- [x] T103 [US1] Add storage query helpers to fetch recent artifacts (ordered by `updated_at`)
- [x] T104 [US1] Add CLI command `status` summarizing credential state and recent artifacts
- [x] T105 [US1] Wire Home navigation to Streamlit pages and ensure session state carries selected artifact IDs

---

## Phase 4: User Story 2 — Curate and Save a Portfolio (Priority: P1)

**Goal**: Portfolio builder page loads seed lists, applies filters, previews liquidity stats, caps universe size, saves with provenance.  
**Independent Test**: Run through portfolio creation using sample CSV and confirm saved JSON matches filters and coverage metadata.

### Tests
- [x] T201 [P] Add unit tests for filter logic and liquidity stats in `tests/unit/test_portfolio_builder.py`
- [x] T202 [P] Add integration test `tests/integration/test_portfolio_save.py` to ensure saved artifact includes provenance
- [x] T206A [P] Add unit test for `portfolio curate` CLI command in `tests/unit/test_portfolio_cli.py`

### Implementation
- [x] T203 [US2] Implement `pages/1_Portfolio_Curator.py` with seed list import, filters, preview table, capped ticker selection
- [x] T204 [US2] Extend loader to compute liquidity stats (median price, dollar volume) using cached shards
- [x] T205 [US2] Implement `src/storage/artifacts.py` helpers for creating/updating `Portfolio` artifacts with schema version
- [x] T206 [US2] Add CLI command `portfolio curate` supporting CSV/index seeds and same filters
- [x] T207 [US2] Provide provenance display in UI (filters, coverage window, tickers count) after save
- [x] T208 [US2] Add Portfolio Curator debug diagnostics (cache/provider attempts, error reporting toggle) to aid data-source troubleshooting

---

## Phase 5: User Story 3 — Configure and Optimize ATR Baseline (Priority: P1)

**Goal**: Model builder page selects ATR strategy, tunes parameters/bounds, runs evolutionary optimization with live telemetry, saves genomes.  
**Independent Test**: Execute optimization on sample portfolio; verify telemetry stream, saved parameter set, and holdout equity chart.

### Tests
- [ ] T301 [P] Unit tests for ATR strategy sizing and signal generation `tests/unit/test_atr_breakout.py`
- [ ] T302 [P] Unit tests for evolutionary objective weighting and constraints `tests/unit/test_evolutionary.py`
- [ ] T303 [P] Integration test `tests/integration/test_optimizer_run.py` verifying telemetry output and saved genome

### Implementation
- [ ] T304 [US3] Implement ATR breakout strategy in `src/engine/atr_breakout.py` with risk-aware sizing toggle
- [ ] T305 [US3] Build backtest engine `src/engine/backtest.py` returning `BacktestResult` with KPI calculations
- [ ] T306 [US3] Implement optimizer driver `src/optimizer/evolutionary.py` (multiprocessing evaluation, weighted objective, gates)
- [ ] T307 [US3] Implement telemetry publisher `src/optimizer/telemetry.py` integrating with `TrainingLogger`
- [ ] T308 [US3] Create Streamlit page `pages/2_Model_Builder.py` with parameter controls, bounds, telemetry display, save genome actions
- [ ] T309 [US3] Add CLI command `optimize` mirroring UI flow with JSON output and console summary
- [ ] T310 [US3] Persist best genomes via `storage/artifacts.py` and update portfolio provenance if needed

---

## Phase 6: User Story 4 — Add and Use a New Model Module (Priority: P2)

**Goal**: Enable drop-in models to auto-register, surface parameters/UI controls, and participate in optimization without code changes.  
**Independent Test**: Install sample “Buy-the-Dip + ATR overlay” plugin, confirm discovery, run optimization, verify outputs.

### Tests
- [ ] T401 [P] Contract tests for model registry validation `tests/contract/test_model_contract.py`
- [ ] T402 [P] Integration test `tests/integration/test_model_autodiscovery.py` using a dummy plugin

### Implementation
- [ ] T403 [US4] Implement model registry `src/models/registry.py` scanning package paths and enforcing `model-contract.md`
- [ ] T404 [US4] Extend `pages/2_Model_Builder.py` UI to render dynamic parameter controls from registry metadata
- [ ] T405 [US4] Update CLI `optimize` command to accept dynamic model IDs and parameter defaults
- [ ] T406 [US4] Provide developer documentation snippet in `docs/models.md` (or update Quickstart) for plugin packaging
- [ ] T407 [US4] Add validation messaging in UI/CLI when contract errors occur

---

## Phase 7: User Story 5 — Log Inspection & Benchmark Review (Priority: P2)

**Goal**: Log inspector page loads JSONL telemetry, scrubs generations, overlays benchmark, surfaces costs/trade counts, exposes debug metadata.  
**Independent Test**: Load sample log, navigate generations, confirm benchmark charts and debug drawer work.

### Tests
- [ ] T501 [P] Add parser tests `tests/unit/test_log_parser.py` ensuring telemetry schema coverage
- [ ] T502 [P] Integration test `tests/integration/test_log_inspector.py` validating Streamlit interactions

### Implementation
- [ ] T503 [US5] Implement telemetry parser utilities in `src/optimizer/log_reader.py`
- [ ] T504 [US5] Build Streamlit page `pages/3_Log_Inspector.py` with generation timeline, benchmark chart (Plotly), cost/trade summary, debug view
- [ ] T505 [US5] Implement CLI command `logs inspect` with summary output and optional CSV export
- [ ] T506 [US5] Ensure benchmark data loaded from `storage/benchmarks/` (download if missing) and cached
- [ ] T507 [US5] Add filters/bookmarks for noteworthy generations (errors, warnings)

---

## Phase 8: User Story 6 — Simulate and Export Results (Priority: P3)

**Goal**: Simulation page runs fresh backtest using stored parameter set, displays KPIs/charts, and exports bundle for headless trading.  
**Independent Test**: Execute simulation from saved genome, inspect KPIs, export bundle, validate artifact.

### Tests
- [ ] T601 [P] Unit tests for bundle assembler `tests/unit/test_bundle_export.py`
- [ ] T602 [P] Integration test `tests/integration/test_simulation_review.py` verifying KPIs and export flow

### Implementation
- [ ] T603 [US6] Implement Streamlit page `pages/4_Simulation_Review.py` with parameter selection, run controls, KPI charts, export CTA
- [ ] T604 [US6] Extend `src/engine/backtest.py` to support replays with arbitrary parameter sets and cost assumptions
- [ ] T605 [US6] Implement bundle exporter in `src/storage/artifacts.py` producing ZIP with manifest
- [ ] T606 [US6] Add CLI command `simulate` + `bundle export`, ensuring JSON summaries
- [ ] T607 [US6] Ensure Home dashboard updates with new simulation/bundle artifacts after completion

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T701 Update documentation (`quickstart.md`, `docs/`) with credential guidance, CLI usage, plugin instructions
- [ ] T702 Accessibility & UI polish: ensure charts/tables readable, add tooltips, handle empty states
- [ ] T703 Performance tuning: profile cache hits, optimizer multiprocessing, telemetry latency
- [ ] T704 Add monitoring for storage usage and log rotation thresholds
- [ ] T705 Final QA regression: run pytest suite, lint, black, manual verification across user stories
- [ ] T706 Prepare release notes summarizing supported workflows and known limitations

---

## Phase Dependencies

- Setup (Phase 1) → Foundational (Phase 2) → User Stories (Phases 3–8) → Polish (Phase 9).
- User stories can proceed in parallel after Phase 2; respect priority order for MVP delivery (P1 first).

## Parallel Opportunities

- Tasks marked `[P]` have no file conflicts and can run concurrently.
- Different user stories can be owned by separate teammates once foundation stabilizes.
