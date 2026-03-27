from __future__ import annotations

import pandas as pd
import pytest

from src.data.loader import SymbolDiagnostics
from src.portfolio.liquidity import fetch_liquidity


class StubLoader:
    def __init__(
        self, frames: dict[str, pd.DataFrame], errors: dict[str, Exception] | None = None
    ) -> None:
        self.frames = frames
        self.errors = errors or {}

    def load_with_diagnostics(
        self, symbol: str, start: str, end: str, *, interval: str, warmup_bars: int
    ):
        diagnostics = SymbolDiagnostics(
            symbol=symbol,
            start=start,
            end=end,
            interval=interval,
            warmup_start=start,
        )
        if symbol in self.errors:
            diagnostics.exception_message = str(self.errors[symbol])
            diagnostics.rows_returned = 0
            return pd.DataFrame(), diagnostics, self.errors[symbol]

        frame = self.frames.get(symbol, pd.DataFrame())
        diagnostics.rows_returned = int(frame.shape[0])
        diagnostics.shard_path = f"/tmp/{symbol}.parquet"
        return frame, diagnostics, None


def _frame(start: str, periods: int) -> pd.DataFrame:
    index = pd.bdate_range(start=start, periods=periods, tz="UTC")
    return pd.DataFrame(
        {
            "close": [100.0 + i for i in range(periods)],
            "volume": [1_000_000 for _ in range(periods)],
        },
        index=index,
    )


def test_fetch_liquidity_complete_coverage() -> None:
    loader = StubLoader({"AAA": _frame("2024-01-01", 5)})

    frame, summary, errors = fetch_liquidity(loader, ["AAA"], "2024-01-01", "2024-01-05")

    assert summary.requested == 1
    assert summary.complete == 1
    assert summary.coverage_ratio == pytest.approx(1.0)
    assert errors == []
    row = frame.loc["AAA"]
    assert row["coverage_status"] == "complete"
    assert row["missing_fraction"] == pytest.approx(0.0)
    assert row["shard_hints"]["cacheKey"] == "/tmp/AAA.parquet"


def test_fetch_liquidity_partial_when_missing_days() -> None:
    # Only 2 of 5 business days populated
    loader = StubLoader({"BBB": _frame("2024-01-01", 2)})

    frame, summary, errors = fetch_liquidity(loader, ["BBB"], "2024-01-01", "2024-01-05")

    assert summary.partial == 1
    row = frame.loc["BBB"]
    assert row["coverage_status"] == "partial"
    assert row["missing_fraction"] > 0.0
    assert errors == []


def test_fetch_liquidity_records_errors() -> None:
    loader = StubLoader({}, errors={"CCC": RuntimeError("provider down")})

    frame, summary, errors = fetch_liquidity(loader, ["CCC"], "2024-01-01", "2024-01-05")

    assert summary.missing == 1
    assert frame.loc["CCC", "coverage_status"] == "missing"
    assert errors[0]["symbol"] == "CCC"


def test_fetch_liquidity_handles_weekend_bounds() -> None:
    loader = StubLoader({"DDD": _frame("2024-01-08", 5)})

    frame, summary, errors = fetch_liquidity(loader, ["DDD"], "2024-01-06", "2024-01-14")

    assert summary.complete == 1
    assert errors == []
    assert frame.loc["DDD", "coverage_status"] == "complete"
