# tests/unit/test_cover_workers_coverage.py
"""cover/query_worker.py 与 cover/manager.py 单元测试

测试策略:
- CoverQueryWorker:mock network.request.SyncNetWorkRequest 与 cover_manager,
  覆盖 run/return_to_model/download_cover/query_url 全部分支(缓存命中/查询/下载/重试)
- CoverManager:mock CoverDatabase,覆盖 arrange_cover_id/create/query/request/
  placeholder/updateCache/getCache
- 不依赖真实网络,所有 httpx 调用通过 mock 替换
"""
import base64
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from util.common.io.directory import directory
from util.download.cover.cache import CoverCache
from util.download.cover.manager import CoverManager
from util.download.cover.query_worker import CoverQueryWorker


# ==================================================================
# 公共夹具
# ==================================================================

@pytest.fixture(autouse=True)
def _clear_cover_cache():
    """每个用例独立 CoverCache,避免相互干扰"""
    CoverCache.cache.clear()
    yield
    CoverCache.cache.clear()


@pytest.fixture
def cover_manager(tmp_path, monkeypatch):
    """创建指向 tmp_path 的 CoverManager,数据库隔离"""
    monkeypatch.setattr(directory, "data_dir", str(tmp_path))
    return CoverManager()


# ==================================================================
# CoverManager
# ==================================================================

def test_arrange_cover_id_returns_md5_hex(cover_manager):
    """arrange_cover_id 返回 32 位 md5 hex"""
    hash_id = cover_manager.arrange_cover_id("https://example.com/cover.jpg")
    assert isinstance(hash_id, str)
    assert len(hash_id) == 32


def test_arrange_cover_id_same_url_same_hash(cover_manager):
    """相同 URL 应得相同 hash_id(lru_cache 命中)"""
    h1 = cover_manager.arrange_cover_id("https://example.com/x.jpg")
    h2 = cover_manager.arrange_cover_id("https://example.com/x.jpg")
    assert h1 == h2


def test_arrange_cover_id_different_url_different_hash(cover_manager):
    """不同 URL 应得不同 hash_id"""
    h1 = cover_manager.arrange_cover_id("https://example.com/a.jpg")
    h2 = cover_manager.arrange_cover_id("https://example.com/b.jpg")
    assert h1 != h2


def test_create_calls_db_add_cover(cover_manager):
    """create 委托给 db_manager.add_cover"""
    mock_db = MagicMock()
    cover_manager.db_manager = mock_db

    cover_manager.create("hash-1", b"binary-data")
    mock_db.add_cover.assert_called_once_with("hash-1", b"binary-data")


def test_query_calls_db_query_cover(cover_manager):
    """query 委托给 db_manager.query_cover"""
    mock_db = MagicMock()
    mock_db.query_cover.return_value = b"raw-bytes"
    cover_manager.db_manager = mock_db

    result = cover_manager.query("hash-1")
    mock_db.query_cover.assert_called_once_with("hash-1")
    assert result == b"raw-bytes"


def test_query_returns_none_when_not_found(cover_manager):
    """query 在数据库无记录时返回 None"""
    mock_db = MagicMock()
    mock_db.query_cover.return_value = None
    cover_manager.db_manager = mock_db

    assert cover_manager.query("missing") is None


def test_placeholder_returns_none(cover_manager):
    """placeholder 在 CLI 版返回 None"""
    assert cover_manager.placeholder() is None
    assert cover_manager.placeholder(cover_size=128) is None


def test_update_cache_adds_new_entry(cover_manager):
    """updateCache 仅在 cover_id 不存在时写入"""
    CoverCache.cache.clear()
    cover_manager.updateCache("id-1", b"data-1")
    assert CoverCache.cache["id-1"] == b"data-1"


def test_update_cache_does_not_overwrite_existing(cover_manager):
    """updateCache 在 cover_id 已存在时不覆盖"""
    CoverCache.cache.clear()
    CoverCache.cache["id-1"] = b"original"
    cover_manager.updateCache("id-1", b"new")
    assert CoverCache.cache["id-1"] == b"original"


def test_get_cache_returns_value_when_exists(cover_manager):
    """getCache 在存在时返回 bytes"""
    CoverCache.cache.clear()
    CoverCache.cache["id-1"] = b"cached"
    assert cover_manager.getCache("id-1") == b"cached"


def test_get_cache_returns_none_when_missing(cover_manager):
    """getCache 在不存在时返回 None"""
    CoverCache.cache.clear()
    assert cover_manager.getCache("missing") is None


def test_request_creates_and_submits_worker(cover_manager, monkeypatch):
    """request 创建 CoverQueryWorker 并提交到 GlobalThreadPoolTask

    通过 patch 模块级 cover_manager.db_manager 让 worker.run() 命中缓存,
    避免触发真实网络下载。
    """
    # 将模块级单例的 db_manager 替换为 mock,让 worker.run() 走缓存命中分支
    from util.download.cover import manager as manager_module
    mock_db = MagicMock()
    mock_db.query_cover.return_value = base64.b64encode(b"raw")  # 缓存命中
    monkeypatch.setattr(manager_module.cover_manager, "db_manager", mock_db)

    submitted = []

    def fake_run(func, *args, **kwargs):
        submitted.append(func)
        func()
        from concurrent.futures import Future
        fut = Future()
        fut.set_result(None)
        return fut

    monkeypatch.setattr(
        "util.download.cover.manager.GlobalThreadPoolTask.run", fake_run
    )

    mock_model = MagicMock()
    manager_module.cover_manager.request(
        model=mock_model,
        query_id="q-1",
        cover_id="hash-1",
        cover_url="https://example.com/cover.jpg",
    )
    assert len(submitted) == 1
    mock_model.updateRowCover.assert_called_once()
    args = mock_model.updateRowCover.call_args[0]
    assert args[0] == "q-1"
    assert args[1] == b"raw"


# ==================================================================
# CoverQueryWorker - run() 缓存命中分支
# ==================================================================

def test_run_uses_cached_cover_when_available(monkeypatch):
    """run() 在缓存命中时不下载,直接 return_to_model"""
    mock_cover_manager = MagicMock()
    cached_b64 = base64.b64encode(b"cached-bytes").decode("utf-8")
    mock_cover_manager.query.return_value = cached_b64
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    mock_model = MagicMock()
    worker = CoverQueryWorker(
        model=mock_model,
        query_id="q-1",
        cover_id="hash-1",
        cover_url="https://example.com/cover.jpg",
    )
    worker.run()

    mock_cover_manager.query.assert_called_once_with("hash-1")
    mock_model.updateRowCover.assert_called_once_with("q-1", b"cached-bytes")


def test_run_uses_query_param_when_provided(monkeypatch):
    """run() 在 query_param 提供时先调用 query_url"""
    mock_cover_manager = MagicMock()
    cached_b64 = base64.b64encode(b"raw").decode("utf-8")
    # 第一次 query_url 设置 cover_id 后,query 返回缓存
    mock_cover_manager.query.return_value = cached_b64
    mock_cover_manager.arrange_cover_id.return_value = "new-hash"
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    # mock SyncNetWorkRequest.query_url 内部调用
    mock_request_class = MagicMock()
    mock_request_instance = MagicMock()
    mock_request_instance.run.return_value = {"data": {"cover": "https://real/cover.jpg"}}
    mock_request_class.return_value = mock_request_instance
    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest", mock_request_class
    )

    mock_model = MagicMock()
    worker = CoverQueryWorker(
        model=mock_model,
        query_id="q-1",
        cover_id="old-hash",
        cover_url="https://old/cover.jpg",
        query_param={"api_url": "https://api", "params": {"k": "v"}},
    )
    worker.run()

    # 调用方应使用从 query_url 拿到的真实 cover_id 与 cover_url
    mock_cover_manager.arrange_cover_id.assert_called_once_with("https://real/cover.jpg")
    mock_model.updateRowCover.assert_called_once_with("q-1", b"raw")


def test_run_returns_early_when_query_url_raises(monkeypatch):
    """run() 在 query_url 抛异常时直接返回,不调用 return_to_model"""
    mock_cover_manager = MagicMock()
    mock_cover_manager.query.return_value = None
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    mock_request_class = MagicMock()
    mock_request_instance = MagicMock()
    mock_request_instance.run.side_effect = RuntimeError("network error")
    mock_request_class.return_value = mock_request_instance
    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest", mock_request_class
    )

    mock_model = MagicMock()
    worker = CoverQueryWorker(
        model=mock_model,
        query_id="q-1",
        cover_id="old-hash",
        cover_url="https://old/cover.jpg",
        query_param={"api_url": "https://api", "params": {}},
    )
    worker.run()

    mock_model.updateRowCover.assert_not_called()


# ==================================================================
# CoverQueryWorker - run() 下载分支
# ==================================================================

def test_run_downloads_and_persists_when_not_cached(monkeypatch):
    """run() 在缓存未命中时下载并写入数据库"""
    mock_cover_manager = MagicMock()
    mock_cover_manager.query.return_value = None  # 缓存未命中
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    # mock download_cover 直接(避开 SyncNetWorkRequest)
    raw_bytes = b"downloaded-binary"
    b64_str = base64.b64encode(raw_bytes).decode("utf-8")

    mock_model = MagicMock()
    worker = CoverQueryWorker(
        model=mock_model,
        query_id="q-1",
        cover_id="hash-1",
        cover_url="https://example.com/cover.jpg",
    )
    worker.download_cover = MagicMock(return_value=(raw_bytes, b64_str))

    worker.run()

    worker.download_cover.assert_called_once()
    mock_cover_manager.create.assert_called_once_with("hash-1", b64_str)
    mock_model.updateRowCover.assert_called_once_with("q-1", raw_bytes)


def test_run_retries_download_on_http_error(monkeypatch):
    """run() 在 httpx.HTTPError 时最多重试 3 次"""
    mock_cover_manager = MagicMock()
    mock_cover_manager.query.return_value = None
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    mock_model = MagicMock()
    worker = CoverQueryWorker(
        model=mock_model,
        query_id="q-1",
        cover_id="hash-1",
        cover_url="https://example.com/cover.jpg",
    )
    # 前两次失败,第三次成功
    side_effects = [httpx.HTTPError("err1"), httpx.HTTPError("err2"), (b"ok", base64.b64encode(b"ok").decode())]
    worker.download_cover = MagicMock(side_effect=side_effects)

    worker.run()

    assert worker.download_cover.call_count == 3
    mock_model.updateRowCover.assert_called_once_with("q-1", b"ok")


def test_run_gives_up_after_three_http_errors(monkeypatch):
    """run() 在 3 次重试后仍失败时抛出异常并终止"""
    mock_cover_manager = MagicMock()
    mock_cover_manager.query.return_value = None
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    mock_model = MagicMock()
    worker = CoverQueryWorker(
        model=mock_model,
        query_id="q-1",
        cover_id="hash-1",
        cover_url="https://example.com/cover.jpg",
    )
    worker.download_cover = MagicMock(side_effect=httpx.HTTPError("always"))

    with pytest.raises(httpx.HTTPError):
        worker.run()

    assert worker.download_cover.call_count == 3
    mock_model.updateRowCover.assert_not_called()


# ==================================================================
# CoverQueryWorker - return_to_model
# ==================================================================

def test_return_to_model_calls_update_row_cover():
    """return_to_model 同步调用 model.updateRowCover"""
    mock_model = MagicMock()
    worker = CoverQueryWorker(
        model=mock_model,
        query_id="q-42",
        cover_id="h",
        cover_url="u",
    )
    worker.return_to_model(b"cover-bytes")
    mock_model.updateRowCover.assert_called_once_with("q-42", b"cover-bytes")


# ==================================================================
# CoverQueryWorker - download_cover
# ==================================================================

def test_download_cover_returns_bytes_and_base64(monkeypatch):
    """download_cover 返回 (bytes, base64_str)"""
    mock_request_class = MagicMock()
    mock_request_instance = MagicMock()
    mock_request_instance.run.return_value = b"raw-image-bytes"
    mock_request_class.return_value = mock_request_instance
    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest", mock_request_class
    )
    # ResponseType 也需要从同一模块导入,确保可用
    from util.network.request import ResponseType
    monkeypatch.setattr("util.network.request.ResponseType", ResponseType)

    worker = CoverQueryWorker(
        model=MagicMock(),
        query_id="q-1",
        cover_id="h",
        cover_url="https://example.com/cover.jpg",
    )

    raw, b64 = worker.download_cover()
    assert raw == b"raw-image-bytes"
    assert base64.b64decode(b64) == b"raw-image-bytes"
    # 验证 request 用 BYTES 类型
    args, kwargs = mock_request_class.call_args
    assert kwargs.get("response_type") == ResponseType.BYTES


# ==================================================================
# CoverQueryWorker - query_url
# ==================================================================

def test_query_url_updates_cover_id_and_url(monkeypatch):
    """query_url 成功时更新 cover_id 与 cover_url"""
    mock_cover_manager = MagicMock()
    mock_cover_manager.arrange_cover_id.return_value = "new-hash"
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    mock_request_class = MagicMock()
    mock_request_instance = MagicMock()
    mock_request_instance.run.return_value = {"data": {"cover": "https://real/cover.jpg"}}
    mock_request_class.return_value = mock_request_instance
    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest", mock_request_class
    )

    worker = CoverQueryWorker(
        model=MagicMock(),
        query_id="q-1",
        cover_id="old-hash",
        cover_url="https://old/cover.jpg",
        query_param={"api_url": "https://api.example.com", "params": {"k": "v"}},
    )
    worker.query_url()

    assert worker.cover_url == "https://real/cover.jpg"
    assert worker.cover_id == "new-hash"
    mock_cover_manager.arrange_cover_id.assert_called_once_with("https://real/cover.jpg")


def test_query_url_raises_when_response_cover_empty(monkeypatch):
    """query_url 在响应中 cover 为空时抛 ValueError"""
    mock_cover_manager = MagicMock()
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    mock_request_class = MagicMock()
    mock_request_instance = MagicMock()
    mock_request_instance.run.return_value = {"data": {"cover": ""}}
    mock_request_class.return_value = mock_request_instance
    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest", mock_request_class
    )

    worker = CoverQueryWorker(
        model=MagicMock(),
        query_id="q-1",
        cover_id="h",
        cover_url="u",
        query_param={"api_url": "https://api", "params": {}},
    )
    with pytest.raises(ValueError, match="获取封面 URL 失败"):
        worker.query_url()


def test_query_url_raises_when_response_missing_data(monkeypatch):
    """query_url 在响应缺 data 键时也抛 ValueError"""
    mock_cover_manager = MagicMock()
    monkeypatch.setattr(
        "util.download.cover.manager.cover_manager", mock_cover_manager
    )

    mock_request_class = MagicMock()
    mock_request_instance = MagicMock()
    mock_request_instance.run.return_value = {"code": 0}
    mock_request_class.return_value = mock_request_instance
    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest", mock_request_class
    )

    worker = CoverQueryWorker(
        model=MagicMock(),
        query_id="q-1",
        cover_id="h",
        cover_url="u",
        query_param={"api_url": "https://api", "params": {}},
    )
    with pytest.raises(ValueError):
        worker.query_url()
