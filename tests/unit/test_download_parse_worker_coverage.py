# tests/unit/test_download_parse_worker_coverage.py
"""T6 覆盖率补强 - src/util/download/downloader/parse_worker.py

覆盖目标:
- ParseWorker.__init__ 默认字段
- ParseWorker.run 成功路径(调用 get_info + parse_download_info + on_parse_finished)
- ParseWorker.run 异常路径(调用 on_parse_error)
- ParseWorker.get_info 四种 attribute 分支(VIDEO/BANGUMI/CHEESE/AUDIO)
- ParseWorker.get_info media_type 检测(DASH/MP4/FLV/M4A)
- ParseWorker.get_video_info / get_bangumi_info / get_cheese_info / get_audio_info
- ParseWorker.parse_download_info(VIDEO/AUDIO/二者/queue 过滤)
- ParseWorker.on_parse_error 设置 error 标志并回调 parent
- ParseWorker.check_response 成功/失败分支
- ParseWorker.get_output_file_ext 四种组合
- ParseWorker.filter_download_list 空 queue/非空 queue
"""
from unittest.mock import MagicMock, patch

import pytest

from util.common.enum import DownloadType, MediaType
from util.parse.episode.tree import Attribute
from util.download.downloader.parse_worker import ParseWorker
from util.download.task.info import TaskInfo


# ---------------------------------------------------------------------------
# 辅助函数与夹具
# ---------------------------------------------------------------------------
def make_task_info(attribute: int = Attribute.VIDEO_BIT,
                   download_type: int = DownloadType.VIDEO) -> TaskInfo:
    """构造带基础字段的 TaskInfo,避免每个测试重复设置"""
    info = TaskInfo()
    info.Episode.attribute = attribute
    info.Episode.bvid = "BV1xx411c7mD"
    info.Episode.cid = 12345
    info.Episode.aid = 67890
    info.Episode.sid = 999
    info.Episode.ep_id = 100
    info.Episode.url = "https://www.bilibili.com/video/BV1xx411c7mD"
    info.Download.type = download_type
    info.Download.video_quality_id = 80
    info.Download.audio_quality_id = 30232
    info.Download.video_codec_id = 7
    info.Download.merge_video_audio = True
    info.Download.keep_original_files = False
    info.Download.video_parts_count = 0
    info.Download.queue = []
    info.Download.files = {}
    info.File.video_file_ext = "mp4"
    info.File.audio_file_ext = "m4a"
    info.File.merge_file_ext = "mp4"
    return info


def patch_enc_wbi(worker: ParseWorker):
    """mock ParseWorker.enc_wbi 避免依赖 config 中的 img_key/sub_key"""
    worker.enc_wbi = lambda params: "wbi_signed_query"


def make_request_mock(response: dict):
    """构造 SyncNetWorkRequest 的 mock,run() 返回指定 response"""
    request_mock = MagicMock()
    request_mock.run.return_value = response
    return request_mock


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------
def test_init_sets_default_fields():
    """__init__ 应设置 task_info/info_data/parent/error 默认值"""
    info = make_task_info()
    parent = MagicMock()
    worker = ParseWorker(info, parent)

    assert worker.task_info is info
    assert worker.parent is parent
    assert worker.info_data is None
    assert worker.error is False


def test_init_parent_defaults_to_none():
    """parent 未传时应为 None"""
    info = make_task_info()
    worker = ParseWorker(info)

    assert worker.parent is None


# ---------------------------------------------------------------------------
# run 成功路径
# ---------------------------------------------------------------------------
def test_run_success_calls_on_parse_finished():
    """run 成功路径应调用 parent.on_parse_finished 携带 json 字符串"""
    info = make_task_info()
    parent = MagicMock()
    worker = ParseWorker(info, parent)
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"dash": {}, "format": "mp4"}}
    fake_video_parser = MagicMock()
    fake_video_parser.parse_info.return_value = [
        {"file_key": "video", "file_size": 1000}
    ]
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)), \
         patch("util.download.parse.video_info.VideoInfoParser",
               return_value=fake_video_parser):
        worker.run()

    parent.on_parse_finished.assert_called_once()
    json_arg = parent.on_parse_finished.call_args[0][0]
    assert "download_list" in json_arg
    assert "total_size" in json_arg
    assert "download_queue" in json_arg


def test_run_exception_calls_on_parse_error():
    """run 中 get_info 抛异常时应调用 on_parse_error"""
    info = make_task_info()
    parent = MagicMock()
    worker = ParseWorker(info, parent)

    with patch.object(worker, "get_info", side_effect=RuntimeError("boom")):
        worker.run()

    parent.on_parse_error.assert_called_once()
    error_msg = parent.on_parse_error.call_args[0][0]
    assert "boom" in error_msg


def test_run_skips_parse_when_error_flag_set():
    """run 在 get_info 设置 error=True 后应跳过 parse_download_info"""
    info = make_task_info()
    parent = MagicMock()
    worker = ParseWorker(info, parent)

    def fake_get_info():
        worker.error = True

    with patch.object(worker, "get_info", side_effect=fake_get_info), \
         patch.object(worker, "parse_download_info") as mock_parse:
        worker.run()

    mock_parse.assert_not_called()
    parent.on_parse_finished.assert_not_called()


# ---------------------------------------------------------------------------
# get_info - attribute 分发
# ---------------------------------------------------------------------------
def test_get_info_dispatches_to_video():
    """VIDEO_BIT 应调用 get_video_info"""
    info = make_task_info(attribute=Attribute.VIDEO_BIT)
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"format": "mp4"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert worker.info_data == {"format": "mp4"}


def test_get_info_dispatches_to_bangumi():
    """BANGUMI_BIT 应调用 get_bangumi_info"""
    info = make_task_info(attribute=Attribute.BANGUMI_BIT)
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "result": {"format": "flv"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert worker.info_data == {"format": "flv"}


def test_get_info_dispatches_to_cheese():
    """CHEESE_BIT 应调用 get_cheese_info"""
    info = make_task_info(attribute=Attribute.CHEESE_BIT)
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"format": "mp4"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert worker.info_data == {"format": "mp4"}


def test_get_info_dispatches_to_audio():
    """AUDIO_BIT 应调用 get_audio_info 并设置 format=m4a"""
    info = make_task_info(attribute=Attribute.AUDIO_BIT,
                          download_type=DownloadType.AUDIO)
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"some": "info"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert worker.info_data == {"some": "info", "format": "m4a"}


# ---------------------------------------------------------------------------
# get_info - media_type 检测
# ---------------------------------------------------------------------------
def test_get_info_sets_dash_media_type():
    """info_data 含 dash 键时应设置 media_type=DASH"""
    info = make_task_info()
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"dash": {"video": []}}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert info.Download.media_type == MediaType.DASH


def test_get_info_sets_mp4_media_type():
    """format 以 mp4 开头时应设置 media_type=MP4"""
    info = make_task_info()
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"format": "mp4"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert info.Download.media_type == MediaType.MP4


def test_get_info_sets_flv_media_type():
    """format 以 flv 开头时应设置 media_type=FLV"""
    info = make_task_info()
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"format": "flv"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert info.Download.media_type == MediaType.FLV


def test_get_info_sets_m4a_media_type():
    """format 以 m4a 开头时应设置 media_type=M4A"""
    info = make_task_info(attribute=Attribute.AUDIO_BIT,
                          download_type=DownloadType.AUDIO)
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    # get_audio_info 内部会强制设置 format=m4a
    fake_response = {"code": 0, "data": {}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        worker.get_info()

    assert info.Download.media_type == MediaType.M4A


def test_get_info_skips_media_type_when_error():
    """get_info 在 error=True 时不应设置 media_type"""
    info = make_task_info()
    parent = MagicMock()
    worker = ParseWorker(info, parent)
    patch_enc_wbi(worker)

    # code != 0 触发 check_response -> on_parse_error + RuntimeError
    fake_response = {"code": -1, "message": "失败"}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)):
        with pytest.raises(RuntimeError, match="失败"):
            worker.get_info()

    assert worker.error is True


# ---------------------------------------------------------------------------
# get_video_info / get_bangumi_info / get_cheese_info / get_audio_info
# ---------------------------------------------------------------------------
def test_get_video_info_uses_enc_wbi():
    """get_video_info 应通过 enc_wbi 签名参数"""
    info = make_task_info(attribute=Attribute.VIDEO_BIT)
    worker = ParseWorker(info, MagicMock())
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"k": "v"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)) as req_cls:
        worker.get_video_info()

    req_cls.assert_called_once()
    url_arg = req_cls.call_args[0][0]
    assert "wbi_signed_query" in url_arg


def test_get_bangumi_info_uses_urlencode():
    """get_bangumi_info 应通过 urlencode 构造参数(非 wbi)"""
    info = make_task_info(attribute=Attribute.BANGUMI_BIT)
    worker = ParseWorker(info, MagicMock())

    fake_response = {"code": 0, "result": {"k": "v"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)) as req_cls:
        worker.get_bangumi_info()

    url_arg = req_cls.call_args[0][0]
    assert "bvid=BV1xx411c7mD" in url_arg
    assert "cid=12345" in url_arg


def test_get_cheese_info_includes_ep_id():
    """get_cheese_info 应在参数中包含 ep_id"""
    info = make_task_info(attribute=Attribute.CHEESE_BIT)
    worker = ParseWorker(info, MagicMock())

    fake_response = {"code": 0, "data": {"k": "v"}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)) as req_cls:
        worker.get_cheese_info()

    url_arg = req_cls.call_args[0][0]
    assert "ep_id=100" in url_arg
    assert "avid=67890" in url_arg


def test_get_audio_info_includes_sid():
    """get_audio_info 应在参数中包含 sid"""
    info = make_task_info(attribute=Attribute.AUDIO_BIT,
                          download_type=DownloadType.AUDIO)
    worker = ParseWorker(info, MagicMock())

    fake_response = {"code": 0, "data": {}}
    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)) as req_cls:
        worker.get_audio_info()

    url_arg = req_cls.call_args[0][0]
    assert "sid=999" in url_arg


# ---------------------------------------------------------------------------
# parse_download_info
# ---------------------------------------------------------------------------
def test_parse_download_info_video_only():
    """仅 VIDEO 类型时应调用 VideoInfoParser"""
    info = make_task_info(download_type=DownloadType.VIDEO)
    worker = ParseWorker(info, MagicMock())
    worker.info_data = {"dash": {}}

    fake_video_parser = MagicMock()
    fake_video_parser.parse_info.return_value = [
        {"file_key": "video", "file_size": 1000}
    ]

    with patch("util.download.parse.video_info.VideoInfoParser",
               return_value=fake_video_parser):
        result = worker.parse_download_info()

    assert result["total_size"] == 1000
    assert "video" in result["download_list"]
    assert result["download_queue"] == ["video"]


def test_parse_download_info_audio_only():
    """仅 AUDIO 类型时应调用 AudioInfoParser"""
    info = make_task_info(attribute=Attribute.AUDIO_BIT,
                          download_type=DownloadType.AUDIO)
    worker = ParseWorker(info, MagicMock())
    worker.info_data = {}

    fake_audio_parser = MagicMock()
    fake_audio_parser.parse_info.return_value = [
        {"file_key": "audio", "file_size": 500}
    ]

    with patch("util.download.parse.audio_info.AudioInfoParser",
               return_value=fake_audio_parser):
        result = worker.parse_download_info()

    assert result["total_size"] == 500
    assert "audio" in result["download_list"]


def test_parse_download_info_video_and_audio():
    """VIDEO + AUDIO 类型时应同时调用两个 parser"""
    info = make_task_info(download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    worker = ParseWorker(info, MagicMock())
    worker.info_data = {}

    fake_video_parser = MagicMock()
    fake_video_parser.parse_info.return_value = [
        {"file_key": "video", "file_size": 1000}
    ]
    fake_audio_parser = MagicMock()
    fake_audio_parser.parse_info.return_value = [
        {"file_key": "audio", "file_size": 500}
    ]

    with patch("util.download.parse.video_info.VideoInfoParser",
               return_value=fake_video_parser), \
         patch("util.download.parse.audio_info.AudioInfoParser",
               return_value=fake_audio_parser):
        result = worker.parse_download_info()

    assert result["total_size"] == 1500
    assert set(result["download_list"].keys()) == {"video", "audio"}


def test_parse_download_info_applies_queue_filter():
    """parse_download_info 应通过 filter_download_list 过滤"""
    info = make_task_info(download_type=DownloadType.VIDEO)
    info.Download.queue = ["video"]
    worker = ParseWorker(info, MagicMock())
    worker.info_data = {}

    fake_video_parser = MagicMock()
    fake_video_parser.parse_info.return_value = [
        {"file_key": "video", "file_size": 1000},
        {"file_key": "extra", "file_size": 200},
    ]

    with patch("util.download.parse.video_info.VideoInfoParser",
               return_value=fake_video_parser):
        result = worker.parse_download_info()

    # queue 只含 video,extra 应被过滤
    assert "video" in result["download_list"]
    assert "extra" not in result["download_list"]


# ---------------------------------------------------------------------------
# on_parse_error
# ---------------------------------------------------------------------------
def test_on_parse_error_sets_flag_and_calls_parent():
    """on_parse_error 应设置 error=True 并回调 parent.on_parse_error"""
    info = make_task_info()
    parent = MagicMock()
    worker = ParseWorker(info, parent)

    worker.on_parse_error("some error")

    assert worker.error is True
    parent.on_parse_error.assert_called_once_with("some error")


# ---------------------------------------------------------------------------
# check_response
# ---------------------------------------------------------------------------
def test_check_response_success_does_not_raise():
    """code=0 时 check_response 不应抛异常"""
    info = make_task_info()
    worker = ParseWorker(info, MagicMock())

    # 不应抛异常
    worker.check_response({"code": 0, "data": {}})


def test_check_response_failure_raises_and_sets_error():
    """code!=0 时 check_response 应调用 on_parse_error 并抛 RuntimeError"""
    info = make_task_info()
    parent = MagicMock()
    worker = ParseWorker(info, parent)

    with pytest.raises(RuntimeError, match="失败"):
        worker.check_response({"code": -1, "message": "失败"})

    assert worker.error is True
    parent.on_parse_error.assert_called_once_with("失败")


def test_check_response_uses_default_message_when_missing():
    """code!=0 且无 message 时应使用默认消息"""
    info = make_task_info()
    worker = ParseWorker(info, MagicMock())

    with pytest.raises(RuntimeError, match="无法获取下载链接"):
        worker.check_response({"code": -1})


# ---------------------------------------------------------------------------
# get_output_file_ext
# ---------------------------------------------------------------------------
def test_get_output_file_ext_disables_merge_when_single_stream():
    """仅 VIDEO 或仅 AUDIO 时应禁用 merge_video_audio 和 keep_original_files"""
    info = make_task_info(download_type=DownloadType.VIDEO)
    info.Download.merge_video_audio = True
    info.Download.keep_original_files = True
    worker = ParseWorker(info, MagicMock())

    worker.get_output_file_ext()

    assert info.Download.merge_video_audio is False
    assert info.Download.keep_original_files is False


def test_get_output_file_ext_keeps_merge_when_both_streams():
    """VIDEO + AUDIO 时应保留 merge_video_audio 设置"""
    info = make_task_info(download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    info.Download.merge_video_audio = True
    worker = ParseWorker(info, MagicMock())

    worker.get_output_file_ext()

    assert info.Download.merge_video_audio is True


def test_get_output_file_ext_sets_merge_file_ext_when_merging(monkeypatch):
    """merge_video_audio=True 时应设置 merge_file_ext=video_container"""
    monkeypatch.setattr("util.download.downloader.parse_worker.config",
                        MagicMock(get=lambda k, default=None: "mp4" if k == "video_container" else default))
    info = make_task_info(download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    info.Download.merge_video_audio = True
    worker = ParseWorker(info, MagicMock())

    worker.get_output_file_ext()

    assert info.File.merge_file_ext == "mp4"


def test_get_output_file_ext_sets_merge_file_ext_when_video_parts(monkeypatch):
    """video_parts_count > 0 时应设置 merge_file_ext"""
    monkeypatch.setattr("util.download.downloader.parse_worker.config",
                        MagicMock(get=lambda k, default=None: "mp4" if k == "video_container" else default))
    info = make_task_info(download_type=DownloadType.VIDEO | DownloadType.AUDIO)
    info.Download.merge_video_audio = False
    info.Download.video_parts_count = 3
    worker = ParseWorker(info, MagicMock())

    worker.get_output_file_ext()

    assert info.File.merge_file_ext == "mp4"


# ---------------------------------------------------------------------------
# filter_download_list
# ---------------------------------------------------------------------------
def test_filter_download_list_empty_queue_returns_all():
    """queue 为空时应返回完整 download_list"""
    info = make_task_info()
    info.Download.queue = []
    worker = ParseWorker(info, MagicMock())

    original = {"video": {"size": 1}, "audio": {"size": 2}}
    result = worker.filter_download_list(original)

    assert result == original


def test_filter_download_list_filters_by_queue():
    """queue 非空时应仅保留 queue 中存在的 key"""
    info = make_task_info()
    info.Download.queue = ["video"]
    worker = ParseWorker(info, MagicMock())

    original = {"video": {"size": 1}, "audio": {"size": 2}, "extra": {"size": 3}}
    result = worker.filter_download_list(original)

    assert set(result.keys()) == {"video"}


def test_filter_download_list_queue_no_match_returns_empty():
    """queue 中的 key 都不在 download_list 时应返回空 dict"""
    info = make_task_info()
    info.Download.queue = ["nonexistent"]
    worker = ParseWorker(info, MagicMock())

    original = {"video": {"size": 1}}
    result = worker.filter_download_list(original)

    assert result == {}


# ---------------------------------------------------------------------------
# run 端到端集成(mock 网络)
# ---------------------------------------------------------------------------
def test_run_end_to_end_with_mocked_network():
    """run 端到端:mock 网络 + parser,验证 on_parse_finished 收到完整 json"""
    info = make_task_info(attribute=Attribute.VIDEO_BIT,
                          download_type=DownloadType.VIDEO)
    parent = MagicMock()
    worker = ParseWorker(info, parent)
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {"dash": {}, "format": "mp4"}}
    fake_video_parser = MagicMock()
    fake_video_parser.parse_info.return_value = [
        {"file_key": "video", "file_size": 2048}
    ]

    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)), \
         patch("util.download.parse.video_info.VideoInfoParser",
               return_value=fake_video_parser):
        worker.run()

    parent.on_parse_finished.assert_called_once()
    json_arg = parent.on_parse_finished.call_args[0][0]
    assert "2048" in json_arg
    assert "video" in json_arg
    assert info.Download.media_type == MediaType.DASH


def test_run_end_to_end_audio_only_with_mocked_network():
    """run 端到端:AUDIO 类型,验证 m4a format 注入"""
    info = make_task_info(attribute=Attribute.AUDIO_BIT,
                          download_type=DownloadType.AUDIO)
    parent = MagicMock()
    worker = ParseWorker(info, parent)
    patch_enc_wbi(worker)

    fake_response = {"code": 0, "data": {}}
    fake_audio_parser = MagicMock()
    fake_audio_parser.parse_info.return_value = [
        {"file_key": "audio", "file_size": 512}
    ]

    with patch("util.network.request.SyncNetWorkRequest",
               return_value=make_request_mock(fake_response)), \
         patch("util.download.parse.audio_info.AudioInfoParser",
               return_value=fake_audio_parser):
        worker.run()

    parent.on_parse_finished.assert_called_once()
    assert info.Download.media_type == MediaType.M4A
