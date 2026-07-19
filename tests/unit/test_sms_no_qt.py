# tests/unit/test_sms_no_qt.py
"""T2.8 测试:auth/sms 去除 Qt 依赖

验证点:
1. 导入 util.auth.sms 不触发 PySide6 加载
2. 源码中不含 QTimer / PySide6 / QObject 等 Qt 关键字
3. SMS 不再继承 QObject
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 sms 模块不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.auth.sms  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "sms 模块仍间接依赖 PySide6"


def test_source_no_qt_calls():
    """源码中不应包含 Qt 调用关键字"""
    _purge_pyside6()
    from util.auth import sms
    source = inspect.getsource(sms)
    for keyword in ("QTimer", "PySide6", "QObject", "QRunnable", "@Slot"):
        assert keyword not in source, f"源码仍含 {keyword}"


def test_sms_not_inherit_qobject():
    """SMS 不应继承 QObject"""
    _purge_pyside6()
    from util.auth.sms import SMS
    for cls in SMS.__mro__:
        assert "QObject" not in cls.__name__, \
            f"SMS 仍继承自 {cls.__name__}"
