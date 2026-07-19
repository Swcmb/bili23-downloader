# tests/unit/test_misc_no_qt.py
"""T2.11 测试:misc/update、web 去除 Qt 依赖

验证点:
1. 导入两个模块不触发 PySide6 加载
2. 源码不含 PySide6/QNetworkAccessManager/QDesktopServices 等 Qt 关键字
3. Updater 不再继承 QObject
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 misc 模块不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.misc.update  # noqa: F401
    import util.misc.web  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "misc 模块仍间接依赖 PySide6"


def test_source_no_qt_calls():
    """源码中不应包含 Qt 调用关键字"""
    _purge_pyside6()
    import util.misc.update as update
    import util.misc.web as web

    keywords = (
        "PySide6", "QObject", "QNetworkAccessManager",
        "QDesktopServices", "QStandardPaths", "QFile", "QTextStream",
        "QRunnable", "@Slot",
    )
    for mod in (update, web):
        source = inspect.getsource(mod)
        for kw in keywords:
            assert kw not in source, f"{mod.__name__} 源码仍含 {kw}"


def test_updater_not_inherit_qobject():
    """Updater 不应继承 QObject"""
    _purge_pyside6()
    from util.misc.update import Updater
    for cls in Updater.__mro__:
        assert "QObject" not in cls.__name__, \
            f"Updater 仍继承自 {cls.__name__}"
