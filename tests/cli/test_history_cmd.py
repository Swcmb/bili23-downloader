# tests/cli/test_history_cmd.py
"""T5.7 bili23 history list/clear 命令测试

使用 monkeypatch + MagicMock 替换 TaskDatabase,避免触碰真实数据库。
通过 `import cli.commands.history` 触发命令注册到 app。
"""
import json
import sqlite3
from unittest.mock import MagicMock

from typer.testing import CliRunner

# 导入即触发 history 命令注册到 app
import cli.commands.history  # noqa: F401
from cli.app import app


runner = CliRunner()


def _patch_db(monkeypatch, *, get_history=None, count_history=0,
              clear_history=0, raises=None):
    """patch TaskDatabase 为 mock 实例,返回该实例便于后续断言

    :param get_history:    get_history 返回值(list[dict])
    :param count_history:  count_history 返回值
    :param clear_history:  clear_history 返回值
    :param raises:         若提供,所有方法抛此异常(优先级高于返回值)
    """
    instance = MagicMock()
    if raises is not None:
        instance.get_history.side_effect = raises
        instance.count_history.side_effect = raises
        instance.clear_history.side_effect = raises
    else:
        instance.get_history.return_value = list(get_history or [])
        instance.count_history.return_value = count_history
        instance.clear_history.return_value = clear_history
    monkeypatch.setattr("cli.commands.history.TaskDatabase", MagicMock(return_value=instance))
    return instance


def _sample_rows(n=3):
    """构造 n 条示例历史记录"""
    return [
        {
            "time": 1721300000 + i * 1000,
            "title": f"视频标题 {i + 1}",
            "url": f"https://www.bilibili.com/video/BV{i + 1:010d}",
            "status": "COMPLETED",
            "file_size": 1024 * 1024 * (i + 1),
        }
        for i in range(n)
    ]


# ---- 注册与帮助 ----

def test_history_registered():
    """history 命令组已注册到主 app"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "history" in result.stdout


def test_history_list_help():
    """`bili23 history list --help` 退出码 0"""
    result = runner.invoke(app, ["history", "list", "--help"])
    assert result.exit_code == 0
    assert "显示条数" in result.stdout or "limit" in result.stdout


def test_history_clear_help():
    """`bili23 history clear --help` 退出码 0"""
    result = runner.invoke(app, ["history", "clear", "--help"])
    assert result.exit_code == 0
    assert "清空" in result.stdout or "clear" in result.stdout


# ---- list 命令 ----

def test_history_list_empty(monkeypatch):
    """无记录时打印'暂无历史记录',退出码 0"""
    _patch_db(monkeypatch, get_history=[], count_history=0)
    result = runner.invoke(app, ["history", "list"])
    assert result.exit_code == 0
    assert "暂无历史记录" in result.stdout


def test_history_list_with_data(monkeypatch):
    """3 条记录时表格展示 3 行数据"""
    _patch_db(monkeypatch, get_history=_sample_rows(3), count_history=3)
    result = runner.invoke(app, ["history", "list"])
    assert result.exit_code == 0
    for i in range(3):
        assert f"视频标题 {i + 1}" in result.stdout


def test_history_list_json(monkeypatch):
    """`--json` 输出 JSON 数组"""
    _patch_db(monkeypatch, get_history=_sample_rows(2), count_history=2)
    result = runner.invoke(app, ["history", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["title"] == "视频标题 1"


def test_history_list_limit(monkeypatch):
    """`-n 2` 限制条数,参数透传至 get_history"""
    instance = _patch_db(monkeypatch, get_history=_sample_rows(2), count_history=2)
    result = runner.invoke(app, ["history", "list", "-n", "2"])
    assert result.exit_code == 0
    args, kwargs = instance.get_history.call_args
    assert kwargs.get("limit") == 2 or (args and 2 in args)


def test_history_list_limit_too_small(monkeypatch):
    """limit < 1 抛 ConfigError(exit_code=9)"""
    _patch_db(monkeypatch)
    result = runner.invoke(app, ["history", "list", "-n", "0"])
    assert result.exit_code == 9


def test_history_list_limit_too_large(monkeypatch):
    """limit > 1000 抛 ConfigError(exit_code=9)"""
    _patch_db(monkeypatch)
    result = runner.invoke(app, ["history", "list", "-n", "1001"])
    assert result.exit_code == 9


def test_history_list_db_corrupted(monkeypatch):
    """数据库损坏抛 Bili23Error(exit_code=70)"""
    _patch_db(monkeypatch, raises=sqlite3.DatabaseError("disk I/O error"))
    result = runner.invoke(app, ["history", "list"])
    assert result.exit_code == 70


# ---- clear 命令 ----

def test_history_clear_yes(monkeypatch):
    """`--yes` 直接清空,打印'已清空 N 条记录'"""
    instance = _patch_db(monkeypatch, count_history=5, clear_history=5)
    result = runner.invoke(app, ["history", "clear", "--yes"])
    assert result.exit_code == 0
    assert "已清空 5 条记录" in result.stdout
    instance.clear_history.assert_called_once()


def test_history_clear_cancel(monkeypatch):
    """无 `--yes` 且用户输入 n,exit_code=3"""
    instance = _patch_db(monkeypatch, count_history=3, clear_history=3)
    result = runner.invoke(app, ["history", "clear"], input="n\n")
    assert result.exit_code == 3
    instance.clear_history.assert_not_called()


def test_history_clear_confirm_yes(monkeypatch):
    """无 `--yes` 但用户输入 y,执行清空"""
    instance = _patch_db(monkeypatch, count_history=3, clear_history=3)
    result = runner.invoke(app, ["history", "clear"], input="y\n")
    assert result.exit_code == 0
    instance.clear_history.assert_called_once()


def test_history_clear_older_than(monkeypatch):
    """`--older-than 7` 仅清 7 天前的记录,参数透传"""
    instance = _patch_db(monkeypatch, count_history=10, clear_history=3)
    result = runner.invoke(app, ["history", "clear", "--older-than", "7", "--yes"])
    assert result.exit_code == 0
    instance.clear_history.assert_called_once()
    args, kwargs = instance.clear_history.call_args
    assert kwargs.get("older_than_days") == 7 or (args and 7 in args)


def test_history_clear_no_records(monkeypatch):
    """清空时无记录,打印'暂无历史记录',不调用 clear_history"""
    instance = _patch_db(monkeypatch, count_history=0, clear_history=0)
    result = runner.invoke(app, ["history", "clear", "--yes"])
    assert result.exit_code == 0
    assert "暂无历史记录" in result.stdout
    instance.clear_history.assert_not_called()


def test_history_clear_db_corrupted(monkeypatch):
    """清空时数据库损坏抛 Bili23Error(exit_code=70)"""
    _patch_db(monkeypatch, count_history=5, raises=sqlite3.DatabaseError("corrupt"))
    result = runner.invoke(app, ["history", "clear", "--yes"])
    assert result.exit_code == 70
