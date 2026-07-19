# src/cli/render/table.py
"""表格渲染器

基于 rich.table.Table 封装 render_table 函数,接受 dict 列表与表头列表,
按 headers 顺序从每行 dict 中取值并打印到 console。
"""
from typing import List, Mapping, Optional

from rich.console import Console
from rich.table import Table


def render_table(
    rows: List[Mapping[str, object]],
    headers: List[str],
    title: Optional[str] = None,
) -> None:
    """渲染 dict 列表为 rich 表格并打印

    :param rows:    行数据,每行为 dict
    :param headers: 需要展示的字段名列表,决定列顺序
    :param title:   表格标题,可选
    """
    table = Table(title=title)
    for header in headers:
        table.add_column(header)
    for row in rows:
        table.add_row(*[str(row.get(header, "")) for header in headers])
    Console().print(table)
