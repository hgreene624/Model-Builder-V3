# Implementation Plan: Portfolio Workflow Overhaul

**Branch**: `002-portfolio-workflow` | **Date**: 2025-10-11 | **Spec**: `/specs/002-portfolio-workflow/spec.md`
**Input**: Feature specification from `/specs/002-portfolio-workflow/spec.md`

## Summary

Implement an end-to-end portfolio curation workflow inside Streamlit that loads researcher-selected index universes, applies interactive filtering and liquidity enrichment, manages draft portfolios, and persists saved artifacts (overwriting on name collisions) for downstream modeling and CLI usage. Work covers Streamlit UI flows, shared services for data access and caching, JSON persistence helpers, and CLI commands offering parity with the UI.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: Streamlit, Pandas, internal OHLCV cache utilities, Click CLI framework  
**Storage**: JSON artifacts under `storage/index_universes/` and `storage/portfolios/` with shard metadata  
**Testing**: pytest (unit + integration), including Streamlit session tests and CLI command coverage  
**Target Platform**: Streamlit web app served via internal tooling; local CLI execution  
**Project Type**: Internal research web interface plus CLI companion  
**Performance Goals**: Filter interactions complete ≤300 ms; liquidity fetch p95 ≤5 s; CLI operations ≤10 s for 1000 symbols  
**Constraints**: Cache universes/liquidity for 15 minutes, surface inline error alerts with retry guidance, disable fetch actions when network unavailable (no offline mode)  
**Scale/Scope**: Index universes up to ~1000 symbols; 10–20 saved portfolios per researcher

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution file currently contains placeholder sections with no ratified principles. Proceeding under repository guidelines (PEP 8, pytest coverage, documentation) while flagging the need to formalize constitution gates before implementation. Post-Phase 1 review confirms no additional guidance was discovered; continue under the same assumptions.

## Project Structure

### Documentation (this feature)

```
specs/002-portfolio-workflow/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
└── tasks.md  (Phase 2 via /speckit.tasks)
```

### Source Code (repository root)

```
src/
└── model_builder/
    ├── portfolio_workflow/
    │   ├── __init__.py
    │   ├── streamlit_app.py
    │   ├── services/
    │   │   ├── universe_loader.py
    │   │   ├── liquidity_fetcher.py
    │   │   └── portfolio_store.py
    │   ├── filters/
    │   │   └── predicates.py
    │   ├── cli/
    │   │   ├── __init__.py
    │   │   ├── curate.py
    │   │   └── delete.py
    │   └── telemetry.py
    └── shared/
        └── ohlcv_cache.py

tests/
└── model_builder/
    ├── portfolio_workflow/
    │   ├── unit/
    │   │   ├── test_universe_loader.py
    │   │   ├── test_filters.py
    │   │   ├── test_portfolio_store.py
    │   │   └── test_liquidity_fetcher.py
    │   └── integration/
    │       ├── test_streamlit_flow.py
    │       └── test_cli_portfolio_commands.py
    └── shared/
        └── test_ohlcv_cache.py

storage/
└── portfolios/
    └── README.md
```

**Structure Decision**: Source modules will live under `src/model_builder/portfolio_workflow/` to encapsulate Streamlit UI flow, shared services, filters, CLI commands, and telemetry. Tests mirror the layout within `tests/model_builder/portfolio_workflow/` for unit and integration coverage. Shared caching helpers remain in `src/model_builder/shared/`. Portfolio artifacts persist beneath `storage/portfolios/` with documentation.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | – | – |
