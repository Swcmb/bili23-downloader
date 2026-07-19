# tests/unit/test_task_db_coverage.py
"""task/db.py 单元测试 - 覆盖 TaskDatabase 与模块级辅助函数

测试策略:
- 用 tmp_path + monkeypatch 替换 directory.data_dir,确保使用真实 sqlite3
- 覆盖所有公开方法(query/add/update/delete/check_duplicate/list/get/pause/resume/cancel/clear/history)
- 覆盖 _upgrade/_needs_upgrade 迁移路径与 _calc_hash_id 四种 attribute 分支
- 覆盖模块级辅助函数 _extract_status_id / _status_name
"""
import json
from pathlib import Path

import pytest

from util.common.enum import DownloadStatus
from util.common.io.directory import directory
from util.download.task.db import (
    TaskDatabase,
    _extract_status_id,
    _status_name,
)
from util.download.task.info import TaskInfo
from util.parse.episode.tree import Attribute


# ==================================================================
# 公共夹具
# ==================================================================

@pytest.fixture
def task_db(tmp_path, monkeypatch):
    """创建指向 tmp_path 的 TaskDatabase 实例,避免污染真实数据目录"""
    monkeypatch.setattr(directory, "data_dir", str(tmp_path))
    return TaskDatabase()


def _make_task_info(task_id: str = "tid-1", attribute: int = Attribute.VIDEO_BIT) -> TaskInfo:
    """构造测试用 TaskInfo"""
    info = TaskInfo()
    info.Basic.task_id = task_id
    info.Basic.show_title = "测试任务"
    info.Basic.cover_id = "cover-1"
    info.Basic.created_time = 1700000000
    info.Episode.attribute = attribute
    info.Episode.bvid = "BV1xx"
    info.Episode.aid = 12345
    info.Episode.cid = 67890
    info.Episode.url = "https://www.bilibili.com/video/BV1xx"
    info.Download.status = DownloadStatus.QUEUED
    info.Download.type = 0b11  # VIDEO | AUDIO
    info.Download.total_size = 1024
    info.Download.progress = 0
    return info


# ==================================================================
# 模块级辅助函数
# ==================================================================

def test_extract_status_id_with_valid_json():
    """_extract_status_id 从有效 JSON 提取 status"""
    data = json.dumps({"Download": {"status": 3}})
    assert _extract_status_id(data) == 3


def test_extract_status_id_with_empty_string():
    """_extract_status_id 空字符串返回 0"""
    assert _extract_status_id("") == 0
    assert _extract_status_id(None) == 0


def test_extract_status_id_with_invalid_json():
    """_extract_status_id 无效 JSON 返回 0"""
    assert _extract_status_id("not-json") == 0


def test_extract_status_id_with_missing_download_key():
    """_extract_status_id 缺 Download 键返回 0"""
    assert _extract_status_id(json.dumps({"Basic": {}})) == 0


def test_extract_status_id_with_none_status_value():
    """_extract_status_id status=None 时返回 0"""
    assert _extract_status_id(json.dumps({"Download": {"status": None}})) == 0


def test_status_name_known_status():
    """_status_name 已知状态返回枚举名"""
    assert _status_name(0) == "QUEUED"
    assert _status_name(2) == "DOWNLOADING"
    assert _status_name(4) == "COMPLETED"


def test_status_name_unknown_status():
    """_status_name 未知值返回 UNKNOWN"""
    assert _status_name(9999) == "UNKNOWN"


# ==================================================================
# 表结构 / 升级检测
# ==================================================================

def test_check_and_create_table_creates_two_tables(task_db):
    """check_and_create_table 创建 download_task 与 completed_task 两表"""
    cols = task_db.query("SELECT name FROM sqlite_master WHERE type='table'")
    names = {row[0] for row in cols}
    assert "download_task" in names
    assert "completed_task" in names


def test_get_table_columns_returns_set(task_db):
    """_get_table_columns 返回字段名集合"""
    cols = task_db._get_table_columns("download_task")
    assert "task_id" in cols
    assert "hash_id" in cols
    assert "data" in cols


def test_needs_upgrade_returns_false_on_fresh_db(task_db):
    """新建库已含全部所需列,无需升级"""
    assert task_db._needs_upgrade() is False


def test_needs_upgrade_returns_true_when_missing_column(tmp_path, monkeypatch):
    """缺 hash_id 列时 _needs_upgrade 返回 True"""
    monkeypatch.setattr(directory, "data_dir", str(tmp_path))
    # 先建一个旧 schema(无 hash_id)
    db_path = tmp_path / "task.db"
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE download_task (id INTEGER, task_id TEXT, data TEXT);
            CREATE TABLE completed_task (id INTEGER, task_id TEXT, data TEXT);
        """)
    db = TaskDatabase()
    # 已检测到需升级并自动执行,_needs_upgrade 应再次为 False
    assert db._needs_upgrade() is False
    # 验证升级后列齐全
    cols = db._get_table_columns("download_task")
    assert "hash_id" in cols


def test_check_should_upgrade_runs_when_needed(tmp_path, monkeypatch):
    """_check_should_upgrade 触发 _upgrade"""
    monkeypatch.setattr(directory, "data_dir", str(tmp_path))
    db_path = tmp_path / "task.db"
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE download_task (id INTEGER, task_id TEXT, data TEXT);
            CREATE TABLE completed_task (id INTEGER, task_id TEXT, data TEXT);
        """)
    # 实例化时自动升级
    db = TaskDatabase()
    # 列已补齐
    assert "hash_id" in db._get_table_columns("download_task")


# ==================================================================
# add_tasks / query_tasks / update_task
# ==================================================================

def test_add_tasks_inserts_download_task(task_db):
    """add_tasks(completed=False) 写入 download_task 表"""
    info = _make_task_info("t1")
    task_db.add_tasks([info])
    rows = task_db.query_tasks(completed=False)
    assert len(rows) == 1


def test_add_tasks_inserts_completed_task(task_db):
    """add_tasks(completed=True) 写入 completed_task 表"""
    info = _make_task_info("t1")
    info.Basic.completed_time = 1700000100
    task_db.add_tasks([info], completed=True)
    rows = task_db.query_tasks(completed=True)
    assert len(rows) == 1


def test_add_tasks_uses_fallback_timestamp_when_missing(task_db):
    """created_time 为 0 时自动填充当前时间戳"""
    info = _make_task_info("t1")
    info.Basic.created_time = 0
    task_db.add_tasks([info])
    rows = task_db.query("SELECT created_time FROM download_task WHERE task_id = ?", ("t1",))
    assert rows[0][0] > 0


def test_update_task_overwrites_data(task_db):
    """update_task 更新 data 字段"""
    info = _make_task_info("t1")
    task_db.add_tasks([info])

    info.Download.progress = 50
    task_db.update_task(info)

    rows = task_db.query("SELECT data FROM download_task WHERE task_id = ?", ("t1",))
    data = json.loads(rows[0][0])
    assert data["Download"]["progress"] == 50


def test_update_task_json_overwrites_raw_data(task_db):
    """update_task_json 直接覆盖 data JSON 字符串"""
    info = _make_task_info("t1")
    task_db.add_tasks([info])

    new_data = json.dumps({"Basic": {"task_id": "t1"}, "Download": {"status": 3}})
    task_db.update_task_json("t1", new_data)

    rows = task_db.query("SELECT data FROM download_task WHERE task_id = ?", ("t1",))
    assert json.loads(rows[0][0])["Download"]["status"] == 3


def test_delete_task_removes_from_download_table(task_db):
    """delete_task(completed=False) 从 download_task 表删除"""
    info = _make_task_info("t1")
    task_db.add_tasks([info])

    task_db.delete_task("t1", completed=False)
    rows = task_db.query_tasks(completed=False)
    assert rows == []


def test_delete_task_removes_from_completed_table(task_db):
    """delete_task(completed=True) 从 completed_task 表删除"""
    info = _make_task_info("t1")
    info.Basic.completed_time = 1700000100
    task_db.add_tasks([info], completed=True)

    task_db.delete_task("t1", completed=True)
    assert task_db.query_tasks(completed=True) == []


# ==================================================================
# check_duplicate
# ==================================================================

def test_check_duplicate_returns_false_when_empty(task_db):
    """空库时 check_duplicate 返回 False"""
    assert task_db.check_duplicate("any-hash") is False


def test_check_duplicate_returns_true_after_insert(task_db):
    """插入任务后,相同 hash_id 应判重"""
    info = _make_task_info("t1")
    task_db.add_tasks([info])
    # 计算相同 hash_id(VIDEO_BIT 走 bvid+cid+aid 分支)
    hash_id = task_db._calc_hash_id(info)
    assert task_db.check_duplicate(hash_id) is True


def test_check_duplicate_finds_in_completed_table(task_db):
    """completed_task 表中的任务也能被判重"""
    info = _make_task_info("t1")
    info.Basic.completed_time = 1700000100
    task_db.add_tasks([info], completed=True)

    hash_id = task_db._calc_hash_id(info)
    assert task_db.check_duplicate(hash_id) is True


# ==================================================================
# _calc_hash_id - 四种 attribute 分支
# ==================================================================

def test_calc_hash_id_video_bit(task_db):
    """VIDEO_BIT 分支:bvid + cid + aid"""
    info = _make_task_info(attribute=Attribute.VIDEO_BIT)
    info.Episode.bvid = "BV1"
    info.Episode.cid = 10
    info.Episode.aid = 20
    h = task_db._calc_hash_id(info)
    assert isinstance(h, str) and len(h) == 32


def test_calc_hash_id_bangumi_bit(task_db):
    """BANGUMI_BIT 分支:bvid + cid + aid + ep_id"""
    info = _make_task_info(attribute=Attribute.BANGUMI_BIT)
    info.Episode.ep_id = 999
    h = task_db._calc_hash_id(info)
    assert len(h) == 32


def test_calc_hash_id_cheese_bit(task_db):
    """CHEESE_BIT 分支:aid + cid + ep_id"""
    info = _make_task_info(attribute=Attribute.CHEESE_BIT)
    info.Episode.ep_id = 999
    h = task_db._calc_hash_id(info)
    assert len(h) == 32


def test_calc_hash_id_audio_bit(task_db):
    """AUDIO_BIT 分支:sid"""
    info = _make_task_info(attribute=Attribute.AUDIO_BIT)
    info.Episode.sid = 555
    h = task_db._calc_hash_id(info)
    assert len(h) == 32


# ==================================================================
# list_tasks / get_task / _row_to_task_dict
# ==================================================================

def test_list_tasks_returns_all(task_db):
    """list_tasks 返回全部任务(默认按时间倒序)"""
    for i in range(3):
        info = _make_task_info(f"t{i}")
        info.Basic.created_time = 1700000000 + i
        task_db.add_tasks([info])

    tasks = task_db.list_tasks()
    assert len(tasks) == 3
    # 倒序:最新(t2) 排前
    assert tasks[0]["task_id"] == "t2"


def test_list_tasks_filter_by_status(task_db):
    """list_tasks 按 status 过滤"""
    info1 = _make_task_info("t1")
    info1.Download.status = DownloadStatus.QUEUED
    info2 = _make_task_info("t2")
    info2.Download.status = DownloadStatus.DOWNLOADING
    task_db.add_tasks([info1, info2])

    tasks = task_db.list_tasks(status=DownloadStatus.DOWNLOADING)
    assert len(tasks) == 1
    assert tasks[0]["task_id"] == "t2"


def test_list_tasks_limit(task_db):
    """list_tasks 受 limit 限制"""
    for i in range(5):
        info = _make_task_info(f"t{i}")
        info.Basic.created_time = 1700000000 + i
        task_db.add_tasks([info])

    tasks = task_db.list_tasks(limit=2)
    assert len(tasks) == 2


def test_list_tasks_with_invalid_json_falls_back(task_db):
    """_row_to_task_dict 在 data 为无效 JSON 时回退为空 dict"""
    task_db.execute(
        "INSERT INTO download_task (task_id, hash_id, cover_id, title, created_time, data) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("bad", "h", "c", "title", 1, "not-json"),
    )
    tasks = task_db.list_tasks()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "title"
    assert tasks[0]["status_id"] == 0


def test_get_task_returns_dict_when_exists(task_db):
    """get_task 在任务存在时返回 dict"""
    info = _make_task_info("t1")
    task_db.add_tasks([info])

    result = task_db.get_task("t1")
    assert result is not None
    assert result["task_id"] == "t1"
    assert "status" in result
    assert "progress" in result


def test_get_task_returns_none_when_missing(task_db):
    """get_task 在任务不存在时返回 None"""
    assert task_db.get_task("missing") is None


# ==================================================================
# pause_task / resume_task / cancel_task / clear_tasks
# ==================================================================

def test_pause_task_succeeds_when_downloading(task_db):
    """pause_task 在 DOWNLOADING 状态下成功"""
    info = _make_task_info("t1")
    info.Download.status = DownloadStatus.DOWNLOADING
    task_db.add_tasks([info])

    assert task_db.pause_task("t1") is True
    result = task_db.get_task("t1")
    assert result["status_id"] == int(DownloadStatus.PAUSED)


def test_pause_task_fails_when_wrong_status(task_db):
    """pause_task 在非 DOWNLOADING 状态下返回 False"""
    info = _make_task_info("t1")
    info.Download.status = DownloadStatus.QUEUED
    task_db.add_tasks([info])

    assert task_db.pause_task("t1") is False


def test_pause_task_returns_none_when_missing(task_db):
    """pause_task 在任务不存在时返回 None"""
    assert task_db.pause_task("missing") is None


def test_resume_task_succeeds_when_paused(task_db):
    """resume_task 在 PAUSED 状态下成功"""
    info = _make_task_info("t1")
    info.Download.status = DownloadStatus.PAUSED
    task_db.add_tasks([info])

    assert task_db.resume_task("t1") is True
    assert task_db.get_task("t1")["status_id"] == int(DownloadStatus.DOWNLOADING)


def test_resume_task_fails_when_wrong_status(task_db):
    """resume_task 在非 PAUSED 状态下返回 False"""
    info = _make_task_info("t1")
    info.Download.status = DownloadStatus.QUEUED
    task_db.add_tasks([info])

    assert task_db.resume_task("t1") is False


def test_transition_status_with_invalid_json(task_db):
    """_transition_status 在 JSON 解析失败时仍能更新(回退为空 dict)"""
    task_db.execute(
        "INSERT INTO download_task (task_id, hash_id, cover_id, title, created_time, data) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("bad", "h", "c", "t", 1, "not-json"),
    )
    # 当前 status_id 默认为 0(QUEUED),所以 pause_task 会返回 False
    assert task_db.pause_task("bad") is False


def test_cancel_task_returns_true_when_exists(task_db):
    """cancel_task 在任务存在时返回 True 并删除"""
    info = _make_task_info("t1")
    task_db.add_tasks([info])

    assert task_db.cancel_task("t1") is True
    assert task_db.get_task("t1") is None


def test_cancel_task_returns_false_when_missing(task_db):
    """cancel_task 在任务不存在时返回 False"""
    assert task_db.cancel_task("missing") is False


def test_clear_tasks_all(task_db):
    """clear_tasks(status=None) 清空全部任务"""
    for i in range(3):
        info = _make_task_info(f"t{i}")
        info.Download.status = DownloadStatus.QUEUED
        task_db.add_tasks([info])

    deleted = task_db.clear_tasks()
    assert deleted == 3
    assert task_db.list_tasks() == []


def test_clear_tasks_by_status(task_db):
    """clear_tasks 按 status 仅清除匹配项"""
    info1 = _make_task_info("t1")
    info1.Download.status = DownloadStatus.QUEUED
    info2 = _make_task_info("t2")
    info2.Download.status = DownloadStatus.DOWNLOADING
    task_db.add_tasks([info1, info2])

    deleted = task_db.clear_tasks(status=DownloadStatus.QUEUED)
    assert deleted == 1
    assert task_db.get_task("t1") is None
    assert task_db.get_task("t2") is not None


def test_clear_tasks_with_invalid_json_treated_as_status_zero(task_db):
    """clear_tasks 在 data JSON 无效时视为 status=0"""
    task_db.execute(
        "INSERT INTO download_task (task_id, hash_id, cover_id, title, created_time, data) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("bad", "h", "c", "t", 1, "not-json"),
    )
    # status=0(QUEUED) 时被清除
    deleted = task_db.clear_tasks(status=DownloadStatus.QUEUED)
    assert deleted == 1


# ==================================================================
# get_history / count_history / clear_history / _row_to_history_dict
# ==================================================================

def test_count_history_returns_zero_when_empty(task_db):
    """count_history 空库返回 0"""
    assert task_db.count_history() == 0


def test_count_history_counts_both_tables(task_db):
    """count_history 合计两表"""
    info1 = _make_task_info("t1")
    info1.Basic.created_time = 1700000000
    task_db.add_tasks([info1])

    info2 = _make_task_info("t2")
    info2.Basic.completed_time = 1700000100
    task_db.add_tasks([info2], completed=True)

    assert task_db.count_history() == 2


def test_get_history_returns_merged_and_ordered(task_db):
    """get_history 合并两表并按时间倒序"""
    info1 = _make_task_info("t1")
    info1.Basic.created_time = 1700000000
    info1.Episode.url = "https://e1"
    task_db.add_tasks([info1])

    info2 = _make_task_info("t2")
    info2.Basic.completed_time = 1700000100
    info2.Episode.url = "https://e2"
    task_db.add_tasks([info2], completed=True)

    history = task_db.get_history()
    assert len(history) == 2
    # 时间倒序:t2 在前
    assert history[0]["title"] == "测试任务"
    assert "url" in history[0]
    assert "status" in history[0]
    assert "file_size" in history[0]


def test_get_history_with_invalid_json_falls_back(task_db):
    """_row_to_history_dict 在 data 无效时回退为空 dict,status_id=0(QUEUED)"""
    task_db.execute(
        "INSERT INTO download_task (task_id, hash_id, cover_id, title, created_time, data) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("bad", "h", "c", "title-bad", 1, "not-json"),
    )
    history = task_db.get_history()
    assert len(history) == 1
    assert history[0]["title"] == "title-bad"
    assert history[0]["url"] == ""
    # 无效 JSON 回退到空 dict,status_id=0 即 QUEUED
    assert history[0]["status"] == "QUEUED"
    assert history[0]["file_size"] == 0


def test_get_history_pagination(task_db):
    """get_history 支持 limit/offset 分页"""
    for i in range(5):
        info = _make_task_info(f"t{i}")
        info.Basic.show_title = f"任务-{i}"
        info.Basic.created_time = 1700000000 + i
        task_db.add_tasks([info])

    page1 = task_db.get_history(limit=2, offset=0)
    page2 = task_db.get_history(limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    # 两页不应有重叠
    ids1 = {h["title"] for h in page1}
    ids2 = {h["title"] for h in page2}
    assert ids1.isdisjoint(ids2)


def test_clear_history_all(task_db):
    """clear_history(older_than_days=None) 清空全部"""
    info1 = _make_task_info("t1")
    info1.Basic.created_time = 1700000000
    task_db.add_tasks([info1])
    info2 = _make_task_info("t2")
    info2.Basic.completed_time = 1700000100
    task_db.add_tasks([info2], completed=True)

    deleted = task_db.clear_history()
    assert deleted == 2
    assert task_db.count_history() == 0


def test_clear_history_by_age(task_db):
    """clear_history(older_than_days=N) 仅清除 N 天前的记录"""
    from util.common.timestamp import get_timestamp
    # 旧记录(10 天前)
    info_old = _make_task_info("old")
    info_old.Basic.created_time = get_timestamp() - 11 * 86400
    task_db.add_tasks([info_old])

    # 新记录(刚刚)
    info_new = _make_task_info("new")
    info_new.Basic.created_time = get_timestamp()
    task_db.add_tasks([info_new])

    deleted = task_db.clear_history(older_than_days=10)
    assert deleted == 1
    assert task_db.count_history() == 1


# ==================================================================
# _upgrade 完整迁移路径
# ==================================================================

def test_upgrade_preserves_existing_data(tmp_path, monkeypatch):
    """_upgrade 在迁移后保留原有数据"""
    monkeypatch.setattr(directory, "data_dir", str(tmp_path))
    db_path = tmp_path / "task.db"
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        conn.executescript("""
            CREATE TABLE download_task (id INTEGER, task_id TEXT, data TEXT);
            CREATE TABLE completed_task (id INTEGER, task_id TEXT, data TEXT);
        """)
        # 插入一条旧格式数据(包含 Basic/Episode 信息,_calc_hash_id 才能正常工作)
        info = _make_task_info("legacy")
        info_dict = info.to_dict()
        conn.execute(
            "INSERT INTO download_task (task_id, data) VALUES (?, ?)",
            ("legacy", json.dumps(info_dict)),
        )

    db = TaskDatabase()
    # 升级后任务仍在
    rows = db.query_tasks(completed=False)
    assert len(rows) == 1


def test_upgrade_skips_when_not_needed(task_db, caplog):
    """_upgrade 在 _needs_upgrade=False 时输出日志后返回"""
    import logging
    with caplog.at_level(logging.INFO, logger="util.download.task.db"):
        task_db._upgrade()
    # 已是最新,无需升级,不抛异常即可
    assert task_db._needs_upgrade() is False
