# tests/cli/test_task_cmd.py
"""T5.6 bili23 task list/pause/resume/cancel/clear 命令测试

使用 monkeypatch + MagicMock 替换 TaskDatabase,避免触碰真实数据库。
通过 `import cli.commands.task` 触发命令注册到 app。
"""
import json
import sqlite3
from unittest.mock import MagicMock

from typer.testing import CliRunner

# 导入即触发 task 命令注册到 app
import cli.commands.task  # noqa: F401
from cli.app import app


runner = CliRunner()


def _patch_db(monkeypatch, **method_returns):
    """patch TaskDatabase 为 mock 实例

    :param method_returns: dict 形如 {"list_tasks": [...], "pause_task": True}
    :return: mock 实例,便于后续断言
    """
    instance = MagicMock()
    for method, ret in method_returns.items():
        getattr(instance, method).return_value = ret
    monkeypatch.setattr(
        "cli.commands.task.TaskDatabase", MagicMock(return_value=instance)
    )
    return instance


def _sample_tasks(n=2):
    """构造 n 条示例任务(状态默认为 DOWNLOADING)"""
    return [
        {
            "task_id": f"task-{i + 1}",
            "title": f"任务 {i + 1}",
            "status": "DOWNLOADING",
            "status_id": 2,
            "progress": 50 + i,
            "speed": 1024 * (i + 1),
            "file_size": 1024 * 1024 * (i + 1),
            "created_time": 1721300000 + i * 1000,
        }
        for i in range(n)
    ]


# ---- 注册与帮助 ----

def test_task_registered():
    """task 命令组已注册到主 app"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "task" in result.stdout


def test_task_list_help():
    """`bili23 task list --help` 退出码 0"""
    result = runner.invoke(app, ["task", "list", "--help"])
    assert result.exit_code == 0


def test_task_pause_help():
    """`bili23 task pause --help` 退出码 0"""
    result = runner.invoke(app, ["task", "pause", "--help"])
    assert result.exit_code == 0


def test_task_resume_help():
    """`bili23 task resume --help` 退出码 0"""
    result = runner.invoke(app, ["task", "resume", "--help"])
    assert result.exit_code == 0


def test_task_cancel_help():
    """`bili23 task cancel --help` 退出码 0"""
    result = runner.invoke(app, ["task", "cancel", "--help"])
    assert result.exit_code == 0


def test_task_clear_help():
    """`bili23 task clear --help` 退出码 0"""
    result = runner.invoke(app, ["task", "clear", "--help"])
    assert result.exit_code == 0


# ---- list 命令 ----

def test_task_list_empty(monkeypatch):
    """无任务时打印'暂无任务'"""
    _patch_db(monkeypatch, list_tasks=[])
    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    assert "暂无任务" in result.stdout


def test_task_list_with_data(monkeypatch):
    """2 条任务时表格显示 2 行数据"""
    _patch_db(monkeypatch, list_tasks=_sample_tasks(2))
    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0
    assert "任务 1" in result.stdout
    assert "任务 2" in result.stdout


def test_task_list_json(monkeypatch):
    """`--json` 输出 JSON 数组"""
    _patch_db(monkeypatch, list_tasks=_sample_tasks(2))
    result = runner.invoke(app, ["task", "list", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout.strip())
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["task_id"] == "task-1"


def test_task_list_filter_status(monkeypatch):
    """`--status downloading` 参数透传至 list_tasks"""
    instance = _patch_db(monkeypatch, list_tasks=_sample_tasks(2))
    result = runner.invoke(app, ["task", "list", "--status", "downloading"])
    assert result.exit_code == 0
    args, kwargs = instance.list_tasks.call_args
    status_arg = kwargs.get("status")
    assert status_arg is not None
    assert int(status_arg) == 2  # DownloadStatus.DOWNLOADING


def test_task_list_limit_too_small(monkeypatch):
    """limit < 1 抛 ConfigError(exit_code=9)"""
    _patch_db(monkeypatch, list_tasks=[])
    result = runner.invoke(app, ["task", "list", "-n", "0"])
    assert result.exit_code == 9


def test_task_list_invalid_status(monkeypatch):
    """未知状态抛 ConfigError(exit_code=9)"""
    _patch_db(monkeypatch, list_tasks=[])
    result = runner.invoke(app, ["task", "list", "--status", "unknown"])
    assert result.exit_code == 9


def test_task_list_db_corrupted(monkeypatch):
    """数据库损坏抛 Bili23Error(exit_code=70)"""
    instance = _patch_db(monkeypatch)
    instance.list_tasks.side_effect = sqlite3.DatabaseError("disk I/O error")
    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 70


# ---- pause 命令 ----

def test_task_pause_success(monkeypatch):
    """pause 一个 downloading 任务成功"""
    _patch_db(monkeypatch, pause_task=True)
    result = runner.invoke(app, ["task", "pause", "task-1"])
    assert result.exit_code == 0
    assert "已暂停" in result.stdout


def test_task_pause_not_found(monkeypatch):
    """pause 不存在的 ID,exit_code=70"""
    _patch_db(monkeypatch, pause_task=None)
    result = runner.invoke(app, ["task", "pause", "no-such-id"])
    assert result.exit_code == 70
    assert "任务不存在" in result.stdout


def test_task_pause_invalid_status(monkeypatch):
    """pause 状态不允许(非 downloading),exit_code=70"""
    _patch_db(monkeypatch, pause_task=False)
    result = runner.invoke(app, ["task", "pause", "task-1"])
    assert result.exit_code == 70


# ---- resume 命令 ----

def test_task_resume_success(monkeypatch):
    """resume 一个 paused 任务成功"""
    _patch_db(monkeypatch, resume_task=True)
    result = runner.invoke(app, ["task", "resume", "task-1"])
    assert result.exit_code == 0
    assert "已恢复" in result.stdout


def test_task_resume_not_found(monkeypatch):
    """resume 不存在的 ID,exit_code=70"""
    _patch_db(monkeypatch, resume_task=None)
    result = runner.invoke(app, ["task", "resume", "no-such-id"])
    assert result.exit_code == 70


def test_task_resume_invalid_status(monkeypatch):
    """resume 状态不允许(非 paused),exit_code=70"""
    _patch_db(monkeypatch, resume_task=False)
    result = runner.invoke(app, ["task", "resume", "task-1"])
    assert result.exit_code == 70


# ---- cancel 命令 ----

def test_task_cancel_yes(monkeypatch):
    """`-y` 跳过确认直接取消"""
    instance = _patch_db(
        monkeypatch,
        get_task={"task_id": "task-1", "title": "任务 1"},
        cancel_task=True,
    )
    result = runner.invoke(app, ["task", "cancel", "task-1", "-y"])
    assert result.exit_code == 0
    assert "已取消" in result.stdout
    instance.cancel_task.assert_called_once_with("task-1")


def test_task_cancel_no(monkeypatch):
    """用户选 No,exit_code=3,不调用 cancel_task"""
    instance = _patch_db(
        monkeypatch,
        get_task={"task_id": "task-1", "title": "任务 1"},
        cancel_task=True,
    )
    result = runner.invoke(app, ["task", "cancel", "task-1"], input="n\n")
    assert result.exit_code == 3
    instance.cancel_task.assert_not_called()


def test_task_cancel_not_found(monkeypatch):
    """cancel 不存在的 ID,exit_code=70"""
    _patch_db(monkeypatch, get_task=None, cancel_task=False)
    result = runner.invoke(app, ["task", "cancel", "no-such-id", "-y"])
    assert result.exit_code == 70


def test_task_cancel_confirm_yes(monkeypatch):
    """无 `-y` 但用户输入 y,执行取消"""
    instance = _patch_db(
        monkeypatch,
        get_task={"task_id": "task-1", "title": "任务 1"},
        cancel_task=True,
    )
    result = runner.invoke(app, ["task", "cancel", "task-1"], input="y\n")
    assert result.exit_code == 0
    instance.cancel_task.assert_called_once()


# ---- clear 命令 ----

def test_task_clear_yes(monkeypatch):
    """`-y` 清空全部"""
    instance = _patch_db(
        monkeypatch,
        list_tasks=_sample_tasks(3),
        clear_tasks=3,
    )
    result = runner.invoke(app, ["task", "clear", "-y"])
    assert result.exit_code == 0
    assert "已清空 3 条任务" in result.stdout
    instance.clear_tasks.assert_called_once()


def test_task_clear_status(monkeypatch):
    """`--status completed -y` 仅清已完成,status 透传至 clear_tasks"""
    instance = _patch_db(
        monkeypatch,
        list_tasks=_sample_tasks(2),
        clear_tasks=2,
    )
    result = runner.invoke(app, ["task", "clear", "--status", "completed", "-y"])
    assert result.exit_code == 0
    args, kwargs = instance.clear_tasks.call_args
    status_arg = kwargs.get("status")
    assert status_arg is not None
    assert int(status_arg) == 4  # DownloadStatus.COMPLETED


def test_task_clear_no(monkeypatch):
    """无 `-y` 用户选 No,exit_code=3"""
    instance = _patch_db(
        monkeypatch,
        list_tasks=_sample_tasks(2),
        clear_tasks=2,
    )
    result = runner.invoke(app, ["task", "clear"], input="n\n")
    assert result.exit_code == 3
    instance.clear_tasks.assert_not_called()


def test_task_clear_empty(monkeypatch):
    """无任务时打印'暂无任务',不调用 clear_tasks"""
    instance = _patch_db(monkeypatch, list_tasks=[], clear_tasks=0)
    result = runner.invoke(app, ["task", "clear", "-y"])
    assert result.exit_code == 0
    assert "暂无任务" in result.stdout
    instance.clear_tasks.assert_not_called()


def test_task_clear_confirm_yes(monkeypatch):
    """无 `-y` 但用户输入 y,执行清空"""
    instance = _patch_db(
        monkeypatch,
        list_tasks=_sample_tasks(2),
        clear_tasks=2,
    )
    result = runner.invoke(app, ["task", "clear"], input="y\n")
    assert result.exit_code == 0
    instance.clear_tasks.assert_called_once()
