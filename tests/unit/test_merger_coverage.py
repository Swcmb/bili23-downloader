# tests/unit/test_merger_coverage.py
"""T6 覆盖率补强 - src/util/download/downloader/merger.py

覆盖目标:
- Merger.__init__ 默认字段
- Merger.start 四种分发分支(merge_video_audio / merge_video_parts / m4a_to_mp3 / rename)
- Merger.merge_video_audio 三种分支(v+a / o_only / error)
- Merger.merge_video_parts 创建 lists 文件并合并
- Merger._run_merge_command 连接 finished/error 信号
- Merger.rename_output_file 四种组合(has_video/has_audio)
- Merger.on_merge_completed keep_original_files True/False
- Merger.on_convert_completed 删除 m4a 并 rename
- Merger.mark_as_completed 设置状态并通知 task_manager
- Merger.keep_original_files BOTH/VIDEO/AUDIO/ValueError
- Merger.on_merge_error 7 种错误关键字 + fallback
- Merger.set_error_message 设置标志并 emit 信号
- Merger.get_cwd / add_file(clear/dedup)
- Merger.m4a_to_mp3 文件存在/不存在
- Merger.check_attach_cover attach_cover on/off + 文件存在/不存在
- Merger.create_lists_file 内容正确
- Merger.fix_mp4_box 文件存在/不存在
- 所有 @property 属性
"""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from util.common.enum import DownloadStatus, DownloadType, OriginalFileType
from util.download.downloader.merger import Merger
from util.download.task.info import TaskInfo


# ---------------------------------------------------------------------------
# 辅助函数与夹具
# ---------------------------------------------------------------------------
def make_task_info(download_path: str = "", download_type: int = DownloadType.VIDEO) -> TaskInfo:
    """构造带基础字段的 TaskInfo"""
    info = TaskInfo()
    info.Basic.task_id = "test-task-001"
    info.File.download_path = download_path
    info.File.folder = ""
    info.File.name = "output"
    info.File.video_file_ext = "mp4"
    info.File.audio_file_ext = "m4a"
    info.File.merge_file_ext = "mp4"
    info.File.relative_files = []
    info.Download.type = download_type
    info.Download.merge_video_audio = False
    info.Download.keep_original_files = False
    info.Download.video_parts_count = 0
    info.Download.status = DownloadStatus.DOWNLOADING
    return info


def make_runner_mock():
    """构造 FFmpegRunner mock,提供 from_command/set_cwd/finished_signal/error_signal/start"""
    runner = MagicMock()
    runner.finished_signal = MagicMock()
    runner.error_signal = MagicMock()
    runner.set_cwd = MagicMock()
    runner.start = MagicMock()
    return runner


@pytest.fixture
def mock_config(monkeypatch):
    """mock merger 模块的 config,返回可配置的 MagicMock

    直接通过 Merger.__init__.__globals__ 修改 Merger 类所在模块的 config,
    避免其他测试(如 test_no_pyside6_import)删除并重新加载 merger 模块后,
    monkeypatch.setattr 通过字符串路径 patch 到新模块,而 Merger 类仍引用旧模块
    导致 patch 不生效。
    """
    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "m4a_to_mp3": False,
        "attach_cover": False,
        "cover_type": "jpg",
    }.get(key, default)
    cfg.keep_original_files_type = OriginalFileType.BOTH
    monkeypatch.setitem(Merger.__init__.__globals__, "config", cfg)
    return cfg


@pytest.fixture
def mock_task_manager(monkeypatch):
    """mock merger 模块的 task_manager 单例

    同 mock_config,直接修改 Merger 类所在模块的 task_manager 名字。
    """
    tm = MagicMock()
    monkeypatch.setitem(Merger.__init__.__globals__, "task_manager", tm)
    return tm


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------
def test_init_sets_default_fields(mock_config, mock_task_manager):
    """__init__ 应设置 task_info/_has_error/_ffmpeg_runner/_output_audio_file"""
    info = make_task_info()
    merger = Merger(info, parent=MagicMock())

    assert merger.task_info is info
    assert merger._has_error is False
    assert merger._ffmpeg_runner is None
    assert merger._output_audio_file is None


# ---------------------------------------------------------------------------
# start 分发逻辑
# ---------------------------------------------------------------------------
def test_start_dispatches_to_merge_video_audio(mock_config, mock_task_manager):
    """merge_video_audio=True 时应调用 merge_video_audio"""
    info = make_task_info()
    info.Download.merge_video_audio = True
    merger = Merger(info)

    with patch.object(merger, "merge_video_audio") as m:
        merger.start()

    m.assert_called_once()


def test_start_dispatches_to_merge_video_parts(mock_config, mock_task_manager):
    """video_parts_count > 0 且非 merge_video_audio 时应调用 merge_video_parts"""
    info = make_task_info()
    info.Download.video_parts_count = 3
    merger = Merger(info)

    with patch.object(merger, "merge_video_parts") as m:
        merger.start()

    m.assert_called_once()


def test_start_dispatches_to_m4a_to_mp3(mock_config, mock_task_manager):
    """audio_file_ext=m4a 且 m4a_to_mp3=True 时应调用 m4a_to_mp3"""
    info = make_task_info()
    info.File.audio_file_ext = "m4a"
    mock_config.get.side_effect = lambda key, default=None: {
        "m4a_to_mp3": True,
        "attach_cover": False,
        "cover_type": "jpg",
    }.get(key, default)
    merger = Merger(info)

    with patch.object(merger, "m4a_to_mp3") as m:
        merger.start()

    m.assert_called_once()


def test_start_dispatches_to_rename_when_m4a_without_convert(mock_config, mock_task_manager):
    """audio_file_ext=m4a 且 m4a_to_mp3=False 时应调用 rename_output_file"""
    info = make_task_info()
    info.File.audio_file_ext = "m4a"
    merger = Merger(info)

    with patch.object(merger, "rename_output_file") as m:
        merger.start()

    m.assert_called_once()


def test_start_dispatches_to_rename_default(mock_config, mock_task_manager):
    """默认分支(非 merge/parts/m4a)应调用 rename_output_file"""
    info = make_task_info()
    info.File.audio_file_ext = "mp3"
    merger = Merger(info)

    with patch.object(merger, "rename_output_file") as m:
        merger.start()

    m.assert_called_once()


# ---------------------------------------------------------------------------
# merge_video_audio
# ---------------------------------------------------------------------------
def test_merge_video_audio_both_exist_runs_command(tmp_path, mock_config, mock_task_manager):
    """v_exists + a_exists 应通过 _run_merge_command 执行合并"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    merger = Merger(info)

    # 创建临时视频和音频文件
    (tmp_path / merger.temp_video_file_name).touch()
    (tmp_path / merger.temp_audio_file_name).touch()

    runner = make_runner_mock()
    with patch("util.download.downloader.merger.FFmpegCommand.merge_video_audio",
               return_value=MagicMock()) as cmd_cls, \
         patch("util.download.downloader.merger.FFmpegRunner.from_command",
               return_value=runner):
        merger.merge_video_audio()

    cmd_cls.assert_called_once()
    runner.set_cwd.assert_called_once()
    runner.start.assert_called_once()


def test_merge_video_audio_output_only_triggers_completed(tmp_path, mock_config, mock_task_manager):
    """仅 output 存在(无 v/a)应调用 on_merge_completed"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    merger = Merger(info)

    (tmp_path / merger.temp_output_file_name).touch()

    with patch.object(merger, "on_merge_completed") as completed:
        merger.merge_video_audio()

    completed.assert_called_once_with(0, "", "")


def test_merge_video_audio_no_files_sets_error(tmp_path, mock_config, mock_task_manager):
    """无任何文件时应调用 set_error_message"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    merger = Merger(info)

    with patch.object(merger, "set_error_message") as err:
        merger.merge_video_audio()

    err.assert_called_once()


# ---------------------------------------------------------------------------
# merge_video_parts
# ---------------------------------------------------------------------------
def test_merge_video_parts_creates_lists_and_runs(tmp_path, mock_config, mock_task_manager):
    """merge_video_parts 应创建 lists 文件并执行合并命令"""
    info = make_task_info(str(tmp_path))
    info.Download.video_parts_count = 2
    merger = Merger(info)

    runner = make_runner_mock()
    with patch("util.download.downloader.merger.FFmpegCommand.merge_video_parts",
               return_value=MagicMock()) as cmd_cls, \
         patch("util.download.downloader.merger.FFmpegRunner.from_command",
               return_value=runner):
        merger.merge_video_parts()

    # lists 文件应被创建
    lists_file = tmp_path / f"lists_{info.Basic.task_id}.txt"
    assert lists_file.exists()
    content = lists_file.read_text(encoding="utf-8")
    assert "file 'video_test-task-001_0.mp4'" in content
    assert "file 'video_test-task-001_1.mp4'" in content

    cmd_cls.assert_called_once()
    runner.start.assert_called_once()


# ---------------------------------------------------------------------------
# rename_output_file
# ---------------------------------------------------------------------------
def test_rename_output_file_returns_when_error(mock_config, mock_task_manager):
    """_has_error=True 时 rename_output_file 应直接返回"""
    info = make_task_info()
    merger = Merger(info)
    merger._has_error = True

    # 不应抛异常,不应执行任何操作
    merger.rename_output_file()


def test_rename_output_file_video_and_audio(tmp_path, mock_config, mock_task_manager):
    """has_video + has_audio 应调用 keep_original_files 并 add_file"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    merger = Merger(info)

    # 创建视频和音频文件供 keep_original_files 重命名
    (tmp_path / merger.temp_video_file_name).touch()
    (tmp_path / merger.temp_audio_file_name).touch()

    with patch.object(merger, "mark_as_completed") as completed:
        merger.rename_output_file()

    completed.assert_called_once()


def test_rename_output_file_video_only(tmp_path, mock_config, mock_task_manager):
    """has_video + !has_audio 应重命名视频文件"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO)
    info.File.video_file_ext = "mp4"
    merger = Merger(info)

    (tmp_path / merger.temp_video_file_name).touch()

    with patch.object(merger, "mark_as_completed") as completed:
        merger.rename_output_file()

    completed.assert_called_once()
    # relative_files 应包含重命名后的文件
    assert len(info.File.relative_files) > 0


def test_rename_output_file_audio_only(tmp_path, mock_config, mock_task_manager):
    """has_audio + !has_video 应重命名音频文件"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.AUDIO)
    info.File.audio_file_ext = "m4a"
    merger = Merger(info)

    (tmp_path / merger.temp_audio_file_name).touch()

    with patch.object(merger, "mark_as_completed") as completed:
        merger.rename_output_file()

    completed.assert_called_once()


def test_rename_output_file_exception_sets_error(tmp_path, mock_config, mock_task_manager):
    """rename 过程中抛异常应调用 set_error_message"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO)
    merger = Merger(info)

    with patch("util.download.downloader.merger.safe_rename",
               side_effect=OSError("boom")):
        with patch.object(merger, "set_error_message") as err:
            merger.rename_output_file()

    err.assert_called_once()


# ---------------------------------------------------------------------------
# on_merge_completed
# ---------------------------------------------------------------------------
def test_on_merge_completed_returns_when_error(mock_config, mock_task_manager):
    """_has_error=True 时 on_merge_completed 应直接返回"""
    info = make_task_info()
    merger = Merger(info)
    merger._has_error = True

    merger.on_merge_completed(0, "", "")


def test_on_merge_completed_keep_original_false(tmp_path, mock_config, mock_task_manager):
    """keep_original_files=False 应删除临时文件并标记完成"""
    info = make_task_info(str(tmp_path))
    info.Download.keep_original_files = False
    info.File.relative_files = ["temp1.mp4", "temp2.m4a"]
    merger = Merger(info)

    (tmp_path / merger.temp_output_file_name).touch()
    (tmp_path / "temp1.mp4").touch()
    (tmp_path / "temp2.m4a").touch()

    with patch.object(merger, "mark_as_completed") as completed:
        merger.on_merge_completed(0, "", "")

    completed.assert_called_once()


def test_on_merge_completed_keep_original_true(tmp_path, mock_config, mock_task_manager):
    """keep_original_files=True 应保留原始文件并标记完成"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    # 使用不同扩展名避免 final_output 与 final_video 文件名冲突
    info.File.merge_file_ext = "mp4"
    info.File.video_file_ext = "mkv"
    info.File.audio_file_ext = "m4a"
    info.Download.keep_original_files = True
    mock_config.keep_original_files_type = OriginalFileType.BOTH
    merger = Merger(info)

    (tmp_path / merger.temp_output_file_name).touch()
    (tmp_path / merger.temp_video_file_name).touch()
    (tmp_path / merger.temp_audio_file_name).touch()

    with patch.object(merger, "mark_as_completed") as completed:
        merger.on_merge_completed(0, "", "")

    completed.assert_called_once()


def test_on_merge_completed_exception_sets_error(tmp_path, mock_config, mock_task_manager):
    """on_merge_completed 异常应调用 set_error_message"""
    info = make_task_info(str(tmp_path))
    merger = Merger(info)

    with patch("util.download.downloader.merger.safe_rename",
               side_effect=OSError("boom")):
        with patch.object(merger, "set_error_message") as err:
            merger.on_merge_completed(0, "", "")

    err.assert_called_once()


# ---------------------------------------------------------------------------
# on_convert_completed
# ---------------------------------------------------------------------------
def test_on_convert_completed_returns_when_error(mock_config, mock_task_manager):
    """_has_error=True 时 on_convert_completed 应直接返回"""
    info = make_task_info()
    merger = Merger(info)
    merger._has_error = True

    merger.on_convert_completed(0, "", "")


def test_on_convert_completed_removes_m4a_and_renames(tmp_path, mock_config, mock_task_manager):
    """on_convert_completed 应删除 m4a 并调用 rename_output_file"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.AUDIO)
    info.File.audio_file_ext = "mp3"
    merger = Merger(info)
    merger._temp_m4a_audio_name = "audio_test.m4a"

    (tmp_path / "audio_test.m4a").touch()

    with patch.object(merger, "rename_output_file") as rename:
        merger.on_convert_completed(0, "", "")

    rename.assert_called_once()
    # m4a 文件应被删除
    assert not (tmp_path / "audio_test.m4a").exists()


def test_on_convert_completed_exception_sets_error(tmp_path, mock_config, mock_task_manager):
    """on_convert_completed 异常应调用 set_error_message"""
    info = make_task_info(str(tmp_path))
    merger = Merger(info)

    with patch("util.download.downloader.merger.safe_remove",
               side_effect=OSError("boom")):
        with patch.object(merger, "set_error_message") as err:
            merger.on_convert_completed(0, "", "")

    err.assert_called_once()


# ---------------------------------------------------------------------------
# mark_as_completed
# ---------------------------------------------------------------------------
def test_mark_as_completed_returns_when_error(mock_config, mock_task_manager):
    """_has_error=True 时 mark_as_completed 应直接返回"""
    info = make_task_info()
    merger = Merger(info)
    merger._has_error = True

    merger.mark_as_completed()
    # task_manager.mark_as_completed 不应被调用
    mock_task_manager.mark_as_completed.assert_not_called()


def test_mark_as_completed_updates_status_and_notifies(mock_config, mock_task_manager):
    """mark_as_completed 应设置 status=COMPLETED 并通知 task_manager"""
    info = make_task_info()
    merger = Merger(info)

    merger.mark_as_completed()

    assert info.Download.status == DownloadStatus.COMPLETED
    assert info.Basic.completed_time > 0
    mock_task_manager.mark_as_completed.assert_called_once_with(info)


# ---------------------------------------------------------------------------
# keep_original_files
# ---------------------------------------------------------------------------
def test_keep_original_files_both(tmp_path, mock_config, mock_task_manager):
    """OriginalFileType.BOTH 应重命名视频和音频文件"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    mock_config.keep_original_files_type = OriginalFileType.BOTH
    merger = Merger(info)

    (tmp_path / merger.temp_video_file_name).touch()
    (tmp_path / merger.temp_audio_file_name).touch()

    result = merger.keep_original_files()

    assert len(result) == 2


def test_keep_original_files_video_only(tmp_path, mock_config, mock_task_manager):
    """OriginalFileType.VIDEO 应仅重命名视频文件"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    mock_config.keep_original_files_type = OriginalFileType.VIDEO
    merger = Merger(info)

    (tmp_path / merger.temp_video_file_name).touch()
    (tmp_path / merger.temp_audio_file_name).touch()

    result = merger.keep_original_files()

    assert len(result) == 1


def test_keep_original_files_audio_only(tmp_path, mock_config, mock_task_manager):
    """OriginalFileType.AUDIO 应仅重命名音频文件"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    mock_config.keep_original_files_type = OriginalFileType.AUDIO
    merger = Merger(info)

    (tmp_path / merger.temp_video_file_name).touch()
    (tmp_path / merger.temp_audio_file_name).touch()

    result = merger.keep_original_files()

    assert len(result) == 1


def test_keep_original_files_invalid_type_falls_back_to_both(tmp_path, mock_config, mock_task_manager):
    """无效的 keep_original_files_type 应回退到 BOTH"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    mock_config.keep_original_files_type = 999  # 无效值
    merger = Merger(info)

    (tmp_path / merger.temp_video_file_name).touch()
    (tmp_path / merger.temp_audio_file_name).touch()

    result = merger.keep_original_files()

    # 应回退到 BOTH,重命名两个文件
    assert len(result) == 2


def test_keep_original_files_exception_returns_empty(mock_config, mock_task_manager):
    """keep_original_files 异常应调用 set_error_message 并返回空列表"""
    info = make_task_info()
    merger = Merger(info)

    with patch("util.download.downloader.merger.safe_rename",
               side_effect=OSError("boom")):
        result = merger.keep_original_files()

    assert result == []
    assert merger._has_error is True


# ---------------------------------------------------------------------------
# on_merge_error
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("stderr_keyword,expected_key", [
    ("No space left on device", "INSUFFICIENT_SPACE"),
    ("Permission denied", "PERMISSION_DENIED"),
    ("Invalid data found when processing input", "CORRUPTED_FILE"),
    ("No such file or directory", "FILE_NOT_FOUND"),
    ("Could not open file", "COULD_NOT_OPEN"),
    ("Device or resource busy", "FILE_IS_BUSY"),
    ("Could not create output file", "CANNOT_CREATE"),
])
def test_on_merge_error_matches_keywords(stderr_keyword, expected_key,
                                          mock_config, mock_task_manager):
    """on_merge_error 应匹配 7 种错误关键字并调用 set_error_message"""
    info = make_task_info()
    merger = Merger(info)

    with patch.object(merger, "set_error_message") as err:
        merger.on_merge_error(RuntimeError("orig"), "", stderr_keyword)

    err.assert_called_once()
    # conftest patch 使 Translator.ERROR_MESSAGES 返回 key 本身
    short_msg = err.call_args[0][0]
    assert short_msg == "DOWNLOAD_FAILED"


def test_on_merge_error_fallback_to_error_str(mock_config, mock_task_manager):
    """无匹配关键字时应使用 error 的字符串表示"""
    info = make_task_info()
    merger = Merger(info)
    error = RuntimeError("unknown error")

    with patch.object(merger, "set_error_message") as err:
        merger.on_merge_error(error, "", "unrecognized stderr")

    err.assert_called_once()
    long_msg = err.call_args[0][1]
    assert "unknown error" in long_msg


# ---------------------------------------------------------------------------
# set_error_message
# ---------------------------------------------------------------------------
def test_set_error_message_sets_flag_and_status(mock_config, mock_task_manager):
    """set_error_message 应设置 _has_error 和 status=FFMPEG_FAILED"""
    info = make_task_info()
    merger = Merger(info)

    merger.set_error_message("short", "long description")

    assert merger._has_error is True
    assert info.Download.status == DownloadStatus.FFMPEG_FAILED


# ---------------------------------------------------------------------------
# get_cwd / add_file
# ---------------------------------------------------------------------------
def test_get_cwd_returns_correct_path(mock_config, mock_task_manager):
    """get_cwd 应返回 Path(download_path, folder)"""
    info = make_task_info("/tmp/dl")
    info.File.folder = "subfolder"
    merger = Merger(info)

    cwd = merger.get_cwd()

    assert cwd == Path("/tmp/dl", "subfolder")


def test_add_file_appends_to_relative_files(mock_config, mock_task_manager):
    """add_file 应将文件名追加到 relative_files"""
    info = make_task_info()
    merger = Merger(info)

    merger.add_file("file1.mp4", "file2.m4a")

    assert "file1.mp4" in info.File.relative_files
    assert "file2.m4a" in info.File.relative_files
    mock_task_manager.update.assert_called_once_with(info)


def test_add_file_clear_resets_list(mock_config, mock_task_manager):
    """add_file(clear=True) 应先清空 relative_files"""
    info = make_task_info()
    info.File.relative_files = ["old.mp4"]
    merger = Merger(info)

    merger.add_file("new.mp4", clear=True)

    assert "old.mp4" not in info.File.relative_files
    assert "new.mp4" in info.File.relative_files


def test_add_file_dedup(mock_config, mock_task_manager):
    """add_file 应去重已存在的文件名"""
    info = make_task_info()
    info.File.relative_files = ["file1.mp4"]
    merger = Merger(info)

    merger.add_file("file1.mp4", "file2.mp4")

    assert info.File.relative_files.count("file1.mp4") == 1
    assert "file2.mp4" in info.File.relative_files


# ---------------------------------------------------------------------------
# m4a_to_mp3
# ---------------------------------------------------------------------------
def test_m4a_to_mp3_file_exists_runs_convert(tmp_path, mock_config, mock_task_manager):
    """m4a 文件存在时应执行转换命令"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.AUDIO)
    merger = Merger(info)

    (tmp_path / merger.temp_audio_file_name).touch()

    runner = make_runner_mock()
    with patch("util.download.downloader.merger.FFmpegCommand.convert_m4a_to_mp3",
               return_value=MagicMock()), \
         patch("util.download.downloader.merger.FFmpegRunner.from_command",
               return_value=runner):
        merger.m4a_to_mp3()

    runner.start.assert_called_once()
    assert info.Download.status == DownloadStatus.CONVERTING
    assert info.File.audio_file_ext == "mp3"


def test_m4a_to_mp3_file_not_exist_sets_error(tmp_path, mock_config, mock_task_manager):
    """m4a 文件不存在时应调用 set_error_message"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.AUDIO)
    merger = Merger(info)

    with patch.object(merger, "set_error_message") as err:
        merger.m4a_to_mp3()

    err.assert_called_once()


# ---------------------------------------------------------------------------
# check_attach_cover
# ---------------------------------------------------------------------------
def test_check_attach_cover_disabled_returns_none(mock_config, mock_task_manager):
    """attach_cover=False 时应返回 None"""
    info = make_task_info()
    mock_config.get.side_effect = lambda key, default=None: {
        "attach_cover": False,
        "cover_type": "jpg",
    }.get(key, default)
    merger = Merger(info)

    assert merger.check_attach_cover() is None


def test_check_attach_cover_enabled_file_exists_returns_path(tmp_path, mock_config, mock_task_manager):
    """attach_cover=True 且封面文件存在时应返回封面文件名"""
    info = make_task_info(str(tmp_path))
    mock_config.get.side_effect = lambda key, default=None: {
        "attach_cover": True,
        "cover_type": "jpg",
    }.get(key, default)
    merger = Merger(info)

    (tmp_path / merger.cover_file_name).touch()

    assert merger.check_attach_cover() == merger.cover_file_name


def test_check_attach_cover_enabled_file_not_exist_returns_none(tmp_path, mock_config, mock_task_manager):
    """attach_cover=True 但封面文件不存在时应返回 None"""
    info = make_task_info(str(tmp_path))
    mock_config.get.side_effect = lambda key, default=None: {
        "attach_cover": True,
        "cover_type": "jpg",
    }.get(key, default)
    merger = Merger(info)

    assert merger.check_attach_cover() is None


# ---------------------------------------------------------------------------
# create_lists_file
# ---------------------------------------------------------------------------
def test_create_lists_file_writes_correct_content(tmp_path, mock_config, mock_task_manager):
    """create_lists_file 应写入正确格式的分片文件列表"""
    info = make_task_info(str(tmp_path))
    info.File.video_file_ext = "flv"
    merger = Merger(info)

    result = merger.create_lists_file(3)

    assert result == f"lists_{info.Basic.task_id}.txt"
    content = (tmp_path / result).read_text(encoding="utf-8")
    assert "file 'video_test-task-001_0.flv'" in content
    assert "file 'video_test-task-001_1.flv'" in content
    assert "file 'video_test-task-001_2.flv'" in content


# ---------------------------------------------------------------------------
# fix_mp4_box
# ---------------------------------------------------------------------------
def test_fix_mp4_box_file_exists_runs_fix(tmp_path, mock_config, mock_task_manager):
    """m4a 文件存在时应执行修复命令"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.AUDIO)
    merger = Merger(info)

    (tmp_path / merger.temp_audio_file_name).touch()

    runner = make_runner_mock()
    with patch("util.download.downloader.merger.FFmpegCommand.fix_mp4_box",
               return_value=MagicMock()), \
         patch("util.download.downloader.merger.FFmpegRunner.from_command",
               return_value=runner):
        merger.fix_mp4_box()

    runner.start.assert_called_once()
    assert info.Download.status == DownloadStatus.CONVERTING


def test_fix_mp4_box_file_not_exist_sets_error(tmp_path, mock_config, mock_task_manager):
    """m4a 文件不存在时应调用 set_error_message"""
    info = make_task_info(str(tmp_path), download_type=DownloadType.AUDIO)
    merger = Merger(info)

    with patch.object(merger, "set_error_message") as err:
        merger.fix_mp4_box()

    err.assert_called_once()


# ---------------------------------------------------------------------------
# @property 属性
# ---------------------------------------------------------------------------
def test_temp_video_file_name(mock_config, mock_task_manager):
    """temp_video_file_name 应包含 task_id 和 video_file_ext"""
    info = make_task_info()
    info.File.video_file_ext = "mp4"
    merger = Merger(info)

    assert merger.temp_video_file_name == "video_test-task-001.mp4"


def test_temp_audio_file_name(mock_config, mock_task_manager):
    """temp_audio_file_name 应包含 task_id 和 audio_file_ext"""
    info = make_task_info()
    info.File.audio_file_ext = "m4a"
    merger = Merger(info)

    assert merger.temp_audio_file_name == "audio_test-task-001.m4a"


def test_temp_output_file_name(mock_config, mock_task_manager):
    """temp_output_file_name 应包含 task_id 和 merge_file_ext"""
    info = make_task_info()
    info.File.merge_file_ext = "mkv"
    merger = Merger(info)

    assert merger.temp_output_file_name == "output_test-task-001.mkv"


def test_temp_cover_file_name(mock_config, mock_task_manager):
    """temp_cover_file_name 应包含 task_id 和 cover_type"""
    info = make_task_info()
    mock_config.get.side_effect = lambda key, default=None: {
        "cover_type": "png",
    }.get(key, default)
    merger = Merger(info)

    assert merger.temp_cover_file_name == "cover_test-task-001.png"


def test_final_output_file_name(mock_config, mock_task_manager):
    """final_output_file_name 应包含 name 和 merge_file_ext"""
    info = make_task_info()
    info.File.name = "my_video"
    info.File.merge_file_ext = "mp4"
    merger = Merger(info)

    assert merger.final_output_file_name == "my_video.mp4"


def test_final_video_file_name(mock_config, mock_task_manager):
    """final_video_file_name 应包含 name 和 video_file_ext"""
    info = make_task_info()
    info.File.name = "my_video"
    info.File.video_file_ext = "mp4"
    merger = Merger(info)

    assert merger.final_video_file_name == "my_video.mp4"


def test_final_mp4_video_file_name(mock_config, mock_task_manager):
    """final_mp4_video_file_name 应固定使用 .mp4 扩展名"""
    info = make_task_info()
    info.File.name = "my_video"
    merger = Merger(info)

    assert merger.final_mp4_video_file_name == "my_video.mp4"


def test_final_audio_file_name(mock_config, mock_task_manager):
    """final_audio_file_name 应包含 name 和 audio_file_ext"""
    info = make_task_info()
    info.File.name = "my_audio"
    info.File.audio_file_ext = "mp3"
    merger = Merger(info)

    assert merger.final_audio_file_name == "my_audio.mp3"


def test_cover_file_name(mock_config, mock_task_manager):
    """cover_file_name 应包含 name 和 cover_type"""
    info = make_task_info()
    info.File.name = "my_video"
    mock_config.get.side_effect = lambda key, default=None: {
        "cover_type": "webp",
    }.get(key, default)
    merger = Merger(info)

    assert merger.cover_file_name == "my_video.webp"
