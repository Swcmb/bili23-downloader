# src/cli/commands/parse.py
"""bili23 parse <url> - 仅解析 URL,展示分集列表(不下载)

解析流程:
1. 调用 util.parse.ParseWorker 同步解析 URL
2. 通过 signal_bus.parse.update_parse_list 捕获根节点
3. 递归收集叶子剧集,提取 UP 主等元信息
4. 渲染 Rich Panel + Table,或输出 JSON 字符串

异常映射:
- URL 无效 / 解析失败 → ParseError(exit_code=4)
"""
import json
from typing import List, Mapping

import typer
from rich.console import Console
from rich.panel import Panel

from cli.app import app
from cli.commands._shared import parse_url  # noqa: F401 - 重新导出,保持向后兼容
from cli.exceptions import Bili23Error
from cli.render.table import render_table

# 模块级默认 Console,用于 Rich Panel 输出
console = Console()


def _format_duration(seconds: object) -> str:
    """将秒数格式化为 H:MM:SS 或 M:SS;无法转换时返回空串"""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{sec:02d}"
    return f"{m:d}:{sec:02d}"


def _build_episode_rows(episodes: List[Mapping[str, object]]) -> List[dict]:
    """将分集列表转为表格行,统一字段名"""
    return [
        {
            "#":     ep.get("number", ""),
            "标题":  ep.get("title", ""),
            "时长":  _format_duration(ep.get("duration", 0)),
            "BV":    ep.get("bvid", ""),
            "CID":   ep.get("cid", ""),
        }
        for ep in episodes
    ]


def _render_result(result: dict, no_color: bool) -> None:
    """以 Rich Panel + Table 渲染解析结果"""
    cnsl = Console(no_color=True) if no_color else console

    title = result.get("title", "")
    uploader = result.get("uploader", "")
    category = result.get("category", "")

    meta_text = (
        f"[bold]标题[/]: {title}\n"
        f"[bold]UP 主[/]: {uploader}\n"
        f"[bold]类型[/]: {category}"
    )
    cnsl.print(Panel(meta_text, title="解析结果", border_style="cyan"))

    episodes = result.get("episodes", [])
    if not episodes:
        cnsl.print("[yellow]无可用分集[/]")
        return

    rows = _build_episode_rows(episodes)
    render_table(rows, ["#", "标题", "时长", "BV", "CID"], title="分集列表")


@app.command("parse")
def parse_cmd(
    url: str = typer.Argument(..., help="B 站 URL(投稿/番剧/课程/UP主空间/收藏夹等)"),
    output_json: bool = typer.Option(False, "--json", help="以 JSON 格式输出解析结果"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用彩色输出"),
):
    """仅解析 URL,展示标题/分集/画质信息,不下载"""
    try:
        result = parse_url(url)
    except Bili23Error as exc:
        # ParseError(4)/UserCancelledError(3) 等统一按 exit_code 退出
        raise typer.Exit(exc.exit_code) from exc

    if output_json:
        typer.echo(json.dumps(result, ensure_ascii=False))
        return

    _render_result(result, no_color=no_color)
