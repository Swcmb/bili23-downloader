# tests/unit/test_network_no_qt.py
"""T2.10 测试:network/request 去除 Qt 依赖

验证点:
1. 导入 util.network.request 不触发 PySide6 加载
2. 源码不含 Signal/QObject/Slot/PySide6/@Slot
3. config 调用形式从 config.get(config.xxx) 改为 config.get("xxx")
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 request 模块不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.network.request  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "request 模块仍间接依赖 PySide6"


def test_source_no_qt_calls():
    """源码中不应包含 Qt 调用关键字"""
    _purge_pyside6()
    from util.network import request
    source = inspect.getsource(request)
    for keyword in ("Signal", "QObject", "Slot", "PySide6", "@Slot", "Qt."):
        assert keyword not in source, f"源码仍含 {keyword}"


def test_config_get_uses_string_keys():
    """config.get 调用应使用字符串键而非 config.xxx 属性"""
    _purge_pyside6()
    from util.network import request
    source = inspect.getsource(request)
    # 不应再出现 config.get(config.xxx) 形式
    assert "config.get(config." not in source, "仍存在 config.get(config.xxx) 调用形式"


def test_network_worker_not_inherit_qobject():
    """NetworkRequestWorker 不应继承 QObject"""
    _purge_pyside6()
    from util.network.request import NetworkRequestWorker
    for cls in NetworkRequestWorker.__mro__:
        assert "QObject" not in cls.__name__, \
            f"NetworkRequestWorker 仍继承自 {cls.__name__}"
