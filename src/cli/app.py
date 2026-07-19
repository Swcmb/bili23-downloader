# src/cli/app.py
"""Typer 应用入口与全局选项

定义 bili23 CLI 根命令及其全局选项:
- -c/--config:  指定配置文件路径
- -v/--verbose: 详细日志输出(DEBUG)
- -q/--quiet:   静默模式(仅 ERROR)
- --no-color:   禁用彩色输出
- --version:    打印版本并退出(eager,优先于其他选项)

子命令通过 `app.command()` 注册到本 Typer 实例。
"""
import typer
from rich.console import Console

from cli import __version__

app = typer.Typer(
    name="bili23",
    help="开源、免费、跨平台的 B 站视频 CLI 下载工具",
    add_completion=False,
)

# 模块级共享 Console,供渲染器与回调复用
console = Console()


def version_callback(value: bool):
    """eager 回调:--version 时打印版本并立即退出"""
    if value:
        console.print(f"bili23 {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: str = typer.Option(None, "-c", "--config", help="指定配置文件路径"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="详细日志输出(DEBUG)"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="静默模式(仅 ERROR)"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用彩色输出"),
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="显示版本号并退出",
    ),
):
    """Bili23-Downloader CLI"""
    # 未传入子命令时打印帮助并以 0 退出(不使用 no_args_is_help,因其退出码为 2)
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit(0)
    ctx.obj = {
        "config_path": config,
        "verbose": verbose,
        "quiet": quiet,
        "no_color": no_color,
    }
