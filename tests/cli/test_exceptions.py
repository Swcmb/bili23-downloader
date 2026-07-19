# tests/cli/test_exceptions.py
def test_exception_exit_codes():
    from cli.exceptions import (
        Bili23Error, ParseError, AuthRequiredError, NetworkError,
        DiskFullError, FFmpegMissingError, ConfigError, UserCancelledError
    )
    assert Bili23Error().exit_code == 70
    assert ParseError().exit_code == 4
    assert AuthRequiredError().exit_code == 5
    assert NetworkError().exit_code == 6
    assert DiskFullError().exit_code == 7
    assert FFmpegMissingError().exit_code == 8
    assert ConfigError().exit_code == 9
    assert UserCancelledError().exit_code == 3
