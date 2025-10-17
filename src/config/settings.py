from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppSettings:
    """Runtime configuration derived from environment variables and Streamlit secrets."""

    data_dir: Path
    preferred_provider: str
    alpaca_key_id: str | None
    alpaca_secret_key: str | None
    alpaca_trade_base_url: str | None
    alpaca_data_base_url: str | None

    @property
    def has_alpaca_credentials(self) -> bool:
        return bool(self.alpaca_key_id and self.alpaca_secret_key)

    @classmethod
    def from_env(cls) -> AppSettings:
        data_dir_env = os.getenv("DATA_DIR", "storage")
        data_dir = Path(data_dir_env)
        if not data_dir.is_absolute():
            data_dir = Path.cwd() / data_dir

        preferred_provider = os.getenv("PREFERRED_PROVIDER", "alpaca").lower()

        secret_key = None
        secret_secret = None
        secret_base = None

        try:
            import streamlit as st

            secret_dict = getattr(st, "secrets", {})
            if secret_dict:
                secret_key = secret_dict.get("ALPACA_API_KEY") or secret_dict.get("ALPACA_KEY_ID")
                secret_secret = secret_dict.get("ALPACA_SECRET_KEY")
                secret_base = secret_dict.get("ALPACA_API_BASE_URL") or secret_dict.get(
                    "ALPACA_BASE_URL"
                )
        except ModuleNotFoundError:
            pass

        env_key = (
            os.getenv("ALPACA_KEY_ID")
            or os.getenv("ALPACA_API_KEY")
            or os.getenv("APCA_API_KEY_ID")
            or secret_key
        )
        env_secret = (
            os.getenv("ALPACA_SECRET_KEY") or os.getenv("APCA_API_SECRET_KEY") or secret_secret
        )
        env_trade = (
            os.getenv("ALPACA_API_BASE_URL") or os.getenv("APCA_API_BASE_URL") or secret_base
        )
        env_data = (
            os.getenv("APCA_DATA_API_BASE_URL")
            or os.getenv("ALPACA_DATA_API_BASE_URL")
            or os.getenv("ALPACA_DATA_URL")
        )

        return cls(
            data_dir=data_dir,
            preferred_provider=preferred_provider,
            alpaca_key_id=env_key,
            alpaca_secret_key=env_secret,
            alpaca_trade_base_url=env_trade,
            alpaca_data_base_url=env_data,
        )
