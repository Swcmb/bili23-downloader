# src/util/thread/worker_base.py
"""Worker 基类 - 纯 Python 实现,替代 QObject 版本

设计要点:
- 继承 object 而非 QObject,移除 Qt 元对象系统开销
- success/error/finished 用纯 Python Signal 替代 Qt Signal
- threading.Event 作为停止信号,跨线程安全
- 移除 @Slot() 装饰器(纯 Python 无需信号槽机制)
"""
import threading

from util.common.signal_bus import Signal


class WorkerBase:
    """Worker 基类,所有 parse/download worker 继承此类

    原 API:QObject 子类 + Qt Signal/Slot。改造后保持调用方
    接口兼容(success/error/finished 三信号、run() 方法),但
    内部实现完全去 Qt 化。
    """

    def __init__(self):
        # 三个对外信号,API 与原 Qt Signal 一致
        # error 携带异常对象,便于上层回调处理
        self.success = Signal()
        self.error = Signal(object)
        self.finished = Signal()
        # 停止信号:threading.Event 跨线程安全,替代原 bool 标志
        self._stop_event = threading.Event()

    @property
    def is_stopped(self) -> bool:
        """是否收到停止信号"""
        return self._stop_event.is_set()

    def stop(self) -> None:
        """设置停止信号,子类 run() 应轮询 is_stopped 主动退出"""
        self._stop_event.set()

    def run(self) -> None:
        """子类实现具体任务逻辑,基类默认抛出 NotImplementedError"""
        raise NotImplementedError("Subclass must implement run()")
