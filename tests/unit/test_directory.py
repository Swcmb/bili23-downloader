# tests/unit/test_directory.py
"""目录路径管理单元测试 - 验证 platformdirs 替代 QStandardPaths"""
import os
import pytest


def test_directory_paths_exist_or_creatable(tmp_path, monkeypatch):
    """目录路径属性存在且合理"""
    # 通过 XDG 环境变量重定向到 tmp_path,避免污染真实配置目录
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from util.common.io.directory import Directory
    d = Directory()
    # config_dir 的父目录应已创建(platformdirs 可能返回嵌套路径)
    assert os.path.isdir(d.config_dir) or os.path.isdir(os.path.dirname(d.config_dir))
    assert d.cookie_path.endswith("cookie.json")
    assert d.task_db_path.endswith("tasks.db")
    assert d.log_dir.endswith("logs")


def test_directory_data_dir_created(tmp_path, monkeypatch):
    """data_dir 与 log_dir 在初始化后真实存在"""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from util.common.io.directory import Directory
    d = Directory()
    assert os.path.isdir(d.data_dir)
    assert os.path.isdir(d.log_dir)


def test_no_pyside6_import():
    """AC: import 不触发 PySide6"""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.io.directory  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
