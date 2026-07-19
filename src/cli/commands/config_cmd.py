# src/cli/commands/config_cmd.py
"""bili23 config - 配置管理子命令组

提供 get/set/list/path 四个子命令,管理用户配置文件。
所有命令通过 util.common.config.config 单例操作,持久化到
<config_dir>/config.json(AC-027)。

设计要点:
- 模块级 `app.add_typer(config_app, name="config")` 注册子命令组
- set 命令根据 _DEFAULT_VALUES 中 key 的默认类型自动转换字符串值
- 异常分层处理:
  * cli.exceptions.ConfigError(未知 key/类型不符):按 exit_code=9 退出
  * util.common.config.ConfigError(范围校验失败):exit 9
  * OSError(文件写入失败):exit 70(对应 Bili23Error.exit_code)
"""
import os

import typer
from rich.console import Console

from cli.app import app
from cli.exceptions import Bili23Error, ConfigError
from cli.render.table import render_table
from cli.render.toast import toast
from util.common.config import (
    _DEFAULT_VALUES,
    ConfigError as _ConfigValueError,
    config,
)
from util.common.io.directory import directory

# 子命令组:config_app 注册为 `bili23 config` 的子命令入口
config_app = typer.Typer(help="配置管理")
app.add_typer(config_app, name="config")

# 模块级共享 Console,用于错误输出着色
console = Console()

# 布尔字符串映射(大小写不敏感)
_BOOL_TRUE = ("true", "1", "yes")
_BOOL_FALSE = ("false", "0", "no")


def _check_known_key(key: str) -> None:
    """校验 key 是否为已知配置项,未知抛 cli.exceptions.ConfigError"""
    if key not in _DEFAULT_VALUES:
        raise ConfigError(f"未知配置项: {key}")


def _coerce_value(key: str, raw: str):
    """根据 _DEFAULT_VALUES 中 key 的默认类型,将字符串值转换为对应类型

    - bool 类型:接受 true/false/1/0/yes/no(大小写不敏感)
    - int 类型:解析为整数,失败抛 ConfigError
    - 其他类型:原样返回字符串
    """
    default = _DEFAULT_VALUES.get(key)
    if isinstance(default, bool):
        low = raw.lower()
        if low in _BOOL_TRUE:
            return True
        if low in _BOOL_FALSE:
            return False
        raise ConfigError(f"{key} 期望布尔值(true/false),得到 {raw!r}")
    if isinstance(default, int):
        try:
            return int(raw)
        except ValueError:
            raise ConfigError(f"{key} 期望整数,得到 {raw!r}")
    return raw


def _exit_with_error(message: str, exit_code: int) -> None:
    """以红色样式打印错误消息,并按 exit_code 退出"""
    console.print(f"[red]错误: {message}[/]")
    raise typer.Exit(exit_code)


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="配置项名")):
    """获取配置项值"""
    try:
        _check_known_key(key)
        # 裸值输出,便于脚本化(如 shell 管道)
        typer.echo(config.get(key))
    except Bili23Error as e:
        # cli.exceptions.ConfigError 等继承自 Bili23Error:按 exit_code 退出
        _exit_with_error(str(e), e.exit_code)


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置项名"),
    value: str = typer.Argument(..., help="配置项值(自动转换类型)"),
):
    """设置配置项值并保存"""
    try:
        _check_known_key(key)
        coerced = _coerce_value(key, value)
        # set 内部已加锁并持久化到 JSON 文件(原子 rename)
        config.set(key, coerced)
        message = f"已设置 {key} = {coerced}"
        typer.echo(message)
        toast(message, level="success")
    except Bili23Error as e:
        # cli.exceptions.ConfigError(未知 key/类型不符):按 exit_code 退出
        _exit_with_error(str(e), e.exit_code)
    except _ConfigValueError as e:
        # util.common.config.ConfigError(范围校验失败):exit 9
        _exit_with_error(str(e), 9)
    except OSError as e:
        # 配置文件写入失败:exit 70(对应 Bili23Error.exit_code)
        _exit_with_error(f"配置文件写入失败: {e}", 70)


@config_app.command("list")
def config_list():
    """列出所有配置项"""
    # 按 _DEFAULT_VALUES 顺序遍历,确保输出稳定
    rows = [{"key": k, "value": config.get(k)} for k in _DEFAULT_VALUES]
    render_table(rows, headers=["key", "value"])


@config_app.command("path")
def config_path():
    """打印配置文件路径"""
    # 裸路径输出,便于脚本化(如 cd "$(bili23 config path)")
    typer.echo(os.path.join(directory.config_dir, "config.json"))
