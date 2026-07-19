# src/util/thread/pool.py
"""全局线程池 - 基于 concurrent.futures.ThreadPoolExecutor

替代 QThreadPool.globalInstance() + QRunnable。
线程池大小:min(32, (cpu_count or 4) * 4),与原 QThreadPool 默认行为一致。
"""
import atexit
import os
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any


def _calc_pool_size() -> int:
    """计算线程池大小,与原 QThreadPool 默认行为一致"""
    cpu = os.cpu_count() or 4
    return min(32, cpu * 4)


class GlobalThreadPoolTask:
    """全局线程池任务提交器,API 兼容原 QThreadPool.start

    原签名 run(runnable: QRunnable) -> None 已废弃,改为
    run(func, *args, **kwargs) -> Future,与 T2.2 调用方约定一致。
    使用 staticmethod 而非 classmethod,确保 run_func = run 别名
    在 `is` 比较下成立(classmethod 每次访问产生新 bound method)。
    """

    @staticmethod
    def run(func: Callable, *args: Any, **kwargs: Any) -> Future:
        """提交后台任务,返回 Future"""
        return global_thread_pool.submit(func, *args, **kwargs)

    # 兼容原 API 别名(原 run_func 同样接受 func + args/kwargs)
    run_func = run


# 模块级单例,保持与原代码 `from util.thread.pool import pool` 风格一致
# 注意:原 pool 变量为 QThreadPool 实例,现改为 ThreadPoolExecutor,
# 调用方应使用 global_thread_pool 名称,旧 pool 名称保留以减少破坏面
global_thread_pool = ThreadPoolExecutor(
    max_workers=_calc_pool_size(),
    thread_name_prefix="bili23-worker",
)
# 进程退出时优雅关闭线程池(wait=False 避免阻塞主线程退出)
atexit.register(global_thread_pool.shutdown, wait=False)
