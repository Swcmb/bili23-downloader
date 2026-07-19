# tests/cli/test_app.py
from typer.testing import CliRunner


def test_version_option():
    from cli.app import app
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "3.0.0" in result.stdout


def test_help_option():
    from cli.app import app
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "bili23" in result.stdout


def test_no_args_shows_help():
    from cli.app import app
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0
