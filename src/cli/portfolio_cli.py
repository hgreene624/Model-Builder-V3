from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from src.config.settings import AppSettings
from src.data.cache import MarketDataCache
from src.data.loader import MarketDataLoader
from src.models.contracts import Portfolio
from src.portfolio import services
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


def _load_symbols(seed: Optional[str], csv: Optional[Path], include: Optional[str]) -> list[str]:
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


@portfolio_app.command("curate")
def curate(
    seed: Optional[str] = typer.Option(None, help="Seed collection name"),
    csv: Optional[Path] = typer.Option(None, help="Path to CSV with tickers"),
    include: Optional[str] = typer.Option(None, help="Only keep tickers containing substring"),
    exclude: Optional[str] = typer.Option(None, help="Drop tickers containing substring"),
    max_count: int = typer.Option(100, min=10, max=500, help="Cap on universe size"),
    start: str = typer.Option("2020-01-01", help="Coverage start (YYYY-MM-DD)"),
    end: str = typer.Option("2025-01-01", help="Coverage end (YYYY-MM-DD)"),
    name: Optional[str] = typer.Option(None, help="Portfolio name"),
    description: Optional[str] = typer.Option(None, help="Optional description"),
    output: Optional[Path] = typer.Option(None, help="Optional path to write portfolio JSON"),
) -> None:
    """Curate and optionally save a portfolio from seeds or CSV."""
    settings = AppSettings.from_env()
    if not seed and not csv:
        raise typer.BadParameter("Provide either --seed or --csv to supply tickers.")

    symbols = _load_symbols(seed, csv, include)
    if exclude:
        symbols = services.apply_filters(symbols, exclude_substring=exclude)
    if not symbols:
        raise typer.Exit("No tickers left after applying filters.")

    loader = _build_loader(settings)
    portfolio, preview = services.build_portfolio(
        name=name or (f"{seed} Universe" if seed else "CLI Portfolio"),
        description=description,
        source="seed" if seed else "manual",
        seed_reference=seed,
        symbols=symbols,
        max_count=max_count,
        coverage_start=start,
        coverage_end=end,
        loader=loader,
        filters={
            "include": include,
            "exclude": exclude,
            "max_count": max_count,
        },
    )

    typer.echo(f"Selected {len(preview.tickers)} tickers. Median price: {preview.stats['median_price']:.2f}")

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(portfolio.__dict__, indent=2))
        typer.echo(f"Portfolio written to {output}")
    else:
        layout = StorageLayout(root=settings.data_dir)
        store = ArtifactStore(layout=layout)
        store.save_portfolio(portfolio)
        typer.echo(f"Portfolio saved under {settings.data_dir / 'portfolios'}")


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
