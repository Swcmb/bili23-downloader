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
from cli.exceptions import Bili23Error, ParseError
from cli.render.table import render_table
from util.common.signal_bus import signal_bus
from util.parse.worker import ParseWorker

# 模块级默认 Console,用于 Rich Panel 输出
console = Console()


def _collect_episodes(root_node) -> List[Mapping[str, object]]:
    """从根节点递归收集所有叶子剧集(排除树节点)"""
    if root_node is None:
        return []
    return [
        {
            "number":   item.get("number", ""),
            "title":    item.get("title", ""),
            "duration": item.get("duration", 0),
            "bvid":     item.get("bvid", ""),
            "cid":      item.get("cid", 0),
        }
        for item in root_node.get_all_children(to_dict=True)
    ]


def _extract_uploader(root_node) -> str:
    """从树节点中提取 UP 主名(取首个叶子节点的 uploader_info)"""
    if root_node is None:
        return ""
    for item in root_node.get_all_children(to_dict=True):
        uploader_info = item.get("uploader_info")
        if uploader_info and uploader_info.get("uploader"):
            return uploader_info["uploader"]
    return ""


def parse_url(url: str) -> dict:
    """解析 URL,返回结构化解析结果

    :raises ParseError: URL 无效或解析失败
    """
    if not url or not isinstance(url, str):
        raise ParseError(f"无效的 URL: {url}")

    captured: dict = {}
    error_captured: dict = {}

    def _on_update_parse_list(title, category_name, root_node, current_episode_data=None):
        """signal_bus.parse.update_parse_list 回调,捕获解析结果"""
        captured["title"] = title
        captured["category"] = category_name
        captured["root_node"] = root_node

    def _on_error(error_msg):
        """ParseWorker.error 信号回调,捕获错误消息"""
        error_captured["message"] = error_msg

    # 注册回调捕获信号(worker.run 同步执行,信号在本线程触发)
    signal_bus.parse.update_parse_list.connect(_on_update_parse_list)
    worker = ParseWorker(url, pn=1)
    worker.error.connect(_on_error)
    try:
        worker.run()
    finally:
        signal_bus.parse.update_parse_list.disconnect(_on_update_parse_list)
        worker.error.disconnect(_on_error)

    # 优先检查 error 信号(ParseWorker 内部捕获异常后通过 error 信号回传)
    if "message" in error_captured:
        raise ParseError(error_captured["message"])

    root_node = captured.get("root_node")
    if root_node is None:
        raise ParseError(f"未能解析 URL: {url}")

    return {
        "title": captured.get("title", ""),
        "uploader": _extract_uploader(root_node),
        "category": captured.get("category", ""),
        "episodes": _collect_episodes(root_node),
        # 画质/音质需额外调用 playurl 接口,parse 命令暂不获取
        "video_qualities": [],
        "audio_qualities": [],
    }


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
