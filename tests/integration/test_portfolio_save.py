from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli.main import app
from src.portfolio.services import build_portfolio
from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader
from src.models.contracts import Portfolio
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout


def stub_loader(tmp_path: Path) -> MarketDataLoader:
    cache = MarketDataCache(root=tmp_path, max_items=4)

    def provider(symbol: str, start: str, end: str, interval: str):
        import pandas as pd

        return pd.DataFrame(
            {
                "timestamp": pd.date_range(start, periods=5, freq="D", tz="UTC"),
                "open": [1, 2, 3, 4, 5],
                "high": [2, 3, 4, 5, 6],
                "low": [0, 1, 2, 3, 4],
                "close": [1, 2, 3, 4, 5],
                "volume": [10, 20, 30, 40, 50],
            }
        ).set_index("timestamp")

    return MarketDataLoader(cache=cache, providers={"alpaca": lambda: provider})


def test_portfolio_save_roundtrip(tmp_path: Path) -> None:
    loader = stub_loader(tmp_path)
    layout = StorageLayout(root=tmp_path)
    store = ArtifactStore(layout=layout)

    portfolio, preview = build_portfolio(
        name="Sample",
        description=None,
        source="manual",
        seed_reference="seed",
        symbols=["AAPL", "MSFT"],
        max_count=10,
        coverage_start="2024-01-01",
        coverage_end="2024-01-05",
        loader=loader,
    )

    path = store.save_portfolio(portfolio)

    assert path.exists()
    saved = json.loads(path.read_text())
    assert saved["tickers"] == ["AAPL", "MSFT"]
    assert saved["coverage_summary"]["start"] == "2024-01-01"
    assert saved["schema_version"] == "1.1.0"


def test_cli_status_counts_with_portfolio(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    layout = StorageLayout(root=storage)
    store = ArtifactStore(layout=layout)
    portfolio = Portfolio(
        portfolio_id="pf",
        name="PF",
        description=None,
        source="manual",
        seed_reference=None,
        filters={},
        coverage_window={"start": "2020", "end": "2025"},
        tickers=["AAPL"],
        liquidity_stats={"median_price": 1.0},
        notes=[],
        coverage_summary={"start": "2020", "end": "2025", "coverage_gap_count": 0},
        shard_hints={},
    )
    store.save_portfolio(portfolio)

    runner = CliRunner()
    result = runner.invoke(app, ["status"], env={"DATA_DIR": str(storage)})
    assert result.exit_code == 0
    assert "Portfolios: 1" in result.stdout


def test_cli_delete_portfolio(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    layout = StorageLayout(root=storage)
    store = ArtifactStore(layout=layout)
    portfolio = Portfolio(
        portfolio_id="deleteme",
        name="DeleteMe",
        description=None,
        source="manual",
        seed_reference=None,
        filters={},
        coverage_window={"start": "2021", "end": "2022"},
        tickers=["AAPL"],
        liquidity_stats={"median_price": 1.0, "coverage_gap_count": 0},
        notes=[],
        coverage_summary={"start": "2021", "end": "2022", "coverage_gap_count": 0},
        shard_hints={},
    )
    store.save_portfolio(portfolio)

    runner = CliRunner()
    result = runner.invoke(app, ["portfolio", "delete", "DeleteMe"], env={"DATA_DIR": str(storage)})

    assert result.exit_code == 0
    assert "Deleted portfolio 'DeleteMe'" in result.stdout
    assert not (storage / "portfolios" / "deleteme.json").exists()
