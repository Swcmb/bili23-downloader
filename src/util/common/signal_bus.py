# src/util/common/signal_bus.py
"""事件总线 - 纯 Python 实现,替代 Qt Signal/QObject

设计要点:
- Signal 用回调列表替代 Qt Signal
- emit 在调用线程同步执行(不再支持 QueuedConnection)
- 跨线程安全通过 threading.Lock 保护回调列表
- 保留 main_window_ready 和 pending_signals 机制兼容原代码
"""
import threading
from typing import Callable, List, Tuple, Any


class Signal:
    """纯 Python 信号,API 兼容 PySide6.QtCore.Signal

    提供 connect/disconnect/emit 三个核心方法,回调列表通过
    threading.Lock 保护,确保跨线程 emit 安全。

    与 Qt Signal(*types) 语法兼容:__init__ 接受并忽略 *args,
    因为纯 Python 实现中参数类型由 emit 时决定,无需在定义时声明。
    """

    def __init__(self, *args: Any, **kwargs: Any):
        # 回调列表:用 Lock 保护,支持并发 connect/disconnect/emit
        # *args/**kwargs 接受并忽略,兼容 Qt Signal(object) 等类型声明语法
        self._callbacks: List[Callable] = []
        self._lock = threading.Lock()

    def connect(self, callback: Callable) -> None:
        """注册回调,重复注册同一回调自动去重"""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def disconnect(self, callback: Callable) -> None:
        """注销回调,不存在时静默忽略"""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def emit(self, *args: Any, **kwargs: Any) -> None:
        """同步触发所有回调(在调用线程执行)

        先在锁内拷贝回调列表,再在锁外执行,避免回调中再次
        connect/disconnect 导致死锁。
        """
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            cb(*args, **kwargs)


class SignalBus:
    """信号总线单例,聚合所有原 Qt 信号名称

    原实现中 ToastNotification/Parse/Download/Login/Update/Interface
    为嵌套 QObject 子类,改造后统一为 Signal 实例属性,API 简化为
    connect/emit/disconnect。
    """

    def __init__(self):
        # 保留原信号名称(原嵌套类名转为 Signal 实例属性)
        self.ToastNotification = Signal()
        self.Parse = Signal()
        self.Download = Signal()
        self.Login = Signal()
        self.Update = Signal()
        self.Interface = Signal()
        # 兼容原 main_window_ready 机制(原存储于 config,改为本机属性)
        self.main_window_ready: bool = False
        # 待发送信号缓存:格式 (signal_name, args, kwargs)
        self.pending_signals: List[Tuple[str, tuple, dict]] = []
        self._pending_lock = threading.Lock()

    def emit_signal(self, signal_name: str, *args: Any, **kwargs: Any) -> None:
        """触发命名信号,若 main_window_ready=False 则缓存到 pending_signals

        双重检查:获取锁后再确认一次 ready 状态,防止竞态条件下
        丢失信号(与原实现行为一致)。
        """
        if not self.main_window_ready:
            with self._pending_lock:
                if not self.main_window_ready:
                    self.pending_signals.append((signal_name, args, kwargs))
                    return
        sig = getattr(self, signal_name, None)
        if sig is None:
            raise AttributeError(f"SignalBus has no signal named '{signal_name}'")
        sig.emit(*args, **kwargs)

    def emit_pending_signals(self) -> None:
        """标记 main_window_ready=True 并 flush 所有待发送信号"""
        self.main_window_ready = True
        with self._pending_lock:
            pending = list(self.pending_signals)
            self.pending_signals.clear()
        for signal_name, args, kwargs in pending:
            sig = getattr(self, signal_name, None)
            if sig is not None:
                sig.emit(*args, **kwargs)


# 模块级单例,保持与原代码 `from util.common.signal_bus import signal_bus` 兼容
signal_bus = SignalBus()
