# tests/unit/test_parse_worker_coverage.py
"""T6 覆盖率补强 - src/util/parse/worker.py

覆盖目标:
- ParserDispatcher.get_parser(各 parser_type 分发 + 未知类型抛 ValueError)
- ParserDispatcher.get_parser_type(url_patterns 匹配 + 无匹配抛 ValueError)
- ParseWorker.run(成功路径 + 异常路径 + signal emit)
- ParseWorker.get_redirect_url(b23/festival 链接处理)
- ParseWorker.on_error
- ProgressParseWorker.run / _get_parser / trigger_stop
- ProgressParseWorker._get_interactive_video_parser / _get_dynamic_parser
"""
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

from util.common.data.auto_parse import AutoParsePayload
from util.common.enum import ParserType
from util.parse.worker import (
    ParserDispatcher,
    ParseWorker,
    ProgressParseWorker,
)


# ---------------------------------------------------------------------------
# ParserDispatcher.get_parser
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "parser_type, module_path, class_name",
    [
        ("video", "util.parse.parser.video", "VideoParser"),
        ("bangumi", "util.parse.parser.bangumi", "BangumiParser"),
        ("cheese", "util.parse.parser.cheese", "CheeseParser"),
        ("space", "util.parse.parser.space", "SpaceParser"),
        ("favlist", "util.parse.parser.favlist", "FavlistParser"),
        ("list", "util.parse.parser.list", "ListParser"),
        ("popular", "util.parse.parser.popular", "PopularParser"),
        ("watch_later", "util.parse.parser.watch_later", "WatchLaterParser"),
        ("history", "util.parse.parser.history", "HistoryParser"),
        ("audio", "util.parse.parser.audio", "AudioParser"),
    ],
)
def test_get_parser_returns_correct_instance(parser_type, module_path, class_name):
    """各 parser_type 应返回对应的解析器实例"""
    fake_instance = MagicMock(name=class_name)
    fake_class = MagicMock(return_value=fake_instance)

    dispatcher = ParserDispatcher()
    with patch.dict(sys.modules, {module_path: MagicMock(**{class_name: fake_class})}):
        result = dispatcher.get_parser(parser_type)

    assert result is fake_instance
    fake_class.assert_called_once_with()


def test_get_parser_unknown_type_raises_value_error():
    """未知 parser_type 应抛出 ValueError"""
    dispatcher = ParserDispatcher()
    with pytest.raises(ValueError, match="未知的解析类型"):
        dispatcher.get_parser("not_a_real_type")


# ---------------------------------------------------------------------------
# ParserDispatcher.get_parser_type
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "url, expected_type",
    [
        ("https://www.bilibili.com/video/BV1xx411c7mD", "video"),
        ("https://www.bilibili.com/bangumi/play/ep12345", "bangumi"),
        ("https://www.bilibili.com/bangumi/media/md12345", "bangumi"),
        ("https://www.bilibili.com/cheese/play/ss123", "cheese"),
        ("https://space.bilibili.com/12345/lists", "list"),
        ("https://space.bilibili.com/12345/favlist", "favlist"),
        ("https://space.bilibili.com/12345", "space"),
        ("https://www.bilibili.com/v/popular/all", "popular"),
        ("bili23://watch_later", "watch_later"),
        ("bili23://history", "history"),
        ("https://b23.tv/abc123", "b23"),
        ("BV1xx411c7mD", "video"),
        ("au12345", "audio"),
    ],
)
def test_get_parser_type_matches_url(url, expected_type):
    """url_patterns 应正确匹配各类 URL"""
    dispatcher = ParserDispatcher()
    assert dispatcher.get_parser_type(url) == expected_type


def test_get_parser_type_no_match_raises_value_error():
    """无匹配的 URL 应抛出 ValueError(INVALID_LINK)"""
    dispatcher = ParserDispatcher()
    with pytest.raises(ValueError):
        dispatcher.get_parser_type("https://example.com/not_a_bili_link")


# ---------------------------------------------------------------------------
# ParseWorker 初始化
# ---------------------------------------------------------------------------
def test_parse_worker_init_defaults():
    """ParseWorker 应正确初始化 url/pn/parser_type 与三个信号"""
    worker = ParseWorker("https://example.com")
    assert worker.url == "https://example.com"
    assert worker.pn == 1
    assert worker.parser_type == ""
    # WorkerBase 应提供三个信号
    assert hasattr(worker, "success")
    assert hasattr(worker, "error")
    assert hasattr(worker, "finished")


def test_parse_worker_init_custom_pn():
    """ParseWorker 应支持自定义 pn"""
    worker = ParseWorker("https://example.com", pn=5)
    assert worker.pn == 5


# ---------------------------------------------------------------------------
# ParseWorker.run 成功路径
# ---------------------------------------------------------------------------
def test_parse_worker_run_success_emits_signals():
    """run 成功路径应依次 emit success/finished"""
    worker = ParseWorker("https://www.bilibili.com/video/BV1xx411c7mD")

    success_payload = []
    finished_count = {"n": 0}

    worker.success.connect(lambda *a, **kw: success_payload.append((a, kw)))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    fake_parser = MagicMock()
    fake_parser.get_category_name.return_value = "video"
    fake_parser.get_extra_data.return_value = {"key": "value"}

    with patch("util.parse.parser.video.VideoParser", return_value=fake_parser), \
         patch("util.parse.episode.tree.EpisodeData") as fake_episode_data:
        worker.run()

    fake_episode_data.clear_cache.assert_called_once()
    fake_parser.parse.assert_called_once_with(worker.url, worker.pn)
    assert success_payload == [(("video", {"key": "value"}), {})]
    assert finished_count["n"] == 1
    assert worker.parser_type == "video"


def test_parse_worker_run_exception_emits_error_and_finished():
    """run 异常路径应 emit error/finished,on_error 被调用"""
    worker = ParseWorker("invalid_url_no_match")

    error_payload = []
    finished_count = {"n": 0}

    worker.error.connect(lambda e: error_payload.append(e))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    with patch("util.parse.episode.tree.EpisodeData") as fake_episode_data:
        # get_parser_type 对 invalid_url 抛 ValueError,触发 except 分支
        worker.run()

    fake_episode_data.clear_cache.assert_called_once()
    assert len(error_payload) == 1
    assert isinstance(error_payload[0], str)
    assert finished_count["n"] == 1


def test_parse_worker_run_parse_exception_propagated_to_error_signal():
    """parser.parse 抛异常时应 emit error 携带异常信息"""
    worker = ParseWorker("https://www.bilibili.com/video/BV1xx411c7mD")

    error_payload = []
    worker.error.connect(lambda e: error_payload.append(e))

    fake_parser = MagicMock()
    fake_parser.parse.side_effect = RuntimeError("parse boom")

    with patch("util.parse.parser.video.VideoParser", return_value=fake_parser), \
         patch("util.parse.episode.tree.EpisodeData"):
        worker.run()

    assert error_payload == ["parse boom"]


# ---------------------------------------------------------------------------
# ParseWorker.get_redirect_url
# ---------------------------------------------------------------------------
def test_get_redirect_url_no_redirect_when_url_not_b23_or_festival():
    """url 不含 b23/festival 时不应重定向"""
    worker = ParseWorker("https://www.bilibili.com/video/BV1xx411c7mD")
    original_url = worker.url
    worker.get_redirect_url()
    assert worker.url == original_url


def test_get_redirect_url_b23_link_parsed():
    """b23 链接应通过 B23Parser 解析为新 URL"""
    worker = ParseWorker("https://b23.tv/abc123")
    fake_b23 = MagicMock()
    fake_b23.parse.return_value = "https://www.bilibili.com/video/BV1xx411c7mD"

    with patch("util.parse.parser.b23.B23Parser", return_value=fake_b23), \
         patch("util.parse.parser.festival.FestivalParser"):
        worker.get_redirect_url()

    fake_b23.parse.assert_called_once_with("https://b23.tv/abc123")
    assert worker.url == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert worker.parser_type == "video"


def test_get_redirect_url_festival_link_parsed():
    """festival 链接应通过 FestivalParser 解析为新 URL"""
    worker = ParseWorker("https://www.bilibili.com/festival/abc")
    fake_festival = MagicMock()
    fake_festival.parse.return_value = "https://www.bilibili.com/video/BV1xx411c7mD"

    with patch("util.parse.parser.festival.FestivalParser", return_value=fake_festival), \
         patch("util.parse.parser.b23.B23Parser"):
        worker.get_redirect_url()

    fake_festival.parse.assert_called_once_with("https://www.bilibili.com/festival/abc")
    assert worker.url == "https://www.bilibili.com/video/BV1xx411c7mD"


def test_get_redirect_url_skips_festival_when_url_only_has_b23():
    """仅含 b23 时,FestivalParser.parse 不应被调用"""
    worker = ParseWorker("https://b23.tv/abc123")
    fake_b23 = MagicMock()
    fake_b23.parse.return_value = "https://www.bilibili.com/video/BV1xx411c7mD"
    fake_festival = MagicMock()

    with patch("util.parse.parser.b23.B23Parser", return_value=fake_b23), \
         patch("util.parse.parser.festival.FestivalParser", return_value=fake_festival):
        worker.get_redirect_url()

    fake_festival.parse.assert_not_called()


# ---------------------------------------------------------------------------
# ParseWorker.on_error
# ---------------------------------------------------------------------------
def test_on_error_does_not_raise():
    """on_error 应安全记录日志,不抛异常"""
    worker = ParseWorker("https://example.com")
    # 直接调用不应抛出异常
    worker.on_error()


# ---------------------------------------------------------------------------
# ProgressParseWorker 初始化
# ---------------------------------------------------------------------------
def test_progress_parse_worker_init():
    """ProgressParseWorker 应初始化 stop_event/update_progress 信号"""
    payload = AutoParsePayload(url="https://example.com", parser_type=ParserType.DYNAMIC)
    worker = ProgressParseWorker(payload)

    assert worker.data is payload
    assert isinstance(worker.stop_event, threading.Event)
    assert not worker.stop_event.is_set()
    assert hasattr(worker, "update_progress")
    assert hasattr(worker, "success")
    assert hasattr(worker, "error")
    assert hasattr(worker, "finished")


# ---------------------------------------------------------------------------
# ProgressParseWorker.run 成功路径
# ---------------------------------------------------------------------------
def test_progress_parse_worker_run_success_emits_signals():
    """run 成功应 emit success(携带 category_name)+ finished"""
    payload = AutoParsePayload(
        url="https://www.bilibili.com/video/BV1xx411c7mD",
        parser_type=ParserType.DYNAMIC,
    )
    worker = ProgressParseWorker(payload)

    success_payload = []
    finished_count = {"n": 0}
    worker.success.connect(lambda *a, **kw: success_payload.append((a, kw)))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    fake_parser = MagicMock()
    fake_parser.get_category_name.return_value = "dynamic"

    with patch.object(worker, "_get_parser", return_value=fake_parser):
        worker.run()

    fake_parser.parse.assert_called_once()
    assert success_payload == [(("dynamic", {}), {})]
    assert finished_count["n"] == 1


def test_progress_parse_worker_run_exception_emits_error():
    """run 异常路径应 emit error/finished"""
    payload = AutoParsePayload(url="https://example.com", parser_type=ParserType.DYNAMIC)
    worker = ProgressParseWorker(payload)

    error_payload = []
    finished_count = {"n": 0}
    worker.error.connect(lambda e: error_payload.append(e))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    with patch.object(worker, "_get_parser", side_effect=RuntimeError("no parser")):
        worker.run()

    assert error_payload == ["no parser"]
    assert finished_count["n"] == 1


# ---------------------------------------------------------------------------
# ProgressParseWorker._get_parser
# ---------------------------------------------------------------------------
def test_get_parser_interactive_video_branch():
    """INTERACTIVE_VIDEO 类型应调用 _get_interactive_video_parser"""
    payload = AutoParsePayload(parser_type=ParserType.INTERACTIVE_VIDEO, data={"bvid": "BV1"})
    worker = ProgressParseWorker(payload)
    fake_iv_parser = MagicMock()

    with patch.object(worker, "_get_interactive_video_parser", return_value=fake_iv_parser) as m:
        result = worker._get_parser()

    assert result is fake_iv_parser
    m.assert_called_once()


def test_get_parser_dynamic_branch():
    """DYNAMIC 类型应调用 _get_dynamic_parser"""
    payload = AutoParsePayload(parser_type=ParserType.DYNAMIC, url="https://example.com")
    worker = ProgressParseWorker(payload)
    fake_dyn_parser = MagicMock()

    with patch.object(worker, "_get_dynamic_parser", return_value=fake_dyn_parser) as m:
        result = worker._get_parser()

    assert result is fake_dyn_parser
    m.assert_called_once()


def test_get_parser_batch_branch_uses_dynamic_parser():
    """BATCH 类型也应调用 _get_dynamic_parser(代码复用)"""
    payload = AutoParsePayload(parser_type=ParserType.BATCH, url="https://example.com")
    worker = ProgressParseWorker(payload)
    fake_dyn_parser = MagicMock()

    with patch.object(worker, "_get_dynamic_parser", return_value=fake_dyn_parser) as m:
        result = worker._get_parser()

    assert result is fake_dyn_parser
    m.assert_called_once()


def test_get_parser_unsupported_type_raises_value_error():
    """不支持的 parser_type 应抛 ValueError"""
    payload = AutoParsePayload(parser_type=ParserType.UNKNOWN)
    worker = ProgressParseWorker(payload)

    with pytest.raises(ValueError, match="Unsupported parser type"):
        worker._get_parser()


# ---------------------------------------------------------------------------
# ProgressParseWorker._get_interactive_video_parser / _get_dynamic_parser
# ---------------------------------------------------------------------------
def test_get_interactive_video_parser_constructs_parser():
    """_get_interactive_video_parser 应使用 data/stop_event 构造 InteractiveVideoParser"""
    payload = AutoParsePayload(
        parser_type=ParserType.INTERACTIVE_VIDEO,
        data={"bvid": "BV1xx"},
    )
    worker = ProgressParseWorker(payload)
    fake_instance = MagicMock()
    fake_class = MagicMock(return_value=fake_instance)

    with patch("util.parse.parser.video.InteractiveVideoParser", fake_class):
        result = worker._get_interactive_video_parser()

    assert result is fake_instance
    fake_class.assert_called_once_with({"bvid": "BV1xx"}, worker._update_progress_callback, worker.stop_event)


def test_get_dynamic_parser_constructs_parser():
    """_get_dynamic_parser 应使用 base_parser 构造 DynamicParser"""
    payload = AutoParsePayload(
        parser_type=ParserType.DYNAMIC,
        url="https://www.bilibili.com/video/BV1xx411c7mD",
    )
    worker = ProgressParseWorker(payload)

    fake_base_parser = MagicMock()
    fake_dynamic_instance = MagicMock()
    fake_dynamic_class = MagicMock(return_value=fake_dynamic_instance)

    with patch.object(worker, "get_parser", return_value=fake_base_parser) as gp, \
         patch("util.parse.parser.dynamic.DynamicParser", fake_dynamic_class):
        result = worker._get_dynamic_parser()

    assert result is fake_dynamic_instance
    gp.assert_called_once()  # get_parser_type 已分发得到 video
    fake_dynamic_class.assert_called_once_with(
        payload, fake_base_parser, worker._update_progress_callback, worker.stop_event
    )


# ---------------------------------------------------------------------------
# ProgressParseWorker._update_progress_callback / trigger_stop
# ---------------------------------------------------------------------------
def test_update_progress_callback_emits_signal():
    """_update_progress_callback 应通过 update_progress 信号 emit 文本"""
    payload = AutoParsePayload(parser_type=ParserType.DYNAMIC)
    worker = ProgressParseWorker(payload)

    received = []
    worker.update_progress.connect(lambda *a, **kw: received.append((a, kw)))

    worker._update_progress_callback("parsing 50%")
    assert received == [(("parsing 50%",), {})]


def test_trigger_stop_sets_stop_event():
    """trigger_stop 应设置 stop_event"""
    payload = AutoParsePayload(parser_type=ParserType.DYNAMIC)
    worker = ProgressParseWorker(payload)

    assert not worker.stop_event.is_set()
    worker.trigger_stop()
    assert worker.stop_event.is_set()
