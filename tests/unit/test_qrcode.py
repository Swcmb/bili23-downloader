# tests/unit/test_qrcode.py
"""T2.7 测试:auth/qrcode 去除 Qt 依赖

验证点:
1. 导入 util.auth.qrcode 不触发 PySide6 加载
2. 源码中不含 QPixmap / PySide6 等 Qt 关键字
3. _build_qrcode_pixmap 改为返回 bytes(PNG 字节流)
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块,确保测试从干净状态开始"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 qrcode 模块不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.auth.qrcode  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "qrcode 模块仍间接依赖 PySide6"


def test_source_no_qt_calls():
    """源码中不应包含 Qt 调用关键字"""
    _purge_pyside6()
    from util.auth import qrcode
    source = inspect.getsource(qrcode)
    for keyword in ("QPixmap", "PySide6", "QImage", "QPainter", "QSize", "QTimer"):
        assert keyword not in source, f"源码仍含 {keyword}"


def test_build_qrcode_returns_bytes():
    """_build_qrcode_pixmap 应返回 bytes(PNG 字节流)而非 QPixmap"""
    _purge_pyside6()
    from util.auth.qrcode import QRCode
    qr = QRCode()
    result = qr._build_qrcode_pixmap("https://www.bilibili.com")
    assert isinstance(result, (bytes, bytearray)), \
        f"期望 bytes,实际 {type(result)}"
    # PNG 文件头:89 50 4E 47 0D 0A 1A 0A
    assert bytes(result[:8]) == b"\x89PNG\r\n\x1a\n", "返回的 bytes 不是 PNG 字节流"
