from ...common._json import json_loads, json_dumps
from ...common.io.directory import directory
from ...common.timestamp import get_timestamp
from ...common.database import Database
from ...common.enum import DownloadStatus
from ...parse.episode.tree import Attribute

from .info import TaskInfo

from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import logging
import sqlite3

logger = logging.getLogger(__name__)

class TaskDatabase(Database):
    def __init__(self):
        # 原 appdata_path 已随 T1 platformdirs 改造移除,
        # 改用 directory.data_dir(已为应用专属目录)
        self.path = Path(directory.data_dir) / "task.db"

        self.check_and_create_table()

        self._check_should_upgrade()

    def _check_should_upgrade(self):
        # 配置版本与任务数据库版本并不等价。始终检查实际表结构，
        # 避免配置升级成功但数据库迁移失败后永久跳过迁移。
        if self._needs_upgrade():
            logger.info("检测到旧版下载任务数据库，正在进行升级")
            self._upgrade()

    def _needs_upgrade(self):
        required_columns = {"task_id", "hash_id", "cover_id", "title", "data"}

        for table_name in ("download_task", "completed_task"):
            column_names = self._get_table_columns(table_name)

            if not required_columns.issubset(column_names):
                return True

        return False

    def _get_table_columns(self, table_name: str):
        result = self.query(f"PRAGMA table_info({table_name});")

        return {row[1] for row in result}

    def check_and_create_table(self):
        self.execute_script("""
            PRAGMA journal_mode = WAL;
            CREATE TABLE IF NOT EXISTS "download_task" (
                "id"	INTEGER UNIQUE,
                "task_id"	TEXT UNIQUE,
                "hash_id"   TEXT,
                "cover_id"	TEXT,
                "title"	TEXT,
                "created_time"	INTEGER,
                "data"	TEXT,
                PRIMARY KEY("id" AUTOINCREMENT)
            );
            CREATE TABLE IF NOT EXISTS "completed_task" (
                "id"	INTEGER UNIQUE,
                "task_id"	TEXT UNIQUE,
                "hash_id"   TEXT,
                "cover_id"	TEXT,
                "title"	TEXT,
                "completed_time"	INTEGER,
                "data"	TEXT,
                PRIMARY KEY("id" AUTOINCREMENT)
            );
            """)

        # 旧版表可能还没有 hash_id，不能在迁移前直接创建索引。
        if "hash_id" in self._get_table_columns("download_task") and "hash_id" in self._get_table_columns("completed_task"):
            self.execute_script("""
                CREATE INDEX IF NOT EXISTS "idx_download_task_hash_id" ON "download_task" ("hash_id");
                CREATE INDEX IF NOT EXISTS "idx_completed_task_hash_id" ON "completed_task" ("hash_id");
                """)
        
    def query_tasks(self, completed: bool = False):
        if completed:
            result = self.query("""
                SELECT data FROM completed_task
            """)
        else:
            result = self.query("""
                SELECT data FROM download_task
            """)

        return result

    def add_tasks(self, task_info_list: List[TaskInfo], completed: bool = False):
        # 通过 completed 参数来区分是插入到 download_task 还是 completed_task 表
        info_list = []

        for task_info in task_info_list:
            timestamp = task_info.Basic.completed_time if completed else task_info.Basic.created_time

            if not timestamp:
                timestamp = get_timestamp()

            info_list.append((
                task_info.Basic.task_id,                                    # task_id
                self._calc_hash_id(task_info),                              # hash_id
                task_info.Basic.cover_id,                                   # cover_id
                task_info.Basic.show_title,                                 # title
                timestamp,                                                  # created_time or completed_time
                json_dumps(task_info.to_dict())                             # data
            ))

        if completed:
            self.executemany("""
                INSERT INTO completed_task (task_id, hash_id, cover_id, title, completed_time, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, info_list)
        else:
            self.executemany("""
                INSERT INTO download_task (task_id, hash_id, cover_id, title, created_time, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, info_list)

    def update_task(self, task_info: TaskInfo):
        self.execute("""
            UPDATE download_task SET data = ? WHERE task_id = ?
        """, (json_dumps(task_info.to_dict()), task_info.Basic.task_id))

    def update_task_json(self, task_id: str, data: str):
        self.execute("""
            UPDATE download_task SET data = ? WHERE task_id = ?
        """, (data, task_id))

    def delete_task(self, task_id: str, completed: bool = False):
        if completed:
            self.execute("""
                DELETE FROM completed_task WHERE task_id = ?
            """, (task_id,))
        else:
            self.execute("""
                DELETE FROM download_task WHERE task_id = ?
            """, (task_id,))

    def check_duplicate(self, hash_id: str):
        completed_result = self.query("""
            SELECT title FROM completed_task WHERE hash_id = ?
        """, (hash_id,))
    
        download_result = self.query("""
            SELECT title FROM download_task WHERE hash_id = ?
        """, (hash_id,))

        return len(completed_result) > 0 or len(download_result) > 0

    def _upgrade(self):
        def _to_task_list(result):
            _task_info_list = []

            for entry in result:
                task_info = TaskInfo()
                task_info.from_dict(json_loads(entry[0]))

                _task_info_list.append(task_info)

            return _task_info_list

        if not self._needs_upgrade():
            logger.info("数据库已是最新版本，无需升级")
            return

        # 取出原有数据
        download_tasks = self.query_tasks(completed = False)
        completed_tasks = self.query_tasks(completed = True)

        download_task_list = _to_task_list(download_tasks)
        completed_task_list = _to_task_list(completed_tasks)

        def _task_records(task_info_list: List[TaskInfo], completed: bool):
            records = []

            for task_info in task_info_list:
                timestamp = task_info.Basic.completed_time if completed else task_info.Basic.created_time

                if not timestamp:
                    timestamp = get_timestamp()

                records.append((
                    task_info.Basic.task_id,
                    self._calc_hash_id(task_info),
                    task_info.Basic.cover_id,
                    task_info.Basic.show_title,
                    timestamp,
                    json_dumps(task_info.to_dict())
                ))

            return records

        download_records = _task_records(download_task_list, completed = False)
        completed_records = _task_records(completed_task_list, completed = True)

        # 在同一个事务中重建表，避免迁移中途失败后留下空表或半成品表。
        with sqlite3.connect(self.path) as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN")

            cursor.execute("DROP TABLE IF EXISTS download_task")
            cursor.execute("DROP TABLE IF EXISTS completed_task")

            cursor.execute("""
                CREATE TABLE download_task (
                    id INTEGER UNIQUE,
                    task_id TEXT UNIQUE,
                    hash_id TEXT,
                    cover_id TEXT,
                    title TEXT,
                    created_time INTEGER,
                    data TEXT,
                    PRIMARY KEY(id AUTOINCREMENT)
                )
            """)
            cursor.execute("""
                CREATE TABLE completed_task (
                    id INTEGER UNIQUE,
                    task_id TEXT UNIQUE,
                    hash_id TEXT,
                    cover_id TEXT,
                    title TEXT,
                    completed_time INTEGER,
                    data TEXT,
                    PRIMARY KEY(id AUTOINCREMENT)
                )
            """)
            cursor.execute("CREATE INDEX idx_download_task_hash_id ON download_task (hash_id)")
            cursor.execute("CREATE INDEX idx_completed_task_hash_id ON completed_task (hash_id)")

            cursor.executemany("""
                INSERT INTO download_task (task_id, hash_id, cover_id, title, created_time, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, download_records)
            cursor.executemany("""
                INSERT INTO completed_task (task_id, hash_id, cover_id, title, completed_time, data)
                VALUES (?, ?, ?, ?, ?, ?)
            """, completed_records)

            conn.commit()

    def _calc_hash_id(self, task_info: TaskInfo):
        # 根据 task_info 计算 hash_id
        attr = task_info.Episode.attribute

        if attr & Attribute.VIDEO_BIT:
            # 投稿视频
            metadata = {
                "bvid": task_info.Episode.bvid,
                "cid": task_info.Episode.cid,
                "aid": task_info.Episode.aid
            }

        elif attr & Attribute.BANGUMI_BIT:
            # 剧集类
            metadata = {
                "bvid": task_info.Episode.bvid,
                "cid": task_info.Episode.cid,
                "aid": task_info.Episode.aid,
                "ep_id": task_info.Episode.ep_id
            }

        elif attr & Attribute.CHEESE_BIT:
            # 课程类
            metadata = {
                "aid": task_info.Episode.aid,
                "cid": task_info.Episode.cid,
                "ep_id": task_info.Episode.ep_id
            }

        elif attr & Attribute.AUDIO_BIT:
            # 音乐类
            metadata = {
                "sid": task_info.Episode.sid
            }

        return hashlib.md5(json_dumps(metadata).encode("utf-8")).hexdigest()

    # ---- 历史记录查询/清除 API(供 cli.commands.history 使用) ----

    def get_history(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """合并查询下载任务与已完成任务,按时间倒序分页返回

        :param limit:  返回条数上限
        :param offset:  偏移量(分页)
        :return: dict 列表,每项含 time/title/url/status/file_size 五个字段
        """
        sql = """
            SELECT time, title, data FROM (
                SELECT created_time AS time, title, data FROM download_task
                UNION ALL
                SELECT completed_time AS time, title, data FROM completed_task
            ) ORDER BY time DESC LIMIT ? OFFSET ?
        """
        rows = self.query(sql, (limit, offset))
        return [self._row_to_history_dict(row) for row in rows]

    def _row_to_history_dict(self, row: tuple) -> Dict[str, Any]:
        """将数据库行(time, title, data_json)解析为 history dict"""
        time_val, title, data_json = row

        # data 字段为 JSON 字符串,解析失败时回退为空 dict
        try:
            data = json_loads(data_json) if data_json else {}
        except Exception:
            logger.warning("历史记录数据 JSON 解析失败,标题=%s", title)
            data = {}

        basic = data.get("Basic", {}) or {}
        episode = data.get("Episode", {}) or {}
        download = data.get("Download", {}) or {}

        status_id = download.get("status", 0)
        status_name = _status_name(status_id)

        return {
            "time": time_val if time_val else basic.get("created_time", 0),
            "title": title or basic.get("show_title", ""),
            "url": episode.get("url", ""),
            "status": status_name,
            "file_size": download.get("total_size", 0),
        }

    def count_history(self) -> int:
        """统计历史记录总数(两表合计)"""
        sql = """
            SELECT COUNT(*) FROM (
                SELECT id FROM download_task
                UNION ALL
                SELECT id FROM completed_task
            )
        """
        result = self.query(sql)
        return result[0][0] if result else 0

    def clear_history(self, older_than_days: Optional[int] = None) -> int:
        """清空历史记录,返回被删除的条数

        :param older_than_days: 仅清除 N 天前的记录;为 None 时清空全部
        """
        if older_than_days is None:
            deleted = self.count_history()
            self.execute("DELETE FROM download_task")
            self.execute("DELETE FROM completed_task")
            return deleted

        # 仅清除 N 天前的记录(get_timestamp 返回秒级时间戳)
        cutoff = get_timestamp() - older_than_days * 86400

        cnt_dl = self.query(
            "SELECT COUNT(*) FROM download_task WHERE created_time < ?",
            (cutoff,),
        )
        cnt_done = self.query(
            "SELECT COUNT(*) FROM completed_task WHERE completed_time < ?",
            (cutoff,),
        )
        deleted = (cnt_dl[0][0] if cnt_dl else 0) + (cnt_done[0][0] if cnt_done else 0)

        self.execute("DELETE FROM download_task WHERE created_time < ?", (cutoff,))
        self.execute("DELETE FROM completed_task WHERE completed_time < ?", (cutoff,))
        return deleted

    # ---- 任务管理 API(供 cli.commands.task 使用) ----

    def list_tasks(
        self,
        limit: int = 50,
        status: Optional["DownloadStatus"] = None,
    ) -> List[Dict[str, Any]]:
        """列出现存下载任务(默认按 created_time 倒序)

        :param limit:  返回条数上限
        :param status: DownloadStatus 枚举,可选过滤
        :return: dict 列表,每项含 task_id/title/status/status_id/progress/speed/file_size/created_time
        """
        # 一次性拉全部任务后内存过滤,避免依赖 SQLite JSON1 扩展
        rows = self.query(
            "SELECT task_id, title, created_time, data FROM download_task "
            "ORDER BY created_time DESC"
        )
        tasks = [self._row_to_task_dict(row) for row in rows]

        if status is not None:
            status_int = int(status)
            tasks = [t for t in tasks if t["status_id"] == status_int]

        return tasks[:limit]

    def _row_to_task_dict(self, row: tuple) -> Dict[str, Any]:
        """将数据库行(task_id, title, created_time, data_json)解析为 task dict"""
        task_id, title, created_time, data_json = row

        try:
            data = json_loads(data_json) if data_json else {}
        except Exception:
            logger.warning("任务数据 JSON 解析失败,task_id=%s", task_id)
            data = {}

        basic = data.get("Basic", {}) or {}
        download = data.get("Download", {}) or {}
        status_id = download.get("status", 0)

        return {
            "task_id": task_id,
            "title": title or basic.get("show_title", ""),
            "status": _status_name(status_id),
            "status_id": status_id,
            "progress": download.get("progress", 0),
            "speed": download.get("speed", 0),
            "file_size": download.get("total_size", 0),
            "created_time": created_time or basic.get("created_time", 0),
        }

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """按 task_id 查询单条任务,不存在返回 None"""
        rows = self.query(
            "SELECT task_id, title, created_time, data FROM download_task WHERE task_id = ?",
            (task_id,),
        )
        if not rows:
            return None
        return self._row_to_task_dict(rows[0])

    def pause_task(self, task_id: str):
        """暂停任务(仅当状态为 DOWNLOADING 时允许)

        :return: True=成功;False=状态不允许;None=任务不存在
        """
        return self._transition_status(
            task_id, DownloadStatus.DOWNLOADING, DownloadStatus.PAUSED
        )

    def resume_task(self, task_id: str):
        """恢复任务(仅当状态为 PAUSED 时允许)

        :return: True=成功;False=状态不允许;None=任务不存在
        """
        return self._transition_status(
            task_id, DownloadStatus.PAUSED, DownloadStatus.DOWNLOADING
        )

    def _transition_status(self, task_id: str, expected_from, target_to):
        """通用状态转换:校验当前状态为 expected_from,转为 target_to

        :return: True=成功;False=状态不允许;None=任务不存在
        """
        rows = self.query(
            "SELECT data FROM download_task WHERE task_id = ?",
            (task_id,),
        )
        if not rows:
            return None

        data_json = rows[0][0]
        try:
            data = json_loads(data_json) if data_json else {}
        except Exception:
            logger.warning("任务数据 JSON 解析失败,task_id=%s", task_id)
            data = {}

        download = data.setdefault("Download", {})
        current_status = download.get("status", 0)
        if current_status != int(expected_from):
            return False

        download["status"] = int(target_to)
        self.execute(
            "UPDATE download_task SET data = ? WHERE task_id = ?",
            (json_dumps(data), task_id),
        )
        return True

    def cancel_task(self, task_id: str) -> bool:
        """取消任务(删除记录)

        :return: True=已删除;False=任务不存在
        """
        exists = self.query(
            "SELECT 1 FROM download_task WHERE task_id = ?",
            (task_id,),
        )
        if not exists:
            return False

        self.execute(
            "DELETE FROM download_task WHERE task_id = ?",
            (task_id,),
        )
        return True

    def clear_tasks(self, status: Optional["DownloadStatus"] = None) -> int:
        """清空下载任务,可按状态过滤

        :param status: DownloadStatus 枚举,仅清除此状态的任务;None 表示全部
        :return: 已删除条数
        """
        rows = self.query("SELECT task_id, data FROM download_task")

        if status is None:
            to_delete = [task_id for task_id, _ in rows]
        else:
            status_int = int(status)
            to_delete = [
                task_id
                for task_id, data_json in rows
                if _extract_status_id(data_json) == status_int
            ]

        for task_id in to_delete:
            self.execute(
                "DELETE FROM download_task WHERE task_id = ?",
                (task_id,),
            )
        return len(to_delete)


def _extract_status_id(data_json: Optional[str]) -> int:
    """从任务 data JSON 中提取 Download.status 整数,解析失败回退为 0"""
    if not data_json:
        return 0
    try:
        data = json_loads(data_json)
    except Exception:
        return 0
    download = data.get("Download", {}) or {}
    return int(download.get("status", 0) or 0)


def _status_name(status_id: int) -> str:
    """将 DownloadStatus 整数值转可读字符串,未知值回退为 'UNKNOWN'"""
    try:
        return DownloadStatus(status_id).name
    except ValueError:
        return "UNKNOWN"
