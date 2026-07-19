# tests/unit/test_parse_preview_worker_coverage.py
"""T6 覆盖率补强 - src/util/parse/preview/worker.py

覆盖目标:
- QueryInfoWorker.__init__
- QueryInfoWorker.run(DASH/MP4/FLV/M4A 分支 + 异常路径 + file_size=0 抛 RuntimeError)
- QueryInfoWorker.query_dash_file_size / query_mp4_file_size
- QueryInfoWorker.get_dash_file_size(mock resolve_download_url)
- QueryInfoWorker.get_mp4_file_size(mock SyncNetWorkRequest,聚合 size/timelength)
- QueryInfoWorker.get_download_urls(list/str 各 key 分支)
- QueryInfoWorker.get_query_url(qn 占位替换)
- QueryInfoWorker.get_durl_list(video/bangumi/cheese parser_type 分支)
"""
from unittest.mock import MagicMock, patch

import pytest

from util.common.enum import MediaType
from util.parse.preview.info import PreviewerInfo
from util.parse.preview.worker import QueryInfoWorker


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------
def test_query_info_worker_init_defaults():
    """__init__ 应初始化 media_info/file_size/break_flag 与三个信号"""
    media_info = {"id": 1}
    worker = QueryInfoWorker(media_info)

    assert worker.media_info is media_info
    assert worker.file_size == 0
    assert worker.break_flag is False
    assert hasattr(worker, "success")
    assert hasattr(worker, "error")
    assert hasattr(worker, "finished")


# ---------------------------------------------------------------------------
# get_download_urls
# ---------------------------------------------------------------------------
def test_get_download_urls_collects_list_and_str_values():
    """get_download_urls 应聚合 list 与 str 类型的 URL 候选"""
    media_info = {
        "baseUrl": "https://base.url/video",
        "backupUrl": ["https://b1.url/video", "https://b2.url/video"],
        "url": "https://single.url/video",
    }
    worker = QueryInfoWorker(media_info)

    urls = worker.get_download_urls(media_info)

    assert "https://base.url/video" in urls
    assert "https://b1.url/video" in urls
    assert "https://b2.url/video" in urls
    assert "https://single.url/video" in urls
    assert len(urls) == 4


def test_get_download_urls_ignores_non_list_str_values():
    """非 list/str 的值应被忽略"""
    media_info = {
        "baseUrl": 12345,            # int,忽略
        "base_url": None,            # None,忽略
        "backupUrl": "https://ok.url",  # str,保留
        "unknown_key": "ignored",    # 不在候选 key 列表中,忽略
    }
    worker = QueryInfoWorker(media_info)
    urls = worker.get_download_urls(media_info)
    assert urls == ["https://ok.url"]


def test_get_download_urls_handles_empty_media_info():
    """空 media_info 应返回空列表"""
    worker = QueryInfoWorker({})
    assert worker.get_download_urls({}) == []


# ---------------------------------------------------------------------------
# get_query_url
# ---------------------------------------------------------------------------
def test_get_query_url_replaces_quality_id():
    """get_query_url 应把 qn=80 替换为指定 quality_id"""
    PreviewerInfo.info_data = {"query_url": "https://api.test/?qn=80&foo=bar"}
    try:
        worker = QueryInfoWorker({"id": 64})
        url = worker.get_query_url(64)
        assert url == "https://api.test/?qn=64&foo=bar"
    finally:
        PreviewerInfo.info_data = {}


def test_get_query_url_no_qn_80_keeps_url_unchanged():
    """query_url 中不含 qn=80 时替换无效,保持原样"""
    PreviewerInfo.info_data = {"query_url": "https://api.test/?foo=bar"}
    try:
        worker = QueryInfoWorker({"id": 32})
        url = worker.get_query_url(32)
        assert url == "https://api.test/?foo=bar"
    finally:
        PreviewerInfo.info_data = {}


# ---------------------------------------------------------------------------
# get_durl_list
# ---------------------------------------------------------------------------
def test_get_durl_list_video_branch():
    """parser_type=video 应从 response.data.durl 取列表"""
    PreviewerInfo.info_data = {"parser_type": "video"}
    try:
        worker = QueryInfoWorker({})
        response = {"data": {"durl": [{"size": 100}]}}
        assert worker.get_durl_list(response) == [{"size": 100}]
    finally:
        PreviewerInfo.info_data = {}


def test_get_durl_list_bangumi_branch():
    """parser_type=bangumi 应从 response.result.durl 取列表"""
    PreviewerInfo.info_data = {"parser_type": "bangumi"}
    try:
        worker = QueryInfoWorker({})
        response = {"result": {"durl": [{"size": 200}]}}
        assert worker.get_durl_list(response) == [{"size": 200}]
    finally:
        PreviewerInfo.info_data = {}


def test_get_durl_list_cheese_branch():
    """parser_type=cheese 应从 response.data.durl 取列表"""
    PreviewerInfo.info_data = {"parser_type": "cheese"}
    try:
        worker = QueryInfoWorker({})
        response = {"data": {"durl": [{"size": 300}]}}
        assert worker.get_durl_list(response) == [{"size": 300}]
    finally:
        PreviewerInfo.info_data = {}


# ---------------------------------------------------------------------------
# get_dash_file_size
# ---------------------------------------------------------------------------
def test_get_dash_file_size_returns_resolved_size():
    """get_dash_file_size 应调用 resolve_download_url 并更新 file_size"""
    worker = QueryInfoWorker({"baseUrl": "https://test.url"})
    fake_result = {"file_size": 9999}

    with patch("util.network.download_url.resolve_download_url", return_value=fake_result) as m:
        size = worker.get_dash_file_size(["https://test.url"])

    assert size == 9999
    assert worker.file_size == 9999
    m.assert_called_once_with(["https://test.url"], min_file_size=10240)


def test_get_dash_file_size_empty_urls_still_calls_resolve():
    """空 URL 列表也应调用 resolve_download_url,以保持一致行为"""
    worker = QueryInfoWorker({})
    with patch("util.network.download_url.resolve_download_url", return_value={"file_size": 0}):
        size = worker.get_dash_file_size([])
    assert size == 0
    assert worker.file_size == 0


# ---------------------------------------------------------------------------
# get_mp4_file_size
# ---------------------------------------------------------------------------
def test_get_mp4_file_size_aggregates_size_and_timelength():
    """get_mp4_file_size 应聚合 durl 列表中的 size 与 length"""
    PreviewerInfo.info_data = {"parser_type": "video"}
    media_info = {"id": 80, "timelength": 0}
    worker = QueryInfoWorker(media_info)

    fake_request = MagicMock()
    fake_request.run.return_value = {
        "data": {"durl": [{"size": 100, "length": 10}, {"size": 200, "length": 20}]}
    }

    try:
        with patch("util.network.request.SyncNetWorkRequest", return_value=fake_request):
            worker.get_mp4_file_size("https://api.test/?qn=80")
    finally:
        PreviewerInfo.info_data = {}

    assert worker.file_size == 300
    assert media_info["timelength"] == 30
    fake_request.run.assert_called_once()


def test_get_mp4_file_size_handles_missing_keys_in_entry():
    """durl 条目缺失 size/length 时应使用 .get 默认值 0,不抛异常"""
    PreviewerInfo.info_data = {"parser_type": "video"}
    media_info = {"id": 80, "timelength": 0}
    worker = QueryInfoWorker(media_info)

    fake_request = MagicMock()
    fake_request.run.return_value = {"data": {"durl": [{}, {"size": 50}]}}

    try:
        with patch("util.network.request.SyncNetWorkRequest", return_value=fake_request):
            worker.get_mp4_file_size("https://api.test/?qn=80")
    finally:
        PreviewerInfo.info_data = {}

    assert worker.file_size == 50
    assert media_info["timelength"] == 0


# ---------------------------------------------------------------------------
# query_dash_file_size / query_mp4_file_size(组合方法)
# ---------------------------------------------------------------------------
def test_query_dash_file_size_invokes_get_dash_file_size():
    """query_dash_file_size 应先取 download_urls,再调用 get_dash_file_size"""
    media_info = {"baseUrl": "https://test.url"}
    worker = QueryInfoWorker(media_info)

    with patch.object(worker, "get_dash_file_size", return_value=8888) as m:
        # query_dash_file_size 无返回值,验证调用参数即可
        worker.query_dash_file_size()

    m.assert_called_once_with(["https://test.url"])


def test_query_mp4_file_size_invokes_get_mp4_file_size():
    """query_mp4_file_size 应先取 query_url,再调用 get_mp4_file_size"""
    PreviewerInfo.info_data = {"query_url": "https://api.test/?qn=80"}
    media_info = {"id": 64}
    worker = QueryInfoWorker(media_info)

    try:
        with patch.object(worker, "get_mp4_file_size") as m:
            worker.query_mp4_file_size()
    finally:
        PreviewerInfo.info_data = {}

    m.assert_called_once_with("https://api.test/?qn=64")


# ---------------------------------------------------------------------------
# run - DASH 路径
# ---------------------------------------------------------------------------
def test_run_dash_success_emits_success_and_finished():
    """run 在 DASH 模式且 file_size>0 时应 emit success/finished"""
    PreviewerInfo.media_type = MediaType.DASH
    media_info = {"baseUrl": "https://test.url"}
    worker = QueryInfoWorker(media_info)

    success_payload = []
    finished_count = {"n": 0}
    worker.success.connect(lambda *a, **kw: success_payload.append((a, kw)))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    try:
        with patch("util.network.download_url.resolve_download_url",
                   return_value={"file_size": 50000}):
            worker.run()
    finally:
        PreviewerInfo.media_type = MediaType.UNKNOWN

    assert success_payload == [((media_info, 50000), {})]
    assert finished_count["n"] == 1
    assert worker.file_size == 50000


def test_run_dash_zero_file_size_emits_error():
    """run 在 DASH 模式且 file_size=0 时应 emit error(RuntimeError)"""
    PreviewerInfo.media_type = MediaType.DASH
    worker = QueryInfoWorker({"baseUrl": "https://test.url"})

    error_payload = []
    finished_count = {"n": 0}
    worker.error.connect(lambda e: error_payload.append(e))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    try:
        with patch("util.network.download_url.resolve_download_url", return_value={"file_size": 0}):
            worker.run()
    finally:
        PreviewerInfo.media_type = MediaType.UNKNOWN

    assert error_payload == ["无法获取文件大小"]
    assert finished_count["n"] == 1


# ---------------------------------------------------------------------------
# run - MP4 / FLV 路径
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("media_type", [MediaType.MP4, MediaType.FLV])
def test_run_mp4_flv_success(media_type):
    """MP4/FLV 模式应通过 query_mp4_file_size 路径聚合大小"""
    PreviewerInfo.media_type = media_type
    PreviewerInfo.info_data = {"parser_type": "video", "query_url": "https://api.test/?qn=80"}
    media_info = {"id": 80, "timelength": 0}
    worker = QueryInfoWorker(media_info)

    success_payload = []
    worker.success.connect(lambda *a, **kw: success_payload.append(a))

    fake_request = MagicMock()
    fake_request.run.return_value = {"data": {"durl": [{"size": 10000, "length": 100}]}}

    try:
        with patch("util.network.request.SyncNetWorkRequest", return_value=fake_request):
            worker.run()
    finally:
        PreviewerInfo.media_type = MediaType.UNKNOWN
        PreviewerInfo.info_data = {}

    assert worker.file_size == 10000
    assert success_payload == [(media_info, 10000)]


def test_run_mp4_zero_file_size_emits_error():
    """MP4 模式且 durl 为空时,file_size 保持 0 应 emit error"""
    PreviewerInfo.media_type = MediaType.MP4
    PreviewerInfo.info_data = {"parser_type": "video", "query_url": "https://api.test/?qn=80"}
    worker = QueryInfoWorker({"id": 80, "timelength": 0})

    error_payload = []
    worker.error.connect(lambda e: error_payload.append(e))

    fake_request = MagicMock()
    fake_request.run.return_value = {"data": {"durl": []}}

    try:
        with patch("util.network.request.SyncNetWorkRequest", return_value=fake_request):
            worker.run()
    finally:
        PreviewerInfo.media_type = MediaType.UNKNOWN
        PreviewerInfo.info_data = {}

    assert error_payload == ["无法获取文件大小"]


# ---------------------------------------------------------------------------
# run - M4A 路径(复用 DASH)
# ---------------------------------------------------------------------------
def test_run_m4a_uses_dash_query_path():
    """M4A 模式应借用 query_dash_file_size 路径"""
    PreviewerInfo.media_type = MediaType.M4A
    worker = QueryInfoWorker({"baseUrl": "https://test.url"})

    success_payload = []
    worker.success.connect(lambda *a, **kw: success_payload.append(a))

    try:
        with patch("util.network.download_url.resolve_download_url",
                   return_value={"file_size": 20480}):
            worker.run()
    finally:
        PreviewerInfo.media_type = MediaType.UNKNOWN

    assert worker.file_size == 20480
    assert success_payload[0][1] == 20480


# ---------------------------------------------------------------------------
# run - 异常路径
# ---------------------------------------------------------------------------
def test_run_exception_emits_error_and_finished():
    """run 在 query 过程抛异常时应 emit error/finished,不向上抛"""
    PreviewerInfo.media_type = MediaType.DASH
    worker = QueryInfoWorker({"baseUrl": "https://test.url"})

    error_payload = []
    finished_count = {"n": 0}
    worker.error.connect(lambda e: error_payload.append(e))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    try:
        with patch("util.network.download_url.resolve_download_url",
                   side_effect=RuntimeError("network down")):
            worker.run()
    finally:
        PreviewerInfo.media_type = MediaType.UNKNOWN

    assert error_payload == ["network down"]
    assert finished_count["n"] == 1
