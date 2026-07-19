# tests/unit/test_auth_no_qt.py
"""T2.9 测试:auth/cookie_login、server、captcha 去除 Qt 依赖

验证点:
1. 导入三个模块不触发 PySide6 加载
2. 三个模块源码不含 PySide6/QPixmap/QWebEngine/signal_bus 关键字
3. CookieLogin / Captcha 不再继承 QObject
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入三个模块不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.auth.cookie_login  # noqa: F401
    import util.auth.server  # noqa: F401
    import util.auth.captcha  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "auth 模块仍间接依赖 PySide6"


def test_source_no_qt_calls():
    """三个模块源码不应包含 Qt 关键字;server.py 还不应含 signal_bus"""
    _purge_pyside6()
    import util.auth.cookie_login as cookie_login
    import util.auth.server as server
    import util.auth.captcha as captcha

    # 所有三个模块均不能含的 GUI 框架关键字
    qt_keywords = (
        "PySide6", "QPixmap", "QWebEngine", "QWebEngineView",
        "QWebEnginePage", "QWebEngineProfile", "QWebEngineSettings",
        "QObject", "QRunnable", "@Slot",
    )
    for mod in (cookie_login, server, captcha):
        source = inspect.getsource(mod)
        for kw in qt_keywords:
            assert kw not in source, f"{mod.__name__} 源码仍含 {kw}"

    # server.py 还需移除 signal_bus 引用(改用回调或 logging)
    server_source = inspect.getsource(server)
    assert "signal_bus" not in server_source, "server.py 源码仍含 signal_bus"


def test_cookie_login_not_inherit_qobject():
    """CookieLogin 不应继承 QObject"""
    _purge_pyside6()
    from util.auth.cookie_login import CookieLogin
    for cls in CookieLogin.__mro__:
        assert "QObject" not in cls.__name__, \
            f"CookieLogin 仍继承自 {cls.__name__}"


def test_captcha_not_inherit_qobject():
    """Captcha 不应继承 QObject"""
    _purge_pyside6()
    from util.auth.captcha import Captcha
    for cls in Captcha.__mro__:
        assert "QObject" not in cls.__name__, \
            f"Captcha 仍继承自 {cls.__name__}"
