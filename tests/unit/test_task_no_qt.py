# tests/unit/test_task_no_qt.py
"""T2.6 验证 download/task 模块无 Qt 依赖"""
import inspect
import pytest


def test_no_pyside6_import():
    """import 三个 task 模块不触发 PySide6"""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.download.task.manager  # noqa: F401
    import util.download.task.query_worker  # noqa: F401
    import util.download.task.reparse_worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)


def test_source_no_qt_calls():
    """源码不含 Qt 关键字(包括 docstring/注释)"""
    import util.download.task.manager as m1
    import util.download.task.query_worker as m2
    import util.download.task.reparse_worker as m3
    qt_keywords = ["QRunnable", "QMetaObject", "Q_ARG", "Qt.ConnectionType",
                   "invokeMethod", "QThread", "QThreadPool", "QObject", "@Slot",
                   "PySide6"]
    for mod in (m1, m2, m3):
        src = inspect.getsource(mod)
        for kw in qt_keywords:
            assert kw not in src, f"{mod.__name__} 源码含 {kw}: {src[:500]}"
