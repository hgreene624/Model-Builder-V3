# Phase 0 Research — Self-Hosted Strategy Research Dashboard

## Objectives
- Validate feasibility of the Streamlit-based workflow that spans portfolio creation, ATR optimisation, log inspection, and simulation.
- Lock down integrations for Alpaca (primary) and Yahoo Finance (fallback) while maintaining reproducible caching with pandas/numpy.
- Confirm design of the evolutionary optimiser, backtest engine, and artifact storage so UI and CLI share consistent schemas.

## Platform & Tooling Decisions
- **Python 3.12**: mandatory baseline to align with repo guidance, support `typing` enhancements, and ensure compatibility with ruff/black/pytest.
- **Streamlit multi-page UI**: Home entry point plus `pages/` modules give a guided workflow without bespoke routing. Streamlit session state handles navigation context.
- **Analytics stack**: pandas + numpy for transforms, SciPy-style computations reserved for metrics; Plotly delivers interactive charts embedded in Streamlit.
- **Dependencies management**: `requirements.txt` for runtime pins; `requirements-dev.txt` extends with ruff, black, pytest.

## Data Providers & Ingestion Strategy
- **Primary**: Alpaca REST API for authenticated OHLCV; `alpaca-py` SDK with rate-limit handling. Environment variables (`ALPACA_KEY_ID`, `ALPACA_SECRET_KEY`) loaded via `config/settings.py`.
- **Fallback**: Yahoo Finance via `yfinance` for daily bars; activated when Alpaca credentials are absent or invalid. Clarification locked to Yahoo.
- **Schema**: standardized OHLCV with UTC index, symbol column, optional corporate action adjustments recorded in metadata.
- **Caching**: three tiers — in-memory LRU (per session), disk parquet shards partitioned by `symbol/date`, and provider fetch. Shard writes must be atomic to avoid partial files. Index alignment verified on load.
- **Provider preference**: env override `PREFERRED_PROVIDER` (default `alpaca`) with automatic downgrade to Yahoo plus UI notice.

## Backtest & Strategy Research
- **ATR breakout baseline**: Implements Wilder ATR smoothing, breakout thresholds, and risk-aware sizing toggle. Warmup period determined by maximum lookback (ATR window + breakout horizon). Leverages loader’s warmup-aware fetch to minimise redundant pulls.
- **BacktestResult contract**: dataclass capturing equity curve, transactions ledger, benchmark series, per-trade costs, and summary KPIs (CAGR, Sharpe, Calmar, max drawdown, hit rate, turnover).
- **Cost diagnostics**: explicit fields for commissions, slippage, borrow fees; aggregated per trade and per run for log inspection.

## Optimisation Approach
- **Evolutionary algorithm**: custom implementation using `multiprocessing` (process pool) for fitness evaluation. Weighted objective derived from CAGR, Calmar ratio, Sharpe; gating constraints for max trade rate and minimum holding period.
- **Telemetry**: `optimizer/telemetry.py` pushes JSON-compatible updates (generation, best/worst fitness, sample genome) to Streamlit via queue/poller. Same events appended to JSONL TrainingLogger.
- **Determinism**: seeds recorded per run; RNG state stored alongside artifact to reproduce results.

## Storage & Artifact Management
- **Directory contract** resolved through `storage/layout.py`:
  - `storage/portfolios/<uuid>.json`
  - `storage/parameters/<run_id>.json`
  - `storage/simulations/<run_id>/result.json` (+ plot assets)
  - `storage/logs/<run_id>.jsonl` (append-only)
  - `storage/bundles/<bundle_id>.zip`
  - `storage/benchmarks/<symbol>.parquet`
- **Atomic writes**: use temp files + `os.replace` to guard against partial saves.
- **Metadata upgrades**: `storage/migrations.py` tracks schema versions, upgrades legacy files on load.
- **CLI parity**: `cli/main.py` wraps portfolio curate, optimize, inspect logs, simulate, bundle export—each command emits summary to console and JSON artifact to disk.

## Observability & Diagnostics
- **TrainingLogger**: rotates JSONL logs with configurable max size; records events for data sourcing, warmup adjustments, generation summaries, holdout evaluations.
- **UI messaging**: Streamlit status banners triggered for provider fallback, cache misses, rate-limit warnings, and model contract errors.
- **CLI inspector**: parses JSONL for timeline visualisation, optionally exports CSV for offline review.

## Testing & Quality Gates
- `pytest` suites:
  - Data loader normalisation & provider failover.
  - Cache eviction ordering, warmup slicing correctness.
  - ATR breakout signal generation and position sizing rails.
  - Backtest engine accuracy vs controlled fixtures.
  - Optimiser telemetry payload schema.
- `pytest.ini` configures slow marker for long optimisation tests. CI (future) runs `ruff`, `black --check`, and targeted pytest subsets.

## Risks & Open Questions
- **Cache correctness**: need rigorous tests ensuring warmup coverage and avoiding mixed-provider shards.
- **EA log volume**: JSONL files could grow large; consider gzip rotation or summarisation if storage pressure observed.
- **Provider rate limits**: Alpaca throttle handling and Yahoo query limits must surface clear retry guidance; may require exponential backoff.
- **Credential UX**: ensure UI communicates fallback gracefully and offers guidance for setting Alpaca keys.
- **Headless integration**: bundle schema must anticipate future headless trading app expectations (e.g., dependency enumeration, version pinning).

## Next Steps
1. Draft detailed data model (`data-model.md`) with entity fields and schema versions.
2. Define contracts (`contracts/model-contract.md`, `storage-layout.md`, `telemetry-schema.md`) using clarified decisions.
3. Establish quickstart guide covering environment setup, Streamlit run command, and CLI usage.
