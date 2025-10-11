from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Dict, Tuple
import warnings

import pandas as pd

try:  # optional parquet engines
    import pyarrow as _pyarrow  # type: ignore  # noqa: F401

    _PARQUET_AVAILABLE = True
except ImportError:
    try:
        import fastparquet as _fastparquet  # type: ignore  # noqa: F401

        _PARQUET_AVAILABLE = True
    except ImportError:
        _PARQUET_AVAILABLE = False


class MarketDataCache:
    """Hybrid in-memory and disk cache for OHLCV bars."""

    def __init__(self, root: Path, max_items: int = 32) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.max_items = max_items
        self.parquet_available = _PARQUET_AVAILABLE
        self._parquet_warning_emitted = False
        self._memory: "OrderedDict[Tuple[str, str], pd.DataFrame]" = OrderedDict()

    # Memory cache -----------------------------------------------------
    def get_memory(self, symbol: str, interval: str) -> pd.DataFrame | None:
        key = (symbol.upper(), interval)
        frame = self._memory.get(key)
        if frame is not None:
            # mark as recently used
            self._memory.move_to_end(key)
        return frame

    def store_memory(self, symbol: str, interval: str, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        key = (symbol.upper(), interval)
        self._memory[key] = frame.copy()
        self._memory.move_to_end(key)
        while len(self._memory) > self.max_items:
            self._memory.popitem(last=False)

    def drop_memory(self, symbol: str, interval: str) -> None:
        key = (symbol.upper(), interval)
        self._memory.pop(key, None)

    # Disk cache -------------------------------------------------------
    def _shard_file(self, symbol: str, interval: str, start: str, end: str) -> Path:
        safe_symbol = symbol.upper()
        return self.root / "ohlcv" / safe_symbol / interval / f"{start}_{end}.parquet"

    def _shard_path(self, symbol: str, interval: str, start: str, end: str) -> Path:
        path = self._shard_file(symbol, interval, start, end)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def store_disk(
        self, symbol: str, interval: str, start: str, end: str, frame: pd.DataFrame
    ) -> Path | None:
        if frame.empty:
            return None
        if not self.parquet_available:
            if not self._parquet_warning_emitted:
                warnings.warn(
                    "Parquet engine not available; disk caching disabled. Install pyarrow or fastparquet to enable.",
                    RuntimeWarning,
                    stacklevel=2,
                )
                self._parquet_warning_emitted = True
            return None
        path = self._shard_path(symbol, interval, start, end)
        tmp_path = path.with_suffix(".parquet.tmp")
        frame.to_parquet(tmp_path)
        tmp_path.replace(path)
        return path

    def load_disk(
        self, symbol: str, interval: str, start: str, end: str
    ) -> pd.DataFrame | None:
        if not self.parquet_available:
            return None
        path = self._shard_file(symbol, interval, start, end)
        if not path.exists():
            return None
        frame = pd.read_parquet(path)
        if frame.index.tz is None:
            frame.index = frame.index.tz_localize("UTC")
        return frame

    def delete_disk(self, symbol: str, interval: str, start: str, end: str) -> None:
        path = self._shard_file(symbol, interval, start, end)
        if path.exists():
            path.unlink()
