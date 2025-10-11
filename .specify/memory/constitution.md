<!--
Sync Impact Report
Version change: 0.0.0 → 1.0.0
Modified principles:
- N/A (initial publication)
Added sections:
- Additional Constraints & Standards
- Development Workflow & Review Process
Removed sections:
- None
Templates:
- ✅ .specify/templates/plan-template.md (constitution check references current principles)
- ✅ .specify/templates/spec-template.md (stories and requirements map to principles)
- ✅ .specify/templates/tasks-template.md (task phases enable modular delivery)
- ✅ .codex/prompts/speckit.plan.md (guides compliance with constitution gates)
Follow-up TODOs:
- TODO(GOVERNANCE_OWNERS): Record ratifying maintainers in docs/configuration.md
-->
# Model Builder V3 Constitution

## Core Principles

### I. Modular Python 3.12 Architecture
- All production code MUST target Python 3.12, use type hints, and organize into cohesive modules beneath `src/model_builder/`.
- Shared behavior belongs in reusable service layers; Streamlit apps and CLI commands MUST import these services rather than duplicating logic.
- Functions and classes SHOULD remain small (≈50 lines max) and embrace dataclasses or TypedDicts for structured data.
- Ruff formatting and linting MUST pass before code review; formatting deviations are not acceptable.

### II. Dual-Surface Delivery
- Every researcher-facing capability MUST offer both Streamlit and CLI entry points unless explicitly waived.
- Command-line interfaces MUST be built with Click and expose the same inputs/outputs as their UI counterparts.
- Services MUST be interface-agnostic so new surfaces (automation, notebooks) can reuse the same logic without refactoring.

### III. Test-First Quality Gates
- Tests and fixtures MUST be authored before implementation; merges are blocked unless new or updated tests fail first and then pass.
- Minimum statement coverage for new or modified code is 85 %; gaps REQUIRE written justification in the PR checklist.
- Test suites (`pytest`, `pytest -m "slow"`) and lint (`ruff check --fix`, `ruff format`) MUST pass locally prior to review sign-off.

### IV. Data Contracts & Schema Stewardship
- JSON artifacts (universes, portfolios, cache shards) MUST declare `schema_version` and remain backward-compatible; breaking changes demand a new major version and migration notes.
- Contracts (OpenAPI, CLI docs) MUST be refreshed when endpoints or artifact shapes change, and referenced in specs and tests.
- Saved data MUST document provenance, caching lifetime, and overwrite semantics to keep downstream modeling deterministic.

### V. Observability & Documentation
- Streamlit flows MUST present actionable error states with retry guidance; services MUST emit structured logs at INFO level or above.
- Quickstart guides, configuration docs, and README entries MUST be updated alongside feature work to remain accurate.
- Telemetry hooks (logging, metrics, checkpoints) SHOULD reuse shared utilities to guarantee consistent formatting and log destinations.


## Additional Constraints & Standards

- Virtual environments MUST isolate dependencies (`python -m venv .venv`); dependencies are pinned via `requirements.txt` and reviewed quarterly.
- Caching for universes and liquidity data MUST default to a 15-minute TTL, with configurable overrides documented in code.
- Liquidity fetch workflows MUST surface progress within 500 ms and complete under 5 s p95 for 1 000 symbols; requests exceeding limits REQUIRE instrumentation and follow-up.
- Secrets MUST load from `.env` entries documented in `docs/configuration.md`; no secrets may reside in source control.
- Large assets (datasets, notebooks) belong outside the repository or under `tests/resources/` with explicit usage notes.

## Development Workflow & Review Process

- Clarification (`/speckit.clarify`) and planning (`/speckit.plan`) workflows MUST complete before implementation tasks begin; unresolved clarifications block downstream phases.
- Implementation planning MUST enumerate affected modules under `src/model_builder/` and matching tests under `tests/model_builder/`.
- Code reviews MUST verify adherence to this constitution, updated specs, passing tests, and documented CLI/Streamlit parity.
- PR checklists MUST include validation commands run, documentation touched, datasets referenced, and reviewer acknowledgements.

## Governance

- This constitution supersedes other internal guidelines for the Model Builder V3 project; conflicts MUST be resolved by amending this document.
- Amendments REQUIRE proposer documentation, reviewer approval from the data engineering lead and research tooling lead, and an updated semantic version.
- Version bumps follow semantic rules: MAJOR for breaking governance changes, MINOR for new principles or sections, PATCH for clarifications.
- Compliance reviews occur during code review and release retrospectives; non-compliant work MUST remediate before deployment.

**Version**: 1.0.0 | **Ratified**: 2025-10-11 | **Last Amended**: 2025-10-11
