# tests/unit/test_misc_update_coverage.py
"""misc/update.py 覆盖率补强测试

覆盖 Updater 的所有方法 + 多分支:
- __init__
- check:should_update True/False × manual True/False × skip_version 命中
- request_update:验证 worker 创建 + signal 连接 + AsyncTask 启动
"""
from unittest.mock import MagicMock, patch

import pytest

from util.common.config import config
from util.common.enum import ToastNotificationCategory
from util.misc.update import Updater


# ==================================================================
# 测试夹具:每次重置 Updater 的 manual 标志,避免相互影响
# ==================================================================

@pytest.fixture
def updater():
    return Updater()


@pytest.fixture(autouse=True)
def _reset_updater_state():
    """每个测试前重置 manual 标志,避免上次测试残留"""
    yield
    if hasattr(Updater, "manual"):
        del Updater.manual


# ==================================================================
# __init__
# ==================================================================

def test_init_does_not_require_parent(updater):
    """Updater 接受 parent=None,不报错"""
    # 验证 __init__ 不抛异常即可
    assert isinstance(updater, Updater)


# ==================================================================
# check - should_update=True 各分支
# ==================================================================

def test_check_should_update_emits_dialog_signal(updater):
    """should_update=True 时 emit show_dialog 信号"""
    response = {
        "should_update": True,
        "required": False,
        "latest_version": {
            "version": "2.12.0",
            "content": "release notes",
            "download_url": "https://example.com/dl",
        },
    }
    emitted = []
    updater.__class__.__bases__  # noqa: B018 - 仅触发引用,确保类已加载
    from util.common.signal_bus import signal_bus
    signal_bus.update.show_dialog.connect(lambda info: emitted.append(info))

    try:
        updater.check(response)
        assert len(emitted) == 1
        info = emitted[0]
        assert info["version"] == "2.12.0"
        assert info["update_url"] == "https://example.com/dl"
        assert info["should_update"] is True
        assert info["required"] is False
    finally:
        signal_bus.update.show_dialog.disconnect(emitted[0]) if emitted else None


def test_check_should_update_skipped_version_skips_when_not_manual(updater, monkeypatch):
    """should_update=True + skip_version 匹配 + not manual -> 不 emit"""
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "skip_version": "2.12.0",
        "app_version": "2.11.0",
    }.get(key, default))
    updater.manual = False

    response = {
        "should_update": True,
        "required": False,
        "latest_version": {
            "version": "2.12.0",
            "content": "x",
            "download_url": "https://example.com/dl",
        },
    }
    from util.common.signal_bus import signal_bus
    emitted = []
    cb = lambda info: emitted.append(info)
    signal_bus.update.show_dialog.connect(cb)
    try:
        updater.check(response)
        assert emitted == []
    finally:
        signal_bus.update.show_dialog.disconnect(cb)


def test_check_should_update_skipped_version_emits_when_manual(updater, monkeypatch):
    """should_update=True + skip_version 匹配 + manual -> 仍 emit"""
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "skip_version": "2.12.0",
        "app_version": "2.11.0",
    }.get(key, default))
    updater.manual = True

    response = {
        "should_update": True,
        "required": False,
        "latest_version": {
            "version": "2.12.0",
            "content": "x",
            "download_url": "https://example.com/dl",
        },
    }
    from util.common.signal_bus import signal_bus
    emitted = []
    cb = lambda info: emitted.append(info)
    signal_bus.update.show_dialog.connect(cb)
    try:
        updater.check(response)
        assert len(emitted) == 1
    finally:
        signal_bus.update.show_dialog.disconnect(cb)


# ==================================================================
# check - should_update=False 各分支
# ==================================================================

def test_check_already_latest_with_manual_emits_toast(updater, monkeypatch):
    """should_update=False + manual -> emit toast"""
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "app_version": "2.11.0",
    }.get(key, default))
    updater.manual = True

    response = {
        "should_update": False,
        "required": False,
        "latest_version": {
            "version": "2.11.0",
            "content": "",
            "download_url": "",
        },
    }
    from util.common.signal_bus import signal_bus
    emitted = []
    cb = lambda *a, **kw: emitted.append((a, kw))
    signal_bus.toast.show.emit = MagicMock(side_effect=lambda *a, **kw: emitted.append((a, kw)))
    # signal_bus.toast.show 是 Signal 实例,需要 patch 它的 emit
    original_emit = signal_bus.toast.show.emit
    signal_bus.toast.show.emit = cb
    try:
        updater.check(response)
        assert len(emitted) == 1
        args, _ = emitted[0]
        # 第一个参数应是 ToastNotificationCategory.SUCCESS
        assert args[0] == ToastNotificationCategory.SUCCESS
    finally:
        signal_bus.toast.show.emit = original_emit


def test_check_already_latest_without_manual_no_toast(updater, monkeypatch):
    """should_update=False + not manual -> 不 emit toast"""
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "app_version": "2.11.0",
    }.get(key, default))
    updater.manual = False

    response = {
        "should_update": False,
        "required": False,
        "latest_version": {
            "version": "2.11.0",
            "content": "",
            "download_url": "",
        },
    }
    from util.common.signal_bus import signal_bus
    emitted = []
    original_emit = signal_bus.toast.show.emit
    signal_bus.toast.show.emit = lambda *a, **kw: emitted.append((a, kw))
    try:
        updater.check(response)
        assert emitted == []
    finally:
        signal_bus.toast.show.emit = original_emit


# ==================================================================
# request_update - 验证调用链
# ==================================================================

def test_request_update_creates_worker_and_starts_async_task(updater, monkeypatch):
    """request_update 应创建 NetworkRequestWorker,连接信号,启动 AsyncTask"""
    fake_worker = MagicMock()
    fake_async = MagicMock()
    fake_async.start = MagicMock()
    fake_async_task_cls = MagicMock(return_value=fake_async)

    # app_version / app_comparable_version 为动态属性,raising=False 允许设置不存在的属性
    monkeypatch.setattr(config, "app_version", "2.11.0", raising=False)
    monkeypatch.setattr(config, "app_comparable_version", 2110000, raising=False)
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "include_prerelease": False,
    }.get(key, default))
    monkeypatch.setattr("util.misc.update.NetworkRequestWorker", MagicMock(return_value=fake_worker))
    monkeypatch.setattr("util.misc.update.AsyncTask", fake_async_task_cls)

    updater.request_update(manual=True)

    # manual 标志被设置
    assert updater.manual is True
    # AsyncTask 被构造并启动
    fake_async_task_cls.assert_called_once()
    fake_async.start.assert_called_once()
    # worker 的 success / error 信号被 connect
    fake_worker.success.connect.assert_called_once()
    fake_worker.error.connect.assert_called_once()


def test_request_update_manual_false(updater, monkeypatch):
    """manual=False 时也走相同流程"""
    fake_worker = MagicMock()
    fake_async_task_cls = MagicMock(return_value=MagicMock())

    monkeypatch.setattr(config, "app_version", "2.11.0", raising=False)
    monkeypatch.setattr(config, "app_comparable_version", 2110000, raising=False)
    monkeypatch.setattr(config, "get", lambda key, default=None: {
        "include_prerelease": True,
    }.get(key, default))
    monkeypatch.setattr("util.misc.update.NetworkRequestWorker", MagicMock(return_value=fake_worker))
    monkeypatch.setattr("util.misc.update.AsyncTask", fake_async_task_cls)

    updater.request_update(manual=False)
    assert updater.manual is False
