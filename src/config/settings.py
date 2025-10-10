from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    """Runtime configuration derived from environment variables."""

    data_dir: Path
    preferred_provider: str
    alpaca_key_id: str | None
    alpaca_secret_key: str | None

    @property
    def has_alpaca_credentials(self) -> bool:
        return bool(self.alpaca_key_id and self.alpaca_secret_key)

    @classmethod
    def from_env(cls) -> "AppSettings":
        data_dir_env = os.getenv("DATA_DIR", "storage")
        data_dir = Path(data_dir_env)
        if not data_dir.is_absolute():
            data_dir = Path.cwd() / data_dir

        preferred_provider = os.getenv("PREFERRED_PROVIDER", "alpaca").lower()

        return cls(
            data_dir=data_dir,
            preferred_provider=preferred_provider,
            alpaca_key_id=os.getenv("ALPACA_KEY_ID"),
            alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY"),
        )
