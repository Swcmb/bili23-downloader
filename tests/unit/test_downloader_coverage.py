# tests/unit/test_downloader_coverage.py
"""T6 覆盖率补强 - src/util/download/downloader/downloader.py

覆盖目标:
- _PeriodicTimer: start/stop/isActive/_schedule/_tick(含异常吞掉)
- TokenBucket: consume(rate<=0/rate>0/sleep)/set_rate
- ChunkWorker: __init__/_invoke_download_error/_is_retryable_exception(各类型)
              /_build_error_message/_report_download_failure/run(成功/停止/重试/失败)
- Downloader: __init__/start/pause/resume/retry/is_generation_active
             /on_parse_finished/on_parse_error/on_download_error
             /start_download/_start_worker_in_background/start_worker/start_merge
             /calc_chunk_list/calc_chunk_range/calc_downloaded_size
             /on_chunk_finished/update_info/on_download_completed
             /wait_merge/on_chunk_start/on_chunk_end/wait/start_timer
             /_calculate_speed/on_delete/update_item/_check_disk_space
"""
import errno
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import httpx
import pytest

from util.common.enum import DownloadStatus, DownloadType, MediaType
from util.download.downloader.downloader import (
    ChunkWorker,
    Downloader,
    TokenBucket,
    _PeriodicTimer,
)
from util.download.task.info import TaskInfo


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------
def make_task_info(download_type: int = DownloadType.VIDEO) -> TaskInfo:
    """构造带基础字段的 TaskInfo"""
    info = TaskInfo()
    info.Basic.task_id = "test-task-001"
    info.Episode.url = "https://www.bilibili.com/video/BV1xx411c7mD"
    info.Episode.bvid = "BV1xx411c7mD"
    info.Episode.cid = 12345
    info.Download.type = download_type
    info.Download.video_quality_id = 80
    info.Download.queue = []
    info.Download.files = {}
    info.Download.total_size = 0
    info.Download.downloaded_size = 0
    info.Download.progress = 0
    info.Download.status = DownloadStatus.QUEUED
    info.File.download_path = "/tmp"
    info.File.folder = ""
    info.File.video_file_ext = "mp4"
    return info


def make_downloader(task_info=None, mock_config=None):
    """构造 Downloader 实例,mock init_session 避免真实网络初始化"""
    if task_info is None:
        task_info = make_task_info()
    with patch.object(Downloader, "init_session"):
        dl = Downloader(task_info)
    return dl


# ===========================================================================
# _PeriodicTimer
# ===========================================================================
class TestPeriodicTimer:
    """_PeriodicTimer 单元测试"""

    def test_init_defaults(self):
        """__init__ 应设置 interval/callback/timer/stopped"""
        timer = _PeriodicTimer(1000, lambda: None)
        assert timer._interval == 1.0
        assert timer._callback is not None
        assert timer._timer is None
        assert timer._stopped is True

    def test_start_schedules_timer(self):
        """start 应调度第一次定时器"""
        timer = _PeriodicTimer(100, lambda: None)
        timer.start()
        assert timer._stopped is False
        assert timer._timer is not None
        timer.stop()

    def test_start_ignores_when_already_running(self):
        """已在运行时 start 应忽略"""
        timer = _PeriodicTimer(100, lambda: None)
        timer.start()
        first_timer = timer._timer
        timer.start()  # 应忽略
        assert timer._timer is first_timer
        timer.stop()

    def test_stop_cancels_timer(self):
        """stop 应取消定时器并设置 stopped"""
        timer = _PeriodicTimer(100, lambda: None)
        timer.start()
        timer.stop()
        assert timer._stopped is True
        assert timer._timer is None

    def test_stop_when_not_running(self):
        """未运行时 stop 应安全执行"""
        timer = _PeriodicTimer(100, lambda: None)
        timer.stop()
        assert timer._stopped is True

    def test_is_active(self):
        """isActive 应反映运行状态"""
        timer = _PeriodicTimer(100, lambda: None)
        assert timer.isActive() is False
        timer.start()
        assert timer.isActive() is True
        timer.stop()
        assert timer.isActive() is False

    def test_tick_calls_callback_and_reschedules(self):
        """_tick 应调用回调并调度下一次"""
        called = {"n": 0}
        timer = _PeriodicTimer(50, lambda: called.__setitem__("n", called["n"] + 1))
        timer.start()
        time.sleep(0.2)
        timer.stop()
        assert called["n"] >= 1

    def test_tick_swallows_callback_exception(self):
        """_tick 应吞掉回调异常,不影响下一次调度"""
        def bad_callback():
            raise ValueError("boom")

        timer = _PeriodicTimer(50, bad_callback)
        timer.start()
        time.sleep(0.15)
        timer.stop()
        # 不应抛异常,定时器应正常停止

    def test_schedule_does_nothing_when_stopped(self):
        """_schedule 在 stopped=True 时不应创建定时器"""
        timer = _PeriodicTimer(100, lambda: None)
        # _stopped 默认为 True
        timer._schedule()
        assert timer._timer is None


# ===========================================================================
# TokenBucket
# ===========================================================================
class TestTokenBucket:
    """TokenBucket 单元测试"""

    def test_init_sets_rate_and_tokens(self):
        """__init__ 应设置 rate/tokens/last_update/lock"""
        bucket = TokenBucket(rate=1024)
        assert bucket.rate == 1024
        assert bucket.tokens == 1024
        assert bucket.lock is not None

    def test_consume_returns_immediately_when_rate_zero(self):
        """rate=0(不限速)时 consume 应立即返回"""
        bucket = TokenBucket(rate=0)
        start = time.monotonic()
        bucket.consume(1024)
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    def test_consume_with_sufficient_tokens(self):
        """令牌充足时 consume 不应休眠"""
        bucket = TokenBucket(rate=1024 * 1024)
        bucket.consume(512)
        assert bucket.tokens < 1024 * 1024  # 令牌已消耗

    def test_consume_with_insufficient_tokens_sleeps(self):
        """令牌不足时 consume 应休眠(分段)"""
        bucket = TokenBucket(rate=100)  # 100 bytes/sec
        # 消耗大量令牌,需要休眠
        stop_event = threading.Event()
        bucket.consume(200, stop_event)  # 需要约 1 秒补充
        # 应该执行完毕(休眠后令牌补充)

    def test_consume_breaks_on_stop_event(self):
        """stop_event 设置时应中断休眠"""
        bucket = TokenBucket(rate=1)  # 1 byte/sec,极慢
        stop_event = threading.Event()
        stop_event.set()  # 预设停止

        start = time.monotonic()
        bucket.consume(1000, stop_event)
        elapsed = time.monotonic() - start
        # 应立即返回(不等待令牌补充)
        assert elapsed < 0.5

    def test_set_rate_updates_rate_and_tokens(self):
        """set_rate 应更新 rate 和 tokens"""
        bucket = TokenBucket(rate=100)
        bucket.set_rate(2000)
        assert bucket.rate == 2000
        assert bucket.tokens == 2000


# ===========================================================================
# ChunkWorker
# ===========================================================================
class TestChunkWorkerInit:
    """ChunkWorker 初始化测试"""

    def test_init_sets_fields(self):
        """__init__ 应设置所有字段"""
        session = MagicMock()
        stop_event = threading.Event()
        lock = threading.Lock()
        token_bucket = TokenBucket(0)
        task_info = make_task_info()
        parent = MagicMock()
        parent.is_generation_active.return_value = True

        worker = ChunkWorker(
            session=session,
            file_key="video",
            chunk_index=0,
            chunk_range=(0, 1024),
            file_path=Path("/tmp/test.mp4"),
            url="https://example.com/video",
            referer="https://example.com",
            task_info=task_info,
            stop_event=stop_event,
            lock=lock,
            token_bucket=token_bucket,
            generation=1,
            parent=parent,
        )

        assert worker.file_key == "video"
        assert worker.chunk_index == 0
        assert worker.chunk_size == 1024
        assert worker.url == "https://example.com/video"
        assert worker.generation == 1
        assert worker.parent is parent


class TestChunkWorkerInvokeDownloadError:
    """ChunkWorker._invoke_download_error 测试"""

    def test_invokes_parent_on_download_error(self):
        """有 parent 时应调用 parent.on_download_error"""
        parent = MagicMock()
        parent.is_generation_active.return_value = True
        worker = _make_chunk_worker(parent=parent)

        worker._invoke_download_error("error msg")

        parent.on_download_error.assert_called_once_with("error msg")

    def test_skips_when_no_parent(self):
        """无 parent 时应安全执行不抛异常"""
        worker = _make_chunk_worker(parent=None)
        # 不应抛异常
        worker._invoke_download_error("error msg")


class TestChunkWorkerIsRetryable:
    """ChunkWorker._is_retryable_exception 测试"""

    def test_stop_iteration_is_retryable(self):
        """StopIteration 应可重试"""
        worker = _make_chunk_worker()
        assert worker._is_retryable_exception(StopIteration()) is True

    def test_http_status_error_permanent(self):
        """永久性状态码(404)应不可重试"""
        worker = _make_chunk_worker()
        response = MagicMock()
        response.status_code = 404
        exc = httpx.HTTPStatusError("404", request=MagicMock(), response=response)
        assert worker._is_retryable_exception(exc) is False

    def test_http_status_error_retryable(self):
        """可重试状态码(503)应可重试"""
        worker = _make_chunk_worker()
        response = MagicMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("503", request=MagicMock(), response=response)
        assert worker._is_retryable_exception(exc) is True

    def test_http_status_error_other_5xx(self):
        """5xx 状态码(550)应可重试"""
        worker = _make_chunk_worker()
        response = MagicMock()
        response.status_code = 550
        exc = httpx.HTTPStatusError("550", request=MagicMock(), response=response)
        assert worker._is_retryable_exception(exc) is True

    def test_request_error_is_retryable(self):
        """httpx.RequestError 应可重试"""
        worker = _make_chunk_worker()
        exc = httpx.ConnectError("conn failed")
        assert worker._is_retryable_exception(exc) is True

    def test_os_error_retryable_errno(self):
        """可重试 errno(ECONNRESET)应可重试"""
        worker = _make_chunk_worker()
        exc = OSError(errno.ECONNRESET, "Connection reset")
        assert worker._is_retryable_exception(exc) is True

    def test_os_error_permanent_errno(self):
        """永久 errno(ENOENT)应不可重试"""
        worker = _make_chunk_worker()
        exc = OSError(errno.ENOENT, "No such file")
        assert worker._is_retryable_exception(exc) is False

    def test_other_exception_not_retryable(self):
        """其他异常应不可重试"""
        worker = _make_chunk_worker()
        assert worker._is_retryable_exception(ValueError("bad")) is False


class TestChunkWorkerBuildErrorMessage:
    """ChunkWorker._build_error_message 测试"""

    def test_http_status_error_message(self):
        """HTTPStatusError 应包含状态码"""
        worker = _make_chunk_worker()
        response = MagicMock()
        response.status_code = 503
        exc = httpx.HTTPStatusError("err", request=MagicMock(), response=response)
        msg = worker._build_error_message(exc)
        assert "503" in msg

    def test_request_error_message(self):
        """RequestError 应返回字符串表示"""
        worker = _make_chunk_worker()
        exc = httpx.ConnectError("conn failed")
        msg = worker._build_error_message(exc)
        assert "conn failed" in msg

    def test_os_error_message(self):
        """OSError 应包含文件读写失败"""
        worker = _make_chunk_worker()
        exc = OSError("disk error")
        msg = worker._build_error_message(exc)
        assert "文件读写失败" in msg

    def test_stop_iteration_message(self):
        """StopIteration 应返回字符串表示"""
        worker = _make_chunk_worker()
        exc = StopIteration("mismatch")
        msg = worker._build_error_message(exc)
        assert "mismatch" in msg

    def test_unknown_exception_message(self):
        """未知异常应包含"未知异常" """
        worker = _make_chunk_worker()
        msg = worker._build_error_message(ValueError("weird"))
        assert "未知异常" in msg


class TestChunkWorkerReportFailure:
    """ChunkWorker._report_download_failure 测试"""

    def test_sets_stop_event_and_invokes_error(self):
        """_report_download_failure 应设置 stop_event 并调用 _invoke_download_error"""
        parent = MagicMock()
        worker = _make_chunk_worker(parent=parent)
        worker.stop_event.clear()

        worker._report_download_failure(RuntimeError("boom"), attempt=3, retryable=False)

        assert worker.stop_event.is_set()
        parent.on_download_error.assert_called_once()

    def test_retryable_message_includes_attempt_count(self):
        """可重试时消息应包含尝试次数"""
        parent = MagicMock()
        worker = _make_chunk_worker(parent=parent)
        worker.stop_event.clear()

        worker._report_download_failure(RuntimeError("boom"), attempt=3, retryable=True)

        msg = parent.on_download_error.call_args[0][0]
        assert "3" in msg

    def test_non_retryable_message_indicates_permanent(self):
        """不可重试时消息应包含"不可重试" """
        parent = MagicMock()
        worker = _make_chunk_worker(parent=parent)
        worker.stop_event.clear()

        worker._report_download_failure(RuntimeError("boom"), attempt=1, retryable=False)

        msg = parent.on_download_error.call_args[0][0]
        assert "不可重试" in msg


class TestChunkWorkerRun:
    """ChunkWorker.run 测试"""

    def test_run_returns_when_stop_event_set(self):
        """stop_event 已设置时 run 应立即返回"""
        worker = _make_chunk_worker()
        worker.stop_event.set()
        worker.run()  # 不应抛异常

    def test_run_returns_when_generation_inactive(self):
        """generation 不活跃时 run 应立即返回"""
        parent = MagicMock()
        parent.is_generation_active.return_value = False
        worker = _make_chunk_worker(parent=parent)
        worker.run()

    def test_run_success_downloads_chunk(self, tmp_path):
        """成功路径应下载分片并调用 on_chunk_finished"""
        file_path = tmp_path / "test.mp4"
        file_path.touch()
        # 预填充文件
        with open(file_path, "wb") as f:
            f.write(b"\0" * 1024)

        parent = MagicMock()
        parent.is_generation_active.return_value = True

        worker = _make_chunk_worker(
            chunk_range=(0, 8),
            file_path=file_path,
            url="https://example.com/video",
            parent=parent,
        )

        # mock session.stream 返回上下文管理器
        fake_response = MagicMock()
        fake_response.headers = {"Content-Length": "8"}
        chunk_data = [b"abcdefgh"]

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__enter__ = MagicMock(return_value=fake_response)
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)

        fake_response.iter_bytes = MagicMock(return_value=iter(chunk_data))
        fake_response.raise_for_status = MagicMock()

        worker.session.stream = MagicMock(return_value=mock_stream_ctx)

        worker.run()

        parent.on_chunk_finished.assert_called_once_with("video", 0)

    def test_run_calls_chunk_start_end_callbacks(self, tmp_path):
        """run 应调用 on_chunk_start 和 on_chunk_end 回调"""
        file_path = tmp_path / "test.mp4"
        file_path.touch()
        with open(file_path, "wb") as f:
            f.write(b"\0" * 1024)

        chunk_start_called = {"n": 0}
        chunk_end_called = {"n": 0}

        parent = MagicMock()
        parent.is_generation_active.return_value = True

        worker = _make_chunk_worker(
            chunk_range=(0, 8),
            file_path=file_path,
            parent=parent,
            on_chunk_start=lambda: chunk_start_called.__setitem__("n", 1),
            on_chunk_end=lambda: chunk_end_called.__setitem__("n", 1),
        )

        fake_response = MagicMock()
        fake_response.headers = {"Content-Length": "8"}
        fake_response.iter_bytes = MagicMock(return_value=iter([b"abcdefgh"]))
        fake_response.raise_for_status = MagicMock()

        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__enter__ = MagicMock(return_value=fake_response)
        mock_stream_ctx.__exit__ = MagicMock(return_value=False)
        worker.session.stream = MagicMock(return_value=mock_stream_ctx)

        worker.run()

        assert chunk_start_called["n"] == 1
        assert chunk_end_called["n"] == 1


def _make_chunk_worker(chunk_range=(0, 1024), file_path=None, url="https://example.com",
                       parent=None, on_chunk_start=None, on_chunk_end=None):
    """构造 ChunkWorker 实例用于单元测试"""
    if file_path is None:
        file_path = Path("/tmp/test.mp4")
    if parent is None:
        parent = MagicMock()
    parent.is_generation_active = MagicMock(return_value=True)

    return ChunkWorker(
        session=MagicMock(),
        file_key="video",
        chunk_index=0,
        chunk_range=chunk_range,
        file_path=file_path,
        url=url,
        referer="https://example.com",
        task_info=make_task_info(),
        stop_event=threading.Event(),
        lock=threading.Lock(),
        token_bucket=TokenBucket(0),
        generation=1,
        parent=parent,
        on_chunk_start=on_chunk_start,
        on_chunk_end=on_chunk_end,
    )


# ===========================================================================
# Downloader
# ===========================================================================
class TestDownloaderInit:
    """Downloader.__init__ 测试"""

    def test_init_sets_fields(self, monkeypatch):
        """__init__ 应设置 task_info/token_bucket/chunk_size/locks 等"""
        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        monkeypatch.setitem(Downloader.__init__.__globals__,
                            "config",
                            MagicMock(get=lambda k, default=None: 0))
        dl = make_downloader()

        assert dl.task_info is not None
        assert dl.token_bucket is not None
        assert dl.chunk_size == 4 * 1024 * 1024
        assert dl.download_list == {}
        assert dl._stop_event is not None
        assert dl.update_lock is not None
        assert dl.active_workers == 0
        assert dl.speed_timer is not None

    def test_init_with_speed_limit(self, monkeypatch):
        """speed_limit_enabled=True 时应创建限速 TokenBucket"""
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, default=None: {
            "speed_limit_enabled": True,
            "speed_limit_rate": 2,  # 2 MB/s
        }.get(k, default)
        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        monkeypatch.setitem(Downloader.__init__.__globals__, "config", cfg)

        dl = make_downloader()
        assert dl.token_bucket.rate == 2 * 1024 * 1024


class TestDownloaderStart:
    """Downloader.start 测试"""

    def test_start_completes_when_progress_100(self, monkeypatch):
        """progress >= 100 时应调用 on_download_completed"""
        dl = make_downloader()
        dl.task_info.Download.progress = 100

        with patch.object(dl, "on_download_completed") as completed:
            dl.start()

        completed.assert_called_once()

    def test_start_starts_parse_worker_for_video(self, monkeypatch):
        """VIDEO 类型应启动 ParseWorker"""
        dl = make_downloader()
        dl.task_info.Download.type = DownloadType.VIDEO
        dl.task_info.Download.queue = ["video"]
        dl.task_info.Download.total_size = 1024

        with patch("util.download.downloader.downloader.GlobalThreadPoolTask.run") as pool, \
             patch("util.download.downloader.parse_worker.ParseWorker") as parse_cls:
            dl.start()

        pool.assert_called_once()
        assert dl.task_info.Download.status == DownloadStatus.PARSING

    def test_start_completes_when_no_video_no_audio(self, monkeypatch):
        """无 VIDEO/AUDIO 类型应直接完成(附加文件)"""
        dl = make_downloader()
        dl.task_info.Download.type = DownloadType.DANMAKU  # 仅附加文件
        dl.task_info.Download.queue = []
        dl.task_info.Download.total_size = 1024

        with patch.object(dl, "on_download_completed") as completed:
            dl.start()

        completed.assert_called_once()


class TestDownloaderParseCallbacks:
    """Downloader.on_parse_finished / on_parse_error 测试"""

    def test_on_parse_finished_starts_download(self):
        """on_parse_finished 应解析 json 并启动下载"""
        dl = make_downloader()
        dl.task_info.Download.files = {}  # 首次解析

        download_info = {
            "total_size": 2048,
            "download_queue": ["video"],
            "download_list": {"video": {"file_size": 2048, "url": "https://example.com"}},
        }
        import json
        json_str = json.dumps(download_info)

        with patch.object(dl, "start_download") as start_dl, \
             patch.object(dl, "update_info"):
            dl.on_parse_finished(json_str)

        assert dl.task_info.Download.status == DownloadStatus.DOWNLOADING
        assert dl.task_info.Download.total_size == 2048
        start_dl.assert_called_once()

    def test_on_parse_finished_skips_when_stopped(self):
        """_stop_event 已设置时 on_parse_finished 应直接返回"""
        dl = make_downloader()
        dl._stop_event.set()

        dl.on_parse_finished('{"total_size": 0, "download_queue": [], "download_list": {}}')
        # 不应修改状态
        assert dl.task_info.Download.status != DownloadStatus.DOWNLOADING

    def test_on_parse_error_sets_failed(self):
        """on_parse_error 应设置 FAILED 状态"""
        dl = make_downloader()

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {"signal_bus": MagicMock()}):
            dl.on_parse_error("parse error")

        assert dl.task_info.Download.status == DownloadStatus.FAILED

    def test_on_download_error_sets_failed_once(self):
        """on_download_error 应设置 FAILED 且去重(仅触发一次)"""
        dl = make_downloader()

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {"signal_bus": MagicMock()}):
            dl.on_download_error("error 1")
            dl.on_download_error("error 2")  # 应被忽略

        assert dl.task_info.Download.status == DownloadStatus.FAILED
        assert dl._download_error_triggered is True


class TestDownloaderGeneration:
    """Downloader.is_generation_active 测试"""

    def test_is_generation_active_true(self):
        """当前 generation 应返回 True"""
        dl = make_downloader()
        dl.download_generation = 5
        assert dl.is_generation_active(5) is True

    def test_is_generation_active_false(self):
        """非当前 generation 应返回 False"""
        dl = make_downloader()
        dl.download_generation = 5
        assert dl.is_generation_active(3) is False


class TestDownloaderPauseResume:
    """Downloader.pause / resume 测试"""

    def test_pause_increments_generation_and_sets_status(self):
        """pause 应递增 generation 并设置 PAUSED"""
        dl = make_downloader()
        dl.download_generation = 1

        dl.pause()

        assert dl.download_generation == 2
        assert dl.task_info.Download.status == DownloadStatus.PAUSED
        assert dl._stop_event.is_set()

    def test_resume_clears_and_starts(self):
        """resume 应清除 stop_event 并调用 start"""
        dl = make_downloader()
        dl._stop_event.set()

        with patch.object(dl, "start") as start_method:
            dl.resume()

        assert not dl._stop_event.is_set()
        assert dl.task_info.Download.status == DownloadStatus.DOWNLOADING
        start_method.assert_called_once()


class TestDownloaderRetry:
    """Downloader.retry 测试"""

    def test_retry_failed_starts_download(self):
        """FAILED 状态应调用 start"""
        dl = make_downloader()
        dl.task_info.Download.status = DownloadStatus.FAILED

        with patch.object(dl, "start") as start_method:
            dl.retry()

        start_method.assert_called_once()

    def test_retry_ffmpeg_failed_starts_merge(self):
        """FFMPEG_FAILED 状态应调用 start_merge"""
        dl = make_downloader()
        dl.task_info.Download.status = DownloadStatus.FFMPEG_FAILED

        with patch.object(dl, "start_merge") as merge_method:
            dl.retry()

        merge_method.assert_called_once()


class TestDownloaderChunkMath:
    """Downloader.calc_chunk_list / calc_chunk_range / calc_downloaded_size 测试"""

    def test_calc_chunk_list_existing_chunks(self):
        """已有 chunks_list 时应直接返回"""
        dl = make_downloader()
        dl.task_info.Download.files = {
            "video": {"chunks_list": [0, 1, 2], "total_chunks": 3}
        }
        result = dl.calc_chunk_list("video", 1024, 256)
        assert result == [0, 1, 2]

    def test_calc_chunk_list_creates_new(self):
        """无 chunks_list 时应创建新列表"""
        dl = make_downloader()
        dl.task_info.Download.files = {
            "video": {"chunks_list": [], "total_chunks": 0}
        }
        result = dl.calc_chunk_list("video", 1024, 256)
        assert result == [0, 1, 2, 3]
        assert dl.task_info.Download.files["video"]["total_chunks"] == 4

    def test_calc_chunk_list_zero_size(self):
        """total_size=0 时应有 1 个分片"""
        dl = make_downloader()
        dl.task_info.Download.files = {
            "video": {"chunks_list": [], "total_chunks": 0}
        }
        result = dl.calc_chunk_list("video", 0, 256)
        assert result == [0]

    def test_calc_chunk_range_normal(self):
        """calc_chunk_range 应正确计算范围"""
        dl = make_downloader()
        start, end = dl.calc_chunk_range(0, 256, 1024)
        assert start == 0
        assert end == 256

    def test_calc_chunk_range_last_chunk(self):
        """最后一个分片应截断到 total_size"""
        dl = make_downloader()
        start, end = dl.calc_chunk_range(3, 256, 1000)
        assert start == 768
        assert end == 1000

    def test_calc_chunk_range_zero_size(self):
        """total_size=0 时 end 应为 0"""
        dl = make_downloader()
        start, end = dl.calc_chunk_range(0, 256, 0)
        assert start == 0
        assert end == 0

    def test_calc_downloaded_size_sums_completed_chunks(self):
        """calc_downloaded_size 应累加已完成分片大小"""
        dl = make_downloader()
        dl.chunk_size = 256
        dl.task_info.Download.files = {
            "video": {
                "total_chunks": 4,
                "file_size": 1024,
                "chunks_list": [2, 3],  # 0 和 1 已完成
            }
        }
        dl.calc_downloaded_size()
        # 分片 0: 0-256, 分片 1: 256-512, 共 512
        assert dl.task_info.Download.downloaded_size == 512


class TestDownloaderOnChunkFinished:
    """Downloader.on_chunk_finished 测试"""

    def test_on_chunk_finished_updates_progress(self):
        """on_chunk_finished 应更新 finished_chunks 和 chunks_list"""
        dl = make_downloader()
        dl.task_info.Download.files = {
            "video": {
                "chunks_list": [0, 1],
                "total_chunks": 2,
                "finished_chunks": 0,
            }
        }
        dl.task_info.Download.queue = ["video"]

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {"task_manager": MagicMock()}):
            dl.on_chunk_finished("video", 0)

        file_info = dl.task_info.Download.files["video"]
        assert 0 not in file_info["chunks_list"]
        assert file_info["finished_chunks"] == 1

    def test_on_chunk_finished_removes_from_queue_when_complete(self):
        """分片完成且进度 100% 时应从 queue 移除"""
        dl = make_downloader()
        dl.task_info.Download.files = {
            "video": {
                "chunks_list": [0],
                "total_chunks": 1,
                "finished_chunks": 0,
            }
        }
        dl.task_info.Download.queue = ["video"]

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {"task_manager": MagicMock()}), \
             patch.object(dl, "start_download") as start_dl:
            dl.on_chunk_finished("video", 0)

        assert "video" not in dl.task_info.Download.queue

    def test_on_chunk_finished_triggers_completed_when_queue_empty(self):
        """queue 全空时应触发 on_download_completed"""
        dl = make_downloader()
        dl.task_info.Download.files = {
            "video": {
                "chunks_list": [0],
                "total_chunks": 1,
                "finished_chunks": 0,
            }
        }
        dl.task_info.Download.queue = ["video"]
        dl.task_info.Download.status = DownloadStatus.DOWNLOADING

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {"task_manager": MagicMock()}), \
             patch.object(dl, "on_download_completed") as completed:
            dl.on_chunk_finished("video", 0)

        completed.assert_called_once()


class TestDownloaderUpdateInfo:
    """Downloader.update_info 测试"""

    def test_update_info_initializes_files_dict(self):
        """首次调用 update_info 应初始化 files 字典"""
        dl = make_downloader()
        dl.task_info.Download.files = {}
        dl.task_info.Download.type = DownloadType.VIDEO | DownloadType.AUDIO

        download_info = {
            "download_queue": ["video", "audio"],
            "download_list": {
                "video": {"file_size": 1024},
                "audio": {"file_size": 512},
            },
        }

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {"task_manager": MagicMock()}):
            dl.update_info(download_info)

        assert "video" in dl.task_info.Download.files
        assert "audio" in dl.task_info.Download.files
        assert dl.task_info.Download.files["video"]["file_size"] == 1024

    def test_update_info_skips_when_files_exist(self):
        """files 非空时 update_info 应跳过初始化"""
        dl = make_downloader()
        dl.task_info.Download.files = {"existing": {}}

        dl.update_info({"download_queue": [], "download_list": {}})

        assert "existing" in dl.task_info.Download.files


class TestDownloaderOnDownloadCompleted:
    """Downloader.on_download_completed 测试"""

    def test_on_download_completed_with_additional(self):
        """有附加文件时应启动 AdditionalParseWorker"""
        dl = make_downloader()
        dl.task_info.Download.type = DownloadType.VIDEO | DownloadType.DANMAKU

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        fake_add_cls = MagicMock()
        fake_async_cls = MagicMock()
        with patch.dict(Downloader.__init__.__globals__, {
            "AdditionalParseWorker": fake_add_cls,
            "AsyncTask": fake_async_cls,
        }):
            fake_worker = MagicMock()
            fake_add_cls.return_value = fake_worker
            dl.on_download_completed()

        assert dl.task_info.Download.status == DownloadStatus.ADDITIONAL_PROCESSING
        fake_add_cls.assert_called_once()

    def test_on_download_completed_without_additional(self):
        """无附加文件时应直接 wait_merge"""
        dl = make_downloader()
        dl.task_info.Download.type = DownloadType.VIDEO

        with patch.object(dl, "wait_merge") as wait:
            dl.on_download_completed()

        wait.assert_called_once()

    def test_on_download_completed_dedup(self):
        """重复调用 on_download_completed 应去重"""
        dl = make_downloader()
        dl.task_info.Download.type = DownloadType.VIDEO

        with patch.object(dl, "wait_merge") as wait:
            dl.on_download_completed()
            dl.on_download_completed()

        wait.assert_called_once()


class TestDownloaderWaitMerge:
    """Downloader.wait_merge 测试"""

    def test_wait_merge_sets_status_and_stops(self):
        """wait_merge 应设置 FFMPEG_QUEUED 并停止"""
        dl = make_downloader()
        dl.session = MagicMock()

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {
            "task_manager": MagicMock(),
            "signal_bus": MagicMock(),
        }):
            dl.wait_merge()

        assert dl.task_info.Download.status == DownloadStatus.FFMPEG_QUEUED
        assert dl._stop_event.is_set()
        dl.session.close.assert_called_once()


class TestDownloaderChunkCallbacks:
    """Downloader.on_chunk_start / on_chunk_end / wait 测试"""

    def test_on_chunk_start_increments_counter(self):
        """on_chunk_start 应递增 active_workers"""
        dl = make_downloader()
        dl.active_workers = 0
        dl.on_chunk_start()
        assert dl.active_workers == 1

    def test_on_chunk_end_decrements_counter(self):
        """on_chunk_end 应递减 active_workers"""
        dl = make_downloader()
        dl.active_workers = 1
        dl.on_chunk_end()
        assert dl.active_workers == 0

    def test_on_chunk_end_triggers_wait_callback(self):
        """active_workers=0 且 wait_flag=True 时应触发 wait_callback"""
        dl = make_downloader()
        dl.active_workers = 1
        dl.wait_flag = True
        dl._stop_event.set()
        callback = MagicMock()
        dl.wait_callback = callback

        dl.on_chunk_end()

        callback.assert_called_once()

    def test_wait_with_no_active_workers(self):
        """无活跃 worker 时 wait 应立即调用回调"""
        dl = make_downloader()
        dl.active_workers = 0
        callback = MagicMock()

        dl.wait(callback)

        callback.assert_called_once()

    def test_wait_with_active_workers(self):
        """有活跃 worker 时 wait 应设置标志,不立即调用"""
        dl = make_downloader()
        dl.active_workers = 1
        callback = MagicMock()

        dl.wait(callback)

        assert dl.wait_flag is True
        callback.assert_not_called()


class TestDownloaderTimer:
    """Downloader.start_timer / _calculate_speed 测试"""

    def test_start_timer_starts_when_inactive(self):
        """speed_timer 未运行时应启动"""
        dl = make_downloader()
        with patch.object(dl.speed_timer, "start") as start:
            dl.start_timer()
        start.assert_called_once()

    def test_start_timer_skips_when_active(self):
        """speed_timer 已运行时应跳过"""
        dl = make_downloader()
        dl.speed_timer._stopped = False  # 模拟运行中
        with patch.object(dl.speed_timer, "start") as start:
            dl.start_timer()
        start.assert_not_called()

    def test_calculate_speed_updates_progress(self):
        """_calculate_speed 应更新 speed 和 progress"""
        dl = make_downloader()
        dl.task_info.Download.downloaded_size = 512
        dl.task_info.Download.total_size = 1024
        dl.last_sampled_size = 0

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {
            "signal_bus": MagicMock(),
            "task_manager": MagicMock(),
        }):
            dl._calculate_speed()

        assert dl.task_info.Download.speed == 512
        assert dl.task_info.Download.progress == 50

    def test_calculate_speed_triggers_completed_when_queue_empty(self):
        """queue 空 + DOWNLOADING 状态时应触发 on_download_completed"""
        dl = make_downloader()
        dl.task_info.Download.queue = []
        dl.task_info.Download.status = DownloadStatus.DOWNLOADING
        dl.task_info.Download.downloaded_size = 100
        dl.task_info.Download.total_size = 100
        dl.last_sampled_size = 100

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        with patch.dict(Downloader.__init__.__globals__, {
            "signal_bus": MagicMock(),
            "task_manager": MagicMock(),
        }), \
             patch.object(dl, "on_download_completed") as completed:
            dl._calculate_speed()

        completed.assert_called_once()


class TestDownloaderOnDelete:
    """Downloader.on_delete 测试"""

    def test_on_delete_clears_references(self):
        """on_delete 应清理 session/task_info/download_list"""
        dl = make_downloader()
        dl.on_delete()
        assert dl.session is None
        assert dl.task_info is None
        assert dl.download_list is None


class TestDownloaderUpdateItem:
    """Downloader.update_item 测试"""

    def test_update_item_emits_signal(self):
        """update_item 应 emit signal 并调用 task_manager.update_async"""
        dl = make_downloader()
        info = make_task_info()

        # 通过 Downloader.__init__.__globals__ 直接 patch,避免 cross-test 污染导致字符串路径 patch 失效
        fake_bus = MagicMock()
        fake_tm = MagicMock()
        with patch.dict(Downloader.__init__.__globals__, {
            "signal_bus": fake_bus,
            "task_manager": fake_tm,
        }):
            dl.update_item(info)

        fake_bus.download.update_downloading_item.emit.assert_called_once_with(info)
        fake_tm.update_async.assert_called_once()


class TestDownloaderCheckDiskSpace:
    """Downloader._check_disk_space 测试"""

    def test_check_disk_space_raises_when_insufficient(self, tmp_path):
        """磁盘空间不足时应抛 OSError"""
        dl = make_downloader()

        # 通过 Downloader.__init__.__globals__ 直接 patch Directory 类方法,避免 cross-test 污染失效
        Directory_cls = Downloader.__init__.__globals__["Directory"]
        with patch.object(Directory_cls, "has_enough_space",
                          return_value=False, create=True):
            with pytest.raises(OSError, match="INSUFFICIENT_SPACE"):
                dl._check_disk_space(tmp_path / "test.mp4", 1024)

    def test_check_disk_space_preallocates_when_enabled(self, tmp_path, monkeypatch):
        """preallocate_file_space=True 时应预分配文件"""
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, default=None: {
            "preallocate_file_space": True,
            "speed_limit_enabled": False,
        }.get(k, default)
        # 通过 Downloader.__init__.__globals__ 直接 patch config/Directory/File,避免 cross-test 污染失效
        monkeypatch.setitem(Downloader.__init__.__globals__, "config", cfg)

        dl = make_downloader()
        file_path = tmp_path / "new.mp4"

        Directory_cls = Downloader.__init__.__globals__["Directory"]
        File_cls = Downloader.__init__.__globals__["File"]
        with patch.object(Directory_cls, "has_enough_space",
                          return_value=True, create=True), \
             patch.object(File_cls, "preallocate_file") as prealloc:
            dl._check_disk_space(file_path, 1024)

        prealloc.assert_called_once()

    def test_check_disk_space_creates_placeholder_when_disabled(self, tmp_path, monkeypatch):
        """preallocate_file_space=False 时应创建占位文件"""
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, default=None: {
            "preallocate_file_space": False,
            "speed_limit_enabled": False,
        }.get(k, default)
        # 通过 Downloader.__init__.__globals__ 直接 patch config/Directory/File,避免 cross-test 污染失效
        monkeypatch.setitem(Downloader.__init__.__globals__, "config", cfg)

        dl = make_downloader()
        file_path = tmp_path / "new.mp4"

        Directory_cls = Downloader.__init__.__globals__["Directory"]
        File_cls = Downloader.__init__.__globals__["File"]
        with patch.object(Directory_cls, "has_enough_space",
                          return_value=True, create=True), \
             patch.object(File_cls, "create_placeholder") as placeholder:
            dl._check_disk_space(file_path, 1024)

        placeholder.assert_called_once()

    def test_check_disk_space_skips_when_file_exists(self, tmp_path, monkeypatch):
        """文件已存在且 file_size > 0 时不应预分配"""
        cfg = MagicMock()
        cfg.get.side_effect = lambda k, default=None: {
            "preallocate_file_space": True,
            "speed_limit_enabled": False,
        }.get(k, default)
        # 通过 Downloader.__init__.__globals__ 直接 patch config/Directory/File,避免 cross-test 污染失效
        monkeypatch.setitem(Downloader.__init__.__globals__, "config", cfg)

        dl = make_downloader()
        file_path = tmp_path / "existing.mp4"
        file_path.touch()

        Directory_cls = Downloader.__init__.__globals__["Directory"]
        File_cls = Downloader.__init__.__globals__["File"]
        with patch.object(Directory_cls, "has_enough_space",
                          return_value=True, create=True), \
             patch.object(File_cls, "preallocate_file") as prealloc:
            dl._check_disk_space(file_path, 1024)

        prealloc.assert_not_called()


class TestDownloaderStartDownload:
    """Downloader.start_download / _start_worker_in_background 测试"""

    def test_start_download_starts_timer_and_submits(self):
        """start_download 应启动 timer 并提交到线程池"""
        dl = make_downloader()

        with patch.object(dl, "start_timer") as start_timer, \
             patch("util.download.downloader.downloader.GlobalThreadPoolTask.run_func") as pool:
            dl.start_download()

        start_timer.assert_called_once()
        pool.assert_called_once()

    def test_start_download_skips_when_pending(self):
        """start_worker_pending=True 时应跳过"""
        dl = make_downloader()
        dl.start_worker_pending = True

        with patch.object(dl, "start_timer"), \
             patch("util.download.downloader.downloader.GlobalThreadPoolTask.run_func") as pool:
            dl.start_download()

        pool.assert_not_called()

    def test_start_download_exception_triggers_error(self):
        """start_download 异常时应调用 on_download_error"""
        dl = make_downloader()

        with patch.object(dl, "start_timer", side_effect=RuntimeError("boom")), \
             patch.object(dl, "on_download_error") as err:
            dl.start_download()

        err.assert_called_once()

    def test_start_worker_in_background_calls_start_worker(self):
        """_start_worker_in_background 应调用 start_worker"""
        dl = make_downloader()
        dl.download_generation = 1

        with patch.object(dl, "start_worker") as start_worker:
            dl._start_worker_in_background(1)

        start_worker.assert_called_once_with(1)

    def test_start_worker_in_background_skips_when_stopped(self):
        """_stop_event 已设置时 _start_worker_in_background 应跳过"""
        dl = make_downloader()
        dl._stop_event.set()

        with patch.object(dl, "start_worker") as start_worker:
            dl._start_worker_in_background(1)

        start_worker.assert_not_called()

    def test_start_worker_in_background_exception_triggers_error(self):
        """start_worker 异常时应调用 on_download_error"""
        dl = make_downloader()
        dl.download_generation = 1  # 使 generation 1 活跃

        with patch.object(dl, "start_worker", side_effect=RuntimeError("boom")), \
             patch.object(dl, "on_download_error") as err:
            dl._start_worker_in_background(1)

        err.assert_called_once()


class TestDownloaderStartWorker:
    """Downloader.start_worker 测试"""

    def test_start_worker_skips_when_queue_empty(self):
        """queue 为空时 start_worker 应直接返回"""
        dl = make_downloader()
        dl.task_info.Download.queue = []

        dl.start_worker(1)  # 不应抛异常

    def test_start_worker_skips_when_generation_inactive(self):
        """generation 不活跃时 start_worker 应直接返回"""
        dl = make_downloader()
        dl.task_info.Download.queue = ["video"]
        dl.download_generation = 2

        dl.start_worker(1)  # generation 1 不活跃

    def test_start_worker_skips_when_stopped(self):
        """_stop_event 已设置时 start_worker 应直接返回"""
        dl = make_downloader()
        dl.task_info.Download.queue = ["video"]
        dl._stop_event.set()

        dl.start_worker(1)


class TestDownloaderStartMerge:
    """Downloader.start_merge 测试"""

    def test_start_merge_creates_merger(self):
        """start_merge 应创建 Merger 并调用 start"""
        dl = make_downloader()

        with patch("util.download.downloader.merger.Merger") as merger_cls:
            fake_merger = MagicMock()
            merger_cls.return_value = fake_merger
            dl.start_merge()

        merger_cls.assert_called_once()
        fake_merger.start.assert_called_once()
        assert dl.task_info.Download.status == DownloadStatus.MERGING
