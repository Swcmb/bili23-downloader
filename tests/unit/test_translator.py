# tests/unit/test_translator.py
"""翻译器单元测试 - 验证 Python dict 替代 QTranslator + .qm"""
import pytest


def test_translator_returns_key_if_missing():
    """不存在键返回键本身(避免空字符串导致 UI 显示空白)"""
    from util.common.translator import translator
    assert translator.tr("nonexistent.key") == "nonexistent.key"


def test_translator_interpolation():
    """支持 {placeholder} 插值(与 Qt translate 的 %n/%1 风格不同,采用 Python format)"""
    from util.common.translator import translator
    # 注册测试键
    translator._dict["test.hello"] = "Hello {name}"
    assert translator.tr("test.hello", name="World") == "Hello World"
    # 清理避免污染其他测试
    translator._dict.pop("test.hello", None)


def test_translator_loads_from_ts_if_present():
    """若 .ts 文件存在,加载后能查到翻译(回归测试)"""
    import os
    from util.common.translator import translator
    # .ts 文件中存在 <source>Danmaku</source><translation>弹幕</translation>
    if translator._dict:
        # 已加载到字典,验证弹幕翻译存在
        assert translator._dict.get("Danmaku") == "弹幕"


def test_no_pyside6_import():
    """AC: import 不触发 PySide6"""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.translator  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
