# tests/cli/test_download_cmd.py
"""T5.1 测试 - bili23 download 主命令

覆盖:
- test_download_registered:           命令注册到 app
- test_download_help:                 `bili23 download --help` 退出码 0
- test_download_help_shows_all_options: --help 输出包含所有必需选项
- test_download_dry_run:              --dry-run 不实际下载,打印计划
- test_download_non_interactive:      --non-interactive --episodes all 不进入交互
- test_download_invalid_url:          无效 URL 退出码 4
- test_download_with_episodes_spec:   --episodes 1-3 选择 1-3 集
- test_download_with_quality:         指定画质/音质/编码,非交互
- test_download_user_cancel:          select_episodes 抛 UserCancelledError,exit 3
- test_download_auth_required:        task_manager 抛 AuthRequiredError,exit 5
- test_download_network_error:        task_manager 抛 NetworkError,exit 6
- test_download_dry_run_no_task_create: dry_run 不调用 task_manager.create
- test_download_extras_options:       --danmaku/--subtitle/--cover/--metadata/--embed-cover 不报错

所有外部依赖(parse_url/select_episodes/select_quality/task_manager/Downloader/ProgressRender)
均通过 monkeypatch mock,不触达网络/数据库/文件系统。
"""
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import cli.commands.download as download_module  # noqa: F401 - 触发命令注册
from cli.app import app
from cli.exceptions import (
    AuthRequiredError,
    NetworkError,
    ParseError,
    UserCancelledError,
)


runner = CliRunner()


# ------------------------------------------------------------------
# 测试夹具与辅助
# ------------------------------------------------------------------

def _fake_parsed_result(num_episodes: int = 5) -> dict:
    """构造测试用解析结果(包含分集、画质、音质、编码)"""
    return {
        "title": "测试视频",
        "uploader": "测试UP主",
        "category": "USER_UPLOADS",
        "episodes": [
            {
                "number": i,
                "id": i,
                "title": f"第 {i} 集",
                "duration": 60 * i,
                "bvid": "BV1xxx",
                "cid": 100 + i,
            }
            for i in range(1, num_episodes + 1)
        ],
        "video_qualities": [
            {"id": 127, "name": "8K 超高清"},
            {"id": 80, "name": "1080P 高清"},
            {"id": 64, "name": "720P 高清"},
        ],
        "audio_qualities": [
            {"id": 30280, "name": "Hi-Res 128K"},
            {"id": 30232, "name": "132K"},
            {"id": 30240, "name": "64K"},
        ],
        "video_codecs": ["AVC", "HEVC", "AV1"],
    }


def _patch_all(monkeypatch, *, parsed=None, selected_episodes=None,
               quality_result=None):
    """统一 patch 所有外部依赖

    :param parsed:            parse_url 返回值,默认 _fake_parsed_result()
    :param selected_episodes: select_episodes 返回值,默认 [1, 2, 3]
    :param quality_result:    select_quality 返回值,默认固定画质/音质/编码
    :return:                  dict 含各 mock 实例,便于断言
    """
    if parsed is None:
        parsed = _fake_parsed_result()
    if selected_episodes is None:
        selected_episodes = [1, 2, 3]
    if quality_result is None:
        quality_result = {
            "video_quality_id": 80,
            "audio_quality_id": 30232,
            "video_codec": "AVC",
        }

    parse_url_mock = MagicMock(return_value=parsed)
    select_episodes_mock = MagicMock(return_value=selected_episodes)
    select_quality_mock = MagicMock(return_value=quality_result)
    task_manager_mock = MagicMock()
    downloader_cls_mock = MagicMock()
    progress_cls_mock = MagicMock()
    process_extras_mock = MagicMock()

    monkeypatch.setattr(download_module, "parse_url", parse_url_mock)
    monkeypatch.setattr(download_module, "select_episodes", select_episodes_mock)
    monkeypatch.setattr(download_module, "select_quality", select_quality_mock)
    monkeypatch.setattr(download_module, "task_manager", task_manager_mock)
    monkeypatch.setattr(download_module, "Downloader", downloader_cls_mock)
    monkeypatch.setattr(download_module, "ProgressRender", progress_cls_mock)
    monkeypatch.setattr(download_module, "_process_extras", process_extras_mock)

    return {
        "parse_url": parse_url_mock,
        "select_episodes": select_episodes_mock,
        "select_quality": select_quality_mock,
        "task_manager": task_manager_mock,
        "Downloader": downloader_cls_mock,
        "ProgressRender": progress_cls_mock,
        "_process_extras": process_extras_mock,
    }


# ------------------------------------------------------------------
# 命令注册与帮助
# ------------------------------------------------------------------

def test_download_registered():
    """download 命令应被注册到 app.registered_commands"""
    names = [cmd.name for cmd in app.registered_commands]
    assert "download" in names


def test_download_help():
    """`bili23 download --help` 退出码 0"""
    result = runner.invoke(app, ["download", "--help"])
    assert result.exit_code == 0


def test_download_help_shows_all_options():
    """--help 输出包含所有必需选项(AC-028-1 子集)"""
    result = runner.invoke(app, ["download", "--help"])
    assert result.exit_code == 0
    required_options = [
        "--episodes",
        "--video-quality",
        "--audio-quality",
        "--video-codec",
        "--danmaku",
        "--subtitle",
        "--cover",
        "--metadata",
        "--embed-cover",
        "--threads",
        "--concurrent",
        "--non-interactive",
        "--dry-run",
        "--overwrite",
    ]
    for opt in required_options:
        assert opt in result.stdout, f"--help 缺少选项: {opt}"


# ------------------------------------------------------------------
# dry_run 模式
# ------------------------------------------------------------------

def test_download_dry_run(monkeypatch):
    """--dry-run 不实际下载,打印计划(AC-028-3 / AC-001-1)"""
    mocks = _patch_all(monkeypatch)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1-3",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    # dry_run 不应触达 task_manager / Downloader
    mocks["task_manager"].create.assert_not_called()
    mocks["Downloader"].assert_not_called()
    # 但应调用 parse / select / quality
    mocks["parse_url"].assert_called_once()
    mocks["select_episodes"].assert_called_once()
    mocks["select_quality"].assert_called_once()
    # 应打印计划(包含集数与画质)
    assert "1-3" in result.output or "3" in result.output


def test_download_dry_run_no_task_create(monkeypatch):
    """dry_run 模式下 task_manager.create 完全不被调用"""
    mocks = _patch_all(monkeypatch)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "all",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    mocks["task_manager"].create.assert_not_called()
    mocks["Downloader"].assert_not_called()


# ------------------------------------------------------------------
# 非交互模式
# ------------------------------------------------------------------

def test_download_non_interactive(monkeypatch):
    """--non-interactive --episodes all 不进入交互模式"""
    mocks = _patch_all(monkeypatch)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "all",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    # 验证 select_episodes 被调用时 interactive=False
    _, kwargs = mocks["select_episodes"].call_args
    assert kwargs.get("interactive") is False
    assert kwargs.get("episode_spec") == "all"


def test_download_with_episodes_spec(monkeypatch):
    """--episodes 1-3 选择 1-3 集(AC-001-2)"""
    mocks = _patch_all(monkeypatch, selected_episodes=[1, 2, 3])

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1-3",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    mocks["select_episodes"].assert_called_once()
    _, kwargs = mocks["select_episodes"].call_args
    assert kwargs.get("episode_spec") == "1-3"


def test_download_with_quality(monkeypatch):
    """--video-quality 80 --audio-quality 30232 --video-codec AVC 非交互"""
    mocks = _patch_all(monkeypatch)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--video-quality", "80",
            "--audio-quality", "30232",
            "--video-codec", "AVC",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    mocks["select_quality"].assert_called_once()
    _, kwargs = mocks["select_quality"].call_args
    assert kwargs.get("video_quality_id") == 80
    assert kwargs.get("audio_quality_id") == 30232
    assert kwargs.get("video_codec") == "AVC"
    assert kwargs.get("interactive") is False


# ------------------------------------------------------------------
# 异常处理
# ------------------------------------------------------------------

def test_download_invalid_url(monkeypatch):
    """无效 URL 触发 ParseError,退出码 4(AC-028-2)"""
    parse_url_mock = MagicMock(side_effect=ParseError("无效的 URL"))
    monkeypatch.setattr(download_module, "parse_url", parse_url_mock)

    result = runner.invoke(app, ["download", "not-a-url", "--dry-run"])

    assert result.exit_code == 4


def test_download_user_cancel(monkeypatch):
    """select_episodes 抛 UserCancelledError,exit 3"""
    mocks = _patch_all(monkeypatch)
    mocks["select_episodes"].side_effect = UserCancelledError("用户取消")

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--dry-run",
        ],
    )

    assert result.exit_code == 3


def test_download_auth_required(monkeypatch):
    """task_manager.create 抛 AuthRequiredError,exit 5"""
    mocks = _patch_all(monkeypatch)
    mocks["task_manager"].create.side_effect = AuthRequiredError("需登录")

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
        ],
    )

    assert result.exit_code == 5


def test_download_network_error(monkeypatch):
    """task_manager.create 抛 NetworkError,exit 6"""
    mocks = _patch_all(monkeypatch)
    mocks["task_manager"].create.side_effect = NetworkError("网络错误")

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
        ],
    )

    assert result.exit_code == 6


# ------------------------------------------------------------------
# 附加产物选项
# ------------------------------------------------------------------

def test_download_extras_options(monkeypatch):
    """--danmaku/--subtitle/--cover/--metadata/--embed-cover 在 dry_run 下不报错"""
    mocks = _patch_all(monkeypatch)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--danmaku", "xml",
            "--subtitle", "srt",
            "--cover", "jpg",
            "--metadata", "nfo",
            "--embed-cover",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output


def test_download_real_run_invokes_task_manager(monkeypatch):
    """非 dry_run 模式调用 task_manager.create(实际下载交给 T5.11/T6)"""
    mocks = _patch_all(monkeypatch)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
        ],
    )

    assert result.exit_code == 0, result.output
    mocks["task_manager"].create.assert_called_once()
