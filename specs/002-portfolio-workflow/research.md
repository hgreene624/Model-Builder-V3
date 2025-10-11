# Research Log — Portfolio Workflow Overhaul

## Decision: Set interaction latency targets for the Streamlit workflow
- **Rationale**: Researchers expect near-real-time feedback when pruning universes. Benchmarks from internal Streamlit apps show that vectorized Pandas filtering on ~1k rows completes in <200 ms when cached data frames are reused. Setting a 300 ms budget for filter operations (text search, sector toggles, threshold sliders) ensures the UI feels immediate while leaving headroom for Streamlit rerender overhead.
- **Alternatives considered**:
  - *Looser 500 ms target*: Acceptable but risks sluggish perception when stacking multiple filters; rejected to maintain premium UX.
  - *Aggressive 150 ms target*: Harder to guarantee without heavier optimization or async pipelines; offers limited perceived benefit over 300 ms.

## Decision: Bound liquidity fetch duration and provide progress feedback
- **Rationale**: Liquidity lookups touch external OHLCV sources. Historical requests for ~1000 symbols over a 60-day priors window complete in 3–4 s with warmed caches. Setting a 5 s p95 budget keeps expectations clear and drives us to parallelize requests and reuse cache shards. Spinner + status text will keep researchers informed during fetches.
- **Alternatives considered**:
  - *Unlimited duration*: Simplifies implementation but fails UX expectations when providers stall.
  - *2 s cap*: Unrealistic given provider throttles; would force aggressive sampling that sacrifices accuracy.

## Decision: Define caching, error handling, and offline tolerance constraints
- **Rationale**: To minimize redundant provider calls, index universes and liquidity responses should be cached in Streamlit session state and persisted to local shard files for 15 minutes. Errors from providers must surface as inline alerts with retry guidance so researchers understand the failure mode. Offline usage is not required, but the UI should detect missing network access and disable fetch actions to avoid confusion.
- **Alternatives considered**:
  - *No caching*: Guarantees fresh data but dramatically slows interaction and increases provider load.
  - *Long-lived (>1 h) cache*: Risks stale liquidity data in fast-moving markets; not acceptable for research accuracy.
  - *Full offline mode*: Valuable but out-of-scope; requires heavier local data management.

## Decision: Apply Streamlit best practices for scalable state management
- **Rationale**: Using `st.session_state` for universe cache, filter state, and draft portfolio ensures stateless rerenders remain performant. Employing `st.cache_data` with explicit TTL aligns with the 15 minute window and prevents redundant disk reads. Breaking UI into modular functions keeps the app maintainable.
- **Alternatives considered**:
  - *Global module-level state*: Simpler but risks cross-user contamination when deployed on shared hosts.
  - *Custom state manager library*: Overkill for current scope; increases maintenance burden.

## Decision: Standardize CLI behavior via Click command group
- **Rationale**: Click already underpins existing CLI tooling in the repo. Extending it with `portfolio curate` and `portfolio delete` commands ensures consistent ergonomics, argument parsing, and help text.
- **Alternatives considered**:
  - *Argparse*: Lightweight but diverges from existing CLI style.
  - *Typer*: Nice developer experience but adds another dependency and pattern.
