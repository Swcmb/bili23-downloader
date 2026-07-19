# src/util/thread/async_.py
"""异步任务 - threading 包装,替代 Qt 异步机制

原实现基于 QThread + WorkerBase.moveToThread,通过 Qt 信号槽
驱动 worker.run()。改造后简化为 threading.Thread 封装,API
从 AsyncTask.run(worker, on_started, on_finished) 静态方法
改为 AsyncTask(func, *args, **kwargs) 实例 + start/join/is_alive。

旧 API 的 on_started/on_finished 回调与 safe_quit() 已移除,
调用方应在 func 内自行处理回调(待 Task 2 全量替换)。
"""
import threading
from typing import Callable, Any, Optional


class AsyncTask:
    """封装 threading.Thread 的异步任务

    使用 daemon=True 确保主进程退出时子线程不阻塞,
    与原 QThread.terminate 行为对齐(避免僵尸线程)。
    """

    def __init__(self, func: Callable, *args: Any, **kwargs: Any):
        # daemon=True:主进程退出时自动终止,避免阻塞退出
        self._thread = threading.Thread(
            target=func,
            args=args,
            kwargs=kwargs,
            daemon=True,
        )

    def start(self) -> None:
        """启动子线程"""
        self._thread.start()

    def join(self, timeout: Optional[float] = None) -> None:
        """等待子线程结束,可指定超时(秒)"""
        self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        """子线程是否仍在运行"""
        return self._thread.is_alive()
