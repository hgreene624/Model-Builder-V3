from __future__ import annotations

import json
from pathlib import Path

import typer

from src.config.settings import AppSettings
from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader
from src.data.universe_loader import UniverseNotFoundError, load_universe
from src.portfolio import services
from src.portfolio.filters import filter_universe
from src.portfolio.liquidity import fetch_liquidity
from src.portfolio.seeds import SEED_COLLECTIONS
from src.storage.artifacts import ArtifactStore
from src.storage.layout import StorageLayout

portfolio_app = typer.Typer(help="Portfolio commands")


def _build_loader(settings: AppSettings) -> MarketDataLoader:
    cache = MarketDataCache(root=settings.data_dir / "cache", max_items=16)

    from src.data.providers.alpaca_client import AlpacaClient
    from src.data.providers.yahoo_client import YahooClient

    providers = {
        "alpaca": lambda: AlpacaClient().fetch_bars,
        "yahoo": lambda: YahooClient().fetch_bars,
    }
    default = "alpaca" if settings.has_alpaca_credentials else "yahoo"
    return MarketDataLoader(cache=cache, providers=providers, default_provider=default)


def _load_symbols(seed: str | None, csv: Path | None, include: str | None) -> list[str]:
    symbols: list[str] = []
    if seed:
        symbols.extend(SEED_COLLECTIONS.get(seed, []))
    if csv:
        contents = Path(csv).read_text().splitlines()
        for line in contents:
            values = [segment.strip() for segment in line.split(",")]
            symbols.extend(values)
    return services.apply_filters(
        services.normalize_symbols(symbols),
        include_substring=include or None,
    )


def _parse_sectors(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [segment.strip() for segment in raw.split(",") if segment.strip()]


@portfolio_app.command("curate")
def curate(
    seed: str | None = typer.Option(None, help="Seed collection name"),
    csv: Path | None = typer.Option(None, help="Path to CSV with tickers"),
    include: str | None = typer.Option(None, help="Only keep tickers containing substring"),
    exclude: str | None = typer.Option(None, help="Drop tickers containing substring"),
    universe: str | None = typer.Option(
        None, help="Universe identifier to load from storage/index_universes"
    ),
    search: str | None = typer.Option(
        None, help="Case-insensitive text search for universe filtering"
    ),
    sectors: str | None = typer.Option(
        None, help="Comma-separated sector filters when using universes"
    ),
    min_price: float | None = typer.Option(None, help="Median price floor"),
    min_dollar_volume: float | None = typer.Option(None, help="Median dollar volume floor"),
    max_count: int = typer.Option(100, min=10, max=500, help="Cap on universe size"),
    start: str = typer.Option("2020-01-01", help="Coverage start (YYYY-MM-DD)"),
    end: str = typer.Option("2025-01-01", help="Coverage end (YYYY-MM-DD)"),
    name: str | None = typer.Option(None, help="Portfolio name"),
    description: str | None = typer.Option(None, help="Optional description"),
    output: Path | None = typer.Option(None, help="Optional path to write portfolio JSON"),
) -> None:
    """Curate and optionally save a portfolio from seeds or CSV."""
    settings = AppSettings.from_env()
    if universe and (seed or csv):
        raise typer.BadParameter("Use either --universe or seed/csv inputs, not both.")
    if not any([universe, seed, csv]):
        raise typer.BadParameter("Provide a universe, seed, or CSV source to supply tickers.")

    sector_list = _parse_sectors(sectors)
    filters_metadata: dict[str, object] = {
        "include": include,
        "exclude": exclude,
        "max_count": max_count,
    }
    thresholds_requested: dict[str, float] = {}
    if min_price is not None:
        thresholds_requested["price_floor"] = float(min_price)
    if min_dollar_volume is not None:
        thresholds_requested["volume_floor"] = float(min_dollar_volume)

    if universe:
        universe_dir = settings.data_dir / "index_universes"
        try:
            universe_model = load_universe(universe, directory=universe_dir)
        except UniverseNotFoundError as exc:
            raise typer.BadParameter(str(exc)) from exc
        frame, _ = filter_universe(
            universe_model,
            search=search,
            sectors=sector_list,
            max_symbols=max_count,
        )
        symbols = frame.index.tolist()
        filters_metadata["search"] = search
        if sector_list:
            filters_metadata["sectors"] = sector_list
        filters_metadata["universe"] = {
            "identifier": universe,
            "name": universe_model.name,
        }
    else:
        symbols = _load_symbols(seed, csv, include)
        if exclude:
            symbols = services.apply_filters(symbols, exclude_substring=exclude)
        if not symbols:
            raise typer.Exit("No tickers left after applying filters.")
        symbols = symbols[:max_count]
        if sector_list:
            filters_metadata["sectors"] = sector_list

    if exclude:
        symbols = services.apply_filters(symbols, exclude_substring=exclude)
    if not symbols:
        raise typer.Exit("No tickers left after applying filters.")

    loader = _build_loader(settings)

    removed_by_thresholds = 0
    if thresholds_requested:
        liquidity_frame, summary, errors = fetch_liquidity(loader, symbols, start, end)
        if errors:
            for err in errors[:5]:
                typer.echo(f"[warn] {err['symbol']}: {err['error']}")
        filtered = liquidity_frame.copy()
        if min_price is not None:
            filtered = filtered[filtered["median_price"].fillna(0) >= min_price]
        if min_dollar_volume is not None:
            filtered = filtered[filtered["median_dollar_volume"].fillna(0) >= min_dollar_volume]
        retained = filtered.index.tolist()
        removed_by_thresholds = len(symbols) - len(retained)
        symbols = [symbol for symbol in symbols if symbol in retained]
        symbols = symbols[:max_count]
        if not symbols:
            typer.echo("No tickers met the requested liquidity thresholds.")
            raise typer.Exit(code=1)

    source_type = "universe" if universe else ("seed" if seed else "manual")
    default_name = name or (
        f"{universe} Portfolio" if universe else (f"{seed} Universe" if seed else "CLI Portfolio")
    )

    portfolio, preview = services.build_portfolio(
        name=default_name,
        description=description,
        source=source_type,
        seed_reference=universe or seed,
        symbols=symbols,
        max_count=max_count,
        coverage_start=start,
        coverage_end=end,
        loader=loader,
        filters={
            **filters_metadata,
            "thresholds": thresholds_requested or None,
        },
    )

    typer.echo(
        f"Selected {len(preview.tickers)} tickers. Median price: {preview.stats['median_price']:.2f}"
    )

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(portfolio.__dict__, indent=2))
        typer.echo(f"Portfolio written to {output}")
    else:
        layout = StorageLayout(root=settings.data_dir)
        store = ArtifactStore(layout=layout)
        store.save_portfolio(portfolio)
        typer.echo(f"Portfolio saved under {settings.data_dir / 'portfolios'}")

    if thresholds_requested:
        typer.echo(
            "Applied thresholds: "
            + ", ".join(f"{key}={value}" for key, value in thresholds_requested.items())
        )
        if removed_by_thresholds:
            typer.echo(f"Pruned {removed_by_thresholds} tickers that failed thresholds.")


@portfolio_app.command("delete")
def delete(
    name: str = typer.Argument(..., help="Portfolio name to delete"),
) -> None:
    """Delete a saved portfolio by name."""
    settings = AppSettings.from_env()
    layout = StorageLayout(root=settings.data_dir)
    store = ArtifactStore(layout=layout)
    portfolio_id = services.normalize_portfolio_id(name)
    if not store.delete_portfolio(portfolio_id):
        typer.echo(f"Portfolio '{name}' not found.")
        raise typer.Exit(code=1)
    typer.echo(f"Deleted portfolio '{name}'.")
