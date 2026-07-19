# tests/cli/test_logout_cmd.py
"""T5.4 测试:bili23 logout 命令

覆盖 AC-026(logout 部分):
- 命令注册成功
- --help 退出码 0
- 无 Cookie 文件:幂等,提示"未登录",exit_code=0
- 有 Cookie 文件且 --yes:删除文件,exit_code=0
- 无 --yes 且用户选 No:exit_code=3(UserCancelledError)
- 无 --yes 且用户选 Yes:删除 Cookie,exit_code=0
- 删除失败(权限):exit_code=70(Bili23Error)
"""
import os

from typer.testing import CliRunner


def _make_cookie_file(tmp_path, content: str = "{}") -> str:
    """在 tmp_path 下创建 cookie 文件,返回路径"""
    path = tmp_path / "cookie.json"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _patch_cookie_path(monkeypatch, path: str) -> str:
    """将 directory.cookie_path 重定向到指定路径"""
    from util.common.io.directory import directory
    monkeypatch.setattr(directory, "cookie_path", path)
    return path


def test_logout_registered():
    """命令注册成功:logout 出现在 app.registered_commands"""
    from cli.app import app
    import cli.commands.logout  # noqa: F401 - 触发命令注册
    names = [cmd.name for cmd in app.registered_commands]
    assert "logout" in names


def test_logout_help():
    """bili23 logout --help 退出码 0"""
    from cli.app import app
    import cli.commands.logout  # noqa: F401
    result = CliRunner().invoke(app, ["logout", "--help"])
    assert result.exit_code == 0
    assert "logout" in result.stdout


def test_logout_no_cookie(monkeypatch, tmp_path):
    """无 Cookie 文件:幂等,提示未登录,exit_code=0"""
    from cli.app import app
    import cli.commands.logout  # noqa: F401
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))
    result = CliRunner().invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "未登录" in result.stdout


def test_logout_with_cookie_yes(monkeypatch, tmp_path):
    """有 Cookie 文件且 --yes:直接删除,exit_code=0"""
    from cli.app import app
    import cli.commands.logout  # noqa: F401
    path = _make_cookie_file(tmp_path)
    _patch_cookie_path(monkeypatch, path)
    result = CliRunner().invoke(app, ["logout", "--yes"])
    assert result.exit_code == 0
    assert "已登出" in result.stdout
    assert not os.path.exists(path)


def test_logout_cancel(monkeypatch, tmp_path):
    """无 --yes 且用户选 No:exit_code=3,文件保留"""
    from cli.app import app
    import cli.commands.logout  # noqa: F401
    from rich.prompt import Confirm
    path = _make_cookie_file(tmp_path)
    _patch_cookie_path(monkeypatch, path)
    monkeypatch.setattr(Confirm, "ask", lambda *a, **kw: False)
    result = CliRunner().invoke(app, ["logout"])
    assert result.exit_code == 3
    assert "已取消" in result.stdout
    assert os.path.exists(path)  # 文件未被删除


def test_logout_confirm_yes(monkeypatch, tmp_path):
    """无 --yes 且用户选 Yes:删除 Cookie,exit_code=0"""
    from cli.app import app
    import cli.commands.logout  # noqa: F401
    from rich.prompt import Confirm
    path = _make_cookie_file(tmp_path)
    _patch_cookie_path(monkeypatch, path)
    monkeypatch.setattr(Confirm, "ask", lambda *a, **kw: True)
    result = CliRunner().invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "已登出" in result.stdout
    assert not os.path.exists(path)


def test_logout_permission_error(monkeypatch, tmp_path):
    """Cookie 文件存在但删除失败(权限):exit_code=70"""
    from cli.app import app
    import cli.commands.logout  # noqa: F401
    path = _make_cookie_file(tmp_path)
    _patch_cookie_path(monkeypatch, path)

    def raise_perm(_path):
        raise PermissionError("mocked permission denied")
    monkeypatch.setattr(os, "remove", raise_perm)

    result = CliRunner().invoke(app, ["logout", "--yes"])
    assert result.exit_code == 70
