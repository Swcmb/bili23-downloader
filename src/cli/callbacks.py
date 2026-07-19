# src/cli/callbacks.py
"""signal_bus 回调注册 → Rich 输出

将 signal_bus 的扁平信号(ToastNotification/Parse/Download)桥接到
CLI 渲染层:Toast 信号转 rich toast,其余信号暂为占位(后续 T5/T6
按需扩展为进度条/表格更新)。

重复注册由 Signal.connect 自动去重,确保 register_callbacks 幂等。
"""
from util.common.signal_bus import signal_bus
from cli.render.toast import toast


def _on_toast(message, level="info"):
    """ToastNotification 信号回调:转发到 rich toast 渲染"""
    toast(message, level=level)


def _on_parse_progress(*args, **kwargs):
    """Parse 信号占位回调(后续 T5 接入解析进度更新)"""
    pass


def _on_download_progress(*args, **kwargs):
    """Download 信号占位回调(后续 T6 接入下载进度更新)"""
    pass


def register_callbacks():
    """注册所有 signal_bus 扁平信号到 CLI 渲染回调

    幂等:Signal.connect 对同一回调自动去重。
    """
    signal_bus.ToastNotification.connect(_on_toast)
    signal_bus.Parse.connect(_on_parse_progress)
    signal_bus.Download.connect(_on_download_progress)
