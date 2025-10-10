# Repository Guidelines

## Project Structure & Module Organization
Keep production code inside `src/model_builder/` so imports stay namespaced under `model_builder`. Add feature subpackages (for example, `src/model_builder/pipelines/`) rather than placing scripts at the repository root. Mirror the hierarchy under `tests/`, parking shared fixtures in `tests/resources/`, and document any heavyweight assets separately instead of committing them.

## Build, Test, and Development Commands
Initialize the environment with `python -m venv .venv && source .venv/bin/activate`; the project targets Python 3.12 per the PyCharm setup. Install dependencies through `python -m pip install -r requirements.txt` and refresh the lock whenever versions change. Run `pytest` for quick feedback and reserve `pytest -m "slow"` for end-to-end coverage. Build distributable artifacts with `python -m build` only after tests pass.

## Coding Style & Naming Conventions
Follow PEP 8 with four-space indentation. Use lowercase module names (`feature_selector.py`), PascalCase for classes, snake_case for functions and variables, and ALL_CAPS for constants. Add type hints to public APIs. Format code with `ruff format` and lint via `ruff check --fix`, committing only warning-free diffs.

## Testing Guidelines
Place tests in `tests/test_<module>.py` and name fixtures descriptively (`model_config`, `mock_dataset`). Tag long-running suites with `@pytest.mark.slow` so `pytest -m "not slow"` stays fast. Target 85 % statement coverage on new code and explain any shortfall in the PR. When pipelines change, add a regression test over synthetic data to guard against API drift.

## Commit & Pull Request Guidelines
Match the current Git history by writing concise, Title-Case summaries in the imperative mood (e.g., “Add Pipeline Registry”). Reference related issues, list validation commands, and flag configuration updates. Include a PR checklist that covers tests executed, docs touched, and datasets referenced. Attach screenshots or CLI output for user-visible changes and request a domain reviewer before merge.

## Environment & Configuration Tips
Keep `.venv/` untracked and avoid committing personal PyCharm workspace files; lean on `.git/info/exclude` for editor noise. Load secrets from an untracked `.env` and document required keys in `docs/configuration.md`. Park exploratory notebooks in `notebooks/` with dated prefixes, then graduate stable logic into packaged modules quickly.
