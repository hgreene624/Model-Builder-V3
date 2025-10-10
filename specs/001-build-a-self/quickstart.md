# Quickstart — Self-Hosted Strategy Research Dashboard

## Prerequisites
- Python 3.12 installed and available on PATH.
- Node/Streamlit not required separately; Streamlit launches via Python.
- Optional: Alpaca API keys (`ALPACA_KEY_ID`, `ALPACA_SECRET_KEY`). Without them the app falls back to Yahoo Finance daily data.

## Environment Setup
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

## Project Layout Highlights
- `Home.py`: Streamlit entry point; checks credentials and routes to workspace pages.
- `pages/`: Streamlit modules for portfolio curation, model builder, log inspector, simulation review.
- `src/`: Shared services (data loader, cache, backtest engine, optimizer, storage helpers).
- `storage/`: All persisted artifacts (portfolios, parameters, simulations, logs, bundles, benchmarks).

## Running the App
```bash
streamlit run Home.py
```
- Home page displays credential status, recent artifacts, and navigation shortcuts.
- If Alpaca credentials are missing or invalid, a banner confirms Yahoo Finance fallback.

## CLI Workflows
```bash
python -m src.cli.main portfolio curate --input data/seed/sp500.csv
python -m src.cli.main optimize --portfolio <portfolio_id> --model atr_breakout --seed 20251010
python -m src.cli.main logs inspect --run <run_id>
python -m src.cli.main simulate --parameter-set <param_id> --benchmark SPY
python -m src.cli.main bundle export --parameter-set <param_id>
```
- CLI commands emit JSON artifacts to `storage/` and concise console summaries.

## Testing & Quality Checks
```bash
python -m pytest
ruff check src tests
black --check src tests
```
- Pytest covers data normalization, cache behavior, backtest outputs, optimizer telemetry.
- Use `pytest -m "slow"` for long-running EA regression tests.

## Data Management
- Configure storage root via `DATA_DIR` environment variable (defaults to `./storage`).
- Market data cached as parquet shards; warmup range respected automatically.
- Use `python -m src.cli.main cache clear --provider yahoo` for maintenance.

## Troubleshooting
- Missing Alpaca keys → Streamlit banner links to documentation; CLI reports `status: missing`.
- Rate limits → logs emit warning events; retry after cooldown.
- Large JSONL logs → use CLI inspector with `--export csv` to down-sample.
