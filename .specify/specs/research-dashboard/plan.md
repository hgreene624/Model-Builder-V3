# Implementation Plan: Self-Hosted Strategy Research Dashboard

**Branch**: `[001-research-dashboard-workspace]` | **Date**: 2025-10-10 | **Spec**: `spec.md`  
**Input**: Feature specification from `/specify/specs/research-dashboard/spec.md`

## Summary

Deliver a self-hosted research workspace that guides users from portfolio curation through strategy optimization, log inspection, and simulation. Core approach: build a modular Python 3.12 backend (FastAPI + task services) with a React/TypeScript front-end, backed by a structured local data store. Strategy models conform to a simple contract so new models drop in, auto-discover, and expose parameters to both UI and CLI flows. ATR breakout ships as the baseline with risk-aware sizing baked into the contract. Artifact persistence, benchmarking, and bundle export ensure reproducible, portable outcomes.

## Technical Context

**Language/Version**: Python 3.12 (backend, CLI), TypeScript 5.x (frontend)  
**Primary Dependencies**: FastAPI, Pydantic v2, SQLModel (for local metadata index), pandas, numpy, plotly, websockets; Frontend uses React 18 + Vite + Chakra UI (or similar) + TanStack Query  
**Storage**: Local `data/` directory (parquet/csv for market data slices, SQLite via SQLModel for metadata index, JSON/YAML bundles for models)  
**Testing**: pytest + httpx for backend, vitest + Playwright for frontend, contract snapshots for model outputs  
**Target Platform**: Local workstation (macOS/Linux) running uvicorn + Node dev server; packaged via Docker & `uvicorn` in production mode  
**Project Type**: Web application (backend API + frontend SPA + CLI tooling)  
**Performance Goals**: Stream optimization progress <1s latency, handle 200 tickers × 5 years within 10 min optimization window, UI interactions <100 ms P95  
**Constraints**: Offline-first except optional credentials, reproducible runs via seed control, zero network dependency for saved artifacts, modular model discovery with strict contract validation  
**Scale/Scope**: Single user per instance, portfolios up to low hundreds of tickers, logs spanning thousands of generations, initial release supports ATR + plug-in models

## Constitution Check

Constitution not yet ratified (`.specify/memory/constitution.md` retains placeholders). Interim guardrails adopted: Python 3.12 best practices (type hints, ruff/pytest gating), modular architecture, reproducible pipelines, and documentation parity for all new modules. Update constitution before Phase 1 design sign-off.

## Project Structure

### Documentation (this feature)

```
specs/research-dashboard/
├── plan.md
├── research.md          # Phase 0 discovery notes
├── data-model.md        # Entity contracts + schemas
├── quickstart.md        # Dev setup & workflows
├── contracts/
│   ├── model-contract.md
│   ├── optimizer-api.md
│   └── bundle-schema.md
└── tasks.md             # Generated during task planning
```

### Source Code (repository root)

```
backend/
├── pyproject.toml
├── app/
│   ├── api/
│   │   ├── v1/
│   │   │   ├── portfolios.py
│   │   │   ├── models.py
│   │   │   ├── optimizer.py
│   │   │   ├── logs.py
│   │   │   └── simulations.py
│   │   └── dependencies.py
│   ├── core/
│   │   ├── config.py
│   │   ├── directory_layout.py
│   │   └── settings.py
│   ├── services/
│   │   ├── portfolio_manager.py
│   │   ├── model_registry.py
│   │   ├── optimizer_service.py
│   │   └── simulation_service.py
│   ├── models/
│   │   ├── base_contract.py
│   │   ├── atr_breakout/
│   │   │   └── strategy.py
│   │   └── interfaces.py
│   ├── repositories/
│   │   ├── metadata_store.py
│   │   └── bundle_store.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py
│   └── main.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── contracts/
└── scripts/
    └── seed_data.py

frontend/
├── package.json
├── vite.config.ts
├── src/
│   ├── app/
│   │   ├── router.tsx
│   │   └── theme.ts
│   ├── api/
│   │   ├── client.ts
│   │   └── hooks.ts
│   ├── pages/
│   │   ├── Home.tsx
│   │   ├── PortfolioStudio.tsx
│   │   ├── ModelStudio.tsx
│   │   ├── Training.tsx
│   │   ├── Logs.tsx
│   │   └── Simulation.tsx
│   ├── components/
│   │   ├── PortfolioFilters.tsx
│   │   ├── ModelParamForm.tsx
│   │   ├── OptimizationProgress.tsx
│   │   ├── BenchmarkChart.tsx
│   │   └── BundleExportModal.tsx
│   ├── state/
│   │   ├── portfolioStore.ts
│   │   ├── modelStore.ts
│   │   └── runStore.ts
│   └── utils/
│       └── formatting.ts
└── tests/
    ├── unit/
    └── e2e/

data/
├── portfolios/
├── models/
├── logs/
├── runs/
└── bundles/
```

**Structure Decision**: Two-project layout (backend FastAPI, frontend React) to separate API/CLI concerns from rich workspace UI while sharing a common data layout. Backend owns models, optimization, persistence, and CLI; frontend consumes REST + websocket APIs for interactivity.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Dual-project (backend + frontend) | UI needs responsive SPA plus reusable API/CLI layer | Single Streamlit-style app would make plugin models, CLI parity, and streaming telemetry harder to maintain |
