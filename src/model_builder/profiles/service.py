from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, MutableMapping

from model_builder.profiles.models import StrategyProfile, new_profile_payload
from .repository import StrategyProfileRepository


def _ensure_mapping(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise TypeError("parameters must be a mapping.")
    return {str(key): value for key, value in payload.items()}


def _ensure_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _coerce_datetime(value: Any, *, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return fallback


class ProfileNotFoundError(FileNotFoundError):
    """Raised when operations target a missing strategy profile."""


def _generate_profile_id() -> str:
    return uuid.uuid4().hex


def _utcnow() -> datetime:
    return datetime.utcnow()


@dataclass
class ProfilesService:
    """Application service orchestrating strategy profile persistence."""

    repository: StrategyProfileRepository
    id_factory: Callable[[], str] = field(default=_generate_profile_id)
    clock: Callable[[], datetime] = field(default=_utcnow)

    def __post_init__(self) -> None:
        if not callable(self.id_factory):
            raise TypeError("id_factory must be callable.")
        if not callable(self.clock):
            raise TypeError("clock must be callable.")

    # DTO helpers -----------------------------------------------------------------
    @staticmethod
    def _to_summary(profile: StrategyProfile) -> dict[str, Any]:
        return {
            "profile_id": profile.profile_id,
            "name": profile.name,
            "portfolio_id": profile.portfolio_id,
            "updated_at": profile.updated_at.isoformat(),
        }

    @staticmethod
    def _to_dict(profile: StrategyProfile) -> dict[str, Any]:
        payload = profile.to_dict()
        payload["created_at"] = profile.created_at.isoformat()
        payload["updated_at"] = profile.updated_at.isoformat()
        return payload

    # Public API ------------------------------------------------------------------
    def list_profiles(self) -> list[dict[str, Any]]:
        profiles = self.repository.list_profiles()
        return [self._to_summary(profile) for profile in profiles]

    def load_profile(self, profile_id: str) -> dict[str, Any]:
        profile = self.repository.load_profile(profile_id)
        if profile is None:
            raise ProfileNotFoundError(f"Strategy profile '{profile_id}' was not found.")
        return self._to_dict(profile)

    def save_profile(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        profile_id = data.get("profile_id") or self.id_factory()
        profile_id = str(profile_id)

        existing = self.repository.load_profile(profile_id)
        now = self.clock()

        if existing is None:
            profile = self._create_profile(profile_id, data, now)
        else:
            profile = self._update_profile(existing, data, now)

        saved = self.repository.save_profile(profile)
        return self._to_dict(saved)

    def _create_profile(
        self,
        profile_id: str,
        data: MutableMapping[str, Any],
        timestamp: datetime,
    ) -> StrategyProfile:
        try:
            name = data["name"]
            portfolio_id = data["portfolio_id"]
            train_percentage = data["train_percentage"]
            atr_warmup_days = data["atr_warmup_days"]
            parameters = data["parameters"]
        except KeyError as exc:
            raise KeyError(f"Missing required field: {exc.args[0]}") from exc

        created_at = _coerce_datetime(data.get("created_at"), fallback=timestamp)

        profile = new_profile_payload(
            profile_id=str(profile_id),
            name=str(name),
            portfolio_id=str(portfolio_id),
            train_percentage=float(train_percentage),
            parameters=_ensure_mapping(parameters),
            description=_ensure_optional_str(data.get("description")),
            atr_warmup_days=int(atr_warmup_days),
            created_at=created_at,
            updated_at=timestamp,
        )
        return profile

    def _update_profile(
        self,
        existing: StrategyProfile,
        data: MutableMapping[str, Any],
        timestamp: datetime,
    ) -> StrategyProfile:
        updates: dict[str, Any] = {"updated_at": timestamp}

        if "name" in data:
            updates["name"] = str(data["name"])
        if "description" in data:
            updates["description"] = _ensure_optional_str(data["description"])
        if "portfolio_id" in data:
            updates["portfolio_id"] = str(data["portfolio_id"])
        if "train_percentage" in data:
            updates["train_percentage"] = float(data["train_percentage"])
        if "atr_warmup_days" in data:
            updates["atr_warmup_days"] = int(data["atr_warmup_days"])
        if "parameters" in data:
            updates["parameters"] = _ensure_mapping(data["parameters"])

        profile = existing.with_updates(**updates)
        return profile

    def delete_profile(self, profile_id: str) -> bool:
        return self.repository.delete_profile(profile_id)


__all__ = ["ProfilesService", "ProfileNotFoundError"]
