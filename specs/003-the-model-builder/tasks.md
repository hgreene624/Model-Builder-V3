# Tasks: Model Builder Strategy Profiles

**Input**: Design documents from `/specs/003-the-model-builder/`
**Prerequisites**: plan.md, spec.md, research.md, contracts/

**Tests**: The spec and constitution require automated coverage; each user story includes targeted test tasks.

**Organization**: Tasks are grouped by user story to keep increments independently deliverable.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Task can run in parallel (affects different files, no ordering dependency)
- **[Story]**: Story label (Setup, Foundation, US1, US2, US3)
- Include concrete file paths in every description

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish package scaffolding so subsequent work lands under `model_builder`.

- [ ] T001 [Setup] Create package skeleton per plan: add `src/model_builder/{profiles,optimization,analytics,ui,cli}/__init__.py` and matching `tests/model_builder/.../.gitkeep`.
- [ ] T002 [P] [Setup] Update `pyproject.toml` packaging section so `model_builder` package is included in distribution.
- [ ] T003 [P] [Setup] Configure `src/model_builder/__init__.py` to expose top-level namespaces (`profiles`, `optimization`, `analytics`, `ui`, `cli`) for Streamlit/CLI imports.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain and storage utilities required by all stories.

**⚠️ CRITICAL**: Complete before starting user story implementation.

- [ ] T004 [Foundation] Define shared constants in `src/model_builder/profiles/constants.py` (e.g., `PROFILE_SCHEMA_VERSION`, default warmup days).
- [ ] T005 [Foundation] Extend `src/storage/layout.py` to add helpers for `strategy_profiles/` and `evaluations/` directories plus ensure they are created.
- [ ] T006 [P] [Foundation] Implement `src/model_builder/profiles/models.py` dataclasses (StrategyProfile, CoverageWindow) with validation helpers used across stories.
- [ ] T007 [P] [Foundation] Implement `src/model_builder/optimization/coverage.py` functions to derive train/holdout/warmup windows (enforcing ≥1 holdout day, extending warmup when necessary).
- [ ] T008 [Foundation] Create telemetry log writer base in `src/model_builder/optimization/telemetry.py` that emits JSONL envelopes and returns log paths (supports FR-016).

**Checkpoint**: Foundation ready — user stories can now proceed.

---

## Phase 3: User Story 1 — Configure Strategy Profile And Run Training (Priority: P1) 🎯 MVP

**Goal**: Researchers manage strategy profiles and execute runs with correct train/holdout/warmup behavior.

**Independent Test**: Load, edit, and save a profile, then start an optimization run while verifying train/test dates and warmup placement follow the settings.

### Tests for User Story 1

- [ ] T009 [P] [US1] Add repository unit tests for load/save round trips in `tests/model_builder/profiles/test_repository.py`.
- [ ] T010 [P] [US1] Add coverage derivation integration test in `tests/model_builder/optimization/test_coverage_flow.py` (train/holdout split, warmup extension).

### Implementation for User Story 1

- [ ] T011 [US1] Implement JSON repository in `src/model_builder/profiles/repository.py` (list/load/save/delete under `storage/strategy_profiles/` with schema version check).
- [ ] T012 [US1] Add service layer in `src/model_builder/profiles/service.py` to orchestrate repository operations and expose CLI-friendly DTOs.
- [ ] T013 [US1] Wire Click commands in `src/model_builder/cli/model_builder.py` for listing, saving, deleting profiles (align with contracts `/strategy-profiles` endpoints).
- [ ] T014 [US1] Update optimizer workflow (`src/optimizer/workflow.py`) to consume `model_builder.optimization.coverage` outputs and restrict optimization to training window.
- [ ] T015 [US1] Update Streamlit entry page `pages/2_Model_Builder.py` to delegate to `model_builder.ui.pages.model_builder_page.run_page`, sourcing profiles via new service and honoring warmup logic.
- [ ] T016 [US1] Implement UI component `src/model_builder/ui/components/profile_editor.py` handling create/save/delete with confirmation, reflecting open-access assumption.
- [ ] T017 [US1] Ensure CLI command results persist replay metadata (run IDs, parameter paths) to seed later stories (write to storage/evaluations via telemetry base).

**Checkpoint**: MVP ready — User Story 1 independently testable.

---

## Phase 4: User Story 2 — Monitor Live Holdout Evaluations (Priority: P2)

**Goal**: Live table captures every candidate evaluated during a run, resets per run, and records telemetry for replay.

**Independent Test**: Trigger an evolutionary run emitting candidate scores and confirm the table appends each row (with score, delta, timestamp, payload) while retaining prior rows from the same run only.

### Tests for User Story 2

- [ ] T018 [P] [US2] Add telemetry log replay test in `tests/model_builder/optimization/test_telemetry_log.py` to ensure candidate events append and reset per run.
- [ ] T019 [P] [US2] Add Streamlit component test using `streamlit.testing` (or mock) in `tests/model_builder/ui/test_live_evaluations_component.py` to assert reset-on-run behavior and column schema.

### Implementation for User Story 2

- [ ] T020 [US2] Implement evaluation appender in `src/model_builder/optimization/runner.py` that streams candidate events to telemetry writer and returns session payloads.
- [ ] T021 [US2] Add session-scoped state manager in `src/model_builder/ui/components/live_evaluations.py` that resets table on new run ID and appends candidate rows.
- [ ] T022 [US2] Update Streamlit page `model_builder_page.py` to subscribe to telemetry events, render the live evaluations component, and surface score deltas.
- [ ] T023 [US2] Extend CLI command `evaluations live-tail` in `src/model_builder/cli/model_builder.py` to stream candidate events using the same telemetry logs.
- [ ] T024 [US2] Update OpenAPI contract `specs/003-the-model-builder/contracts/model-builder.openapi.yaml` with any field changes introduced by telemetry payloads (if needed).

**Checkpoint**: User Stories 1 and 2 work independently.

---

## Phase 5: User Story 3 — Review Best Candidate Insights (Priority: P3)

**Goal**: Pin best candidate callout with refreshed equity, heatmap, and trade timeline visuals that persist for the session.

**Independent Test**: Promote a candidate to top score and confirm the callout, charts, and timeline refresh immediately and remain after reruns.

### Tests for User Story 3

- [ ] T025 [P] [US3] Add unit tests for analytics builders (`heatmap_builder`, `trade_timeline`) in `tests/model_builder/analytics/test_visual_builders.py`.
- [ ] T026 [P] [US3] Add UI integration test in `tests/model_builder/ui/test_best_candidate_module.py` asserting visuals persist across reruns within session state.

### Implementation for User Story 3

- [ ] T027 [US3] Implement momentum heatmap builder in `src/model_builder/analytics/heatmap_builder.py` supporting 5/10/20/60-day intervals with narrative text.
- [ ] T028 [US3] Implement trade timeline transformer in `src/model_builder/analytics/trade_timeline.py` sizing bubbles by notional and color-coding P&L.
- [ ] T029 [US3] Implement best candidate presenter in `src/model_builder/ui/components/candidate_summary.py` combining callout, equity curve chart, heatmap, and timeline.
- [ ] T030 [US3] Update `model_builder_page.py` to pin best candidate visuals in `st.session_state` and restore them after reruns.
- [ ] T031 [US3] Extend telemetry/log schema in `model_builder/optimization/telemetry.py` to include references to equity curve and visual artifacts for replay (align with FR-016).

**Checkpoint**: All user stories independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T032 [P] [Polish] Update `docs/configuration.md` and `specs/003-the-model-builder/quickstart.md` with new CLI commands and storage locations.
- [ ] T033 [Polish] Run full validation suite (`ruff format`, `ruff check --fix`, `pytest -m "not slow"`) and address issues.
- [ ] T034 [Polish] Refresh `specs/003-the-model-builder/contracts/model-builder.openapi.yaml` example payloads and ensure CLI help text matches commands.
- [ ] T035 [Polish] Conduct UX pass on `pages/2_Model_Builder.py` (copy tweaks, empty states, error messaging) and capture screenshots for PR checklist.

---

## Dependencies & Execution Order

- **Setup → Foundational → User Stories → Polish** in strict sequence.
- After Phase 2, User Stories 1–3 may proceed in parallel (respecting priority for MVP delivery).
- Within each story:
  - Tests (T009/T010, T018/T019, T025/T026) precede implementations but can run concurrently where marked [P].
  - Services must exist before UI or CLI wiring.
  - Telemetry/log schema updates (T017, T023, T031) must remain consistent.

### Story Dependency Graph

```
Setup → Foundation → US1 → US2 → US3
```

US2 and US3 conceptually depend on telemetry/log artifacts introduced in earlier phases; however, they can start once foundational work is complete if shared contracts remain stable.

### Parallel Opportunities

- T002 & T003 (setup) can run alongside each other after T001.
- T006 & T007 (foundation) can proceed in parallel after T004/T005.
- Per-story test tasks (T009/T010, T018/T019, T025/T026) can execute concurrently.
- Within US1: T011/T012 ([P] across different modules) may proceed in parallel once models are ready.
- Distinct stories can be split across developers after foundation, provided telemetry schema remains synchronized.

---

## Implementation Strategy

### MVP Focus
1. Complete Phases 1–2.
2. Deliver Phase 3 (US1) end-to-end and validate via Streamlit + CLI smoke tests.
3. Ship MVP once US1 passes acceptance scenarios.

### Incremental Expansion
4. Layer Phase 4 (US2) to add live evaluations.
5. Layer Phase 5 (US3) for best candidate analytics.
6. Perform Phase 6 polish before release.

---
