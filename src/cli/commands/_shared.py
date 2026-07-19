# src/cli/commands/_shared.py
"""命令共享工具模块

将 `parse` / `download` 等命令共用的解析逻辑集中于此,避免代码重复。

主要内容:
- ``parse_url(url)``:同步解析 URL,返回结构化解析结果(标题/UP主/分集/可用画质音质)
- ``_collect_episodes(root_node)``:从根节点递归收集叶子分集
- ``_extract_uploader(root_node)``:从根节点提取 UP 主名

异常映射:
- URL 无效 / 解析失败 → ``ParseError``(exit_code=4)
"""
from typing import List, Mapping

from util.common.signal_bus import signal_bus
from util.parse.worker import ParseWorker

from cli.exceptions import ParseError


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

    :returns: dict 含 ``title``/``uploader``/``category``/``episodes``/
              ``video_qualities``/``audio_qualities`` 字段
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
