# Quickstart — Model Builder Strategy Profiles

## 1. Environment Setup
- Create and activate the project virtualenv:
  ```bash
  python -m venv .venv
  source .venv/bin/activate
  python -m pip install -r requirements.txt -r requirements-dev.txt
  ```
- Export a `DATA_DIR` (or rely on defaults) pointing to writable storage for portfolios, profiles, and logs.
- Ensure Streamlit secrets remain empty; strategy profiles are intentionally open-access per spec.

## 2. Running the Streamlit Workspace
- Launch the app from repo root:
  ```bash
  streamlit run Home.py
  ```
- Open the **Model Builder** page. The UI loads strategy profiles via `model_builder.profiles.service`:
  1. Pick an existing profile or create one with train percentage, ATR warmup, and parameter payload.
  2. Start an evolutionary run. Live evaluations reset at run start and append candidate rows as telemetry arrives.
  3. Inspect the pinned best candidate module: equity curve, momentum heatmap, and trade timeline refresh whenever the leader changes.

## 3. CLI Parity
- Interact with the same services using Click commands:
  ```bash
  # List all strategy profiles
  python -m model_builder.cli.model_builder profiles list [--output json|table]

  # Create or update a profile from file
  python -m model_builder.cli.model_builder profiles save --file profiles/sample.json

  # Create or update a profile with inline options
  python -m model_builder.cli.model_builder profiles save \
    --name "My Strategy" \
    --portfolio-id <portfolio_id> \
    --train-percentage 0.7 \
    --atr-warmup-days 14 \
    --parameters '{"population_size": 90, "generations": 30}'

  # Delete a profile
  python -m model_builder.cli.model_builder profiles delete <profile_id> [--force]

  # Run optimization with a profile
  python -m model_builder.cli.model_builder optimize \
    --profile-id <id> \
    [--train-percent 0.7] \
    [--warmup-days 14] \
    [--symbol-count 5] \
    [--seed 42] \
    [--use-synthetic] \
    [--output results.json]

  # Stream live evaluation events
  python -m model_builder.cli.model_builder evaluations live-tail \
    --run-id <id> \
    [--follow] \
    [--payload-only]
  ```
- CLI commands read/write the same JSON artifacts under `storage/strategy_profiles/` and `storage/evaluations/`.

## 4. Testing & Quality Gates
- Run unit + integration suites before implementation work lands:
  ```bash
  pytest tests/model_builder -m "not slow"
  ruff check --fix
  ruff format
  ```
- Add `@pytest.mark.slow` to long-running evolutionary tests. Maintain ≥85 % coverage on new modules.

## 5. Data & Telemetry Artifacts
- Strategy profiles: `storage/strategy_profiles/<profile_id>.json` (schema_versioned).
- Evaluation logs: `storage/evaluations/<run_id>.jsonl` for replay plus directories for equity curves and visual assets.
- Session cache persists best candidate visuals per browser session; clearing session resets pinned charts.

## 6. Next Steps for Contributors
- Review `spec.md`, `plan.md`, and `data-model.md` before picking up tasks.
- Use `/speckit.tasks` once design work is approved to generate implementation tickets.
- Document any new dependencies or configuration switches in `docs/configuration.md`.
