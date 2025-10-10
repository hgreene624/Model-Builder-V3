from __future__ import annotations

from pathlib import Path

from src.storage.layout import StorageLayout


def test_storage_layout_paths(tmp_path: Path) -> None:
    layout = StorageLayout(root=tmp_path)
    run_id = "1234"
    portfolio_id = "pf-1"
    symbol = "AAPL"

    assert layout.portfolio_path(portfolio_id) == tmp_path / "portfolios" / "pf-1.json"
    assert layout.parameter_set_path("ps-1") == tmp_path / "parameters" / "ps-1.json"
    assert layout.run_log_path(run_id) == tmp_path / "logs" / "1234.jsonl"
    assert layout.logs_directory() == tmp_path / "logs"
    assert layout.market_shard_path(symbol, "1d", "2020-01-01", "2020-01-31") == (
        tmp_path / "ohlcv" / "AAPL" / "1d" / "2020-01-01_2020-01-31.parquet"
    )
