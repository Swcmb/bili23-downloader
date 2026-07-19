# src/cli/commands/history.py
"""bili23 history list/clear 命令组

下载历史记录管理:列出与清空(支持按天数过滤)。
数据存储于 TaskDatabase(download_task + completed_task 两表)。

异常处理:
- limit 越界           → ConfigError(exit_code=9)
- 数据库损坏            → Bili23Error(exit_code=70)
- 用户在交互提示中取消 → UserCancelledError(exit_code=3)
"""
import json as _json
import logging
import sqlite3
from typing import Any, Dict, List

import typer
from rich.console import Console
from rich.table import Table

from cli.app import app
from cli.exceptions import Bili23Error, ConfigError, UserCancelledError
from util.download.task.db import TaskDatabase

logger = logging.getLogger(__name__)
console = Console()

# limit 参数范围(闭区间)
_LIMIT_MIN = 1
_LIMIT_MAX = 1000

# Rich 表格表头
_TABLE_HEADERS = ["时间", "标题", "URL", "状态", "文件大小"]

history_app = typer.Typer(help="下载历史管理")
# 模块导入时注册到主 app(与 cli.app 解耦)
app.add_typer(history_app, name="history")


def _validate_limit(limit: int) -> None:
    """校验 limit 范围,越界抛 ConfigError"""
    if limit < _LIMIT_MIN or limit > _LIMIT_MAX:
        raise ConfigError(
            f"--limit 必须在 [{_LIMIT_MIN}, {_LIMIT_MAX}] 范围内,当前为 {limit}"
        )


def _get_db() -> TaskDatabase:
    """构造 TaskDatabase,捕获 sqlite 错误转 Bili23Error

    TaskDatabase.__init__ 会自动创建表,因此"数据库文件不存在"
    不会在此处报错,而是后续查询返回空列表。
    """
    try:
        return TaskDatabase()
    except sqlite3.Error as e:
        raise Bili23Error(f"数据库不可用: {e}") from e
    except OSError as e:
        raise Bili23Error(f"数据库目录不可访问: {e}") from e


def _format_time(ts: int) -> str:
    """将 Unix 时间戳(秒/毫秒)格式化为可读字符串"""
    if not ts:
        return ""
    # 兼容毫秒级时间戳(TaskInfo.Basic.created_time 是毫秒)
    if ts > 10_000_000_000:
        ts = ts // 1000
    from datetime import datetime
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return str(ts)


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


def _render_history_table(rows: List[Dict[str, Any]]) -> None:
    """以 Rich Table 渲染历史记录列表"""
    table = Table(title="下载历史")
    for header in _TABLE_HEADERS:
        table.add_column(header)
    for row in rows:
        table.add_row(
            _format_time(row.get("time", 0)),
            str(row.get("title", "")),
            str(row.get("url", "")),
            str(row.get("status", "")),
            _format_size(row.get("file_size", 0) or 0),
        )
    console.print(table)


@history_app.command("list")
def history_list(
    limit: int = typer.Option(50, "-n", "--limit", help="显示条数(默认 50)"),
    offset: int = typer.Option(0, "--offset", help="偏移量(分页)"),
    output_json: bool = typer.Option(False, "--json", help="JSON 格式输出"),
):
    """列出下载历史"""
    try:
        _validate_limit(limit)
        db = _get_db()
        rows = db.get_history(limit=limit, offset=offset)
    except Bili23Error as e:
        console.print(f"[red]✗ {e}[/]")
        raise typer.Exit(code=e.exit_code)
    except sqlite3.Error as e:
        console.print(f"[red]✗ 数据库损坏: {e}[/]")
        raise typer.Exit(code=70)

    if not rows:
        console.print("暂无历史记录")
        return

    if output_json:
        console.print_json(_json.dumps(rows, ensure_ascii=False, default=str))
        return

    _render_history_table(rows)


@history_app.command("clear")
def history_clear(
    force: bool = typer.Option(False, "-y", "--yes", help="跳过确认"),
    older_than_days: int = typer.Option(None, "--older-than", help="仅清除 N 天前的记录"),
):
    """清空下载历史"""
    try:
        _validate_older_than(older_than_days)
        db = _get_db()
        total = db.count_history()

        if total == 0:
            console.print("暂无历史记录")
            return

        if not force:
            scope = f"({older_than_days} 天前的)" if older_than_days is not None else ""
            confirmed = typer.confirm(
                f"确认清空 {total} 条{scope}历史记录?", default=False
            )
            if not confirmed:
                raise UserCancelledError("用户取消清空历史记录")

        deleted = db.clear_history(older_than_days=older_than_days)
    except Bili23Error as e:
        console.print(f"[red]✗ {e}[/]")
        raise typer.Exit(code=e.exit_code)
    except sqlite3.Error as e:
        console.print(f"[red]✗ 数据库损坏: {e}[/]")
        raise typer.Exit(code=70)

    console.print(f"[green]✓ 已清空 {deleted} 条记录[/]")


def _validate_older_than(older_than_days) -> None:
    """校验 --older-than 参数(可为 None)"""
    if older_than_days is None:
        return
    if older_than_days < 1:
        raise ConfigError(f"--older-than 必须为正整数,当前为 {older_than_days}")
