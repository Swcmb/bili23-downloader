# tests/unit/test_directory_more.py
"""Directory 类补充测试 - 覆盖 get_cwd / 模块级单例 / ImportError 兜底

补充 tests/unit/test_directory.py 未覆盖的分支:
- Directory.get_cwd 优先使用 PYSTAND_HOME 环境变量
- Directory.get_cwd 回退到 Path.cwd()
- 模块级 directory 单例属性可访问
- platformdirs ImportError 时的兜底路径生成
"""
import os
from pathlib import Path

import pytest


def test_get_cwd_uses_pystand_home(monkeypatch, tmp_path):
    """get_cwd 在 PYSTAND_HOME 设置时返回该路径"""
    from util.common.io.directory import Directory

    custom_home = str(tmp_path / "pystand_home")
    Path(custom_home).mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PYSTAND_HOME", custom_home)

    cwd = Directory.get_cwd()
    assert cwd == Path(custom_home)


def test_get_cwd_falls_back_to_path_cwd(monkeypatch):
    """get_cwd 在 PYSTAND_HOME 未设置时回退到当前工作目录"""
    from util.common.io.directory import Directory

    # 确保 PYSTAND_HOME 未设置
    monkeypatch.delenv("PYSTAND_HOME", raising=False)

    cwd = Directory.get_cwd()
    assert cwd == Path.cwd()


def test_directory_module_singleton():
    """模块级 directory 单例属性完整"""
    from util.common.io.directory import directory

    assert isinstance(directory.config_dir, str)
    assert isinstance(directory.data_dir, str)
    assert isinstance(directory.log_dir, str)
    assert isinstance(directory.cookie_path, str)
    assert isinstance(directory.task_db_path, str)
    # cookie 文件应位于 data_dir 下
    assert directory.cookie_path.startswith(directory.data_dir)
    assert directory.task_db_path.startswith(directory.data_dir)
    # log_dir 应在 data_dir 下
    assert directory.log_dir.startswith(directory.data_dir)


def test_directory_log_dir_under_data_dir():
    """log_dir 是 data_dir 的子目录"""
    from util.common.io.directory import directory

    assert "logs" in directory.log_dir
    # log_dir 路径应以 data_dir 开头
    assert directory.log_dir.startswith(directory.data_dir)


def test_directory_cookie_path_end_with_filename():
    """cookie_path 以 cookie.json 文件名结尾"""
    from util.common.io.directory import directory

    assert directory.cookie_path.endswith("cookie.json")


def test_directory_task_db_path_end_with_filename():
    """task_db_path 以 tasks.db 文件名结尾"""
    from util.common.io.directory import directory

    assert directory.task_db_path.endswith("tasks.db")


def test_directory_import_error_fallback(monkeypatch):
    """platformdirs ImportError 时使用兜底路径生成函数"""
    import importlib

    # 用一个独立的子模块名重新加载,触发 ImportError 分支
    import sys
    # 备份并删除已加载的模块,使下次 import 重新走 try 块
    modules_to_remove = [
        m for m in list(sys.modules.keys())
        if m == "util.common.io.directory" or m == "platformdirs"
    ]
    for m in modules_to_remove:
        monkeypatch.syspath_prepend(None)  # noop,但保留 monkeypatch session
        del sys.modules[m]

    # 让 import platformdirs 抛 ImportError
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "platformdirs":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    # 重新导入 directory 模块,会走 except ImportError 兜底
    import util.common.io.directory as dir_module
    importlib.reload(dir_module)

    # 验证兜底函数返回 ~/.config 或 ~/.local/share 路径
    d = dir_module.Directory()
    assert ".config" in d.config_dir or "Bili23-Downloader" in d.config_dir
    assert ".local/share" in d.data_dir or "Bili23-Downloader" in d.data_dir
