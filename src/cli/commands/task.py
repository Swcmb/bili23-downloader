# src/cli/commands/task.py
"""bili23 task list/pause/resume/cancel/clear 命令组

下载任务管理:列出现存任务、暂停/恢复/取消单条任务、批量清空。
仅操作 download_task 表(进行中任务),不影响已完成历史记录。

异常处理:
- 任务不存在              → Bili23Error(exit_code=70)
- 状态转换不允许          → Bili23Error(exit_code=70)
- 用户取消交互式确认      → UserCancelledError(exit_code=3)
- 数据库错误              → Bili23Error(exit_code=70)
"""
import json as _json
import logging
import sqlite3
from typing import Any, Dict, List, Optional

import typer
from rich.console import Console
from rich.table import Table

from cli.app import app
from cli.exceptions import Bili23Error, ConfigError, UserCancelledError
from util.common.enum import DownloadStatus
from util.download.task.db import TaskDatabase

logger = logging.getLogger(__name__)
console = Console()

# limit 参数范围(闭区间)
_LIMIT_MIN = 1
_LIMIT_MAX = 1000

# Rich 表格表头
_TABLE_HEADERS = ["ID", "标题", "状态", "进度", "速度", "文件大小"]

# CLI 状态字符串 → DownloadStatus 枚举映射
_STATUS_FILTER_MAP = {
    "downloading": DownloadStatus.DOWNLOADING,
    "paused": DownloadStatus.PAUSED,
    "completed": DownloadStatus.COMPLETED,
    "failed": DownloadStatus.FAILED,
}

task_app = typer.Typer(help="下载任务管理")
# 模块导入时注册到主 app(与 cli.app 解耦)
app.add_typer(task_app, name="task")


def _validate_limit(limit: int) -> None:
    """校验 limit 范围,越界抛 ConfigError"""
    if limit < _LIMIT_MIN or limit > _LIMIT_MAX:
        raise ConfigError(
            f"--limit 必须在 [{_LIMIT_MIN}, {_LIMIT_MAX}] 范围内,当前为 {limit}"
        )


def _parse_status_filter(status: Optional[str]) -> Optional[DownloadStatus]:
    """将 CLI 状态字符串解析为 DownloadStatus 枚举,未知值抛 ConfigError"""
    if status is None:
        return None
    key = status.lower()
    if key not in _STATUS_FILTER_MAP:
        raise ConfigError(
            f"--status 仅支持 {list(_STATUS_FILTER_MAP.keys())},当前为 {status!r}"
        )
    return _STATUS_FILTER_MAP[key]


def _get_db() -> TaskDatabase:
    """构造 TaskDatabase,捕获 sqlite/OSError 转 Bili23Error"""
    try:
        return TaskDatabase()
    except sqlite3.Error as e:
        raise Bili23Error(f"数据库不可用: {e}") from e
    except OSError as e:
        raise Bili23Error(f"数据库目录不可访问: {e}") from e


def _format_size(size: int) -> str:
    """将字节数格式化为人类可读大小"""
    if not size:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    val = float(size)
    for unit in units:
        if val < 1024 or unit == units[-1]:
            return f"{val:.2f} {unit}"
        val /= 1024
    return f"{size} B"


def _format_speed(speed: int) -> str:
    """将字节/秒格式化为人类可读速度"""
    return f"{_format_size(speed)}/s"


def _format_progress(progress: int) -> str:
    """进度值格式化为百分比"""
    return f"{progress}%"


def _render_task_table(rows: List[Dict[str, Any]]) -> None:
    """以 Rich Table 渲染任务列表"""
    table = Table(title="下载任务")
    for header in _TABLE_HEADERS:
        table.add_column(header)
    for row in rows:
        table.add_row(
            str(row.get("task_id", "")),
            str(row.get("title", "")),
            str(row.get("status", "")),
            _format_progress(row.get("progress", 0) or 0),
            _format_speed(row.get("speed", 0) or 0),
            _format_size(row.get("file_size", 0) or 0),
        )
    console.print(table)


def _exit_with_bili23_error(e: Bili23Error) -> None:
    """打印错误并按 e.exit_code 退出"""
    console.print(f"[red]✗ {e}[/]")
    raise typer.Exit(code=e.exit_code)


def _exit_with_db_error(e: sqlite3.Error) -> None:
    """打印数据库错误并以 exit_code=70 退出"""
    console.print(f"[red]✗ 数据库损坏: {e}[/]")
    raise typer.Exit(code=70)


@task_app.command("list")
def task_list(
    limit: int = typer.Option(50, "-n", "--limit", help="显示条数(默认 50)"),
    status: Optional[str] = typer.Option(
        None, "--status", help="按状态过滤(downloading/paused/completed/failed)"
    ),
    output_json: bool = typer.Option(False, "--json", help="JSON 格式输出"),
):
    """列出现存下载任务(默认按时间倒序)"""
    try:
        _validate_limit(limit)
        status_filter = _parse_status_filter(status)
        db = _get_db()
        rows = db.list_tasks(limit=limit, status=status_filter)
    except Bili23Error as e:
        _exit_with_bili23_error(e)
    except sqlite3.Error as e:
        _exit_with_db_error(e)

    if not rows:
        console.print("暂无任务")
        return

    if output_json:
        console.print_json(_json.dumps(rows, ensure_ascii=False, default=str))
        return

    _render_task_table(rows)


def _transition_command(
    task_id: str,
    transition_fn,
    success_msg: str,
    invalid_msg: str,
) -> None:
    """通用状态转换命令:pause/resume 共用同一交互逻辑

    :param transition_fn: db.pause_task 或 db.resume_task
    :param success_msg:   成功时打印的提示
    :param invalid_msg:   状态不允许时抛出的 Bili23Error 消息
    """
    try:
        db = _get_db()
        result = transition_fn(db, task_id)
    except Bili23Error as e:
        _exit_with_bili23_error(e)
    except sqlite3.Error as e:
        _exit_with_db_error(e)

    if result is None:
        _exit_with_bili23_error(Bili23Error(f"任务不存在: {task_id}"))
    if not result:
        _exit_with_bili23_error(Bili23Error(f"{invalid_msg}: {task_id}"))

    console.print(f"[green]✓ {success_msg}: {task_id}[/]")


@task_app.command("pause")
def task_pause(
    task_id: str = typer.Argument(..., help="任务 ID"),
):
    """暂停指定任务(仅当状态为 downloading)"""
    _transition_command(
        task_id,
        lambda db, tid: db.pause_task(tid),
        "已暂停任务",
        "任务状态不允许暂停(仅 downloading 可暂停)",
    )


@task_app.command("resume")
def task_resume(
    task_id: str = typer.Argument(..., help="任务 ID"),
):
    """恢复指定任务(仅当状态为 paused)"""
    _transition_command(
        task_id,
        lambda db, tid: db.resume_task(tid),
        "已恢复任务",
        "任务状态不允许恢复(仅 paused 可恢复)",
    )


@task_app.command("cancel")
def task_cancel(
    task_id: str = typer.Argument(..., help="任务 ID"),
    force: bool = typer.Option(False, "-y", "--yes", help="跳过确认"),
):
    """取消指定任务(删除任务记录)"""
    try:
        db = _get_db()
        task = db.get_task(task_id)
        if task is None:
            raise Bili23Error(f"任务不存在: {task_id}")

        if not force:
            title = task.get("title", "")
            confirmed = typer.confirm(
                f"确认取消任务 [{task_id}] {title}?", default=False
            )
            if not confirmed:
                raise UserCancelledError("用户取消取消任务")

        ok = db.cancel_task(task_id)
        if not ok:
            raise Bili23Error(f"任务不存在: {task_id}")
    except Bili23Error as e:
        _exit_with_bili23_error(e)
    except sqlite3.Error as e:
        _exit_with_db_error(e)

    console.print(f"[green]✓ 已取消任务: {task_id}[/]")


@task_app.command("clear")
def task_clear(
    force: bool = typer.Option(False, "-y", "--yes", help="跳过确认"),
    status: Optional[str] = typer.Option(
        None,
        "--status",
        help="仅清除指定状态(downloading/paused/completed/failed)",
    ),
):
    """清空任务列表(可按状态过滤,需确认)"""
    try:
        status_filter = _parse_status_filter(status)
        db = _get_db()
        # 先取符合条件的任务总数,用于确认提示
        matched = db.list_tasks(limit=_LIMIT_MAX, status=status_filter)
        if not matched:
            console.print("暂无任务")
            return

        total = len(matched)
        if not force:
            scope = f"(状态: {status.lower()})" if status else ""
            confirmed = typer.confirm(
                f"确认清空 {total} 条{scope}任务?", default=False
            )
            if not confirmed:
                raise UserCancelledError("用户取消清空任务")

        deleted = db.clear_tasks(status=status_filter)
    except Bili23Error as e:
        _exit_with_bili23_error(e)
    except sqlite3.Error as e:
        _exit_with_db_error(e)

    console.print(f"[green]✓ 已清空 {deleted} 条任务[/]")
