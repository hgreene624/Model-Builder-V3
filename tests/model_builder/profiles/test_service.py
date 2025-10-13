from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

import pytest

from model_builder.profiles.repository import StrategyProfileRepository
from model_builder.profiles.service import ProfileNotFoundError, ProfilesService
from src.storage.layout import StorageLayout


def _clock_factory(*timestamps: datetime) -> Callable[[], datetime]:
    queue = list(timestamps)

    def _clock() -> datetime:
        if not queue:
            raise AssertionError("Clock exhausted.")
        return queue.pop(0)

    return _clock


def test_save_profile_creates_new_profile(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)
    service = ProfilesService(
        repository=repository,
        id_factory=lambda: "generated-1",
        clock=_clock_factory(datetime(2025, 1, 1, 12, 0)),
    )

    payload = {
        "name": "Momentum Breakout",
        "portfolio_id": "portfolio-1",
        "train_percentage": 0.65,
        "atr_warmup_days": 20,
        "parameters": {"atr_window": 21},
        "description": "Baseline profile",
    }

    saved = service.save_profile(payload)
    assert saved["profile_id"] == "generated-1"
    assert saved["schema_version"] == "1.0.0"
    assert saved["name"] == "Momentum Breakout"
    assert saved["train_percentage"] == pytest.approx(0.65)
    assert saved["atr_warmup_days"] == 20
    assert saved["parameters"] == {"atr_window": 21}
    assert saved["created_at"] == "2025-01-01T12:00:00"
    assert saved["updated_at"] == "2025-01-01T12:00:00"


def test_save_profile_updates_existing(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)
    service = ProfilesService(
        repository=repository,
        id_factory=lambda: "generated-1",
        clock=_clock_factory(
            datetime(2025, 1, 1, 12, 0, 0),
            datetime(2025, 1, 2, 9, 30, 0),
        ),
    )

    base_payload = {
        "name": "Momentum Breakout",
        "portfolio_id": "portfolio-1",
        "train_percentage": 0.65,
        "atr_warmup_days": 20,
        "parameters": {"atr_window": 21},
    }
    created = service.save_profile(base_payload)

    updated = service.save_profile(
        {
            "profile_id": created["profile_id"],
            "name": "Momentum Breakout v2",
            "train_percentage": 0.7,
            "parameters": {"atr_window": 18},
        }
    )

    assert updated["profile_id"] == created["profile_id"]
    assert updated["name"] == "Momentum Breakout v2"
    assert updated["train_percentage"] == pytest.approx(0.7)
    assert updated["parameters"] == {"atr_window": 18}
    assert updated["created_at"] == "2025-01-01T12:00:00"
    assert updated["updated_at"] == "2025-01-02T09:30:00"


def test_list_profiles_returns_summaries(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)
    service = ProfilesService(
        repository=repository,
        id_factory=lambda: "alpha",
        clock=_clock_factory(
            datetime(2025, 1, 1, 12, 0, 0),
            datetime(2025, 1, 2, 15, 0, 0),
        ),
    )

    service.save_profile(
        {
            "name": "Alpha",
            "portfolio_id": "portfolio-1",
            "train_percentage": 0.6,
            "atr_warmup_days": 14,
            "parameters": {},
        }
    )
    service.save_profile(
        {
            "profile_id": "beta",
            "name": "Beta",
            "portfolio_id": "portfolio-2",
            "train_percentage": 0.7,
            "atr_warmup_days": 10,
            "parameters": {},
        }
    )

    summaries = service.list_profiles()
    assert [summary["profile_id"] for summary in summaries] == ["beta", "alpha"]
    assert summaries[0]["name"] == "Beta"
    assert summaries[0]["portfolio_id"] == "portfolio-2"


def test_load_profile_missing_raises(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)
    service = ProfilesService(repository=repository)

    with pytest.raises(ProfileNotFoundError):
        service.load_profile("does-not-exist")


def test_delete_profile_returns_boolean(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)
    service = ProfilesService(
        repository=repository,
        id_factory=lambda: "alpha",
        clock=_clock_factory(datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc)),
    )

    service.save_profile(
        {
            "name": "Alpha",
            "portfolio_id": "portfolio-1",
            "train_percentage": 0.6,
            "atr_warmup_days": 14,
            "parameters": {},
        }
    )

    assert service.delete_profile("alpha") is True
    assert service.delete_profile("alpha") is False
