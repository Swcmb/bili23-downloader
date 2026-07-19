# tests/unit/test_json.py
"""JSON 工具单元测试 - json_dumps / json_loads(orjson 回退)

覆盖:
- json_dumps 默认无缩进 / 显式 indent=None
- json_loads 解析 JSON 字符串
- _orjson_available True/False 两条路径都测一遍(通过 monkeypatch 强制走 fallback)
- orjson 与 stdlib json 输出兼容
"""
import json as stdlib_json
import pytest


def test_json_dumps_returns_str():
    """json_dumps 返回 str 类型(orjson 默认返回 bytes,需解码)"""
    from util.common._json import json_dumps

    out = json_dumps({"key": "value"})
    assert isinstance(out, str)
    assert stdlib_json.loads(out) == {"key": "value"}


def test_json_dumps_with_indent_none():
    """json_dumps 在 indent=None 时(orjson 模式)产生缩进输出"""
    from util.common._json import json_dumps

    out = json_dumps({"a": 1, "b": 2})
    # orjson 默认带缩进
    parsed = stdlib_json.loads(out)
    assert parsed == {"a": 1, "b": 2}


def test_json_loads_basic():
    """json_loads 解析简单 JSON 字符串"""
    from util.common._json import json_loads

    obj = json_loads('{"name": "bili23", "version": 3}')
    assert obj == {"name": "bili23", "version": 3}


def test_json_loads_array():
    """json_loads 解析数组"""
    from util.common._json import json_loads

    arr = json_loads("[1, 2, 3, 4]")
    assert arr == [1, 2, 3, 4]


def test_json_dumps_with_explicit_indent():
    """json_dumps 显式传入 indent=None,orjson 分支不传 option"""
    from util.common._json import json_dumps

    out = json_dumps([1, 2, 3], indent=None)
    assert stdlib_json.loads(out) == [1, 2, 3]


def test_json_roundtrip():
    """json_dumps + json_loads 往返一致"""
    from util.common._json import json_dumps, json_loads

    original = {
        "string": "hello",
        "int": 42,
        "list": [1, "two", 3.0],
        "nested": {"a": True, "b": None},
    }
    serialized = json_dumps(original)
    restored = json_loads(serialized)
    assert restored == original


# ==================================================================
# 强制走 stdlib json 回退路径
# ==================================================================

def test_json_dumps_fallback_to_stdlib(monkeypatch):
    """monkeypatch _orjson_available=False,强制走 stdlib json 分支"""
    import util.common._json as json_module

    monkeypatch.setattr(json_module, "_orjson_available", False)

    # 重新导入 stdlib json
    import json as stdlib_json_fallback
    monkeypatch.setattr(json_module, "json", stdlib_json_fallback)

    out = json_module.json_dumps({"k": "v"}, indent=2)
    assert stdlib_json_fallback.loads(out) == {"k": "v"}
    # 缩进应在输出中体现
    assert "  \"k\":" in out or '  "k":' in out


def test_json_loads_fallback_to_stdlib(monkeypatch):
    """monkeypatch _orjson_available=False,强制走 stdlib json.loads 分支"""
    import util.common._json as json_module

    monkeypatch.setattr(json_module, "_orjson_available", False)

    import json as stdlib_json_fallback
    monkeypatch.setattr(json_module, "json", stdlib_json_fallback)

    obj = json_module.json_loads('{"x": 1}')
    assert obj == {"x": 1}


def test_json_dumps_fallback_no_indent(monkeypatch):
    """stdlib json 分支默认 indent=None,输出为单行"""
    import util.common._json as json_module

    monkeypatch.setattr(json_module, "_orjson_available", False)
    import json as stdlib_json_fallback
    monkeypatch.setattr(json_module, "json", stdlib_json_fallback)

    out = json_module.json_dumps({"a": 1, "b": 2})
    assert "\n" not in out  # 单行
    assert stdlib_json_fallback.loads(out) == {"a": 1, "b": 2}


def test_orjson_flag_is_bool():
    """_orjson_available 必须是布尔值(导入阶段决定)"""
    from util.common import _json as json_module

    assert isinstance(json_module._orjson_available, bool)
