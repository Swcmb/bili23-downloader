# tests/unit/test_parse_worker_no_qt.py
"""T2.4 测试:parse_worker 去除 Qt 依赖

验证点:
1. 导入 parse_worker 模块不会触发 PySide6 加载
2. ParseWorker 不再继承 QRunnable
3. 源码中不含 QMetaObject / QRunnable / Q_ARG / Qt.ConnectionType 字样
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块,确保测试从干净状态开始"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 parse_worker 不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.download.downloader.parse_worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "parse_worker 仍间接依赖 PySide6"


def test_parse_worker_not_inherit_qrunnable():
    """ParseWorker 不应继承 QRunnable"""
    _purge_pyside6()
    from util.download.downloader.parse_worker import ParseWorker
    # 排除 PySide6.QRunnable 在 MRO 中
    for cls in ParseWorker.__mro__:
        assert "QRunnable" not in cls.__name__, \
            f"ParseWorker 仍继承自 {cls.__name__}"


def test_source_no_qt_calls():
    """源码中不应包含 Qt 调用关键字"""
    _purge_pyside6()
    from util.download.downloader import parse_worker
    source = inspect.getsource(parse_worker)
    for keyword in ("QRunnable", "QMetaObject", "Q_ARG", "Qt.ConnectionType", "invokeMethod"):
        assert keyword not in source, f"源码仍含 {keyword}"
