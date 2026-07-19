# tests/unit/test_thread_pool.py
"""线程池单元测试 - 验证 ThreadPoolExecutor 替代 QThreadPool"""
import time
import pytest


def test_run_executes_func():
    from util.thread.pool import GlobalThreadPoolTask
    result = GlobalThreadPoolTask.run(lambda x: x * 2, 21).result(timeout=5)
    assert result == 42


def test_run_func_is_alias():
    from util.thread.pool import GlobalThreadPoolTask
    assert GlobalThreadPoolTask.run_func is GlobalThreadPoolTask.run


def test_concurrent_tasks():
    from util.thread.pool import global_thread_pool
    futures = [global_thread_pool.submit(lambda i: i, i) for i in range(50)]
    results = [f.result(timeout=5) for f in futures]
    assert results == list(range(50))


def test_no_pyside6_import():
    """AC-023-1: import 不触发 PySide6"""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.thread.pool  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)


def test_worker_base_stop_signal():
    """WorkerBase 停止信号机制"""
    from util.thread.worker_base import WorkerBase
    worker = WorkerBase()
    assert worker.is_stopped is False
    worker.stop()
    assert worker.is_stopped is True


def test_worker_base_has_signals():
    """WorkerBase 暴露 success/error/finished 三个 Signal 属性"""
    from util.thread.worker_base import WorkerBase
    worker = WorkerBase()
    assert hasattr(worker, "success")
    assert hasattr(worker, "error")
    assert hasattr(worker, "finished")
    # 验证信号可 connect/emit
    received = []
    worker.finished.connect(lambda: received.append(1))
    worker.finished.emit()
    assert received == [1]
