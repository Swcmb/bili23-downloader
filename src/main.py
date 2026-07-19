# src/main.py
"""bili23 CLI 入口

通过 pyproject.toml [project.scripts] 注册:
    bili23 = "src.main:app"

模块导入时即注册 signal_bus 回调,确保任何子命令执行期间
ToastNotification 等信号都能被 CLI 渲染层捕获。

显式导入各 commands 模块以触发 ``app.command()`` / ``app.add_typer()``
副作用注册,使 `bili23 --help` 能列出全部 7 类命令。
"""
# 显式 import 触发命令注册(顺序按命令组类型分组)
from cli.commands import (  # noqa: F401 - 副作用导入,触发注册
    config_cmd,
    download,
    history,
    login,
    logout,
    parse,
    task,
)
from cli.app import app
from cli.callbacks import register_callbacks


# 模块导入时注册回调:保证 `from src.main import app` 后信号即生效
register_callbacks()


if __name__ == "__main__":
    app()
