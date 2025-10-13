from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import Any, Dict, Mapping

from .constants import (
    DEFAULT_ATR_WARMUP_DAYS,
    MIN_HOLDOUT_DAYS,
    PROFILE_SCHEMA_VERSION,
)


def _major_version(version: str) -> str:
    return version.split(".", maxsplit=1)[0]


def _ensure(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date string (YYYY-MM-DD).") from exc


def _parse_datetime(value: str, field_name: str) -> datetime:
    try:
        # fromisoformat accepts both naive and offset-aware values
        return datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(
            f"{field_name} must be an ISO 8601 datetime string (e.g., 2025-01-01T00:00:00)."
        ) from exc


def _iso_date(value: date) -> str:
    return value.isoformat()


def _iso_datetime(value: datetime) -> str:
    return value.isoformat()


def _ensure_text_bounds(value: str, field_name: str, *, max_length: int) -> None:
    _ensure(value.strip() != "", f"{field_name} must be non-empty.")
    _ensure(len(value) <= max_length, f"{field_name} must be ≤ {max_length} characters.")


def _ensure_percentage(value: float, field_name: str) -> None:
    _ensure(0 < value < 1, f"{field_name} must be between 0 and 1 (exclusive).")


def _ensure_positive_int(value: int, field_name: str, *, minimum: int = 1) -> None:
    _ensure(isinstance(value, int), f"{field_name} must be an integer.")
    _ensure(value >= minimum, f"{field_name} must be ≥ {minimum}.")


@dataclass(frozen=True)
class CoverageWindow:
    portfolio_id: str
    coverage_start: date
    coverage_end: date
    train_start: date
    train_end: date
    holdout_start: date
    holdout_end: date
    warmup_start: date

    def validate(self) -> None:
        _ensure_text_bounds(self.portfolio_id, "portfolio_id", max_length=80)
        _ensure(
            self.coverage_start <= self.coverage_end,
            "coverage_end must be on or after coverage_start.",
        )
        _ensure(
            self.coverage_start <= self.train_start <= self.train_end <= self.coverage_end,
            "train window must fall within overall coverage.",
        )
        _ensure(
            self.coverage_start <= self.holdout_start <= self.holdout_end <= self.coverage_end,
            "holdout window must fall within overall coverage.",
        )
        _ensure(self.train_end < self.holdout_start, "holdout must start after training ends.")
        holdout_days = (self.holdout_end - self.holdout_start).days + 1
        _ensure(
            holdout_days >= MIN_HOLDOUT_DAYS,
            f"holdout window must contain at least {MIN_HOLDOUT_DAYS} day(s).",
        )
        _ensure(
            self.warmup_start <= self.train_start,
            "warmup_start must be on or before train_start.",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "coverage_start": _iso_date(self.coverage_start),
            "coverage_end": _iso_date(self.coverage_end),
            "train_start": _iso_date(self.train_start),
            "train_end": _iso_date(self.train_end),
            "holdout_start": _iso_date(self.holdout_start),
            "holdout_end": _iso_date(self.holdout_end),
            "warmup_start": _iso_date(self.warmup_start),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> CoverageWindow:
        instance = cls(
            portfolio_id=str(payload["portfolio_id"]),
            coverage_start=_parse_date(str(payload["coverage_start"]), "coverage_start"),
            coverage_end=_parse_date(str(payload["coverage_end"]), "coverage_end"),
            train_start=_parse_date(str(payload["train_start"]), "train_start"),
            train_end=_parse_date(str(payload["train_end"]), "train_end"),
            holdout_start=_parse_date(str(payload["holdout_start"]), "holdout_start"),
            holdout_end=_parse_date(str(payload["holdout_end"]), "holdout_end"),
            warmup_start=_parse_date(str(payload["warmup_start"]), "warmup_start"),
        )
        instance.validate()
        return instance

    def with_warmup_start(self, warmup_start: date) -> CoverageWindow:
        return replace(self, warmup_start=warmup_start)


@dataclass(frozen=True)
class StrategyProfile:
    schema_version: str
    profile_id: str
    name: str
    description: str | None
    portfolio_id: str
    train_percentage: float
    atr_warmup_days: int
    parameters: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime

    def validate(self) -> None:
        supported_major = _major_version(PROFILE_SCHEMA_VERSION)
        _ensure(
            _major_version(self.schema_version) == supported_major,
            f"Unsupported schema version '{self.schema_version}'. Expected major version "
            f"{supported_major}.",
        )
        _ensure_text_bounds(self.profile_id, "profile_id", max_length=64)
        _ensure_text_bounds(self.name, "name", max_length=80)
        if self.description is not None:
            _ensure(len(self.description) <= 500, "description must be ≤ 500 characters.")
        _ensure_text_bounds(self.portfolio_id, "portfolio_id", max_length=80)
        _ensure_percentage(self.train_percentage, "train_percentage")
        _ensure_positive_int(self.atr_warmup_days, "atr_warmup_days", minimum=1)
        _ensure(
            isinstance(self.parameters, Mapping),
            "parameters must be a mapping of strategy-specific settings.",
        )
        _ensure(
            self.created_at <= self.updated_at,
            "updated_at must be on or after created_at.",
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "name": self.name,
            "description": self.description,
            "portfolio_id": self.portfolio_id,
            "train_percentage": self.train_percentage,
            "atr_warmup_days": self.atr_warmup_days,
            "parameters": dict(self.parameters),
            "created_at": _iso_datetime(self.created_at),
            "updated_at": _iso_datetime(self.updated_at),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> StrategyProfile:
        description = payload.get("description")
        instance = cls(
            schema_version=str(payload.get("schema_version", PROFILE_SCHEMA_VERSION)),
            profile_id=str(payload["profile_id"]),
            name=str(payload["name"]),
            description=str(description) if description is not None else None,
            portfolio_id=str(payload["portfolio_id"]),
            train_percentage=float(payload["train_percentage"]),
            atr_warmup_days=int(payload.get("atr_warmup_days", DEFAULT_ATR_WARMUP_DAYS)),
            parameters=dict(payload.get("parameters", {})),
            created_at=_parse_datetime(str(payload["created_at"]), "created_at"),
            updated_at=_parse_datetime(str(payload["updated_at"]), "updated_at"),
        )
        instance.validate()
        return instance

    def with_updates(self, **changes: Any) -> StrategyProfile:
        """Return a copy with specific fields updated."""

        candidate = replace(self, **changes)
        candidate.validate()
        return candidate

    def ensure_supported_schema(self) -> None:
        """Explicit hook for callers that only need to enforce schema compliance."""

        self.validate()


def new_profile_payload(
    *,
    profile_id: str,
    name: str,
    portfolio_id: str,
    train_percentage: float,
    parameters: Mapping[str, Any] | None = None,
    description: str | None = None,
    atr_warmup_days: int = DEFAULT_ATR_WARMUP_DAYS,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> StrategyProfile:
    """Factory helper used by repositories and services."""

    now = datetime.utcnow()
    created = created_at or now
    updated = updated_at or now
    profile = StrategyProfile(
        schema_version=PROFILE_SCHEMA_VERSION,
        profile_id=profile_id,
        name=name,
        description=description,
        portfolio_id=portfolio_id,
        train_percentage=train_percentage,
        atr_warmup_days=atr_warmup_days,
        parameters=dict(parameters or {}),
        created_at=created,
        updated_at=updated,
    )
    profile.validate()
    return profile
