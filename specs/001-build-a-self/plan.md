# Implementation Plan: Self-Hosted Strategy Research Dashboard

**Branch**: `[001-build-a-self]` | **Date**: 2025-10-10 | **Spec**: [`spec.md`](spec.md)  
**Input**: Feature specification refined via `/speckit.specify` plus clarification decisions (Yahoo Finance fallback, CLI JSON output, five-year history).

## Summary

Deliver a self-hosted, Streamlit-based workspace that orchestrates the research loop end to end. The Streamlit entrypoint (`Home.py`) validates Alpaca credentials, falls back to Yahoo Finance when absent, and routes users to dedicated pages for portfolio curation, model evolution, log inspection, and simulation review. Core services live in Python 3.12 modules leveraging pandas/numpy for analytics, a custom backtest engine implementing the ATR breakout baseline, and an evolutionary optimizer that streams weighted CAGR/Calmar/Sharpe telemetry back to the UI. Artifacts (portfolios, parameters, simulations, logs, benchmarks) persist through a storage layer that enforces normalized schemas, atomic writes, and predictable folder layouts. Observability relies on append-only JSONL logs consumable by both UI and CLI inspectors.

**Integration Guardrail**: The Model Builder page treats the profile editor as the live source of truth—coverage summaries, train/holdout splits, and plots must react to in-session adjustments (train percentage, warmup days, parameter bounds) even before a profile is saved. Downstream graphs should consume this draft state to stay in sync with the next optimization run.

## Technical Context

**Language/Version**: Python 3.12 with strict typing  
**Primary Dependencies**: Streamlit for UI; pandas/numpy for data transforms; Plotly for interactive charts; yfinance + Alpaca SDK for market data; `multiprocessing` + custom EA utilities for optimization  
**Storage**: Local filesystem under configurable `DATA_DIR`; parquet shards for OHLCV, JSON/JSONL for artifacts and telemetry  
**Testing**: pytest (unit + integration), pytest.ini for markers; ruff for lint; black for formatting; tests exercise data loaders, caching, warmup, contract compliance  
**Target Platform**: Single workstation (macOS/Linux/WSL) running Streamlit app and CLI scripts; optional container packaging later  
**Project Type**: Streamlit multi-page application with shared service modules and CLI entrypoints  
**Performance Goals**: Handle five-year history for 200 tickers within RAM/disk constraints; optimization telemetry latency <1 s; backtests finish within spec success criteria  
**Constraints**: Offline-friendly once data cached; deterministic runs given seed; requirements pinned; CLI mirrors UI outputs as JSON artifacts  
**Scale/Scope**: Single concurrent researcher; up to hundreds of tickers; evolutionary logs spanning thousands of generations; append-only log rotation

## Constitution Check

Project constitution is still a template with placeholders. Until ratified, we adopt provisional rules: Python 3.12 typing and lint gates, modular architecture, reproducibility via seeds, and documented storage contracts. A formal constitution update must precede broader scaling work.

## Project Structure

### Documentation (this feature)

```
specs/001-build-a-self/
├── plan.md
├── research.md          # Phase 0 discovery (to be created via /speckit.plan Phase 0 output)
├── data-model.md        # Entities, schemas, storage contracts
├── quickstart.md        # Developer setup and workflows
├── contracts/
│   ├── model-contract.md
│   ├── storage-layout.md
│   └── telemetry-schema.md
└── tasks.md             # Generated later via /speckit.tasks
```

### Source Code (repository root)

```
Home.py                     # Streamlit entrypoint (credentials check, navigation)
pages/
├── 1_Portfolio_Curator.py  # Universe creation & stats
├── 2_Model_Builder.py      # EA optimization workspace with live telemetry
├── 3_Log_Inspector.py      # JSONL session explorer & benchmark views
└── 4_Simulation_Review.py  # KPI dashboards and bundle export

src/
├── __init__.py
├── config/
│   ├── settings.py         # Env parsing, DATA_DIR resolution, provider priority
│   └── constants.py
├── data/
│   ├── providers/
│   │   ├── alpaca_client.py
│   │   └── yahoo_client.py
│   ├── loader.py           # Cache-aware OHLCV ingestion
│   └── cache.py            # RAM LRU + parquet disk cache
├── engine/
│   ├── atr_breakout.py     # Baseline strategy & sizing logic
│   ├── backtest.py         # Backtest engine returning BacktestResult
│   └── metrics.py          # KPI calculations
├── optimizer/
│   ├── evolutionary.py     # Evolutionary search driver (CAGR/Calmar/Sharpe weights)
│   └── telemetry.py        # Async progress publishing
├── storage/
│   ├── layout.py           # Canonical paths (portfolios/, params/, logs/, etc.)
│   ├── artifacts.py        # Atomic JSON writes, bundle export/import
│   └── migrations.py       # Legacy upgrades
├── models/
│   ├── contracts.py        # Shared dataclasses (Portfolio, ParameterSet, BacktestResult)
│   └── registry.py         # Model discovery & validation
└── cli/
    └── main.py             # `streamlit run` alternative commands (optimize, simulate, inspect)

tests/
├── unit/
│   ├── test_loader.py
│   ├── test_cache.py
│   ├── test_atr_breakout.py
│   └── test_storage.py
├── integration/
│   ├── test_backtest_pipeline.py
│   └── test_optimizer_flow.py
└── fixtures/               # Sample OHLCV shards, portfolios

storage/
├── logs/                   # Rotating JSONL telemetry
├── portfolios/
├── parameters/
├── simulations/
├── bundles/
└── benchmarks/
```

**Structure Decision**: Streamlit multi-page app with shared `src/` modules ensures UI remains thin while analytics, storage, and optimization logic stay reusable by the CLI. Dedicated `storage/` tree keeps artifacts discoverable per spec.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| Multi-tier caching (RAM LRU + parquet) | Needed to satisfy responsiveness while handling 5-year history for hundreds of tickers | Single-layer cache would either thrash memory or incur repeated network fetches |
| Custom evolutionary optimizer module | Required for weighted CAGR/Calmar/Sharpe scoring and telemetry hooks | Off-the-shelf AutoML tools lack fine-grained logging and strategy-specific constraints |
