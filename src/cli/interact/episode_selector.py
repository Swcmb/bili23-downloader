# src/cli/interact/episode_selector.py
"""分集勾选交互组件(T5.8)

提供 ``select_episodes`` 主入口与 ``parse_episode_spec`` 工具函数,支持:

- 非交互模式:接收 ``episode_spec`` 字符串(如 ``"1-3,5,7-9"`` / ``"all"`` / ``"last"``)
  直接解析为升序集号列表,便于脚本化调用。
- 交互模式:Rich Table 渲染全部分集 + ``input()`` 提示输入集号规范。

设计说明:跨平台键盘捕获(↑↓/空格)依赖第三方 ``keyboard`` 库且权限复杂,
故采用**简化版交互**:渲染表格后让用户输入集号规范字符串,与 ``--episodes``
参数语义一致,无需额外依赖。

异常:
- ``ParseError``:         episode_spec 解析失败(格式错误 / 范围越界)
- ``UserCancelledError``: 用户输入 ``q`` 取消或遇到 EOF
"""
import re
from typing import List, Optional, Set

from rich.console import Console
from rich.table import Table

from cli.exceptions import ParseError, UserCancelledError


# ==================================================================
# 集号规范解析(parse_episode_spec)
# ==================================================================

# 单个集号,如 "12"
_NUM_RE = re.compile(r"^\d+$")
# 范围,如 "3-5"
_RANGE_RE = re.compile(r"^(\d+)-(\d+)$")
# 最后一集 / 倒数 N 集:"last" / "last-N" / "-1"
#   - group(1): last-N 中的 N(无后缀时为 None)
#   - 第二条 alternation `^-1$` 仅匹配字面 "-1",group(1) 仍为 None
_LAST_RE = re.compile(r"^last(?:-(\d+))?$|^-1$")


def parse_episode_spec(spec: str, total: int) -> List[int]:
    """解析集号规范字符串为升序集号列表

    支持格式:

    - ``"all"`` / ``"*"``:        全部集号 ``[1..total]``
    - ``"last"`` / ``"-1"``:      最后一集 ``[total]``
    - ``"last-N"``:               倒数 N 集 ``[total-N+1 .. total]``
    - ``"1,3,5"``:                离散集号
    - ``"1-3"``:                  连续范围
    - ``"1-3,5,7-9"``:            范围与离散混合(自动去重、升序)

    :param spec:  集号规范字符串
    :param total: 总集数,用于 ``all`` / ``last`` 解析与边界校验
    :returns:     升序集号列表(从 1 开始,已去重)
    :raises ParseError: 字符串为空、格式非法或集号超出 ``[1, total]``
    """
    if spec is None or not spec.strip():
        raise ParseError("集号规范为空")
    spec = spec.strip()
    if total < 0:
        raise ParseError(f"总集数非法: {total}")

    # 全集
    if spec in ("all", "*"):
        return list(range(1, total + 1))

    # 最后一集 / 倒数 N 集
    last_match = _LAST_RE.match(spec)
    if last_match:
        n_str = last_match.group(1)
        n = int(n_str) if n_str else 1
        if n < 1:
            raise ParseError(f"倒数集数非法: {n}")
        if n > total:
            raise ParseError(f"倒数 {n} 集超出总集数 {total}")
        start = max(1, total - n + 1)
        return list(range(start, total + 1))

    # 离散 / 范围列表(逗号分隔)
    result: Set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            raise ParseError(f"集号规范片段为空: {spec!r}")
        range_match = _RANGE_RE.match(part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            if start > end:
                raise ParseError(f"范围起始 {start} 大于结束 {end}")
            if start < 1 or end > total:
                raise ParseError(f"集号范围 {start}-{end} 超出 [1, {total}]")
            result.update(range(start, end + 1))
            continue
        if _NUM_RE.match(part):
            n = int(part)
            if n < 1 or n > total:
                raise ParseError(f"集号 {n} 超出 [1, {total}]")
            result.add(n)
            continue
        raise ParseError(f"无效的集号规范片段: {part!r}")

    if not result:
        raise ParseError(f"集号规范未匹配任何集: {spec!r}")
    return sorted(result)


# ==================================================================
# 分集工具
# ==================================================================

def _extract_episode_number(ep: dict) -> int:
    """从分集 dict 提取集号

    优先使用 ``id`` 字段(对外契约),回退到 ``number`` 字段
    (与 ``util.parse`` 中 ParseWorker 输出兼容)。

    :raises ParseError: 字段缺失或值无法转为整数
    """
    for key in ("id", "number"):
        if key in ep:
            try:
                return int(ep[key])
            except (TypeError, ValueError) as e:
                raise ParseError(f"分集 {key} 非法: {ep.get(key)!r}") from e
    raise ParseError(f"分集缺少 'id' 或 'number' 字段: {ep!r}")


def _format_duration(seconds: object) -> str:
    """将秒数格式化为 ``M:SS`` 或 ``H:MM:SS``;无法转换时返回空串"""
    try:
        s = int(seconds)
    except (TypeError, ValueError):
        return ""
    if s < 0:
        return ""
    hours, rem = divmod(s, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


def _render_episode_table(episodes: List[dict], selected: Set[int]) -> None:
    """以 Rich Table 渲染分集列表,标注已选状态

    表头:序号 | 集号 | 标题 | 时长 | 状态(✓/空)
    """
    console = Console()
    console.print(
        "[bold cyan]请选择分集[/]: 输入集号(如 1-3,5 / all / last / last-3),"
        "空回车使用预选,q 取消"
    )

    table = Table(title="分集列表", show_lines=False)
    table.add_column("#", justify="right", style="dim")
    table.add_column("集号", justify="right")
    table.add_column("标题")
    table.add_column("时长")
    table.add_column("状态", justify="center")

    for idx, ep in enumerate(episodes, start=1):
        number = _extract_episode_number(ep)
        title = str(ep.get("title", ""))
        duration = _format_duration(ep.get("duration", 0))
        status = "[green]✓[/]" if number in selected else ""
        table.add_row(str(idx), str(number), title, duration, status)

    console.print(table)
    console.print(f"[bold]已选 {len(selected)}/{len(episodes)} 集[/]")


# ==================================================================
# 主入口
# ==================================================================

def select_episodes(
    episodes: List[dict],
    preselected: Optional[Set[int]] = None,
    interactive: bool = True,
    episode_spec: Optional[str] = None,
) -> List[int]:
    """选择分集,返回选中的集号列表(从 1 开始)

    Args:
        episodes:    分集列表,每个 dict 至少含 ``id``(或 ``number``)、
                     ``title``、``duration``(秒)
        preselected: 预选中的集号集合
        interactive: 是否交互式;``False`` 时直接返回 preselected 或全部
        episode_spec: 非交互模式下的集号规范,如 ``"1-3,5,7-9"`` 或 ``"all"``

    Returns:
        选中的集号列表(按集号升序)

    Raises:
        UserCancelledError: 用户按 ``q`` 取消或遇到 EOF
        ParseError:         ``episode_spec`` 解析失败或分集字段缺失
    """
    if not episodes:
        return []

    # 提取所有集号,顺带校验字段完整性
    numbers = [_extract_episode_number(ep) for ep in episodes]
    total = len(numbers)
    valid_numbers = set(numbers)

    # 非交互模式:优先 episode_spec,其次 preselected,最后全部
    if not interactive:
        if episode_spec is not None:
            return parse_episode_spec(episode_spec, total)
        if preselected is not None:
            # 过滤掉不在分集列表中的预选号
            return sorted(set(preselected) & valid_numbers)
        return sorted(numbers)

    # 交互模式:渲染表格 + 提示输入集号规范
    selected = set(preselected) if preselected else set()
    _render_episode_table(episodes, selected)

    prompt = "请输入集号规范"
    if preselected:
        prompt += f"(空回车使用预选 {len(preselected)} 集)"
    prompt += ",q 取消: "

    try:
        raw = input(prompt)
    except EOFError as e:
        raise UserCancelledError("输入已结束(EOF)") from e

    raw = raw.strip()
    if not raw:
        # 空回车:有 preselected 用之,否则默认全选
        if preselected is not None:
            return sorted(set(preselected) & valid_numbers)
        return sorted(numbers)
    if raw.lower() == "q":
        raise UserCancelledError("用户取消分集选择")
    return parse_episode_spec(raw, total)
