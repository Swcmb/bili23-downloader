# tests/cli/test_config_cmd.py
"""bili23 config 子命令测试

覆盖 AC-027:bili23 config get/set/list/path

通过 monkeypatch 替换 config_cmd 模块内的 config 单例与 directory 引用,
确保测试不污染真实用户配置目录。
"""
from types import SimpleNamespace

from typer.testing import CliRunner

# 触发 config_app 注册到 cli.app.app(模块级副作用)
import cli.commands.config_cmd  # noqa: F401
from util.common.config import Config


def _setup_isolated_config(tmp_path, monkeypatch):
    """在 tmp_path 下创建独立的 config 与 directory,注入到 config_cmd 模块

    :return: 新建的 Config 单例,供断言验证使用
    """
    cfg = Config(config_path=str(tmp_path / "config.json"))
    monkeypatch.setattr("cli.commands.config_cmd.config", cfg)
    monkeypatch.setattr(
        "cli.commands.config_cmd.directory",
        SimpleNamespace(config_dir=str(tmp_path)),
    )
    return cfg


def test_config_help(tmp_path, monkeypatch):
    """AC-027: bili23 config --help 退出码 0 且列出子命令"""
    _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    result = CliRunner().invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "get" in result.stdout
    assert "set" in result.stdout
    assert "list" in result.stdout
    assert "path" in result.stdout


def test_config_get_existing(tmp_path, monkeypatch):
    """AC-027: get 输出裸值,便于脚本化"""
    _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    result = CliRunner().invoke(app, ["config", "get", "download_threads"])
    assert result.exit_code == 0
    assert result.stdout.strip() == "8"


def test_config_get_unknown_key(tmp_path, monkeypatch):
    """AC-027: 未知 key 抛 ConfigError(exit_code=9)"""
    _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    result = CliRunner().invoke(app, ["config", "get", "nonexistent_key"])
    assert result.exit_code == 9


def test_config_set_int(tmp_path, monkeypatch):
    """AC-027: set int 类型自动转换并持久化"""
    cfg = _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    runner = CliRunner()
    result = runner.invoke(app, ["config", "set", "download_threads", "16"])
    assert result.exit_code == 0
    assert "已设置 download_threads = 16" in result.stdout
    # 验证持久化:reload 后从磁盘读取,值仍为 16
    cfg.reload()
    assert cfg.get("download_threads") == 16


def test_config_set_bool(tmp_path, monkeypatch):
    """AC-027: set bool 类型自动转换(true/false/1/0/yes/no)"""
    cfg = _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    runner = CliRunner()
    result = runner.invoke(app, ["config", "set", "download_danmaku", "true"])
    assert result.exit_code == 0
    cfg.reload()
    assert cfg.get("download_danmaku") is True


def test_config_set_invalid_value(tmp_path, monkeypatch):
    """AC-027: set 值超出范围抛 ConfigError(exit_code=9)"""
    _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    result = CliRunner().invoke(app, ["config", "set", "download_threads", "999"])
    assert result.exit_code == 9


def test_config_list(tmp_path, monkeypatch):
    """AC-027: list 列出所有配置项(Rich Table)"""
    _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    result = CliRunner().invoke(app, ["config", "list"])
    assert result.exit_code == 0
    assert "download_threads" in result.stdout
    assert "user_agent" in result.stdout


def test_config_path(tmp_path, monkeypatch):
    """AC-027: path 输出配置文件路径(裸路径)"""
    _setup_isolated_config(tmp_path, monkeypatch)
    from cli.app import app
    result = CliRunner().invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert "config.json" in result.stdout
    assert str(tmp_path) in result.stdout
