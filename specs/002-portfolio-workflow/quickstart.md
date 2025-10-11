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
python -m model_builder.portfolio_workflow.cli curate \
  --universe sp500 \
  --text-query "energy" \
  --max-symbols 30 \
  --price-floor 5 \
  --volume-floor 1e6

python -m model_builder.portfolio_workflow.cli delete --name sp500-energy
```

## Testing
```bash
source .venv/bin/activate
pytest tests/model_builder/portfolio_workflow
```
- Use `pytest -m "not slow"` for fast iterations and `pytest -m "slow"` when exercising end-to-end flows.

## Troubleshooting
- If liquidity fetch exceeds 5 s, check provider status and retry; cached shards expire after 15 minutes.
- When artifacts fail to save, confirm the `storage/portfolios/` directory is writable.
