# Storage Layout Contract

## Root

`DATA_DIR` defaults to `<project>/storage`. All paths below are relative to this root. Atomic writes use `*.tmp` followed by `os.replace`.

## Directory Structure

```
storage/
├── ohlcv/                 # Parquet shards per symbol/interval
│   └── {symbol}/
│       └── {interval}/
│           └── {start}_{end}.parquet
├── portfolios/
│   └── {portfolio_id}.json
├── parameters/
│   └── {parameter_set_id}.json
├── runs/
│   └── {run_id}/          # Optional intermediate artifacts/checkpoints
├── logs/
│   └── {run_id}.jsonl     # TrainingLogger output
├── simulations/
│   └── {simulation_id}/
│       ├── result.json
│       ├── equity_curve.json
│       └── charts/
│           └── {chart_id}.json
├── bundles/
│   └── {bundle_id}.zip
├── benchmarks/
│   └── {symbol}.parquet
├── models/
│   ├── registry.json      # Registered model metadata
│   └── {model_id}/        # Optional packaged models
│       └── strategy.py
└── credentials/
    └── status.json
```

## File Format Requirements
- **JSON**: UTF-8 encoded, newline-terminated. Includes `schema_version` and `generated_at`.
- **JSONL**: Each line is independent event with `timestamp`.
- **Parquet**: Snappy compression, column types enforced as per data model.
- **ZIP Bundles**: Contains `bundle.json`, `model/`, `parameters/`, and optional `artifacts/`.

## Access Helpers
- `storage/layout.py` exposes functions:
  - `path_for_portfolio(portfolio_id)`
  - `path_for_parameter_set(parameter_set_id)`
  - `path_for_log(run_id)`
  - `path_for_simulation(simulation_id)`
  - `path_for_bundle(bundle_id)`
  - `path_for_benchmark(symbol)`
  - `path_for_market_shard(symbol, interval, start, end)`

## Migration Policy
- Each JSON artifact includes `schema_version`. When loading, `storage/migrations.py` upgrades to latest version before returning data.
- Parquet schema evolution handled via DataFrame reindexing on write.

## Retention & Rotation
- JSONL logs rotate when exceeding 10 MB (configurable). Rotated files suffixed with `.1`, `.2`, etc.
- Simulation charts older than configurable retention may be archived; manifest references remain intact.

## Integrity Checks
- Checksums stored alongside bundles (`bundle.json` -> `checksum` field).
- Loader verifies file presence before exposure in UI; missing files raise `ArtifactMissingError`.

## Permissions
- Files created with `0o600` default permissions to avoid accidental sharing of credentials or proprietary data.
