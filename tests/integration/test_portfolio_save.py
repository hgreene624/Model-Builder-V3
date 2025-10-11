from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.portfolio.services import build_portfolio
from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader, SymbolDiagnostics
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


def test_cli_curate_with_universe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    universe_dir = storage / "index_universes"
    universe_dir.mkdir(parents=True, exist_ok=True)
    universe_payload = {
        "name": "Sample Universe",
        "symbols": [
            {"ticker": "AAA", "name": "Alpha Tech", "sector": "Technology", "industry": "Software"},
            {"ticker": "BBB", "name": "Beta Utilities", "sector": "Utilities", "industry": "Electric"},
        ],
    }
    (universe_dir / "sample.json").write_text(json.dumps(universe_payload))

    class StubLoader:
        def _frame(self, symbol: str) -> pd.DataFrame:
            index = pd.bdate_range(start="2024-01-01", periods=5, tz="UTC")
            close = [2.5, 3.0, 3.5, 4.0, 4.5]
            volume = [1_500_000 for _ in range(5)]
            return pd.DataFrame({"close": close, "volume": volume}, index=index)

        def load(self, symbol: str, start: str, end: str, *, interval: str, warmup_bars: int) -> pd.DataFrame:
            return self._frame(symbol)

        def load_with_diagnostics(
            self,
            symbol: str,
            start: str,
            end: str,
            *,
            interval: str,
            warmup_bars: int,
        ):
            frame = self._frame(symbol)
            diagnostics = SymbolDiagnostics(
                symbol=symbol,
                start=start,
                end=end,
                interval=interval,
                warmup_start=start,
            )
            diagnostics.rows_returned = int(frame.shape[0])
            diagnostics.shard_path = f"/tmp/{symbol}.parquet"
            return frame, diagnostics, None

    monkeypatch.setattr("src.cli.portfolio_cli._build_loader", lambda settings: StubLoader())

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "portfolio",
            "curate",
            "--universe",
            "sample",
            "--search",
            "tech",
            "--sectors",
            "Technology",
            "--min-price",
            "2",
            "--min-dollar-volume",
            "1000000",
            "--name",
            "Sample Portfolio",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-05",
        ],
        env={"DATA_DIR": str(storage)},
    )

    assert result.exit_code == 0, result.output
    saved_path = storage / "portfolios" / "sample-portfolio.json"
    assert saved_path.exists()
    saved = json.loads(saved_path.read_text())
    assert saved["filters"]["universe"]["identifier"] == "sample"
    assert saved["filters"]["thresholds"]["price_floor"] == 2.0
    assert saved["filters"]["thresholds"]["volume_floor"] == 1_000_000.0
    assert saved["tickers"] == ["AAA"]
