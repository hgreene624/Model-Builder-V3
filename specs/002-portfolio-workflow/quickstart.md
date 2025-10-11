# Quickstart — Portfolio Workflow Overhaul

## Prerequisites
- Python 3.12 with virtual environment tooling.
- Market data credentials configured via `.env` (see `docs/configuration.md`).
- Index universe JSON files placed under `storage/index_universes/`.

## Setup
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
ruff check --fix
ruff format
```

## Launch the Streamlit workflow
```bash
source .venv/bin/activate
streamlit run src/model_builder/portfolio_workflow/streamlit_app.py
```
- Select an index universe, apply filters, fetch liquidity, and save the curated portfolio.
- Saved artifacts appear under `storage/portfolios/` with overwrite semantics when names collide.

## Run CLI commands
```bash
source .venv/bin/activate
export DATA_DIR=$(pwd)/storage

python -m src.cli.main portfolio curate \
  --universe sp500 \
  --search "energy" \
  --sectors "Energy,Utilities" \
  --min-price 5 \
  --min-dollar-volume 1000000 \
  --max-count 30 \
  --name "SP500 Energy Screen"

python -m src.cli.main portfolio delete "SP500 Energy Screen"
```
- To curate from seeds or CSVs instead of an index, swap `--universe` for `--seed <name>` or `--csv path/to/file.csv`; the liquidity threshold flags (`--min-price`, `--min-dollar-volume`) work in both modes.

## Testing
```bash
source .venv/bin/activate
pytest tests/model_builder/portfolio_workflow
```
- Use `pytest -m "not slow"` for fast iterations and `pytest -m "slow"` when exercising end-to-end flows.

## Troubleshooting
- If liquidity fetch exceeds 5 s, check provider status and retry; cached shards expire after 15 minutes.
- When artifacts fail to save, confirm the `storage/portfolios/` directory is writable.
