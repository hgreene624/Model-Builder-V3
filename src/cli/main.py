from __future__ import annotations

import typer

from src.cli.optimizer_cli import optimizer_app
from src.cli.portfolio_cli import portfolio_app
from src.config.settings import AppSettings
from src.home.dashboard import collect_home_summary

app = typer.Typer(help="Model Builder CLI")


@app.command()
def status() -> None:
    """Print credential and storage status."""
    settings = AppSettings.from_env()
    typer.echo(f"DATA_DIR: {settings.data_dir}")
    typer.echo(f"Preferred provider: {settings.preferred_provider}")
    typer.echo(
        "Alpaca credentials: present"
        if settings.has_alpaca_credentials
        else "Alpaca credentials: missing"
    )
    summary = collect_home_summary(settings.data_dir)
    typer.echo(
        f"Portfolios: {len(summary.portfolios)} | Parameters: {len(summary.parameter_sets)} | "
        f"Simulations: {len(summary.simulations)} | Logs: {len(summary.logs)}"
    )


app.add_typer(portfolio_app, name="portfolio")
app.add_typer(optimizer_app, name="optimize")


if __name__ == "__main__":
    app()
