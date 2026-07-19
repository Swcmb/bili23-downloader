# src/cli/commands/download.py
"""bili23 download <url> - 主下载命令(T5.1)

完整执行流程:
1. 解析 URL(复用 ``cli.commands._shared.parse_url``)
2. 选择分集(交互式或基于 ``--episodes``)
3. 选择画质/音质/编码(交互式或基于 ``--video-quality`` 等参数)
4. ``--dry-run`` 模式:仅打印下载计划,不实际下载
5. 创建下载任务(``task_manager.create``)
6. 启动下载(``Downloader.start``),由 ``ProgressRender`` 实时显示进度
7. 完成后处理附加产物(弹幕/字幕/封面/NFO/封面嵌入)

异常映射(对应规格 7.1 节退出码):
- ``ParseError``(4):          URL 无效或解析失败
- ``AuthRequiredError``(5):   未登录访问会员内容
- ``NetworkError``(6):        网络错误
- ``DiskFullError``(7):       磁盘空间不足
- ``FFmpegMissingError``(8):  FFmpeg 缺失(合并/嵌入需要)
- ``ConfigError``(9):         配置错误
- ``UserCancelledError``(3):  用户取消
"""
from typing import List, Optional

import typer
from rich.console import Console

from cli.app import app
from cli.commands._shared import parse_url
from cli.exceptions import Bili23Error
from cli.interact.episode_selector import select_episodes
from cli.interact.quality_selector import select_quality
from cli.render.progress import ProgressRender
from util.download.downloader.downloader import Downloader
from util.download.task.manager import task_manager

# 模块级共享 Console,供计划打印与错误提示复用
console = Console()


# ==================================================================
# 流程子步骤(模块化,便于测试中 monkeypatch 替换)
# ==================================================================

def _do_parse(url: str) -> dict:
    """解析 URL,返回结构化解析结果

    :raises ParseError: URL 无效或解析失败
    """
    return parse_url(url)


def _select_episodes(parsed: dict, episodes_arg: Optional[str],
                     non_interactive: bool) -> List[int]:
    """选择分集,返回选中的集号列表

    - ``--episodes`` 指定时:非交互解析集号规范
    - ``--non-interactive`` 且未指定 ``--episodes``:默认全部
    - 否则:进入交互式选择
    """
    episodes_list = parsed.get("episodes", []) or []
    # --episodes 指定时强制非交互(参数即选择结果)
    interactive = (episodes_arg is None) and (not non_interactive)
    return select_episodes(
        episodes=episodes_list,
        interactive=interactive,
        episode_spec=episodes_arg,
    )


def _select_quality(parsed: dict, video_quality: Optional[int],
                    audio_quality: Optional[int],
                    video_codec: Optional[str],
                    non_interactive: bool) -> dict:
    """选择画质/音质/编码

    - 任一画质/音质/编码参数已指定时:强制非交互(参数即选择结果)
    - ``--non-interactive`` 且未指定任何参数:使用列表第一项(最高)
    - 否则:进入交互式选择
    """
    quality_specified = any([video_quality, audio_quality, video_codec])
    interactive = (not quality_specified) and (not non_interactive)
    return select_quality(
        video_qualities=parsed.get("video_qualities", []) or [],
        audio_qualities=parsed.get("audio_qualities", []) or [],
        video_codecs=parsed.get("video_codecs", []) or [],
        video_quality_id=video_quality,
        audio_quality_id=audio_quality,
        video_codec=video_codec,
        interactive=interactive,
    )


def _filter_episode_infos(parsed: dict, selected_numbers: List[int]) -> List[dict]:
    """根据选中的集号过滤分集列表,返回 episode_info 列表

    集号匹配优先级:
    1. 分集 dict 的 ``number`` 字段
    2. 分集 dict 的 ``id`` 字段(回退)
    """
    if not selected_numbers:
        return []
    selected_set = set(selected_numbers)
    result = []
    for ep in parsed.get("episodes", []) or []:
        num = ep.get("number")
        if num is None:
            num = ep.get("id")
        try:
            if int(num) in selected_set:
                result.append(ep)
        except (TypeError, ValueError):
            continue
    return result


def _create_tasks(episode_info_list: List[dict]) -> None:
    """调用 task_manager 创建下载任务(持久化 + 信号触发)

    :raises AuthRequiredError: 未登录访问会员内容
    :raises NetworkError:      网络错误
    :raises DiskFullError:     磁盘空间不足
    """
    if not episode_info_list:
        return
    task_manager.create(episode_info_list, show_toast=False)


def _run_download(parsed: dict, quality: dict) -> None:
    """启动下载器(实际下载)

    本函数为 T5.1 占位实现:依赖 signal_bus 触发的下载链路;
    完整的同步下载编排留给 T5.11/T6 阶段。

    :raises FFmpegMissingError: 合并/嵌入需要 FFmpeg 但缺失
    :raises DiskFullError:      磁盘空间不足
    :raises NetworkError:       网络错误
    """
    # ProgressRender 实例化即代表"下载已启动",具体进度由 signal_bus 回调驱动
    render = ProgressRender()
    render.start()
    try:
        # 占位:实际下载由 task_manager.create 触发的信号链路异步执行,
        # 此处保留 Downloader 引用以备 T5.11 同步编排使用
        _ = Downloader  # noqa: F841 - 防止未使用告警,保留导入语义
    finally:
        render.stop()


def _process_extras(parsed: dict, danmaku: Optional[str], subtitle: Optional[str],
                    cover: Optional[str], metadata: Optional[str],
                    embed_cover: bool) -> None:
    """处理附加产物:弹幕/字幕/封面/NFO/封面嵌入

    本函数为 T5.1 占位,实际产物下载由 T5.11/T6 阶段在下载完成后调用。
    """
    # 占位:具体实现见 T5.11/T6(根据 parsed + 选项生成附加文件)
    _ = (parsed, danmaku, subtitle, cover, metadata, embed_cover)


def _print_plan(parsed: dict, selected_numbers: List[int],
                quality: dict, output_dir: Optional[str]) -> None:
    """dry_run 模式下打印下载计划"""
    title = parsed.get("title", "")
    total_eps = len(parsed.get("episodes", []) or [])
    vq_id = quality.get("video_quality_id", "")
    aq_id = quality.get("audio_quality_id", "")
    vc = quality.get("video_codec", "")
    out = output_dir or "(当前目录)"

    console.print("[bold cyan]下载计划(dry-run)[/]")
    console.print(f"  标题:   {title}")
    console.print(f"  分集:   {len(selected_numbers)}/{total_eps} 集 "
                  f"(集号: {selected_numbers})")
    console.print(f"  画质:   {vq_id}")
    console.print(f"  音质:   {aq_id}")
    console.print(f"  编码:   {vc}")
    console.print(f"  输出:   {out}")


# ==================================================================
# 主命令
# ==================================================================

@app.command("download")
def download_cmd(
    url: str = typer.Argument(..., help="B 站 URL"),
    # 输出控制
    output_dir: str = typer.Option(
        None, "-o", "--output", help="输出目录(默认当前目录)"),
    filename_template: str = typer.Option(
        None, "--filename", help="文件名模板"),
    # 分集选择
    episodes: str = typer.Option(
        None, "--episodes",
        help="分集规范,如 '1-3,5' 或 'all'(默认交互选择)"),
    # 画质音质编码
    video_quality: int = typer.Option(
        None, "--video-quality",
        help="画质 ID(127=8K,126=杜比,125=HDR,120=4K,116=1080P60,"
             "112=1080P+,80=1080P,74=720P60,64=720P,32=480P,16=360P)"),
    audio_quality: int = typer.Option(
        None, "--audio-quality",
        help="音质 ID(30280=Hi-Res,30232=132K,30255=杜比,"
             "30250=全景声,30240=64K)"),
    video_codec: str = typer.Option(
        None, "--video-codec", help="视频编码(AVC/HEVC/AV1)"),
    # 附加产物
    danmaku: str = typer.Option(
        None, "--danmaku", help="弹幕格式(xml/ass/json)"),
    subtitle: str = typer.Option(
        None, "--subtitle", help="字幕格式(srt/lrc/txt/ass/json)"),
    cover: str = typer.Option(
        None, "--cover", help="封面格式(jpg/png/avif/webp)"),
    metadata: str = typer.Option(
        None, "--metadata", help="元数据(nfo)"),
    embed_cover: bool = typer.Option(
        False, "--embed-cover", help="封面嵌入视频(需 ffmpeg)"),
    # 下载选项
    download_threads: int = typer.Option(
        None, "--threads", help="下载线程数(1-32)"),
    max_concurrent: int = typer.Option(
        None, "--concurrent", help="最大并发任务数(1-10)"),
    # 模式控制
    non_interactive: bool = typer.Option(
        False, "--non-interactive",
        help="非交互模式(默认全部选项必须由参数指定)"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="仅模拟,不实际下载"),
    # 覆盖控制
    overwrite: bool = typer.Option(
        False, "--overwrite", help="覆盖已存在文件"),
):
    """下载 B 站视频/番剧/课程等"""
    # 预留参数(目前仅校验存在,实际语义在 T5.11/T6 接入)
    _ = (filename_template, download_threads, max_concurrent, overwrite)

    try:
        # 1. 解析 URL
        parsed = _do_parse(url)
        # 2. 选择分集
        selected_numbers = _select_episodes(parsed, episodes, non_interactive)
        # 3. 选择画质/音质/编码
        quality = _select_quality(
            parsed, video_quality, audio_quality, video_codec, non_interactive
        )
        # 4. dry_run:打印计划并返回
        if dry_run:
            _print_plan(parsed, selected_numbers, quality, output_dir)
            return
        # 5. 创建下载任务(过滤后的 episode_info_list)
        episode_info_list = _filter_episode_infos(parsed, selected_numbers)
        _create_tasks(episode_info_list)
        # 6. 启动下载
        _run_download(parsed, quality)
        # 7. 附加产物
        _process_extras(
            parsed, danmaku, subtitle, cover, metadata, embed_cover
        )
    except Bili23Error as exc:
        # 所有 Bili23 内部异常按其 exit_code 退出
        raise typer.Exit(exc.exit_code) from exc
