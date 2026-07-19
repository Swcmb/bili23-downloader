# tests/unit/test_signal_bus.py
"""事件总线单元测试 - 验证纯 Python 实现替代 Qt Signal"""
import threading
import time
import pytest


def test_signal_connect_and_emit():
    """connect 后 emit 触发回调"""
    from util.common.signal_bus import Signal
    received = []
    sig = Signal()
    sig.connect(lambda *a, **kw: received.append((a, kw)))
    sig.emit("hello", key="value")
    assert received == [(("hello",), {"key": "value"})]


def test_signal_disconnect():
    """disconnect 后不再触发"""
    from util.common.signal_bus import Signal
    received = []
    sig = Signal()
    def cb():
        received.append(1)
    sig.connect(cb)
    sig.emit()
    sig.disconnect(cb)
    sig.emit()
    assert received == [1]


def test_signal_cross_thread_safe():
    """跨线程 emit 安全(AC-022-3)"""
    from util.common.signal_bus import Signal
    counter = {"count": 0}
    lock = threading.Lock()
    sig = Signal()
    def cb():
        with lock:
            counter["count"] += 1
    sig.connect(cb)
    threads = [threading.Thread(target=sig.emit) for _ in range(1000)]
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    elapsed = time.time() - start
    assert counter["count"] == 1000
    assert elapsed < 5.0


def test_pending_signals_cache_and_flush():
    """pending_signals 在 main_window_ready=False 时缓存,True 后 flush(AC-022-4)"""
    from util.common import signal_bus
    received = []
    signal_bus.signal_bus.ToastNotification.connect(lambda *a, **kw: received.append((a, kw)))
    signal_bus.signal_bus.main_window_ready = False
    signal_bus.signal_bus.emit_signal("ToastNotification", "cached_msg")
    assert received == []  # 未 flush
    signal_bus.signal_bus.emit_pending_signals()  # 标记 ready 并 flush
    assert len(received) == 1
    assert received[0] == (("cached_msg",), {})


def test_no_pyside6_import():
    """AC-022-1: import 不触发 PySide6"""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.signal_bus  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
