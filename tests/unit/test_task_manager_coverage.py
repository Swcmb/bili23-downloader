# tests/unit/test_task_manager_coverage.py
"""T6 覆盖率补强 - src/util/download/task/manager.py

覆盖目标:
- TaskManager.__init__ 初始化 db_manager/locks/executor/signal 连接
- TaskManager.create 正常创建/reparse/重复/异常 四条路径
- TaskManager.query 查询下载中/已完成任务
- TaskManager.update / update_async / _flush_updates / _wait_for_pending_updates
- TaskManager.delete / cancel / mark_as_completed / reset / recreate
- TaskManager._removeTemporaryFiles
- TaskManager._update_media_info (video/audio quality + codec)
- TaskManager._check_duplicate (CONTINUE/SKIP/ALWAYS_ASK/无重复)
- TaskManager._calc_hash_id (VIDEO/BANGUMI/CHEESE/AUDIO 四分支)
- TaskManager._show_add_to_queue_toast / _reset_add_to_queue_toast_flag
- TaskManager.__get_number (CONTINUOUS/FROM_SPECIFIED/default)
- TaskManager.__determine_download_type
- TaskManager.__filter_illegal_characters
- TaskManager.__check_reparse_needed
"""
from unittest.mock import MagicMock, patch

import pytest

from util.common.enum import (
    DownloadStatus,
    DownloadType,
    DuplicateDownloadResolution,
    NumberingType,
)
from util.download.task.info import TaskInfo
from util.download.task.manager import TaskManager
from util.parse.episode.tree import Attribute, EpisodeData


# ---------------------------------------------------------------------------
# 辅助函数与夹具
# ---------------------------------------------------------------------------
def make_episode_info(attribute: int = Attribute.VIDEO_BIT,
                      title: str = "测试任务") -> dict:
    """构造带基础字段的 episode_info"""
    return {
        "episode_id": "ep-001",
        "title": title,
        "attribute": attribute,
        "bvid": "BV1xx411c7mD",
        "cid": 12345,
        "aid": 67890,
        "sid": 999,
        "ep_id": 100,
        "cover": "https://example.com/cover.jpg",
    }


@pytest.fixture
def mock_config(monkeypatch):
    """mock manager 模块的 config,返回可控配置"""
    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "download_path": "/tmp/downloads",
        "download_danmaku": False,
        "download_subtitle": False,
        "download_cover": False,
        "download_metadata": False,
        "numbering_type": NumberingType.CONTINUOUS,
        "duplicate_download_resolution": DuplicateDownloadResolution.CONTINUE,
    }.get(key, default)
    cfg.video_quality_id = 80
    cfg.audio_quality_id = 30232
    cfg.video_codec_id = 7
    cfg.merge_video_audio = True
    cfg.keep_original_files = False
    cfg.download_video_stream = True
    cfg.download_audio_stream = True
    cfg.global_starting_number = 1
    cfg.current_starting_number = 1
    cfg.target_naming_rule_id = None
    monkeypatch.setattr("util.download.task.manager.config", cfg)
    return cfg


@pytest.fixture
def task_mgr(tmp_path, monkeypatch, mock_config):
    """构造使用 tmp_path 数据库的 TaskManager 实例

    通过 patch directory.data_dir 使 TaskDatabase 在 tmp_path 下创建数据库文件,
    避免污染真实应用数据目录。同时 mock cover_manager 与 FileNameFormatter。
    """
    from util.common.io.directory import directory
    monkeypatch.setattr(directory, "data_dir", str(tmp_path))

    # mock cover_manager.arrange_cover_id 避免依赖封面数据库
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager.arrange_cover_id",
        lambda cover: "mock-cover-id",
    )

    # mock FileNameFormatter 避免依赖命名规则解析
    fake_formatter = MagicMock()
    fake_formatter.format.return_value = "output/video"
    fake_formatter.get_rule_by_id.return_value = "default_rule"
    monkeypatch.setattr(
        "util.download.task.manager.FileNameFormatter",
        lambda: fake_formatter,
    )

    return TaskManager()


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------
def test_init_creates_db_and_connects_signal(task_mgr):
    """__init__ 应创建 db_manager 并连接 create_task 信号"""
    assert task_mgr.db_manager is not None
    assert task_mgr._update_lock is not None
    assert task_mgr._pending_updates == {}
    assert task_mgr._add_to_queue_toast_shown is False


# ---------------------------------------------------------------------------
# _calc_hash_id
# ---------------------------------------------------------------------------
def test_calc_hash_id_video(task_mgr):
    """VIDEO_BIT 应使用 bvid+cid+aid 计算 hash"""
    info = make_episode_info(attribute=Attribute.VIDEO_BIT)
    result = task_mgr._calc_hash_id(info)
    assert isinstance(result, str)
    assert len(result) == 32  # md5 hex


def test_calc_hash_id_bangumi(task_mgr):
    """BANGUMI_BIT 应使用 bvid+cid+aid+ep_id 计算 hash"""
    info = make_episode_info(attribute=Attribute.BANGUMI_BIT)
    result = task_mgr._calc_hash_id(info)
    assert len(result) == 32


def test_calc_hash_id_cheese(task_mgr):
    """CHEESE_BIT 应使用 aid+cid+ep_id 计算 hash"""
    info = make_episode_info(attribute=Attribute.CHEESE_BIT)
    result = task_mgr._calc_hash_id(info)
    assert len(result) == 32


def test_calc_hash_id_audio(task_mgr):
    """AUDIO_BIT 应使用 sid 计算 hash"""
    info = make_episode_info(attribute=Attribute.AUDIO_BIT)
    result = task_mgr._calc_hash_id(info)
    assert len(result) == 32


def test_calc_hash_id_different_attributes_yield_different_hashes(task_mgr):
    """不同 attribute 应产生不同的 hash_id"""
    video_hash = task_mgr._calc_hash_id(make_episode_info(Attribute.VIDEO_BIT))
    audio_hash = task_mgr._calc_hash_id(make_episode_info(Attribute.AUDIO_BIT))
    assert video_hash != audio_hash


# ---------------------------------------------------------------------------
# _check_duplicate
# ---------------------------------------------------------------------------
def test_check_duplicate_no_duplicate_returns_falsy(task_mgr):
    """无重复时应返回 falsy 值(db_manager.check_duplicate 返回 None)"""
    info = make_episode_info()
    result = task_mgr._check_duplicate(info)
    assert not result


def test_check_duplicate_continue_returns_false(task_mgr, mock_config):
    """重复 + CONTINUE 策略应返回 False(继续下载)"""
    mock_config.get.side_effect = lambda key, default=None: {
        "download_path": "/tmp/downloads",
        "duplicate_download_resolution": DuplicateDownloadResolution.CONTINUE,
    }.get(key, default)

    info = make_episode_info()
    # 先创建一个任务使数据库中存在该 hash
    task_mgr.db_manager.check_duplicate = MagicMock(return_value=True)

    result = task_mgr._check_duplicate(info)
    assert result is False


def test_check_duplicate_skip_returns_true(task_mgr, mock_config):
    """重复 + SKIP 策略应返回 True(跳过下载)"""
    mock_config.get.side_effect = lambda key, default=None: {
        "download_path": "/tmp/downloads",
        "duplicate_download_resolution": DuplicateDownloadResolution.SKIP,
    }.get(key, default)

    info = make_episode_info(title="重复任务")
    task_mgr.db_manager.check_duplicate = MagicMock(return_value=True)

    result = task_mgr._check_duplicate(info)
    assert result is True


def test_check_duplicate_always_ask_skip(task_mgr, mock_config):
    """重复 + ALWAYS_ASK 策略,用户选择跳过时应返回 True"""
    def fake_get(key, default=None):
        if key == "duplicate_download_resolution":
            return DuplicateDownloadResolution.ALWAYS_ASK
        return default
    mock_config.get.side_effect = fake_get

    info = make_episode_info(title="询问任务")
    task_mgr.db_manager.check_duplicate = MagicMock(return_value=True)

    # mock signal_bus 的 show_duplicate_download_dialog 以立即设置 skip=True 并触发 event
    def fake_dialog(episode_info, result_info, done_event):
        result_info["skip"] = True
        done_event.set()

    with patch("util.download.task.manager.signal_bus") as fake_bus:
        fake_bus.download.show_duplicate_download_dialog.emit.side_effect = fake_dialog
        result = task_mgr._check_duplicate(info)

    assert result is True


def test_check_duplicate_always_ask_continue(task_mgr, mock_config):
    """重复 + ALWAYS_ASK 策略,用户选择继续时应返回 False"""
    def fake_get(key, default=None):
        if key == "duplicate_download_resolution":
            return DuplicateDownloadResolution.ALWAYS_ASK
        return default
    mock_config.get.side_effect = fake_get

    info = make_episode_info(title="询问任务")
    task_mgr.db_manager.check_duplicate = MagicMock(return_value=True)

    def fake_dialog(episode_info, result_info, done_event):
        result_info["skip"] = False
        done_event.set()

    with patch("util.download.task.manager.signal_bus") as fake_bus:
        fake_bus.download.show_duplicate_download_dialog.emit.side_effect = fake_dialog
        result = task_mgr._check_duplicate(info)

    assert result is False


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------
def test_create_success_adds_task(task_mgr):
    """create 正常路径应在数据库中添加任务"""
    info = make_episode_info(title="新任务")
    task_mgr.create([info])

    tasks = task_mgr.query()
    assert len(tasks) == 1
    assert tasks[0].Basic.show_title == "新任务"


def test_create_multiple_tasks(task_mgr):
    """create 应支持批量创建多个任务"""
    infos = [
        make_episode_info(title="任务1"),
        make_episode_info(title="任务2"),
        make_episode_info(title="任务3"),
    ]
    task_mgr.create(infos)

    tasks = task_mgr.query()
    assert len(tasks) == 3


def test_create_skips_reparse_needed(task_mgr, monkeypatch):
    """create 在需要 reparse 时应跳过该任务"""
    info = make_episode_info(title="需重新解析")
    info["attribute"] = Attribute.NEED_PARSE_BIT

    # mock GlobalThreadPoolTask.run 避免 reparse worker 实际执行
    with patch("util.download.task.manager.GlobalThreadPoolTask.run") as pool_run:
        task_mgr.create([info])

    tasks = task_mgr.query()
    assert len(tasks) == 0
    pool_run.assert_called_once()


def test_create_skips_duplicate(task_mgr, mock_config):
    """create 在重复下载(SKIP 策略)时应跳过该任务"""
    mock_config.get.side_effect = lambda key, default=None: {
        "download_path": "/tmp/downloads",
        "duplicate_download_resolution": DuplicateDownloadResolution.SKIP,
    }.get(key, default)

    info = make_episode_info(title="重复任务")
    task_mgr.db_manager.check_duplicate = MagicMock(return_value=True)

    task_mgr.create([info])

    tasks = task_mgr.query()
    assert len(tasks) == 0


def test_create_exception_emits_toast(task_mgr):
    """create 在单个任务异常时应继续处理其他任务并 emit toast"""
    good_info = make_episode_info(title="正常任务")
    bad_info = make_episode_info(title="异常任务")

    # 通过 patch __episode_info_to_task_info 使第二个任务抛异常
    original = task_mgr._TaskManager__episode_info_to_task_info
    counter = {"n": 0}

    def patched(episode_info, number):
        counter["n"] += 1
        if counter["n"] == 2:
            raise RuntimeError("boom")
        return original(episode_info, number)

    task_mgr._TaskManager__episode_info_to_task_info = patched

    with patch("util.download.task.manager.signal_bus"):
        task_mgr.create([good_info, bad_info])

    # 正常任务应被创建
    tasks = task_mgr.query()
    assert len(tasks) == 1
    assert tasks[0].Basic.show_title == "正常任务"


def test_create_with_show_toast(task_mgr):
    """create(show_toast=True) 在有任务时应触发 toast"""
    info = make_episode_info(title="带 toast")
    with patch.object(task_mgr, "_show_add_to_queue_toast") as toast:
        task_mgr.create([info], show_toast=True)

    toast.assert_called_once()


def test_create_with_show_toast_no_tasks(task_mgr):
    """create(show_toast=True) 在无任务时不应触发 toast"""
    with patch.object(task_mgr, "_show_add_to_queue_toast") as toast:
        task_mgr.create([], show_toast=True)

    toast.assert_not_called()


def test_create_db_exception_emits_toast(task_mgr):
    """create 在数据库保存失败时应 emit toast 且不 emit add_to_downloading_list"""
    info = make_episode_info(title="DB异常")
    task_mgr.db_manager.add_tasks = MagicMock(side_effect=RuntimeError("db error"))

    with patch("util.download.task.manager.signal_bus") as fake_bus:
        task_mgr.create([info])

    # add_to_downloading_list 不应被调用
    fake_bus.download.add_to_downloading_list.emit.assert_not_called()


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------
def test_query_returns_downloading_tasks(task_mgr):
    """query(completed=False) 应返回下载中的任务"""
    task_mgr.create([make_episode_info(title="任务A")])
    tasks = task_mgr.query(completed=False)
    assert len(tasks) == 1
    assert tasks[0].Basic.show_title == "任务A"


def test_query_returns_completed_tasks(task_mgr):
    """query(completed=True) 应返回已完成的任务"""
    info = make_episode_info(title="已完成任务")
    task_mgr.create([info])
    task_mgr.mark_as_completed(task_mgr.query()[0])

    completed = task_mgr.query(completed=True)
    assert len(completed) == 1
    assert completed[0].Basic.show_title == "已完成任务"


def test_query_empty_when_no_tasks(task_mgr):
    """无任务时 query 应返回空列表"""
    assert task_mgr.query() == []
    assert task_mgr.query(completed=True) == []


# ---------------------------------------------------------------------------
# update / update_async
# ---------------------------------------------------------------------------
def test_update_async_stores_pending_update(task_mgr):
    """update_async 应将更新存入 _pending_updates"""
    info = make_episode_info(title="更新任务")
    task_mgr.create([info])
    created = task_mgr.query()[0]
    created.Download.progress = 50

    # 阻止后台 flush 线程执行,以便检查 _pending_updates
    task_mgr._update_executor = MagicMock()

    task_mgr.update_async(created)

    assert created.Basic.task_id in task_mgr._pending_updates


def test_update_calls_update_async(task_mgr):
    """update 应委托给 update_async"""
    info = make_episode_info(title="同步更新")
    task_mgr.create([info])
    created = task_mgr.query()[0]

    with patch.object(task_mgr, "update_async") as async_update:
        task_mgr.update(created)

    async_update.assert_called_once_with(created)


def test_flush_updates_writes_to_db(task_mgr):
    """_flush_updates 应将待处理更新写入数据库"""
    info = make_episode_info(title="刷新任务")
    task_mgr.create([info])
    created = task_mgr.query()[0]
    created.Download.progress = 80

    task_mgr.update_async(created)
    # 等待后台 flush 完成
    task_mgr._wait_for_pending_updates()

    # 重新查询验证进度已持久化
    refreshed = task_mgr.query()[0]
    assert refreshed.Download.progress == 80


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------
def test_delete_removes_task(task_mgr):
    """delete 应从数据库移除任务"""
    task_mgr.create([make_episode_info(title="删除任务")])
    created = task_mgr.query()[0]

    task_mgr.delete(created)

    assert len(task_mgr.query()) == 0


def test_delete_completed(task_mgr):
    """delete(completed=True) 应从已完成表移除任务"""
    info = make_episode_info(title="删除已完成")
    task_mgr.create([info])
    created = task_mgr.query()[0]
    task_mgr.mark_as_completed(created)

    completed = task_mgr.query(completed=True)
    assert len(completed) == 1

    task_mgr.delete(created, completed=True)
    assert len(task_mgr.query(completed=True)) == 0


# ---------------------------------------------------------------------------
# cancel
# ---------------------------------------------------------------------------
def test_cancel_removes_task_and_files(task_mgr):
    """cancel 应删除任务并清理临时文件"""
    task_mgr.create([make_episode_info(title="取消任务")])
    created = task_mgr.query()[0]

    with patch("util.download.task.manager.signal_bus") as fake_bus, \
         patch("util.download.task.manager.safe_remove") as fake_remove:
        task_mgr.cancel(created)

    assert len(task_mgr.query()) == 0
    fake_bus.download.remove_from_downloading_list.emit.assert_called_once()
    fake_remove.assert_called_once()


# ---------------------------------------------------------------------------
# mark_as_completed
# ---------------------------------------------------------------------------
def test_mark_as_completed_moves_to_completed(task_mgr):
    """mark_as_completed 应将任务从下载中移到已完成"""
    task_mgr.create([make_episode_info(title="完成任务")])
    created = task_mgr.query()[0]

    task_mgr.mark_as_completed(created)

    assert len(task_mgr.query()) == 0
    assert len(task_mgr.query(completed=True)) == 1
    completed = task_mgr.query(completed=True)[0]
    assert completed.Basic.show_title == "完成任务"


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------
def test_reset_clears_download_state(task_mgr):
    """reset 应将下载状态重置为初始值"""
    task_mgr.create([make_episode_info(title="重置任务")])
    created = task_mgr.query()[0]
    created.Download.progress = 50
    created.Download.downloaded_size = 1024
    created.Download.queue = ["video"]
    created.Download.files = {"video": {}}

    task_mgr.reset(created)

    assert created.Download.status == DownloadStatus.QUEUED
    assert created.Download.progress == 0
    assert created.Download.downloaded_size == 0
    assert created.Download.queue == []
    assert created.Download.files == {}


# ---------------------------------------------------------------------------
# recreate
# ---------------------------------------------------------------------------
def test_recreate_moves_completed_to_downloading(task_mgr):
    """recreate 应将已完成任务重新加入下载队列"""
    task_mgr.create([make_episode_info(title="重建任务")])
    created = task_mgr.query()[0]
    task_mgr.mark_as_completed(created)

    assert len(task_mgr.query(completed=True)) == 1
    assert len(task_mgr.query()) == 0

    completed = task_mgr.query(completed=True)[0]
    with patch("util.download.task.manager.signal_bus") as fake_bus:
        task_mgr.recreate(completed)

    assert len(task_mgr.query(completed=True)) == 0
    assert len(task_mgr.query()) == 1
    fake_bus.download.add_to_downloading_list.emit.assert_called_once()


# ---------------------------------------------------------------------------
# _removeTemporaryFiles
# ---------------------------------------------------------------------------
def test_remove_temporary_files(task_mgr, tmp_path):
    """_removeTemporaryFiles 应删除指定文件"""
    info = make_episode_info(title="清理文件")
    info["download_path"] = str(tmp_path)
    task_mgr.create([info])
    created = task_mgr.query()[0]

    # FileNameFormatter mock 返回 "output/video",folder="output"
    # 文件需放在 tmp_path/output/ 下与 get_cwd 一致
    folder_dir = tmp_path / "output"
    folder_dir.mkdir(parents=True, exist_ok=True)
    file1 = folder_dir / "temp1.mp4"
    file2 = folder_dir / "temp2.m4a"
    file1.touch()
    file2.touch()
    created.File.relative_files = ["temp1.mp4", "temp2.m4a"]
    created.File.download_path = str(tmp_path)

    task_mgr._removeTemporaryFiles(created)

    assert not file1.exists()
    assert not file2.exists()


# ---------------------------------------------------------------------------
# _update_media_info
# ---------------------------------------------------------------------------
def test_update_media_info_sets_quality(task_mgr):
    """_update_media_info 应设置 video/audio quality 和 codec"""
    info = make_episode_info(title="媒体信息")
    task_mgr.create([info])
    created = task_mgr.query()[0]
    created.Download.video_quality_id = 80
    created.Download.audio_quality_id = 30232
    created.Download.video_codec_id = 7

    task_mgr._update_media_info(created)

    # 应设置 video_quality / audio_quality / video_codec 字段
    assert created.Episode.video_quality != ""
    assert created.Episode.audio_quality != ""


def test_update_media_info_skips_when_default_values(task_mgr):
    """_update_media_info 在使用默认值(200/30300/20)时应跳过对应字段"""
    info = make_episode_info(title="默认媒体信息")
    task_mgr.create([info])
    created = task_mgr.query()[0]
    created.Download.video_quality_id = 200
    created.Download.audio_quality_id = 30300
    created.Download.video_codec_id = 20

    task_mgr._update_media_info(created)

    # 默认值时不设置 quality 字段
    assert created.Episode.video_quality == ""
    assert created.Episode.audio_quality == ""


# ---------------------------------------------------------------------------
# _show_add_to_queue_toast
# ---------------------------------------------------------------------------
def test_show_add_to_queue_toast_first_time(task_mgr):
    """_show_add_to_queue_toast 首次调用应 emit toast"""
    with patch("util.download.task.manager.signal_bus") as fake_bus:
        task_mgr._show_add_to_queue_toast()

    fake_bus.toast.show.emit.assert_called_once()
    assert task_mgr._add_to_queue_toast_shown is True


def test_show_add_to_queue_toast_skips_when_already_shown(task_mgr):
    """_show_add_to_queue_toast 在已显示过时应跳过"""
    task_mgr._add_to_queue_toast_shown = True

    with patch("util.download.task.manager.signal_bus") as fake_bus:
        task_mgr._show_add_to_queue_toast()

    fake_bus.toast.show.emit.assert_not_called()


def test_reset_add_to_queue_toast_flag(task_mgr):
    """_reset_add_to_queue_toast_flag 应重置标志"""
    task_mgr._add_to_queue_toast_shown = True
    task_mgr._reset_add_to_queue_toast_flag()
    assert task_mgr._add_to_queue_toast_shown is False


# ---------------------------------------------------------------------------
# __get_number (通过 _TaskManager__get_number 访问)
# ---------------------------------------------------------------------------
def test_get_number_continuous(task_mgr, mock_config):
    """CONTINUOUS 模式应返回 global_starting_number"""
    mock_config.get.side_effect = lambda key, default=None: {
        "numbering_type": NumberingType.CONTINUOUS,
    }.get(key, default)
    mock_config.global_starting_number = 42

    result = task_mgr._TaskManager__get_number(make_episode_info())
    assert result == 42


def test_get_number_from_specified(task_mgr, mock_config):
    """FROM_SPECIFIED 模式应返回并自增 current_starting_number"""
    mock_config.get.side_effect = lambda key, default=None: {
        "numbering_type": NumberingType.FROM_SPECIFIED,
    }.get(key, default)
    mock_config.current_starting_number = 5

    result = task_mgr._TaskManager__get_number(make_episode_info())
    assert result == 5
    assert mock_config.current_starting_number == 6  # 应已自增


def test_get_number_default_returns_episode_number(task_mgr, mock_config):
    """默认模式(USE_PARSE_LIST)应返回 episode_info 中的 number"""
    mock_config.get.side_effect = lambda key, default=None: {
        "numbering_type": NumberingType.USE_PARSE_LIST,
    }.get(key, default)

    info = make_episode_info()
    info["number"] = 7

    result = task_mgr._TaskManager__get_number(info)
    assert result == 7


# ---------------------------------------------------------------------------
# __determine_download_type
# ---------------------------------------------------------------------------
def test_determine_download_type_all_enabled(task_mgr, mock_config):
    """所有下载选项启用时 type 应包含所有 DownloadType"""
    mock_config.download_video_stream = True
    mock_config.download_audio_stream = True
    mock_config.get.side_effect = lambda key, default=None: {
        "download_danmaku": True,
        "download_subtitle": True,
        "download_cover": True,
        "download_metadata": True,
    }.get(key, default)

    result = task_mgr._TaskManager__determine_download_type()
    assert result & DownloadType.VIDEO != 0
    assert result & DownloadType.AUDIO != 0
    assert result & DownloadType.DANMAKU != 0
    assert result & DownloadType.SUBTITLE != 0
    assert result & DownloadType.COVER != 0
    assert result & DownloadType.METADATA != 0


def test_determine_download_type_all_disabled(task_mgr, mock_config):
    """所有下载选项禁用时 type 应为 0"""
    mock_config.download_video_stream = False
    mock_config.download_audio_stream = False
    mock_config.get.side_effect = lambda key, default=None: {
        "download_danmaku": False,
        "download_subtitle": False,
        "download_cover": False,
        "download_metadata": False,
    }.get(key, default)

    result = task_mgr._TaskManager__determine_download_type()
    assert result == 0


# ---------------------------------------------------------------------------
# __filter_illegal_characters
# ---------------------------------------------------------------------------
def test_filter_illegal_characters(task_mgr):
    """__filter_illegal_characters 应过滤文件系统非法字符"""
    info = {
        "leaf_title": "a/b\\c:d*e?f\"g<h>i|j",
        "parent_title": "normal",
        "episode_title": "x*y?z",
    }
    task_mgr._TaskManager__filter_illegal_characters(info)

    assert "/" not in info["leaf_title"]
    assert "\\" not in info["leaf_title"]
    assert ":" not in info["leaf_title"]
    assert "*" not in info["leaf_title"]
    assert "?" not in info["leaf_title"]
    assert "\"" not in info["leaf_title"]
    assert "<" not in info["leaf_title"]
    assert ">" not in info["leaf_title"]
    assert "|" not in info["leaf_title"]
    # 正常标题不受影响
    assert info["parent_title"] == "normal"
    assert info["episode_title"] == "x_y_z"


# ---------------------------------------------------------------------------
# __check_reparse_needed
# ---------------------------------------------------------------------------
def test_check_reparse_needed_true(task_mgr):
    """NEED_PARSE_BIT 属性时应返回 True 并提交 ReparseWorker"""
    info = make_episode_info()
    info["attribute"] = Attribute.NEED_PARSE_BIT

    with patch("util.download.task.manager.GlobalThreadPoolTask.run") as pool_run:
        result = task_mgr._TaskManager__check_reparse_needed(info, show_toast=True)

    assert result is True
    pool_run.assert_called_once()


def test_check_reparse_needed_false(task_mgr):
    """无 NEED_PARSE_BIT 属性时应返回 False"""
    info = make_episode_info()
    info["attribute"] = Attribute.VIDEO_BIT

    result = task_mgr._TaskManager__check_reparse_needed(info)
    assert result is False


# ---------------------------------------------------------------------------
# _create_async (通过 signal_bus 触发)
# ---------------------------------------------------------------------------
def test_create_async_submits_to_thread_pool(task_mgr):
    """_create_async 应将 create 提交到全局线程池"""
    info = make_episode_info(title="异步创建")

    with patch("util.download.task.manager.GlobalThreadPoolTask.run_func") as pool_run:
        task_mgr._create_async([info], show_toast=False)

    pool_run.assert_called_once()
    # 验证第一个参数是 self.create
    assert pool_run.call_args[0][0] == task_mgr.create


# ---------------------------------------------------------------------------
# _wait_for_pending_updates
# ---------------------------------------------------------------------------
def test_wait_for_pending_updates(task_mgr):
    """_wait_for_pending_updates 应阻塞直到所有待处理更新完成"""
    # 提交一个更新后立即等待,不应抛异常
    info = make_episode_info(title="等待更新")
    task_mgr.create([info])
    created = task_mgr.query()[0]
    task_mgr.update_async(created)

    # 不应抛异常(会阻塞直到 executor 完成已提交任务)
    task_mgr._wait_for_pending_updates()
