# src/cli/interact/quality_selector.py
"""画质/音质/编码选择交互组件

提供 select_quality() 选择画质 ID、音质 ID 与视频编码:
- 非交互模式:直接校验预设值;未指定字段默认取列表第一项(最高)
- 交互模式:渲染 Rich Table 后用 input() 询问,空回车取默认,"q" 取消

异常映射:
- UserCancelledError(3):用户输入 "q" 取消
- ParseError(4):指定的 ID/codec 不在可用列表中
"""
from typing import List, Optional

from rich.console import Console
from rich.table import Table

from cli.exceptions import ParseError, UserCancelledError


# 模块级 Console,供渲染表格使用(测试中可被 monkeypatch 屏蔽输出)
console = Console()


# 画质 ID -> 友好名称(规格 6.x 节)
QUALITY_NAMES = {
    127: "8K 超高清",
    126: "杜比视界",
    125: "HDR",
    120: "4K 超清",
    116: "1080P60 高帧率",
    112: "1080P 高码率",
    80: "1080P 高清",
    74: "720P60 高帧率",
    64: "720P 高清",
    32: "480P 清晰",
    16: "360P 流畅",
}

# 音质 ID -> 友好名称
AUDIO_QUALITY_NAMES = {
    30280: "Hi-Res 128K",
    30232: "132K",
    30255: "杜比音频",
    30250: "杜比全景声",
    30240: "64K",
}


def _render_options(title: str, items: List[dict]) -> None:
    """渲染 Rich Table 展示可选画质/音质

    列固定为 "#"、"ID"、"名称",序号从 1 开始。
    """
    table = Table(title=title)
    table.add_column("#")
    table.add_column("ID")
    table.add_column("名称")
    for i, item in enumerate(items, start=1):
        table.add_row(str(i), str(item.get("id", "")), str(item.get("name", "")))
    console.print(table)


def _render_codec_options(title: str, codecs: List[str]) -> None:
    """渲染 Rich Table 展示可选视频编码"""
    table = Table(title=title)
    table.add_column("#")
    table.add_column("编码")
    for i, codec in enumerate(codecs, start=1):
        table.add_row(str(i), codec)
    console.print(table)


def parse_input(raw: str, max_index: int) -> Optional[int]:
    """解析用户单次输入

    Args:
        raw:       原始输入字符串
        max_index: 最大可选数量(1..N)

    Returns:
        0-indexed 索引;None 表示使用默认(空回车)

    Raises:
        UserCancelledError: 输入 "q"(不区分大小写)
        ValueError:         输入无法解析为整数或超出 1..N 范围
    """
    raw = raw.strip()
    # 空输入:使用默认(列表第一项)
    if raw == "":
        return None
    # 取消选择
    if raw.lower() == "q":
        raise UserCancelledError("用户取消选择")
    # 解析为整数
    try:
        idx = int(raw)
    except ValueError as exc:
        raise ValueError(f"无效输入: {raw!r}") from exc
    # 范围检查(用户输入 1..N,内部转为 0..N-1)
    if idx < 1 or idx > max_index:
        raise ValueError(f"输入超出范围(1-{max_index}): {idx}")
    return idx - 1


def _prompt_choice(prompt_text: str, items: List) -> int:
    """循环提示用户选择,返回 0-indexed 索引

    Args:
        prompt_text: 提示文本
        items:       可选项列表(仅取长度)

    Returns:
        0-indexed 索引;空回车返回 0(默认第一项)

    Raises:
        UserCancelledError: 用户输入 "q"
    """
    while True:
        raw = input(prompt_text)
        try:
            idx = parse_input(raw, len(items))
        except UserCancelledError:
            raise
        except ValueError:
            # 无效或超范围:重新提示
            continue
        # None 表示使用默认(列表第一项)
        return 0 if idx is None else idx


def _validate_or_default(
    items: List[dict],
    item_id: Optional[int],
    label: str,
) -> int:
    """非交互模式校验画质/音质 ID

    Args:
        items:   可选项列表(dict 含 "id")
        item_id: 用户指定的 ID,None 表示未指定
        label:   用于错误信息的项名(画质/音质)

    Returns:
        选中项的 ID

    Raises:
        ParseError: 列表为空,或指定的 ID 不在列表中
    """
    if not items:
        raise ParseError(f"无可用{label}")
    if item_id is None:
        return items[0]["id"]
    for item in items:
        if item.get("id") == item_id:
            return item_id
    raise ParseError(f"指定的{label} ID {item_id} 不在可用列表中")


def _validate_codec(codecs: List[str], codec: Optional[str]) -> str:
    """非交互模式校验视频编码,未指定使用第一项

    Raises:
        ParseError: 列表为空,或指定的编码不在列表中
    """
    if not codecs:
        raise ParseError("无可用视频编码")
    if codec is None:
        return codecs[0]
    if codec in codecs:
        return codec
    raise ParseError(f"指定的视频编码 {codec} 不在可用列表中")


def select_quality(
    video_qualities: List[dict],
    audio_qualities: List[dict],
    video_codecs: List[str],
    video_quality_id: Optional[int] = None,
    audio_quality_id: Optional[int] = None,
    video_codec: Optional[str] = None,
    interactive: bool = True,
) -> dict:
    """选择画质/音质/编码

    Args:
        video_qualities:  可用画质列表(从高到低),形如 [{"id": 127, "name": "8K 超高清"}]
        audio_qualities:  可用音质列表
        video_codecs:     可用编码列表,如 ["AVC", "HEVC", "AV1"]
        video_quality_id: 指定画质 ID(非交互或预设)
        audio_quality_id: 指定音质 ID
        video_codec:      指定编码
        interactive:      是否交互式

    Returns:
        {"video_quality_id": int, "audio_quality_id": int, "video_codec": str}

    Raises:
        UserCancelledError: 用户取消(交互模式输入 "q")
        ParseError:         指定的 ID/codec 不在可用列表中(非交互模式)
    """
    # 非交互模式:校验指定值,未指定字段使用默认
    if not interactive:
        vq_id = _validate_or_default(video_qualities, video_quality_id, "画质")
        aq_id = _validate_or_default(audio_qualities, audio_quality_id, "音质")
        vc = _validate_codec(video_codecs, video_codec)
        return {
            "video_quality_id": vq_id,
            "audio_quality_id": aq_id,
            "video_codec": vc,
        }

    # 交互模式:渲染表格 -> 逐项询问
    _render_options("可选画质", video_qualities)
    vq_idx = _prompt_choice("请选择画质(1-N,默认 1 最高):", video_qualities)

    _render_options("可选音质", audio_qualities)
    aq_idx = _prompt_choice("请选择音质(1-N,默认 1 最高):", audio_qualities)

    _render_codec_options("可选编码", video_codecs)
    vc_idx = _prompt_choice("请选择编码(1-N,默认 1):", video_codecs)

    return {
        "video_quality_id": video_qualities[vq_idx]["id"],
        "audio_quality_id": audio_qualities[aq_idx]["id"],
        "video_codec": video_codecs[vc_idx],
    }
