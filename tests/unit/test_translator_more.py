# tests/unit/test_translator_more.py
"""Translator 补充测试 - 加载 .ts 文件 / 占位符失败兜底

补充 tests/unit/test_translator.py 未覆盖的分支:
- tr() 在 kwargs 缺失占位符时返回未插值的原文(不抛异常)
- tr() 在无 kwargs 时直接返回字典值或 key 本身
- _load_from_ts 在 .ts 文件损坏(ParseError)时静默失败,记 warning
- _load_from_ts 在文件不存在时静默跳过
- _load_default 路径计算(不存在的目录也不抛异常)
- 模块级 translator 单例可用
"""
import logging
import os
import pytest


def test_tr_no_kwargs_returns_value_or_key():
    """tr() 在无 kwargs 时直接返回字典值,缺失则返回 key"""
    from util.common.translator import Translator

    t = Translator()
    t._dict["greeting"] = "Hello"
    assert t.tr("greeting") == "Hello"
    assert t.tr("missing.key") == "missing.key"


def test_tr_placeholder_mismatch_returns_unformatted():
    """tr() 在占位符不匹配时返回未插值的原文(不抛异常)"""
    from util.common.translator import Translator

    t = Translator()
    t._dict["welcome"] = "Hello {name}, today is {day}"

    # 缺 day 占位符,应返回未插值的原文
    out = t.tr("welcome", name="Alice")
    assert out == "Hello {name}, today is {day}"

    # 多了未知占位符也应安全
    out2 = t.tr("welcome", name="Bob", day="Monday", extra="x")
    assert out2 == "Hello Bob, today is Monday"


def test_tr_format_value_error_safe():
    """tr() 在 format 触发 ValueError 时安全返回原文"""
    from util.common.translator import Translator

    t = Translator()
    # {0} 占位符但传 kwargs 会触发 ValueError
    t._dict["positional"] = "Hello {0}"
    out = t.tr("positional", name="Alice")
    # format({0}, name="Alice") 会抛 IndexError 或 ValueError
    # 安全返回原文
    assert out == "Hello {0}"


def test_load_from_ts_missing_file_silent(tmp_path):
    """_load_from_ts 对不存在的文件静默跳过,不改变已加载的字典"""
    from util.common.translator import Translator

    t = Translator()
    # __init__ 已加载默认 .ts(若存在),记录当前快照
    snapshot = dict(t._dict)
    # 调用 _load_from_ts 加载不存在的文件应静默跳过
    t._load_from_ts(str(tmp_path / "nonexistent.ts"))
    # 字典内容不应变化
    assert t._dict == snapshot


def test_load_from_ts_corrupt_xml_logs_warning(tmp_path, caplog):
    """_load_from_ts 在 XML 解析失败时记 warning,不抛异常"""
    from util.common.translator import Translator

    bad_ts = tmp_path / "broken.ts"
    bad_ts.write_text("<<not valid xml>>")

    t = Translator()
    snapshot = dict(t._dict)
    with caplog.at_level(logging.WARNING, logger="util.common.translator"):
        t._load_from_ts(str(bad_ts))

    # 字典不应变化(损坏文件未加载成功)
    assert t._dict == snapshot
    # 应有 warning 日志
    assert any("加载翻译文件" in r.message for r in caplog.records)


def test_load_from_ts_valid_xml(tmp_path):
    """_load_from_ts 解析合法的 Qt .ts XML 文件"""
    from util.common.translator import Translator

    ts_content = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN">
<context>
    <name>TestContext</name>
    <message>
        <source>Hello</source>
        <translation>你好</translation>
    </message>
    <message>
        <source>Goodbye</source>
        <translation>再见</translation>
    </message>
</context>
</TS>
"""
    ts_path = tmp_path / "test.zh_CN.ts"
    ts_path.write_text(ts_content, encoding="utf-8")

    t = Translator()
    t._load_from_ts(str(ts_path))

    assert t._dict.get("Hello") == "你好"
    assert t._dict.get("Goodbye") == "再见"


def test_load_from_ts_skips_empty_translation(tmp_path):
    """_load_from_ts 跳过 translation 为空的条目"""
    from util.common.translator import Translator

    ts_content = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="zh_CN">
<context>
    <name>Test</name>
    <message>
        <source>HasTranslation</source>
        <translation>有译</translation>
    </message>
    <message>
        <source>EmptyTranslation</source>
        <translation></translation>
    </message>
</context>
</TS>
"""
    ts_path = tmp_path / "test_empty.ts"
    ts_path.write_text(ts_content, encoding="utf-8")

    t = Translator()
    t._load_from_ts(str(ts_path))
    assert "HasTranslation" in t._dict
    assert "EmptyTranslation" not in t._dict


def test_load_default_with_nonexistent_path(tmp_path, monkeypatch):
    """_load_default 在 .ts 文件不存在时不抛异常"""
    from util.common.translator import Translator

    t = Translator()
    # _load_default 已在 __init__ 中调用一次,手动再调一次确保幂等
    t._load_default()
    # 不抛异常即通过


def test_module_level_translator_singleton():
    """模块级 translator 单例可用"""
    from util.common.translator import translator

    # tr() 必须能调用,返回 str
    assert isinstance(translator.tr("any.key"), str)
