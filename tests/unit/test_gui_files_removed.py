# tests/unit/test_gui_files_removed.py
"""验证 GUI 专用模块已删除(AC: 移除清单)

注意:仅用 pytest.raises(ImportError) 在无 PySide6 环境下会误判
(模块因 PySide6 缺失而 ImportError,而非被删除)。因此同时检查
源文件不存在,确保测试真正验证删除而非依赖 PySide6 缺失。
"""
import importlib
import os
import pytest

_SRC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src", "util", "common")


def test_icon_module_removed():
    """util.common.icon 应已删除(GUI 专用 QIcon/QPixmap)"""
    # 文件级检查:源文件不应存在
    assert not os.path.exists(os.path.join(_SRC_DIR, "icon.py"))
    # 导入级检查:import 应失败
    with pytest.raises(ImportError):
        importlib.import_module("util.common.icon")


def test_style_sheet_module_removed():
    """util.common.style_sheet 应已删除(GUI 专用 QSS 主题)"""
    assert not os.path.exists(os.path.join(_SRC_DIR, "style_sheet.py"))
    with pytest.raises(ImportError):
        importlib.import_module("util.common.style_sheet")


def test_color_module_removed():
    """util.common.color 应已删除(GUI 专用 QColor,改用 rich.color)"""
    assert not os.path.exists(os.path.join(_SRC_DIR, "color.py"))
    with pytest.raises(ImportError):
        importlib.import_module("util.common.color")
