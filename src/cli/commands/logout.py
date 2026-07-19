# src/cli/commands/logout.py
"""bili23 logout 子命令 - 清除 Cookie 文件并登出当前账号

登出流程:
1. 检查 Cookie 文件是否存在,不存在则幂等返回(提示未登录)
2. 默认通过 Rich Confirm 询问用户;--yes 跳过确认
3. 删除 Cookie 文件并清除 request 模块内存中的 Cookie 状态

异常映射:
- 用户取消 → UserCancelledError(exit_code=3)
- 删除失败 → Bili23Error(exit_code=70)
"""
import os

import typer
from rich.console import Console
from rich.prompt import Confirm

from cli.app import app
from cli.exceptions import Bili23Error, UserCancelledError
from cli.render.toast import toast
from util.common.io.directory import directory

# 模块级 Console,用于打印取消提示等非 toast 文本
console = Console()


def _clear_request_cookies() -> None:
    """清除 request 模块内存中的 Cookie 状态(若客户端已创建)

    httpx 客户端为懒加载,未发起网络请求时 _client 为 None,此时无需清理。
    直接读取模块级 _client 避免触发不必要的客户端创建。
    """
    from util.network import request as request_module

    client = request_module._client
    if client is None:
        return
    try:
        client.cookies.clear()
    except Exception:
        # 清理失败不阻塞登出主流程(Cookie 文件已删除即视为登出成功)
        pass


def _delete_cookie_file(path: str) -> None:
    """删除 Cookie 文件;权限不足抛 Bili23Error

    :param path: Cookie 文件路径
    :raises Bili23Error: 删除失败(权限不足)
    """
    try:
        os.remove(path)
    except FileNotFoundError:
        # 文件不存在视为已登出(幂等保护,理论上调用方已检查存在性)
        return
    except PermissionError as exc:
        raise Bili23Error(f"删除 Cookie 文件失败(权限不足): {exc}") from exc


def _perform_logout(force: bool) -> None:
    """执行登出核心逻辑,可能抛出 UserCancelledError 或 Bili23Error

    :param force: True 跳过确认提示
    """
    cookie_path = directory.cookie_path

    # 无 Cookie 文件:幂等,提示未登录
    if not os.path.exists(cookie_path):
        toast("当前未登录", level="warning")
        return

    # 默认走 Rich Confirm 确认;--yes 跳过
    if not force:
        if not Confirm.ask("确认登出当前账号?", default=False):
            console.print("已取消")
            raise UserCancelledError("用户取消登出")

    # 删除 Cookie 文件并清除内存 Cookie 状态
    _delete_cookie_file(cookie_path)
    _clear_request_cookies()

    toast("已登出", level="success")


@app.command("logout")
def logout_cmd(
    force: bool = typer.Option(False, "-y", "--yes", help="跳过确认提示"),
):
    """清除 Cookie 文件,登出当前账号"""
    try:
        _perform_logout(force)
    except Bili23Error as exc:
        # UserCancelledError 与其他 Bili23 错误统一按 exit_code 退出
        raise typer.Exit(exc.exit_code) from exc
