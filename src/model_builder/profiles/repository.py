from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from model_builder.profiles.models import StrategyProfile
from src.storage.layout import StorageLayout


def _load_profile(path: Path) -> StrategyProfile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    profile = StrategyProfile.from_dict(payload)
    profile.ensure_supported_schema()
    return profile


@dataclass(frozen=True)
class StrategyProfileRepository:
    """Persistence layer for strategy profile artifacts."""

    layout: StorageLayout

    def list_profiles(self) -> list[StrategyProfile]:
        directory = self.layout.strategy_profiles_directory()
        profiles: list[StrategyProfile] = []
        for path in directory.glob("*.json"):
            profile = _load_profile(path)
            profiles.append(profile)

        profiles.sort(key=lambda item: (item.updated_at, item.profile_id), reverse=True)
        return profiles

    def iter_profiles(self) -> Iterable[StrategyProfile]:
        """Yield strategy profiles without materializing the entire list."""

        for profile in self.list_profiles():
            yield profile

    def load_profile(self, profile_id: str) -> StrategyProfile | None:
        path = self.layout.strategy_profile_path(profile_id)
        if not path.exists():
            return None
        return _load_profile(path)

    def save_profile(self, profile: StrategyProfile) -> StrategyProfile:
        profile.ensure_supported_schema()
        path = self.layout.strategy_profile_path(profile.profile_id)
        payload = profile.to_dict()

        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temp_path.replace(path)
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        path = self.layout.strategy_profile_path(profile_id)
        if not path.exists():
            return False
        path.unlink()
        return True


__all__ = ["StrategyProfileRepository"]
