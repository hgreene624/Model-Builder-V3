from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Sequence, Tuple


class UniverseNotFoundError(FileNotFoundError):
    """Raised when an index universe file cannot be located."""


class UniverseValidationError(ValueError):
    """Raised when an index universe file fails validation rules."""


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


DEFAULT_UNIVERSE_DIR = _project_root() / "storage" / "index_universes"


def _normalize_identifier(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


@dataclass(frozen=True)
class UniverseSymbol:
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    list_date: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "name": self.name,
            "sector": self.sector,
            "industry": self.industry,
            "market_cap": self.market_cap,
            "list_date": self.list_date,
        }


@dataclass(frozen=True)
class IndexUniverse:
    name: str
    as_of: str | None
    metadata: dict[str, Any]
    symbols: Tuple[UniverseSymbol, ...]
    source_path: Path

    @property
    def tickers(self) -> List[str]:
        return [symbol.ticker for symbol in self.symbols]

    def to_records(self) -> List[dict[str, Any]]:
        return [symbol.as_dict() for symbol in self.symbols]


@dataclass(frozen=True)
class UniverseSummary:
    identifier: str
    name: str
    as_of: str | None
    symbol_count: int
    source_path: Path
    aliases: Tuple[str, ...]


def list_universes(directory: Path | None = None) -> List[UniverseSummary]:
    base_dir = directory or DEFAULT_UNIVERSE_DIR
    if not base_dir.exists():
        return []

    summaries: List[UniverseSummary] = []
    for path in sorted(base_dir.glob("*.json")):
        with path.open() as handle:
            payload = json.load(handle)
        symbols = payload.get("symbols") or payload.get("rows") or []
        metadata = payload.get("metadata") or {}
        name = payload.get("name") or path.stem
        as_of = payload.get("as_of")
        aliases: set[str] = {path.stem, name}
        original = metadata.get("original_index_id")
        if original:
            aliases.add(original)
        summaries.append(
            UniverseSummary(
                identifier=path.stem,
                name=name,
                as_of=as_of,
                symbol_count=len(symbols),
                source_path=path,
                aliases=tuple(sorted({_normalize_identifier(alias) for alias in aliases if alias})),
            )
        )
    summaries.sort(key=lambda summary: summary.name.lower())
    return summaries


def _resolve_universe(identifier: str, directory: Path) -> UniverseSummary:
    if not identifier:
        raise UniverseNotFoundError("Universe identifier is empty.")
    normalized = _normalize_identifier(identifier)

    for summary in list_universes(directory):
        if normalized in summary.aliases:
            return summary
    # Fallback to direct filename match
    candidate = directory / f"{identifier}.json"
    if candidate.exists():
        with candidate.open() as handle:
            payload = json.load(handle)
        metadata = payload.get("metadata") or {}
        aliases = {_normalize_identifier(identifier)}
        if payload.get("name"):
            aliases.add(_normalize_identifier(payload["name"]))
        original = metadata.get("original_index_id")
        if original:
            aliases.add(_normalize_identifier(original))
        return UniverseSummary(
            identifier=candidate.stem,
            name=payload.get("name", candidate.stem),
            as_of=payload.get("as_of"),
            symbol_count=len(payload.get("symbols") or payload.get("rows") or []),
            source_path=candidate,
            aliases=tuple(sorted(aliases)),
        )
    raise UniverseNotFoundError(f"Unable to locate universe for identifier '{identifier}'.")


def _ensure_unique_tickers(symbols: Sequence[UniverseSymbol]) -> None:
    seen: set[str] = set()
    for symbol in symbols:
        ticker = symbol.ticker
        if ticker in seen:
            raise UniverseValidationError(f"Duplicate ticker detected: {ticker}")
        seen.add(ticker)


def _coerce_symbols(raw_symbols: Iterable[dict[str, Any]]) -> Tuple[UniverseSymbol, ...]:
    parsed: List[UniverseSymbol] = []
    for entry in raw_symbols:
        ticker_raw = entry.get("ticker") or entry.get("symbol")
        if not ticker_raw:
            raise UniverseValidationError("Symbol entry missing 'ticker'.")
        ticker = ticker_raw.strip().upper()
        if not ticker:
            raise UniverseValidationError("Ticker value cannot be empty.")
        symbol = UniverseSymbol(
            ticker=ticker,
            name=entry.get("name"),
            sector=entry.get("sector"),
            industry=entry.get("industry"),
            market_cap=entry.get("market_cap"),
            list_date=entry.get("list_date"),
        )
        parsed.append(symbol)
    if not parsed:
        raise UniverseValidationError("Universe must contain at least one symbol.")
    _ensure_unique_tickers(parsed)
    return tuple(parsed)


def load_universe(
    identifier: str,
    *,
    directory: Path | None = None,
) -> IndexUniverse:
    base_dir = directory or DEFAULT_UNIVERSE_DIR
    summary = _resolve_universe(identifier, base_dir)
    with summary.source_path.open() as handle:
        payload = json.load(handle)

    symbols = _coerce_symbols(payload.get("symbols") or payload.get("rows") or [])
    metadata = dict(payload.get("metadata") or {})
    metadata["record_count"] = len(symbols)

    return IndexUniverse(
        name=payload.get("name", summary.name),
        as_of=payload.get("as_of"),
        metadata=metadata,
        symbols=symbols,
        source_path=summary.source_path,
    )
