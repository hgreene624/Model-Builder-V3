from __future__ import annotations

import typer

from src.config.settings import AppSettings

app = typer.Typer(help="Model Builder CLI")


@app.command()
def status() -> None:
    """Print credential and storage status."""
    settings = AppSettings.from_env()
    typer.echo(f"DATA_DIR: {settings.data_dir}")
    typer.echo(f"Preferred provider: {settings.preferred_provider}")
    typer.echo(
        "Alpaca credentials: present" if settings.has_alpaca_credentials else "Alpaca credentials: missing"
    )


@app.command("portfolio")
def portfolio() -> None:  # pragma: no cover - placeholder for future implementation
    typer.echo("Portfolio commands will arrive in Phase 3 (use the Streamlit UI for now).")


@app.command("optimize")
def optimize() -> None:  # pragma: no cover
    typer.echo("Optimization CLI will be implemented in a later phase.")


if __name__ == "__main__":
    app()
