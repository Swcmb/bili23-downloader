# tests/unit/test_network_request_coverage.py
"""network/request.py 覆盖率补强测试

覆盖:
- 模块级函数:get_mounts / get_cookies / update_cookies / _apply_cookies
                  _create_client / _ensure_client / get_client
- _LazyClientProxy __getattr__ / __repr__
- SyncNetWorkRequest.__init__ / run (各 ResponseType) / update_headers
- NetworkRequestWorker.run / set_proxies

外部依赖全部 mock:httpx.Client / httpx.HTTPTransport / Proxy / get_cookies。
"""
from unittest.mock import MagicMock, patch, call

import httpx
import pytest

from util.common.config import config
from util.network import request as request_module
from util.network.request import (
    RequestType,
    ResponseType,
    SyncNetWorkRequest,
    NetworkRequestWorker,
    _LazyClientProxy,
    get_mounts,
    get_cookies,
    update_cookies,
    _apply_cookies,
    _create_client,
    _ensure_client,
    get_client,
)


# ==================================================================
# 公共夹具:每个测试前重置单例 client
# ==================================================================

@pytest.fixture(autouse=True)
def _reset_request_module_state(monkeypatch):
    """重置 request._client 单例,避免跨测试影响"""
    monkeypatch.setattr(request_module, "_client", None)
    yield
    monkeypatch.setattr(request_module, "_client", None)


# ==================================================================
# get_mounts
# ==================================================================

def test_get_mounts_without_proxies_returns_none():
    assert get_mounts(None) is None
    assert get_mounts({}) is None


def test_get_mounts_with_http_proxy():
    """有 http 代理时返回 mounts dict"""
    with patch("util.network.request.httpx.HTTPTransport") as fake_transport:
        mounts = get_mounts({"http": "http://1.2.3.4:8080"})
        assert "http://" in mounts
        assert "https://" in mounts
        # HTTPTransport 被调用 2 次(http 和 https 各一次)
        assert fake_transport.call_count == 2


def test_get_mounts_prefers_http_over_https():
    """proxies 同时含 http 和 https 时优先使用 http"""
    with patch("util.network.request.httpx.HTTPTransport") as fake_transport:
        get_mounts({"http": "http://a", "https": "http://b"})
        # 验证传给 HTTPTransport 的 proxy 参数是 http
        _, kwargs = fake_transport.call_args
        assert kwargs["proxy"] == "http://a"


def test_get_mounts_with_only_https_falls_back():
    """无 http 键时回退到 https 键"""
    with patch("util.network.request.httpx.HTTPTransport"):
        mounts = get_mounts({"https": "http://b"})
        assert mounts is not None


# ==================================================================
# get_cookies
# ==================================================================

def test_get_cookies_not_logged_in(monkeypatch):
    """未登录时返回基础 cookie,不含 bili_jct 等"""
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "uuid": "uuid-val",
        "b_lsid": "lsid-val",
        "b_nut": "100",
        "bili_ticket": "ticket-val",
        "bili_ticket_expires": "9999",
        "buvid_fp": "fp-val",
        "buvid3": "bv3-val",
        "buvid4": "bv4-val",
        "is_login": False,
    }.get(key, default))

    cookies = get_cookies()
    assert cookies["_uuid"] == "uuid-val"
    assert cookies["b_lsid"] == "lsid-val"
    assert cookies["b_nut"] == "100"  # str 包装
    assert cookies["CURRENT_FNVAL"] == "4048"
    assert cookies["CURRENT_QUALITY"] == "0"
    # 未登录不应包含这些
    assert "bili_jct" not in cookies
    assert "SESSDATA" not in cookies


def test_get_cookies_logged_in(monkeypatch):
    """登录后 cookie 含 bili_jct / DedeUserID / SESSDATA 等"""
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "uuid": "u", "b_lsid": "l", "b_nut": 1, "bili_ticket": "t",
        "bili_ticket_expires": 2, "buvid_fp": "f", "buvid3": "3", "buvid4": "4",
        "is_login": True,
        "bili_jct": "jct", "DedeUserID": "uid",
        "DedeUserID__ckMd5": "md5", "SESSDATA": "sess",
    }.get(key, default))

    cookies = get_cookies()
    assert cookies["bili_jct"] == "jct"
    assert cookies["DedeUserID"] == "uid"
    assert cookies["DedeUserID__ckMd5"] == "md5"
    assert cookies["SESSDATA"] == "sess"


# ==================================================================
# _apply_cookies
# ==================================================================

def test_apply_cookies_sets_all_entries():
    """_apply_cookies 遍历 dict 调用 client_obj.cookies.set"""
    fake_client = MagicMock()
    cookies = {"k1": "v1", "k2": "v2"}
    _apply_cookies(fake_client, cookies)
    assert fake_client.cookies.set.call_count == 2
    # 验证 domain / path 参数
    for c in fake_client.cookies.set.call_args_list:
        _, kwargs = c
        assert kwargs["domain"] == ".bilibili.com"
        assert kwargs["path"] == "/"


# ==================================================================
# _create_client - 启用代理时记录日志
# ==================================================================

def test_create_client_without_proxy(monkeypatch):
    """config 中未启用代理时,_create_client 不调用 Proxy.get_proxies"""
    fake_proxy_instance = MagicMock()
    fake_proxy_instance.get_proxies.return_value = None
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "proxy_enabled": False,
    }.get(key, default))
    # Proxy 在 _create_client 内部通过 `from .proxy import Proxy` 引入,
    # 需 patch util.network.proxy.Proxy 才能影响内部局部名
    monkeypatch.setattr("util.network.proxy.Proxy", MagicMock(return_value=fake_proxy_instance))

    with patch("util.network.request.httpx.Client") as fake_client_cls:
        _create_client()
        fake_client_cls.assert_called_once()


def test_create_client_with_proxy(monkeypatch):
    """启用代理时调用 Proxy().get_proxies()"""
    fake_proxy_instance = MagicMock()
    fake_proxy_instance.get_proxies.return_value = {"http": "http://1.2.3.4"}
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "proxy_enabled": True,
        "proxy_type": "http",
        "proxy_server": "1.2.3.4",
        "proxy_port": 8080,
    }.get(key, default))
    monkeypatch.setattr("util.network.proxy.Proxy", MagicMock(return_value=fake_proxy_instance))

    with patch("util.network.request.httpx.Client") as fake_client_cls:
        _create_client()
        fake_proxy_instance.get_proxies.assert_called_once()


# ==================================================================
# _ensure_client / get_client - 单例缓存
# ==================================================================

def test_ensure_client_creates_singleton(monkeypatch):
    """_ensure_client 创建后再次调用返回同一实例"""
    fake_client_obj = MagicMock()
    fake_cookies = {"k1": "v1"}

    with patch("util.network.request._create_client", return_value=fake_client_obj) as fake_create, \
         patch("util.network.request._load_persisted_cookies", return_value=fake_cookies) as fake_load:
        c1 = _ensure_client()
        c2 = _ensure_client()
        assert c1 is c2 is fake_client_obj
        # _create_client / _load_persisted_cookies 仅被调用一次
        fake_create.assert_called_once()
        fake_load.assert_called_once()


def test_get_client_delegates_to_ensure_client(monkeypatch):
    """get_client 直接委托 _ensure_client"""
    fake_client = MagicMock()
    monkeypatch.setattr(request_module, "_client", fake_client)
    assert get_client() is fake_client


# ==================================================================
# _LazyClientProxy
# ==================================================================

def test_lazy_client_proxy_getattr_delegates():
    """_LazyClientProxy.__getattr__ 委托到 get_client() 返回的对象"""
    fake_client = MagicMock()
    fake_client.some_attr = "value"
    with patch("util.network.request.get_client", return_value=fake_client):
        proxy = _LazyClientProxy()
        assert proxy.some_attr == "value"


def test_lazy_client_proxy_repr():
    """_LazyClientProxy.__repr__ 返回内部 client 的 repr"""
    fake_client = MagicMock()
    fake_client.__repr__ = lambda self: "<FakeClient>"
    with patch("util.network.request.get_client", return_value=fake_client):
        proxy = _LazyClientProxy()
        assert repr(proxy) == "<FakeClient>"


# ==================================================================
# update_cookies - 整合 _ensure_client + _apply_cookies
# ==================================================================

def test_update_cookies_applies_to_client(monkeypatch):
    """update_cookies 将新 cookies 应用到 _ensure_client 返回的对象"""
    fake_client = MagicMock()
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "uuid": "u", "b_lsid": "l", "b_nut": 1, "bili_ticket": "t",
        "bili_ticket_expires": 2, "buvid_fp": "f", "buvid3": "3", "buvid4": "4",
        "is_login": False,
    }.get(key, default))

    update_cookies()
    # 应调用 cookies.set 至少一次
    assert fake_client.cookies.set.call_count >= 1


# ==================================================================
# SyncNetWorkRequest.__init__
# ==================================================================

def test_sync_network_request_init_defaults():
    req = SyncNetWorkRequest("https://example.com")
    assert req.url == "https://example.com"
    assert req.request_type == RequestType.GET
    assert req.response_type == ResponseType.JSON
    assert req.raise_for_status is True
    assert req.proxies is None


def test_sync_network_request_init_custom():
    req = SyncNetWorkRequest(
        "https://example.com",
        request_type=RequestType.POST,
        params={"a": "1"},
        response_type=ResponseType.TEXT,
        raise_for_status=False,
        json_data={"k": "v"},
        data={"d": "e"},
        content_type="application/json",
    )
    assert req.request_type == RequestType.POST
    assert req.params == {"a": "1"}
    assert req.response_type == ResponseType.TEXT
    assert req.raise_for_status is False
    assert req.json_data == {"k": "v"}
    assert req.data == {"d": "e"}
    assert req.content_type == "application/json"


# ==================================================================
# SyncNetWorkRequest.run - 各 ResponseType 路径
# ==================================================================

def _make_response(*, text='{"k": "v"}', content=b"bytes", headers={"X": "Y"}, url="https://example.com"):
    resp = MagicMock()
    resp.text = text
    resp.content = content
    resp.headers = headers
    resp.url = url
    return resp


def test_run_returns_text(monkeypatch):
    fake_client = MagicMock()
    fake_client.request.return_value = _make_response(text="plain text")
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", response_type=ResponseType.TEXT, raise_for_status=False)
    assert req.run() == "plain text"


def test_run_returns_json(monkeypatch):
    """JSON 路径调用 json_loads"""
    fake_client = MagicMock()
    fake_client.request.return_value = _make_response(text='{"k": "v"}')
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", response_type=ResponseType.JSON, raise_for_status=False)
    result = req.run()
    assert result == {"k": "v"}


def test_run_returns_bytes(monkeypatch):
    fake_client = MagicMock()
    fake_client.request.return_value = _make_response(content=b"rawbytes")
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", response_type=ResponseType.BYTES, raise_for_status=False)
    assert req.run() == b"rawbytes"


def test_run_returns_headers(monkeypatch):
    fake_client = MagicMock()
    fake_client.request.return_value = _make_response(headers={"X-Custom": "value"})
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", response_type=ResponseType.HEADERS, raise_for_status=False)
    result = req.run()
    assert result == {"X-Custom": "value"}


def test_run_returns_redirect_url(monkeypatch):
    fake_client = MagicMock()
    fake_client.request.return_value = _make_response(url="https://redirected.example.com")
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", response_type=ResponseType.REDIRECT_URL, raise_for_status=False)
    assert req.run() == "https://redirected.example.com"


def test_run_returns_response_object(monkeypatch):
    fake_client = MagicMock()
    fake_response = _make_response()
    fake_client.request.return_value = fake_response
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", response_type=ResponseType.RESPONSE, raise_for_status=False)
    assert req.run() is fake_response


# ==================================================================
# SyncNetWorkRequest.run - raise_for_status
# ==================================================================

def test_run_raises_for_status_when_enabled(monkeypatch):
    """raise_for_status=True 时调用 response.raise_for_status()"""
    fake_response = _make_response()
    fake_response.raise_for_status = MagicMock()
    fake_client = MagicMock()
    fake_client.request.return_value = fake_response
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", raise_for_status=True)
    req.run()
    fake_response.raise_for_status.assert_called_once()


# ==================================================================
# SyncNetWorkRequest.run - proxies 路径
# ==================================================================

def test_run_with_proxies_uses_temp_client(monkeypatch):
    """proxies 非 None 时构造临时 httpx.Client"""
    fake_response = _make_response()
    fake_temp_client = MagicMock()
    fake_temp_client.request.return_value = fake_response
    fake_temp_client.__enter__ = MagicMock(return_value=fake_temp_client)
    fake_temp_client.__exit__ = MagicMock(return_value=False)
    monkeypatch.setattr(request_module, "_client", MagicMock())
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    with patch("util.network.request.httpx.Client", return_value=fake_temp_client):
        req = SyncNetWorkRequest("https://example.com", raise_for_status=False)
        # SyncNetWorkRequest 无 set_proxies 方法,直接赋值给 self.proxies
        req.proxies = {"http": "http://1.2.3.4"}
        req.run()
        fake_temp_client.request.assert_called_once()


# ==================================================================
# SyncNetWorkRequest.update_headers
# ==================================================================

def test_update_headers_sets_referer_and_user_agent(monkeypatch):
    """update_headers 始终设置 Referer 与 User-Agent"""
    fake_client = MagicMock()
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "MyUA" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", raise_for_status=False)
    req.update_headers()
    fake_client.headers.update.assert_called_once()
    headers_arg = fake_client.headers.update.call_args[0][0]
    assert headers_arg["Referer"] == "https://www.bilibili.com/"
    assert headers_arg["User-Agent"] == "MyUA"


def test_update_headers_with_content_type(monkeypatch):
    """指定 content_type 时设置 Content-Type"""
    fake_client = MagicMock()
    fake_client.headers = {}  # dict 模式
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "MyUA" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", content_type="application/json", raise_for_status=False)
    req.update_headers()
    assert fake_client.headers["Content-Type"] == "application/json"
    # 同时也设置了 Referer / User-Agent
    assert fake_client.headers["Referer"] == "https://www.bilibili.com/"
    assert fake_client.headers["User-Agent"] == "MyUA"


def test_update_headers_without_content_type_removes_existing(monkeypatch):
    """未指定 content_type 时移除已存在的 Content-Type"""
    fake_client = MagicMock()
    # 使用真实 dict 以便 in / pop 真实生效
    fake_client.headers = {"Content-Type": "old"}
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "MyUA" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", raise_for_status=False)
    req.update_headers()
    # Content-Type 应被 pop 掉
    assert "Content-Type" not in fake_client.headers


def test_update_headers_without_content_type_no_existing(monkeypatch):
    """未指定 content_type 且原本无 Content-Type 时不调用 pop"""
    fake_client = MagicMock()
    fake_client.headers = {}  # 真实空 dict
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "MyUA" if key == "user_agent" else default)

    req = SyncNetWorkRequest("https://example.com", raise_for_status=False)
    req.update_headers()
    # dict 中不应有 Content-Type
    assert "Content-Type" not in fake_client.headers


# ==================================================================
# NetworkRequestWorker - run / set_proxies
# ==================================================================

def test_worker_run_success_emits_success_and_finished(monkeypatch):
    """run() 成功时依次 emit success / finished,重置 proxies"""
    fake_response = {"k": "v"}
    monkeypatch.setattr(
        SyncNetWorkRequest, "run", lambda self: fake_response
    )
    fake_client = MagicMock()
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    worker = NetworkRequestWorker("https://example.com", raise_for_status=False)
    success_calls = []
    error_calls = []
    finished_calls = []
    worker.success.connect(lambda r: success_calls.append(r))
    worker.error.connect(lambda e: error_calls.append(e))
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.set_proxies({"http": "http://1.2.3.4"})
    worker.run()

    assert success_calls == [fake_response]
    assert error_calls == []
    assert finished_calls == [None]
    # proxies 应被重置
    assert worker.proxies is None


def test_worker_run_error_emits_error_and_finished(monkeypatch):
    """run() 抛异常时 emit error(str(e)) / finished,重置 proxies"""
    def _raise(self):
        raise ValueError("network error")

    monkeypatch.setattr(SyncNetWorkRequest, "run", _raise)
    fake_client = MagicMock()
    monkeypatch.setattr(request_module, "_client", fake_client)
    monkeypatch.setattr(config, "get", lambda key, default=None: "ua" if key == "user_agent" else default)

    worker = NetworkRequestWorker("https://example.com", raise_for_status=False)
    success_calls = []
    error_calls = []
    finished_calls = []
    worker.success.connect(lambda r: success_calls.append(r))
    worker.error.connect(lambda e: error_calls.append(e))
    worker.finished.connect(lambda: finished_calls.append(None))

    worker.run()

    assert success_calls == []
    assert len(error_calls) == 1
    assert "network error" in error_calls[0]
    assert finished_calls == [None]


def test_worker_set_proxies():
    """set_proxies 存储 proxies"""
    worker = NetworkRequestWorker("https://example.com", raise_for_status=False)
    worker.set_proxies({"http": "http://proxy"})
    assert worker.proxies == {"http": "http://proxy"}


# ==================================================================
# NetworkRequestWorker.__init__ - 继承 WorkerBase
# ==================================================================

def test_worker_inherits_worker_base_signals():
    """NetworkRequestWorker 应有 success/error/finished 三个 Signal(来自 WorkerBase)"""
    worker = NetworkRequestWorker("https://example.com", raise_for_status=False)
    from util.common.signal_bus import Signal
    assert isinstance(worker.success, Signal)
    assert isinstance(worker.error, Signal)
    assert isinstance(worker.finished, Signal)


def test_worker_is_stopped_initially_false():
    """新构造的 worker.is_stopped 应为 False"""
    worker = NetworkRequestWorker("https://example.com", raise_for_status=False)
    assert worker.is_stopped is False


def test_worker_stop_sets_is_stopped():
    """stop() 后 is_stopped 为 True"""
    worker = NetworkRequestWorker("https://example.com", raise_for_status=False)
    worker.stop()
    assert worker.is_stopped is True
