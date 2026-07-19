# tests/unit/test_cover_no_qt.py
"""T2.5 测试:cover 模块去除 Qt 依赖

验证点:
1. 导入 cover.manager / cache / query_worker 不触发 PySide6 加载
2. CoverCache.cache 值类型为 bytes(原 QPixmap)
3. CoverQueryWorker 继承 WorkerBase 而非 QRunnable
4. 源码中不含 QPixmap/QImage/QBuffer/QMetaObject/QRunnable 字样
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 cover 三个模块不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.download.cover.manager  # noqa: F401
    import util.download.cover.cache  # noqa: F401
    import util.download.cover.query_worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "cover 模块仍间接依赖 PySide6"


def test_cover_cache_value_is_bytes():
    """CoverCache.cache 应为 Dict[str, bytes]"""
    _purge_pyside6()
    from util.download.cover.cache import CoverCache
    assert isinstance(CoverCache.cache, dict)
    # 通过类型注解判断,值应为 bytes
    hints = CoverCache.__annotations__
    assert hints.get("cache") is bytes or "bytes" in str(hints.get("cache"))


def test_query_worker_inherits_worker_base():
    """CoverQueryWorker 应继承 WorkerBase"""
    _purge_pyside6()
    from util.download.cover.query_worker import CoverQueryWorker
    from util.thread.worker_base import WorkerBase
    assert issubclass(CoverQueryWorker, WorkerBase)


def test_source_no_qt_calls():
    """三个文件源码中不应包含 Qt 关键字"""
    _purge_pyside6()
    import util.download.cover.manager as manager
    import util.download.cover.cache as cache
    import util.download.cover.query_worker as query_worker

    keywords = ("QPixmap", "QImage", "QBuffer", "QMetaObject",
                "QRunnable", "Q_ARG", "Qt.ConnectionType", "invokeMethod",
                "QThreadPool", "QAbstractListModel", "QSize")
    for mod in (manager, cache, query_worker):
        source = inspect.getsource(mod)
        for kw in keywords:
            assert kw not in source, f"{mod.__name__} 源码仍含 {kw}"
