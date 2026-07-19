# tests/unit/test_parse_workers.py
"""T2.1 验证 - parse/preview/additional workers 移除 Qt 依赖

测试目标:
- ParseWorker / ProgressParseWorker / QueryInfoWorker / AdditionalParseWorker
  继承自纯 Python 版本的 WorkerBase
- import 三个 worker 模块不触发 PySide6 导入
"""
import sys


def _purge_pyside6():
    """清除已加载的 PySide6 模块,确保测试从干净状态开始"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_parse_worker_inherits_new_worker_base():
    """ParseWorker 必须是 util.thread.worker_base.WorkerBase 的子类"""
    from util.parse.worker import ParseWorker
    from util.thread.worker_base import WorkerBase
    assert issubclass(ParseWorker, WorkerBase)


def test_no_pyside6_import():
    """导入三个 worker 模块时不应触发 PySide6 导入"""
    _purge_pyside6()
    # 同时清除已加载的 worker 模块,确保重新触发导入
    for mod in list(sys.modules.keys()):
        if mod.startswith("util.parse"):
            del sys.modules[mod]
    import util.parse.worker  # noqa: F401
    import util.parse.preview.worker  # noqa: F401
    import util.parse.additional.worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        f"PySide6 模块被意外加载: {[m for m in sys.modules if m.startswith('PySide6')]}"
