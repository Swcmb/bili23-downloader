# tests/unit/test_downloader.py
"""T2.2 验证 - download/downloader/downloader.py 移除 Qt 依赖

测试目标:
- ChunkWorker 仅继承 WorkerBase(不再继承 QRunnable)
- import downloader 模块不触发 PySide6 导入
"""
import sys


def _purge_pyside6():
    """清除已加载的 PySide6 模块,确保测试从干净状态开始"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_chunk_worker_inherits_worker_base_only():
    """ChunkWorker 必须仅继承 WorkerBase(去除 QRunnable)"""
    from util.download.downloader.downloader import ChunkWorker
    from util.thread.worker_base import WorkerBase
    assert ChunkWorker.__bases__ == (WorkerBase,)


def test_no_pyside6_import():
    """导入 downloader 模块时不应触发 PySide6 导入"""
    _purge_pyside6()
    # 同时清除已加载的 downloader 模块,确保重新触发导入
    for mod in list(sys.modules.keys()):
        if mod.startswith("util.download"):
            del sys.modules[mod]
    import util.download.downloader.downloader  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        f"PySide6 模块被意外加载: {[m for m in sys.modules if m.startswith('PySide6')]}"
