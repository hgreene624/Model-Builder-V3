from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from src.cli.main import app
from src.cli import portfolio_cli
from src.data.loader import MarketDataLoader
from src.data.cache import MarketDataCache


def seed_csv(tmp_path: Path, symbols: list[str]) -> Path:
    path = tmp_path / "tickers.csv"
    path.write_text("\n".join(",".join(symbols[i : i + 5]) for i in range(0, len(symbols), 5)))
    return path


def test_portfolio_cli_requires_source(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["portfolio", "curate"], env={"DATA_DIR": str(tmp_path / "storage")})
    assert result.exit_code != 0
    assert "Provide either" in result.stdout


def test_portfolio_cli_saves(tmp_path: Path, monkeypatch) -> None:
    runner = CliRunner()
    storage = tmp_path / "storage"
    storage.mkdir()
    csv = seed_csv(tmp_path, ["AAPL", "MSFT", "GOOGL", "NVDA"])

    def fake_fetch(symbol: str, start: str, end: str, interval: str):
        import pandas as pd

        return pd.DataFrame(
            {
                "timestamp": pd.date_range(start, periods=3, freq="D", tz="UTC"),
                "open": [1, 2, 3],
                "high": [2, 3, 4],
                "low": [0, 1, 2],
                "close": [1.5, 2.5, 3.5],
                "volume": [10, 20, 30],
            }
        ).set_index("timestamp")

    from src.portfolio import services

    original_load = services.compute_liquidity_table

    def stub_table(loader, symbols, start, end, diagnostics=None):
        import pandas as pd

        rows = []
        for symbol in symbols:
            rows.append({"symbol": symbol, "median_price": 1.0, "median_dollar_volume": 2.0, "observations": 3})
        if diagnostics is not None:
            diagnostics.extend([])
        return pd.DataFrame(rows)

    services.compute_liquidity_table = stub_table

    def stub_loader(settings):
        return MarketDataLoader(cache=MarketDataCache(root=tmp_path / "cache"), providers={"stub": lambda: fake_fetch}, default_provider="stub")

    monkeypatch.setattr(portfolio_cli, "_build_loader", stub_loader)

    result = runner.invoke(
        app,
        [
            "portfolio",
            "curate",
            "--csv",
            str(csv),
            "--max-count",
            "20",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-05",
        ],
        env={"DATA_DIR": str(storage)},
        catch_exceptions=False,
    )
    services.compute_liquidity_table = original_load

    assert result.exit_code == 0
    saved_files = list((storage / "portfolios").glob("*.json"))
    assert saved_files, "portfolio should be saved"
