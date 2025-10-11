from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.config.settings import AppSettings


def test_settings_defaults(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.delenv("PREFERRED_PROVIDER", raising=False)
    monkeypatch.delenv("ALPACA_KEY_ID", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("APCA_API_KEY_ID", raising=False)
    monkeypatch.delenv("APCA_API_SECRET_KEY", raising=False)
    monkeypatch.delenv("ALPACA_API_BASE_URL", raising=False)
    monkeypatch.delenv("APCA_API_BASE_URL", raising=False)

    import sys
    import types

    dummy_streamlit = types.SimpleNamespace(secrets={})
    monkeypatch.setitem(sys.modules, "streamlit", dummy_streamlit)

    settings = AppSettings.from_env()

    assert settings.data_dir == tmp_path / "storage"
    assert settings.preferred_provider == "alpaca"
    assert not settings.has_alpaca_credentials


def test_settings_env_overrides(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "custom"))
    monkeypatch.setenv("PREFERRED_PROVIDER", "yahoo")
    monkeypatch.setenv("ALPACA_KEY_ID", "key")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "secret")

    settings = AppSettings.from_env()

    assert settings.data_dir == tmp_path / "custom"
    assert settings.preferred_provider == "yahoo"
    assert settings.has_alpaca_credentials
