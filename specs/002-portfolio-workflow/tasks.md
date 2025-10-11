# Tasks: Portfolio Workflow Overhaul

**Input**: `spec.md`, `plan.md`, existing contracts in `src/models/contracts.py`

## Phase 0: Foundationsalmost
- [X] T001 Document index universe JSON schema and create `storage/index_universes/` scaffold.
- [X] T002 Capture portfolio metadata additions (coverage, shard hints) and update contracts outline.

## Phase 1: Universe Loading & Filtering
- [X] T101 Implement index universe loader utility (`src/data/universe_loader.py`) with tests.
- [X] T102 Persist selected universe in Streamlit session state and expose search + sector filters.
- [X] T103 Add max-symbol cap control with live counts and priors window stamping.
- [X] T104 Replace max-symbol slider with numeric input control.

## Phase 2: Liquidity Fetch & Thresholding
- [X] T201 Extend `MarketDataLoader` (or helper) to return coverage ranges and shard metadata.
- [X] T202 Implement “Fetch Liquidity” action on the portfolios page with loading states and error messaging.
- [X] T203 Add median price / dollar-volume threshold filters and highlight insufficient coverage.

## Phase 3: Draft Portfolio Assembly
- [X] T301 Build selection UI (multi-select + add/remove) and maintain draft portfolio in session state.
- [X] T302 Display draft pori made some changes to the portdfoliotfolio table with aggregate liquidity stats and priors window summary.
- [X] T303 Prevent duplicates and allow clearing selections.

## Phase 4: Persistence & Management
- [X] T401 Update `Portfolio` contract + storage helpers to include coverage + shard hints (bump schema_version).
- [X] T402 Implement “Save Portfolio” action with confirmation and success messaging.
- [X] T403 Add delete controls (UI + CLI) and ensure storage cleanup + UI refresh.
- [X] T404 Extend CLI `portfolio curate`/`portfolio delete` to support new workflow parameters.

## Phase 5: QA & Docs
- [X] T501 Update documentation / README with new workflow instructions.
- [X] T502 Add/refresh tests: unit, integration, CLI for the new flow.
- [X] T503 Run full regression (`pytest`, lint) and summarize release notes.
