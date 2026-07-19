# tests/unit/test_danmaku_ass.py
"""T2.12 测试:parse/additional/file/danmaku_ass 去除 Qt 依赖

验证点:
1. 导入模块不触发 PySide6 加载
2. 源码含 PIL/ImageFont,不含 QFontMetrics/QApplication
3. _measure_text_width 函数存在并能测量文本宽度
"""
import inspect
import sys


def _purge_pyside6():
    """清空已加载的 PySide6 子模块"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 danmaku_ass 不应触发 PySide6 加载"""
    _purge_pyside6()
    import util.parse.additional.file.danmaku_ass  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        "danmaku_ass 仍间接依赖 PySide6"


def test_text_width_measurement_with_pil():
    """源码应使用 PIL ImageFont 测量文本宽度,不再依赖 GUI 框架"""
    _purge_pyside6()
    from util.parse.additional.file import danmaku_ass
    source = inspect.getsource(danmaku_ass)

    # 应使用 PIL
    assert "ImageFont" in source or "PIL" in source, "源码未使用 PIL"

    # 不应使用 GUI 框架的字体度量工具
    for kw in ("QFontMetrics", "QApplication", "PySide6", "horizontalAdvance"):
        assert kw not in source, f"源码仍含 {kw}"


def test_measure_text_width_function_exists():
    """_measure_text_width 函数应存在并能返回正数宽度"""
    _purge_pyside6()
    from util.parse.additional.file.danmaku_ass import _measure_text_width, _load_pil_font

    font = _load_pil_font("sans", 16, False)
    width = _measure_text_width(font, "hello world")
    assert isinstance(width, int)
    assert width > 0


def test_measure_text_width_handles_empty_text():
    """_measure_text_width 对空字符串应返回 0"""
    _purge_pyside6()
    from util.parse.additional.file.danmaku_ass import _measure_text_width, _load_pil_font

    font = _load_pil_font("sans", 16, False)
    width = _measure_text_width(font, "")
    assert width == 0
