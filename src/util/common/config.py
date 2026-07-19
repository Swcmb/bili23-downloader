# src/util/common/config.py
"""配置系统 - 纯 Python + JSON + platformdirs

替代 qfluentwidgets.QConfig + ConfigItem。

设计要点:
- 配置目录:platformdirs.user_config_dir("Bili23-Downloader")
- 配置文件:<config_dir>/config.json
- 范围校验迁移到 set() 中,失败抛出 ConfigError
- threading.Lock 保护并发写入,确保线程安全(AC-024-5)
- 损坏 JSON 自动备份为 .bak 并重置为默认值(AC-024-3)

注意:原 API `config.get(config.xxx).value` 已废弃,
新 API 为 `config.get("xxx")`,待 T2.13 全量替换 53 个文件 162 处调用。
"""
import json
import logging
import os
import threading
from typing import Any, Dict, Optional

try:
    from platformdirs import user_config_dir
except ImportError:
    # 兜底,避免 platformdirs 未安装时 import 失败
    def user_config_dir(app: str) -> str:
        return os.path.expanduser(f"~/.config/{app}")


logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """配置错误(范围校验失败、类型不符等)"""


# 范围校验规则:(min, max) 闭区间
_RANGE_RULES = {
    "download_threads": (1, 32),
    "max_concurrent_tasks": (1, 10),
}


# 内置默认值:保留原 DefaultValue 中的关键配置项 + 新增 CLI 专用项
# download_threads/max_concurrent_tasks 为 CLI 版新增(替代原 download_thread/download_parallel)
_DEFAULT_VALUES: Dict[str, Any] = {
    # 下载相关
    "video_quality_id": 80,
    "audio_quality_id": 30280,
    "video_codec": 7,
    "download_threads": 8,
    "max_concurrent_tasks": 3,
    "video_container": "mp4",
    "retry_count": 5,
    # 画质优先级(原 DefaultValue.video_quality_priority)
    "video_quality_priority": [127, 126, 125, 120, 116, 112, 100, 80, 64, 32, 16],
    "audio_quality_priority": [30251, 30250, 30280, 30232, 30216],
    "video_codec_priority": [7, 12, 13],
    # 附加产物
    "download_danmaku": False,
    "download_subtitle": False,
    "download_cover": False,
    "download_metadata": False,
    # 高级
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36 Edg/147.0.0.0"
    ),
    # FFmpeg 来源(bundled/system/custom,对应 FFmpegSource 枚举的 value)
    "ffmpeg_source": "bundled",
    "custom_ffmpeg_path": "",
}


class Config:
    """配置类,提供 get/set/save/load/reload API

    所有 set 操作立即持久化到 JSON 文件,并加锁保证线程安全。
    """

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_dir = user_config_dir("Bili23-Downloader")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.json")
        self._path = config_path
        self._lock = threading.Lock()
        # 深拷贝默认值,避免单例间共享可变对象
        self._data: Dict[str, Any] = json.loads(json.dumps(_DEFAULT_VALUES))
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """读取配置项,不存在返回 default"""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置并立即持久化,带范围校验

        范围校验失败抛出 ConfigError,不修改内部状态。
        """
        # 范围校验(在锁外执行,避免锁内抛异常)
        if key in _RANGE_RULES:
            lo, hi = _RANGE_RULES[key]
            if not isinstance(value, int) or isinstance(value, bool) or not (lo <= value <= hi):
                raise ConfigError(f"{key} must be int in [{lo}, {hi}], got {value!r}")
        # set + save 在同一锁内,保证并发 set 的原子性(避免 tmp 文件竞争)
        with self._lock:
            self._data[key] = value
            self._write_under_lock()

    def save(self) -> None:
        """显式保存到文件(原子写入:先写临时文件再 rename)"""
        with self._lock:
            self._write_under_lock()

    def _write_under_lock(self) -> None:
        """在已持锁的情况下写入文件(原子 rename)"""
        # 深拷贝避免序列化期间被其他线程修改
        data = json.loads(json.dumps(self._data))
        # 临时文件 + rename 实现原子写入;tmp 文件名带线程 ID 避免并发冲突
        tmp_path = f"{self._path}.tmp.{threading.get_ident()}"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self._path)

    def load(self) -> None:
        """加载配置文件,损坏时备份并重置为默认值

        损坏判定:JSON 解析失败或根节点非 dict。
        """
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("config root must be object")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            # 备份损坏的文件,便于用户排查
            bak = self._path + ".bak"
            try:
                os.replace(self._path, bak)
                logger.warning("配置文件损坏,已备份到 %s,重置为默认值: %s", bak, e)
            except OSError as backup_err:
                logger.error("备份损坏配置文件失败: %s", backup_err)
            return
        with self._lock:
            self._data.update(loaded)

    def reload(self) -> None:
        """重置为默认值后重新加载文件(用于测试)"""
        with self._lock:
            self._data = json.loads(json.dumps(_DEFAULT_VALUES))
        self.load()


# 模块级单例,保持与原代码 `from util.common.config import config` 兼容
config = Config()
