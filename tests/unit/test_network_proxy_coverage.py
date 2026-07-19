# tests/unit/test_network_proxy_coverage.py
"""network/proxy.py 覆盖率补强测试

覆盖 Proxy 类的所有方法:
- __init__:从 config 加载各字段
- set_data:从 dict 写入各字段
- get_proxies:disabled / enabled HTTP (无认证) / enabled HTTP (有认证)
"""
import pytest

from util.common.config import config
from util.common.enum import ProxyType
from util.network.proxy import Proxy


# ==================================================================
# __init__ - 从 config 加载
# ==================================================================

def test_init_loads_from_config(monkeypatch):
    """__init__ 从 config 加载 enabled/type/server/port/uname/password"""
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "proxy_enabled": True,
        "proxy_type": ProxyType.HTTP,
        "proxy_server": "1.2.3.4",
        "proxy_port": 8080,
        "proxy_uname": "user",
        "proxy_password": "pass",
    }.get(key, default))

    p = Proxy()
    assert p.enabled is True
    assert p.type == ProxyType.HTTP
    assert p.server == "1.2.3.4"
    assert p.port == 8080
    assert p.uname == "user"
    assert p.password == "pass"


# ==================================================================
# set_data
# ==================================================================

def test_set_data_overrides_fields():
    """set_data 用 dict 覆盖各字段,并强制 enabled=True"""
    p = Proxy()
    p.enabled = False
    data = {
        "type": ProxyType.HTTP,
        "server": "5.6.7.8",
        "port": 1080,
        "uname": "u2",
        "password": "p2",
    }
    p.set_data(data)
    assert p.enabled is True
    assert p.server == "5.6.7.8"
    assert p.port == 1080
    assert p.uname == "u2"
    assert p.password == "p2"


def test_set_data_with_missing_keys():
    """dict 中缺失的键对应字段为 None"""
    p = Proxy()
    p.set_data({"type": ProxyType.HTTP, "server": "1.1.1.1"})
    assert p.enabled is True
    assert p.port is None
    assert p.uname is None
    assert p.password is None


# ==================================================================
# get_proxies - disabled
# ==================================================================

def test_get_proxies_disabled_returns_none():
    p = Proxy()
    p.enabled = False
    assert p.get_proxies() is None


# ==================================================================
# get_proxies - HTTP, 无认证
# ==================================================================

def test_get_proxies_http_without_auth():
    p = Proxy()
    p.enabled = True
    p.type = ProxyType.HTTP
    p.server = "1.2.3.4"
    p.port = 8080
    p.uname = None
    p.password = None
    result = p.get_proxies()
    assert result == {
        "http": "http://1.2.3.4:8080",
        "https": "http://1.2.3.4:8080",
    }


def test_get_proxies_http_with_empty_auth():
    """uname/password 为空字符串时也走无认证路径(逻辑仅判断 truthy)"""
    p = Proxy()
    p.enabled = True
    p.type = ProxyType.HTTP
    p.server = "1.2.3.4"
    p.port = 8080
    p.uname = ""
    p.password = ""
    result = p.get_proxies()
    assert result == {
        "http": "http://1.2.3.4:8080",
        "https": "http://1.2.3.4:8080",
    }


# ==================================================================
# get_proxies - HTTP, 有认证
# ==================================================================

def test_get_proxies_http_with_auth():
    p = Proxy()
    p.enabled = True
    p.type = ProxyType.HTTP
    p.server = "1.2.3.4"
    p.port = 8080
    p.uname = "alice"
    p.password = "secret"
    result = p.get_proxies()
    assert result == {
        "http": "http://alice:secret@1.2.3.4:8080",
        "https": "http://alice:secret@1.2.3.4:8080",
    }


def test_get_proxies_http_with_auth_only_uname():
    """只有 uname 没有 password -> 走无认证路径(truthy 检查)"""
    p = Proxy()
    p.enabled = True
    p.type = ProxyType.HTTP
    p.server = "1.2.3.4"
    p.port = 8080
    p.uname = "alice"
    p.password = None
    result = p.get_proxies()
    # password 为 None -> falsy -> 走无认证格式
    assert "@" not in result["http"]


# ==================================================================
# get_proxies - 未匹配的 type(无 case 命中)
# ==================================================================

def test_get_proxies_http_with_unknown_type_returns_none():
    """type 不匹配任何 case(match 无 default)时返回 None"""
    p = Proxy()
    p.enabled = True
    p.type = "unknown_type"  # 非 ProxyType.HTTP
    p.server = "1.2.3.4"
    p.port = 8080
    result = p.get_proxies()
    assert result is None
