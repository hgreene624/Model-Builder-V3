from __future__ import annotations

from datetime import datetime

from model_builder.profiles.models import StrategyProfile, new_profile_payload
from model_builder.profiles.repository import StrategyProfileRepository
from src.storage.layout import StorageLayout


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _make_profile(profile_id: str, updated_at: str) -> StrategyProfile:
    timestamp = _dt(updated_at)
    return new_profile_payload(
        profile_id=profile_id,
        name=f"Profile {profile_id}",
        portfolio_id="portfolio-1",
        train_percentage=0.6,
        parameters={"atr_window": 14},
        atr_warmup_days=14,
        created_at=timestamp,
        updated_at=timestamp,
    )


def test_save_and_load_roundtrip(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)
    profile = _make_profile("alpha", "2025-01-01T00:00:00")

    repository.save_profile(profile)

    loaded = repository.load_profile("alpha")
    assert loaded == profile


def test_list_profiles_sorted_by_updated_descending(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)

    for profile_id, updated in [
        ("alpha", "2025-01-01T01:00:00"),
        ("bravo", "2025-01-01T03:00:00"),
        ("charlie", "2025-01-01T02:00:00"),
    ]:
        repository.save_profile(_make_profile(profile_id, updated))

    ordered = repository.list_profiles()
    assert [profile.profile_id for profile in ordered] == ["bravo", "charlie", "alpha"]


def test_delete_profile_removes_artifact(tmp_path) -> None:
    layout = StorageLayout(root=tmp_path)
    repository = StrategyProfileRepository(layout=layout)
    repository.save_profile(_make_profile("alpha", "2025-01-01T00:00:00"))

    assert repository.delete_profile("alpha") is True
    assert repository.load_profile("alpha") is None
    assert repository.delete_profile("alpha") is False
