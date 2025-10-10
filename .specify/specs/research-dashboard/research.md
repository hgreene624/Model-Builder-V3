# Phase 0 Research: Self-Hosted Strategy Research Dashboard

## Goals & Framing
- Build a reproducible, modular research workspace that spans portfolio creation → strategy optimization → log inspection → simulation → exportable bundles.
- Guarantee Python 3.12 compliance across backend + model ecosystem and keep the UI/CLI aligned so headless workflows share the same contracts.
- Ship with ATR breakout baseline while enabling frictionless addition of new model modules.

## Market Data Strategy
- **Primary**: Assume user-supplied paid credentials (Polygon, Alpaca, Quandl). Need adapter abstractions so we can plug different vendor SDKs but present uniform bars to models (OHLCV plus computed features like ATR).
- **Fallback**: Public sources (e.g., Stooq, AlphaVantage demo, Nasdaq FTP) for limited universes. Must annotate outputs when fallback is in use. Evaluate rate limits and caching rules early.
- Implement local caching in `data/market/` (parquet partitioned by ticker/date) with metadata recorded in SQLite to avoid redundant downloads and keep offline runs possible.

## Architecture Notes
- Backend: FastAPI + Uvicorn with modular routers. Services use dependency-injected repositories so we can swap in-memory vs persisted stores for tests.
- Task execution: synchronous for MVP but design async-friendly pipeline (e.g., `asyncio`, `anyio`) so progress updates stream via websockets/SSE. For heavy optimization, consider background worker (celery? arq?) but postpone until perf profiling says otherwise.
- Frontend: React + Vite + Chakra UI (or Mantine). Use TanStack Query for caching API calls, websockets for live updates, and plotly.js/react for charting.
- CLI: Typer-based interface sharing service layer with FastAPI to avoid duplication.

## Model Contract Exploration
- Define abstract base class (`StrategyModel`) with:
  - `metadata`: name, version, description.
  - `param_schema`: dataclass/`pydantic.BaseModel` with ranges/meta for UI rendering.
  - `generate_signals(bars: pd.DataFrame, features: dict, params: StrategyParams) -> TradeIntentFrame`.
  - Optional hooks: `warmup_period`, `supports_position_sizing`.
- Discovery via entry points or scanning `data/models/registry.toml`. Need verification step (contract tests + runtime validation).
- Output standardization: DataFrame with columns (`timestamp`, `ticker`, `action`, `weight`, `stop`, `target`, `notes`). Ensure dtype normalization for portability.
- ATR model design: use Wilder’s smoothing; risk-aware sizing multiplies base position with reward/risk score clamped between min/max rails. Confirm formula that scales by `expected_move / atr` or similar.

## Optimization Engine Research
- Candidate libraries: `nevergrad`, `optuna`, `scikit-opt`, `deap`. Need reproducible seeds, intermediate callbacks, ability to respect parameter bounds and discrete/continuous mixes.
- Likely approach: use Optuna with evolutionary sampler (CMA-ES/NSGA-II) to get callbacks and persistent study storage in SQLite.
- Progress streaming: store per-generation metrics (fitness, Sharpe, drawdown) and push deltas over websocket. Persist JSON log per run (`data/logs/<run_id>.jsonl`) for inspector.
- Determine compute budget heuristics: default populations, number of generations for 200 tickers; allow early stopping on plateau.

## Simulation & Benchmarking
- Simulation engine should consume standardized trade intents plus historical bars to produce equity curve, trades ledger, cost calculations (commissions, slippage), benchmark comparison (SPY TR / custom). Evaluate `vectorbt`, `backtrader`, or custom pandas-based simulator; custom may be clearer for contract enforcement.
- KPI calculation: Sharpe (annualized), CAGR, max drawdown, hit rate, turnover, avg trade P/L. Ensure consistent risk-free assumption (configurable).
- Visualization: use plotly for front-end interactive charts. CLI exports static PNG/JSON.

## Artifact Persistence & Bundles
- Directory layout:
  - `data/portfolios/<name>/<timestamp>.json` with filters + tickers.
  - `data/models/<model_id>/` for strategy code + metadata.
  - `data/parameters/<run_id>.json` for genomes.
  - `data/logs/<run_id>.jsonl` for optimizer progress.
  - `data/runs/<run_id>/report.json` for simulation output.
  - `data/bundles/<bundle_id>.zip` packaging model reference + params + checksum.
- SQLite metadata index referencing all artifacts for quick lookup on Home screen.
- Export format: zipped directory containing `model_metadata.json`, `param_set.json`, `contract_version.txt`, optional `requirements.txt`.

## CLI & Headless Support
- CLI commands: `mbv3 portfolio curate`, `mbv3 model inspect`, `mbv3 optimize`, `mbv3 logs inspect`, `mbv3 simulate`, `mbv3 bundle export`.
- Ensure CLI shares validation logic via service layer. Provide `--seed` for reproducibility and `--output` path overrides.

## Risks & Open Questions
- **Data licensing**: need guidance on which credentialed providers to support first; fallback data quality may limit ATR reliability.
- **Performance**: 200 tickers × 5 years may challenge pure pandas; consider numpy vectorization or numba; benchmark early.
- **Extensibility**: plugin model packaging—should we allow compiled extensions? For now restrict to pure Python modules zipped with metadata.
- **UI Responsiveness**: websockets vs SSE compatibility in self-hosted environments; ensure graceful degradation.
- **Testing**: gather representative historical datasets (maybe synthetic) for automated regression to maintain determinism.
- **Security**: storing API keys locally—document `.env` usage and encryption needs?
- **Constitution Gap**: formal governance doc still pending; track to avoid drifting from intended process.

## Immediate Next Steps
1. Prototype data ingestion layer with credential adapter interface + public fallback.
2. Finalize strategy model base contract and write contract tests (Python 3.12 typing, pydantic).
3. Spike optimization with Optuna to validate progress callbacks and logging format.
4. Draft entity schemas for SQLite metadata store and log structure (feeds into Phase 1 data-model.md).
5. Decide on front-end component library (Chakra vs Mantine) and charting stack baseline.
