# src/main.py
"""bili23 CLI 入口

通过 pyproject.toml [project.scripts] 注册:
    bili23 = "src.main:app"

模块导入时即注册 signal_bus 回调,确保任何子命令执行期间
ToastNotification 等信号都能被 CLI 渲染层捕获。
"""
from cli.app import app
from cli.callbacks import register_callbacks


# 模块导入时注册回调:保证 `from src.main import app` 后信号即生效
register_callbacks()


if __name__ == "__main__":
    app()
