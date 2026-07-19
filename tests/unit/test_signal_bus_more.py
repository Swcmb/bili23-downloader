# tests/unit/test_signal_bus_more.py
"""SignalBus 补充测试 - 覆盖 emit_signal 边缘路径

补充 tests/unit/test_signal_bus.py 未覆盖的分支:
- emit_signal 在 main_window_ready=True 时立即触发
- emit_signal 对不存在的字符串信号名抛 AttributeError
- emit_signal 接受 Signal 对象(非字符串)
- pending_signals 缓存多个信号后一并 flush
- emit_pending_signals 第二次调用不重复 flush
- 嵌套分组(signal_bus.download.X 等)connect/emit 通路
- Signal.connect 重复注册同一回调自动去重
- Signal.disconnect 不存在的回调静默忽略
"""
import threading
import pytest


def test_emit_signal_immediate_when_ready():
    """main_window_ready=True 时立即 emit,不缓存"""
    from util.common.signal_bus import SignalBus

    bus = SignalBus()
    bus.main_window_ready = True

    received = []
    bus.ToastNotification.connect(lambda *a, **kw: received.append((a, kw)))

    bus.emit_signal("ToastNotification", "immediate", k=1)
    assert received == [(("immediate",), {"k": 1})]
    # 不应缓存
    assert bus.pending_signals == []


def test_emit_signal_unknown_name_raises():
    """emit_signal 对不存在的信号名抛 AttributeError"""
    from util.common.signal_bus import SignalBus

    bus = SignalBus()
    bus.main_window_ready = True  # ready=True 才会查找属性

    with pytest.raises(AttributeError, match="NonExistentSignal"):
        bus.emit_signal("NonExistentSignal", "arg")


def test_emit_signal_accepts_signal_object():
    """emit_signal 直接接受 Signal 对象作为参数"""
    from util.common.signal_bus import SignalBus, Signal

    bus = SignalBus()
    bus.main_window_ready = True
    sig = Signal()

    received = []
    sig.connect(lambda *a, **kw: received.append((a, kw)))

    bus.emit_signal(sig, "via_obj", x=2)
    assert received == [(("via_obj",), {"x": 2})]


def test_emit_signal_caches_multiple_pending():
    """main_window_ready=False 时多次 emit 全部缓存"""
    from util.common.signal_bus import SignalBus

    bus = SignalBus()
    bus.main_window_ready = False

    received = []
    bus.ToastNotification.connect(lambda *a, **kw: received.append((a, kw)))

    bus.emit_signal("ToastNotification", "msg-1")
    bus.emit_signal("ToastNotification", "msg-2")
    bus.emit_signal("ToastNotification", "msg-3")

    assert received == []  # 尚未 flush
    assert len(bus.pending_signals) == 3

    bus.emit_pending_signals()
    assert len(received) == 3
    assert received[0] == (("msg-1",), {})
    assert received[2] == (("msg-3",), {})


def test_emit_pending_signals_idempotent():
    """第二次调用 emit_pending_signals 不重复 flush"""
    from util.common.signal_bus import SignalBus

    bus = SignalBus()
    bus.main_window_ready = False
    bus.emit_signal("ToastNotification", "once")

    received = []
    bus.ToastNotification.connect(lambda *a, **kw: received.append(a))
    bus.emit_pending_signals()
    assert received == [("once",)]

    # 再次调用,不应重复触发
    bus.emit_pending_signals()
    assert received == [("once",)]


def test_nested_group_signal_emit_path():
    """嵌套分组 SignalBus().download.create_task.emit 触发回调

    使用独立 SignalBus 实例避免模块级 signal_bus 被业务代码
    (TaskManager 等)污染导致的 kwarg 不匹配问题。
    """
    from util.common.signal_bus import SignalBus

    bus = SignalBus()
    received = []
    cb = lambda *a, **kw: received.append((a, kw))
    bus.download.create_task.connect(cb)
    try:
        bus.download.create_task.emit("task-1", status="queued")
        # emit("task-1", status="queued") -> args=("task-1",), kwargs={"status": "queued"}
        assert received == [(("task-1",), {"status": "queued"})]
    finally:
        bus.download.create_task.disconnect(cb)


def test_nested_group_toast_signals_exist():
    """所有原 Qt 嵌套分组信号名都存在"""
    from util.common.signal_bus import signal_bus

    # Toast
    for name in ("show", "show_long_message", "sys_show"):
        assert hasattr(signal_bus.toast, name)

    # Parse
    for name in ("update_parse_list", "preview_init", "parse_url", "search_keyword"):
        assert hasattr(signal_bus.parse, name)

    # Download
    for name in (
        "create_task", "show_duplicate_download_dialog",
        "add_to_downloading_list", "add_to_completed_list",
        "start_next_task",
    ):
        assert hasattr(signal_bus.download, name)

    # Login
    for name in ("start_server", "stop_server", "send_sms", "update_avatar"):
        assert hasattr(signal_bus.login, name)

    # Update / Interface
    assert hasattr(signal_bus.update, "check")
    assert hasattr(signal_bus.update, "show_dialog")
    assert hasattr(signal_bus.interface, "mica_effect_changed")


def test_signal_connect_deduplicates():
    """Signal.connect 对同一回调自动去重"""
    from util.common.signal_bus import Signal

    sig = Signal()
    counter = {"count": 0}
    cb = lambda *a, **kw: counter.update(count=counter["count"] + 1)

    sig.connect(cb)
    sig.connect(cb)  # 重复注册应被去重
    sig.emit()
    assert counter["count"] == 1


def test_signal_disconnect_silent_on_missing():
    """Signal.disconnect 对未注册的回调静默忽略"""
    from util.common.signal_bus import Signal

    sig = Signal()
    # 未注册的回调,不抛异常
    sig.disconnect(lambda: None)


def test_signal_emit_no_callbacks():
    """Signal.emit 在无回调时不抛异常"""
    from util.common.signal_bus import Signal

    sig = Signal()
    sig.emit()  # no-op
    sig.emit("a", "b", k=1)


def test_signal_emit_kwargs_passed_to_callbacks():
    """Signal.emit 同时传递 args 与 kwargs"""
    from util.common.signal_bus import Signal

    sig = Signal()
    received = []
    sig.connect(lambda *a, **kw: received.append((a, kw)))
    sig.emit(1, 2, 3, x=10, y=20)
    assert received == [((1, 2, 3), {"x": 10, "y": 20})]


def test_signal_concurrent_connect_disconnect_safe():
    """并发 connect/disconnect 不会破坏 Signal 内部状态"""
    from util.common.signal_bus import Signal

    sig = Signal()

    def adder():
        for i in range(100):
            cb = lambda *a, i=i: None
            sig.connect(cb)

    def remover():
        for _ in range(100):
            # disconnect 不存在的回调也不抛异常
            sig.disconnect(lambda *a: None)

    threads = [threading.Thread(target=adder), threading.Thread(target=remover)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    # 不抛异常即通过
