# tests/cli/test_main.py
from typer.testing import CliRunner


def test_main_app_callable():
    from src.main import app
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0


def test_main_app_registers_callbacks():
    from util.common.signal_bus import signal_bus
    import src.main  # noqa: F401
    assert len(signal_bus.ToastNotification._callbacks) > 0
