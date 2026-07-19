# src/cli/render/toast.py
"""Toast 通知渲染器

将 signal_bus.ToastNotification 信号转译为 rich 彩色控制台输出。
level 支持 info/success/warning/error 四档,分别映射到不同样式。
"""
from rich.console import Console

# level -> (rich 样式前缀, 默认前缀符号)
_LEVEL_STYLES = {
    "info": ("[cyan]", "ℹ"),
    "success": ("[green]", "✓"),
    "warning": ("[yellow]", "⚠"),
    "error": ("[red]", "✗"),
}


def toast(message: str, level: str = "info") -> None:
    """以指定级别打印 toast 消息到控制台

    :param message: 消息文本
    :param level:   info/success/warning/error 之一,未知按 info 处理
    """
    style, prefix = _LEVEL_STYLES.get(level, _LEVEL_STYLES["info"])
    Console().print(f"{style}{prefix} {message}[/]")
