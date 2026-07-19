# tests/unit/test_config.py
"""配置系统单元测试 - 验证 JSON + platformdirs 替代 QConfig"""
import json
import os
import threading
import pytest
from unittest.mock import patch


def test_config_get_with_default(tmp_path):
    from util.common.config import Config
    cfg = Config(config_path=str(tmp_path / "config.json"))
    assert cfg.get("nonexistent", default=42) == 42


def test_config_set_persists(tmp_path):
    from util.common.config import Config
    path = str(tmp_path / "config.json")
    cfg = Config(config_path=path)
    cfg.set("video_quality_id", 80)
    # 重新加载验证持久化
    cfg2 = Config(config_path=path)
    assert cfg2.get("video_quality_id") == 80


def test_config_corrupt_json_backup_and_reset(tmp_path):
    """AC-024-3: 损坏 JSON 备份并重置"""
    from util.common.config import Config
    path = str(tmp_path / "config.json")
    with open(path, "w") as f:
        f.write("{invalid json")
    cfg = Config(config_path=path)
    # 备份文件存在
    assert os.path.exists(path + ".bak")
    # 重置为默认值,不报错
    assert cfg.get("download_threads") == 8


def test_config_concurrent_set_thread_safe(tmp_path):
    """AC-024-5: 并发 set 线程安全"""
    from util.common.config import Config
    cfg = Config(config_path=str(tmp_path / "config.json"))
    keys = [f"key_{i}" for i in range(100)]
    threads = [threading.Thread(target=cfg.set, args=(k, i)) for i, k in enumerate(keys)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    cfg.reload()
    for i, k in enumerate(keys):
        assert cfg.get(k) == i


def test_config_download_threads_range_validation(tmp_path):
    """AC-024-7: download_threads 范围校验"""
    from util.common.config import Config, ConfigError
    cfg = Config(config_path=str(tmp_path / "config.json"))
    with pytest.raises(ConfigError):
        cfg.set("download_threads", 0)
    with pytest.raises(ConfigError):
        cfg.set("download_threads", 33)
    cfg.set("download_threads", 16)
    assert cfg.get("download_threads") == 16


def test_config_max_concurrent_tasks_range_validation(tmp_path):
    """AC-024-7: max_concurrent_tasks 范围校验"""
    from util.common.config import Config, ConfigError
    cfg = Config(config_path=str(tmp_path / "config.json"))
    with pytest.raises(ConfigError):
        cfg.set("max_concurrent_tasks", 0)
    with pytest.raises(ConfigError):
        cfg.set("max_concurrent_tasks", 11)


def test_no_pyside6_import():
    """AC-024-1: import 不触发 PySide6"""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.config  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
