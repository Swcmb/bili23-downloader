# src/util/common/signal_bus.py
"""事件总线 - 纯 Python 实现,替代 Qt Signal/QObject

设计要点:
- Signal 用回调列表替代 Qt Signal
- emit 在调用线程同步执行(不再支持 QueuedConnection)
- 跨线程安全通过 threading.Lock 保护回调列表
- 保留 main_window_ready 和 pending_signals 机制兼容原代码
- 同时支持嵌套分组 API(signal_bus.download.X)与扁平 API(signal_bus.Download)
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


class _SignalGroup:
    """信号分组命名空间,替代原 Qt 嵌套 QObject 子类

    每个分组实例持有若干 Signal 属性,与原 signal_bus.download.X /
    signal_bus.toast.X 等嵌套 API 完全兼容。原 Qt 实现中每个分组是
    QObject 子类,纯 Python 版改为简单命名空间以避免 QObject 依赖。
    """
    pass


def _make_group(*signal_names: str) -> _SignalGroup:
    """创建信号分组并初始化指定的 Signal 属性

    :param signal_names: 分组内信号名称列表
    :return: 填充好 Signal 属性的分组对象
    """
    group = _SignalGroup()
    for name in signal_names:
        setattr(group, name, Signal())
    return group


class SignalBus:
    """信号总线单例,聚合所有原 Qt 信号名称

    支持两套 API:
    1. 嵌套分组 API(原 Qt 设计,业务代码使用):
       signal_bus.download.create_task / signal_bus.toast.show 等
    2. 扁平 API(T1 引入,test_signal_bus.py 兼容用):
       signal_bus.ToastNotification / signal_bus.Download 等

    嵌套分组保留原 Qt signal_bus 的完整信号目录,确保业务代码的
    emit/connect 调用无需修改(符合"信号 emit 保持不变"原则)。
    """

    def __init__(self):
        # === 嵌套分组(原 Qt 嵌套 QObject 子类的纯 Python 等价) ===
        # Toast 通知分组
        self.toast = _make_group(
            "show",
            "show_long_message",
            "sys_show",
        )

        # 解析分组
        self.parse = _make_group(
            "update_parse_list",
            "update_parse_list_count",
            "preview_init",
            "preview_finish",
            "query_video_info",
            "query_audio_info",
            "update_column_settings",
            "update_preview_info",
            "parse_url",
            "search_keyword",
            "show_interactive_video_dialog",
        )

        # 下载分组
        self.download = _make_group(
            "create_task",
            "show_duplicate_download_dialog",
            "show_skip_duplicate_download_toast",
            "add_to_downloading_list",
            "auto_manage_concurrent_downloads",
            "add_to_completed_list",
            "remove_from_downloading_list",
            "remove_from_completed_list",
            "sort_downloading_list",
            "sort_completed_list",
            "update_downloading_count",
            "update_downloading_item",
            "start_next_task",
        )

        # 登录分组
        self.login = _make_group(
            "start_server",
            "stop_server",
            "send_sms",
            "update_avatar",
        )

        # 更新分组
        self.update = _make_group(
            "check",
            "show_dialog",
        )

        # 界面分组
        self.interface = _make_group(
            "mica_effect_changed",
        )

        # === 扁平信号别名(T1 引入,保留以兼容 test_signal_bus.py) ===
        # 这些扁平 Signal 实例独立于嵌套分组,仅用于 T1 测试兼容
        self.ToastNotification = Signal()
        self.Parse = Signal()
        self.Download = Signal()
        self.Login = Signal()
        self.Update = Signal()
        self.Interface = Signal()

        # 兼容原 main_window_ready 机制(原存储于 config,改为本机属性)
        self.main_window_ready: bool = False
        # 待发送信号缓存:格式 (signal, args, kwargs)
        # signal 可为 Signal 对象或信号名字符串
        self.pending_signals: List[Tuple[Any, tuple, dict]] = []
        self._pending_lock = threading.Lock()

    def emit_signal(self, signal: Any, *args: Any, **kwargs: Any) -> None:
        """触发命名信号,若 main_window_ready=False 则缓存到 pending_signals

        双重检查:获取锁后再确认一次 ready 状态,防止竞态条件下
        丢失信号(与原实现行为一致)。

        :param signal: 信号名(str)或 Signal 对象(兼容原 Qt API)
        """
        # 兼容字符串名与 Signal 对象两种调用方式
        if isinstance(signal, str):
            sig = getattr(self, signal, None)
            if sig is None:
                raise AttributeError(f"SignalBus has no signal named '{signal}'")
        else:
            sig = signal

        if not self.main_window_ready:
            with self._pending_lock:
                if not self.main_window_ready:
                    self.pending_signals.append((sig, args, kwargs))
                    return
        sig.emit(*args, **kwargs)

    def emit_pending_signals(self) -> None:
        """标记 main_window_ready=True 并 flush 所有待发送信号"""
        self.main_window_ready = True
        with self._pending_lock:
            pending = list(self.pending_signals)
            self.pending_signals.clear()
        for sig, args, kwargs in pending:
            sig.emit(*args, **kwargs)


# 模块级单例,保持与原代码 `from util.common.signal_bus import signal_bus` 兼容
signal_bus = SignalBus()
