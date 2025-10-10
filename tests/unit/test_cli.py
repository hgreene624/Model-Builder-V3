from __future__ import annotations

from typer.testing import CliRunner

from src.cli.main import app


def test_cli_commands_exist() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "status" in result.stdout
    assert "portfolio" in result.stdout
    assert "optimize" in result.stdout
