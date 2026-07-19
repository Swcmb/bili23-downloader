# src/cli/interact/qr_terminal.py
"""终端二维码渲染组件

将 QR 矩阵渲染为终端可显示的字符串:
- Unicode 模式:用 ▀ ▄ █ 半块字符压缩行数(两行模块合并为一行字符)
- ASCII 模式:用 ## 和双空格 表示黑白,保持终端字符比例

设计要点:
- 渲染逻辑与 QR 矩阵生成解耦,便于单元测试
- invert 用于深色终端:反转黑白使深色背景上二维码可读
- border 直接传给 qrcode 库,由其在矩阵中加入静默区
"""
from typing import List, Optional

from qrcode import QRCode
from rich.console import Console

# 支持的渲染模式
_VALID_MODES = ("unicode", "ascii")


def _build_matrix(data: str, border: int) -> List[List[bool]]:
    """生成 QR 码布尔矩阵

    :param data:   二维码内容
    :param border: 边框宽度(模块数,即静默区)
    :return: 二维布尔矩阵,True 表示深色模块
    :raises ValueError: 数据过长无法生成二维码
    """
    qr = QRCode(border=border)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.get_matrix()


def _matrix_to_ascii(matrix: List[List[bool]], invert: bool = False) -> str:
    """将 QR 矩阵渲染为 ASCII 字符串

    每个模块用 ## (深)或双空格 (浅)表示,保持 2:1 字符宽度比例。

    :param matrix: 布尔矩阵
    :param invert: 是否反转黑白
    :return: 多行字符串(末尾换行)
    """
    if not matrix:
        return "\n"

    lines = []
    for row in matrix:
        # 单行构建,减少字符串拼接次数
        chars = []
        for is_dark in row:
            # invert=True 时反转:深 <-> 浅
            effective = (not is_dark) if invert else is_dark
            chars.append("##" if effective else "  ")
        lines.append("".join(chars))
    return "\n".join(lines) + "\n"


def _matrix_to_unicode(matrix: List[List[bool]], invert: bool = False) -> str:
    """将 QR 矩阵渲染为 Unicode 字符串(半块字符优化)

    两行模块合并为一行字符,使二维码高度减半:
    - 上白下白 -> " "
    - 上黑下白 -> "▀"
    - 上白下黑 -> "▄"
    - 上黑下黑 -> "█"

    若矩阵行数为奇数,最后一行作为"上","下"视为白。

    :param matrix: 布尔矩阵
    :param invert: 是否反转黑白
    :return: 多行字符串(末尾换行)
    """
    if not matrix:
        return "\n"

    width = len(matrix[0])
    height = len(matrix)

    def is_dark(row_idx: int, col_idx: int) -> bool:
        """安全取值:越界行视为白色(invert 时反之由调用点决定)"""
        if row_idx >= height:
            return False
        val = matrix[row_idx][col_idx]
        return (not val) if invert else val

    lines = []
    # 步长 2:每次合并上下两行
    for top_idx in range(0, height, 2):
        chars = []
        bot_idx = top_idx + 1
        for col in range(width):
            top_dark = is_dark(top_idx, col)
            bot_dark = is_dark(bot_idx, col)
            # 半块字符映射:提前返回减少分支
            if top_dark and bot_dark:
                chars.append("█")
            elif top_dark:
                chars.append("▀")
            elif bot_dark:
                chars.append("▄")
            else:
                chars.append(" ")
        lines.append("".join(chars))
    return "\n".join(lines) + "\n"


def render_qr(
    data: str,
    mode: str = "unicode",
    invert: bool = False,
    border: int = 1,
) -> str:
    """渲染二维码为终端字符串

    Args:
        data: 二维码内容(URL 或文本)
        mode: "unicode"(用 █ ▀ ▄ 半块字符)或 "ascii"(用 # 空格)
        invert: 反转黑白(适应深色终端)
        border: 边框宽度(模块数)

    Returns:
        多行字符串,每行表示二维码的一行(末尾换行)

    Raises:
        ValueError: data 过长无法生成二维码,或 mode 无效
    """
    if mode not in _VALID_MODES:
        raise ValueError(
            f"无效的 mode: {mode!r},应为 {', '.join(_VALID_MODES)}"
        )

    try:
        matrix = _build_matrix(data, border)
    except ValueError:
        # qrcode 库在数据过长时抛 ValueError,透传给调用方
        raise
    except Exception as e:
        # 其他异常统一包装为 ValueError
        raise ValueError(f"无法生成二维码: {e}") from e

    if mode == "unicode":
        return _matrix_to_unicode(matrix, invert=invert)
    return _matrix_to_ascii(matrix, invert=invert)


def print_qr(
    data: str,
    mode: str = "unicode",
    invert: bool = False,
    console: Optional[Console] = None,
) -> None:
    """打印二维码到终端(用 Rich Console)

    :param data:    二维码内容
    :param mode:    渲染模式 unicode / ascii
    :param invert:  是否反转黑白(深色终端用)
    :param console: Rich Console 实例,None 则新建
    """
    if console is None:
        console = Console()
    # render_qr 输出已含末尾换行,这里 end="" 避免重复换行
    console.print(render_qr(data, mode=mode, invert=invert), end="")
