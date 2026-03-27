# Implementation Plan: Model Builder Strategy Profiles

**Branch**: `[003-the-model-builder]` | **Date**: 2025-10-11 | **Spec**: [`spec.md`](spec.md)  
**Input**: Feature specification from `/specs/003-the-model-builder/spec.md`

## Summary

Deliver a revamped Model Builder workspace that treats strategy profiles as first-class JSON artifacts, lets researchers tune train/holdout windows with enforced warmup, and surfaces live holdout telemetry with persistent best-candidate insights. The Streamlit page will delegate to new `model_builder` service modules that also power CLI parity, while analytics utilities render equity, heatmap, and trade timeline views derived from the latest holdout leader.

## Technical Context

**Language/Version**: Python 3.12 with full typing coverage  
**Primary Dependencies**: Streamlit 1.39, pandas 2.2, numpy 2.1, Plotly 5.23, Click 8.1 for CLI parity  
**Storage**: JSON strategy profiles and evaluation logs under `storage/strategy_profiles/` and `storage/evaluations/` (schema-versioned), parquet/CSV equity curves under existing layout  
**Testing**: pytest with unit coverage for repositories/analytics, integration tests for coverage derivation and CLI flows, ruff for lint/format  
**Target Platform**: Streamlit multi-page app in browser plus CLI commands for macOS/Linux workstations  
**Project Type**: Modular Python package (`src/model_builder/`) consumed by Streamlit pages and CLI entry points  
**Performance Goals**: Append live evaluation rows within 5 s of candidate scoring; regenerate best-candidate charts within 3 s; support 500 candidate rows per run without UI degradation  
**Constraints**: Runs must enforce ≥1 holdout trading day, extend ATR warmup into testing if history is short, remain offline once data cached, and emit structured logs for replay  
**Scale/Scope**: Single researcher per session, up to 20 saved profiles, evolutionary runs producing ~1 000 evaluations per session retained per run

## Constitution Check

*GATE: All principles satisfied prior to Phase 0.*

- **Modular Python 3.12 Architecture** → PASS: All new code lands under `src/model_builder/` with typed interfaces and shared services.  
- **Dual-Surface Delivery** → PASS: Streamlit page delegates to reusable services exposed via new Click CLI commands.  
- **Test-First Quality Gates** → PASS: Plan mandates unit/integration tests and ruff/pytest automation before merge.  
- **Data Contracts & Schema Stewardship** → PASS: Strategy profile schema gains `schema_version`, contracts exported in OpenAPI, migrations documented.  
- **Observability & Documentation** → PASS: Live telemetry uses structured logging, quickstart and config docs updated alongside feature.

## Project Structure

### Documentation (this feature)

```
specs/003-the-model-builder/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── contracts/
    └── model-builder.openapi.yaml
```

### Source Code (repository root)

```
src/model_builder/
├── __init__.py
├── profiles/
│   ├── __init__.py
│   ├── models.py
│   ├── repository.py
│   └── service.py
├── optimization/
│   ├── __init__.py
│   ├── coverage.py
│   ├── runner.py
│   └── telemetry.py
├── analytics/
│   ├── __init__.py
│   ├── heatmap_builder.py
│   └── trade_timeline.py
├── ui/
│   ├── __init__.py
│   ├── pages/
│   │   └── model_builder_page.py
│   └── components/
│       ├── profile_editor.py
│       ├── live_evaluations.py
│       └── candidate_summary.py
└── cli/
    ├── __init__.py
    └── model_builder.py

pages/
└── 2_Model_Builder.py  # Delegates to model_builder.ui.pages.model_builder_page.run_page()

tests/model_builder/
├── profiles/
│   ├── test_models.py
│   └── test_repository.py
├── optimization/
│   ├── test_coverage.py
│   └── test_runner.py
├── analytics/
│   ├── test_heatmap_builder.py
│   └── test_trade_timeline.py
└── ui/
    └── test_live_evaluations_component.py
```

**Structure Decision**: Introduce a namespaced `model_builder` package housing profiles, optimization orchestration, analytics, UI composition, and CLI exposure so Streamlit and CLI share the same services while existing `pages/2_Model_Builder.py` becomes a thin delegate.

## Complexity Tracking

No constitutional violations or extraordinary complexities identified.
**Polish & Cross-Cutting Concerns Phase**: Runs after all stories to tune UX polish, logging, and documentation updates that span multiple journeys.
