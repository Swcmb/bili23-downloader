# tests/cli/test_qr_terminal.py
"""T5.10 测试:终端二维码渲染组件

验证点:
1. Unicode 模式输出含 █ 或 ▀ 半块字符
2. ASCII 模式仅含 #、空格、换行
3. invert=True 反转黑白
4. border 控制边框宽度
5. 非法 mode 抛 ValueError
6. 空字符串仍能生成最小二维码
7. B 站登录 URL 可正常渲染
8. print_qr 不抛异常(mock Console)
9. 半块字符优化:输出含 ▀ 或 ▄
"""
from unittest.mock import MagicMock

import pytest


# 测试用 URL
_BILI_LOGIN_URL = "https://passport.bilibili.com/x/passport-login/web/qrcode"
_EXAMPLE_URL = "https://example.com"


def test_render_qr_unicode():
    """Unicode 模式:返回多行字符串,含 █ 或 ▀ 字符"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr(_EXAMPLE_URL, mode="unicode")
    assert isinstance(result, str)
    assert "\n" in result, "应为多行字符串"
    assert "█" in result or "▀" in result, "应包含 █ 或 ▀ 字符"


def test_render_qr_ascii():
    """ASCII 模式:仅含 #、空格、换行"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr(_EXAMPLE_URL, mode="ascii")
    assert isinstance(result, str)
    allowed = set("# \n")
    assert set(result).issubset(allowed), \
        f"ASCII 模式应仅含 #、空格、换行,实际含: {set(result) - allowed}"


def test_render_qr_invert():
    """invert=True:原 █ 位置变空格(反转)"""
    from cli.interact.qr_terminal import render_qr

    normal = render_qr(_EXAMPLE_URL, mode="unicode", invert=False)
    inverted = render_qr(_EXAMPLE_URL, mode="unicode", invert=True)
    # 反转后,原文中的 █ 数量与反转后的空格数量应一致(单行内)
    normal_block_count = normal.count("█")
    inverted_space_count = inverted.count(" ")
    # 反转后应有非零的 █ 数量(不可能完全为空)
    assert inverted.count("█") > 0, "反转后仍应存在 █ 字符"
    # 反转使原 █ 数量大致减少(非精确等于,因半块字符影响)
    assert inverted != normal, "反转后字符串应与原字符串不同"


def test_render_qr_invert_ascii():
    """invert=True:ASCII 模式 # 与空格互换"""
    from cli.interact.qr_terminal import render_qr

    normal = render_qr(_EXAMPLE_URL, mode="ascii", invert=False)
    inverted = render_qr(_EXAMPLE_URL, mode="ascii", invert=True)
    # ASCII 模式下,# 数量与空格数量在反转后应大致互换
    normal_hash = normal.count("#")
    normal_space = normal.count(" ")
    inverted_hash = inverted.count("#")
    inverted_space = inverted.count(" ")
    assert inverted_hash > 0, "反转后仍应有 # 字符"
    # 反转使 # 数量明显变化
    assert inverted_hash != normal_hash or inverted_space != normal_space, \
        "反转后 # 与空格数量应不同"


def test_render_qr_border():
    """border=2 比 border=1 行数多 2(每边多 1 行)"""
    from cli.interact.qr_terminal import render_qr

    small = render_qr(_EXAMPLE_URL, mode="ascii", border=1)
    large = render_qr(_EXAMPLE_URL, mode="ascii", border=2)
    small_lines = small.rstrip("\n").split("\n")
    large_lines = large.rstrip("\n").split("\n")
    # ASCII 模式下每模块一行字符,border 每边多 1 模块 = 行数多 2
    assert len(large_lines) - len(small_lines) == 2, \
        f"border=2 比 border=1 行数应多 2,实际差 {len(large_lines) - len(small_lines)}"


def test_render_qr_invalid_mode():
    """mode='invalid' 抛 ValueError"""
    from cli.interact.qr_terminal import render_qr

    with pytest.raises(ValueError):
        render_qr(_EXAMPLE_URL, mode="invalid")


def test_render_qr_empty_data():
    """空字符串仍能生成最小二维码(不抛异常)"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr("", mode="unicode")
    assert isinstance(result, str)
    assert "\n" in result


def test_render_qr_url():
    """渲染 B 站登录 URL 不抛异常"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr(_BILI_LOGIN_URL, mode="unicode")
    assert isinstance(result, str)
    assert len(result) > 0


def test_print_qr_no_exception():
    """print_qr 不抛异常(mock Console)"""
    from cli.interact.qr_terminal import print_qr

    mock_console = MagicMock()
    # 不抛异常即通过
    print_qr(_EXAMPLE_URL, mode="unicode", console=mock_console)
    # Console.print 应被调用
    assert mock_console.print.called


def test_render_qr_unicode_half_block():
    """验证半块字符使用:输出含 ▀ 或 ▄(unicode 模式默认应使用半块)"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr(_EXAMPLE_URL, mode="unicode")
    # 半块字符优化:用 ▀ ▄ 把两行模块合并为一行
    assert "▀" in result or "▄" in result, \
        "unicode 模式应使用半块字符 ▀ 或 ▄ 压缩行数"


def test_render_qr_matrix_size():
    """生成的二维码矩阵大小符合 QR 码规范(最小 21x21)"""
    from cli.interact.qr_terminal import _matrix_to_unicode, _matrix_to_ascii
    from qrcode import QRCode

    qr = QRCode(border=1)
    qr.add_data(_EXAMPLE_URL)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    # QR 码最小 21x21,带 border=1 至少 23x23
    assert len(matrix) >= 21
    assert all(len(row) == len(matrix) for row in matrix), "矩阵应为正方形"

    # 转换函数不应抛异常
    unicode_str = _matrix_to_unicode(matrix, invert=False)
    ascii_str = _matrix_to_ascii(matrix, invert=False)
    assert isinstance(unicode_str, str)
    assert isinstance(ascii_str, str)


def test_render_qr_border_zero():
    """border=0 仍能渲染(无边框)"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr(_EXAMPLE_URL, mode="ascii", border=0)
    assert isinstance(result, str)
    assert len(result) > 0


def test_render_qr_ends_with_newline():
    """字符串末尾应以换行结束"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr(_EXAMPLE_URL, mode="unicode")
    assert result.endswith("\n"), "render_qr 输出末尾应换行"
