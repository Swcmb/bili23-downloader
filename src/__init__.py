"""bili23-downloader 包根模块

将本目录加入 sys.path,使 ``cli.*`` 与 ``util.*`` 顶层导入在
entry point(``bili23 = "src.main:app"``)调用时可用。

背景:项目代码统一使用 ``from cli.xxx import ...`` 与
``from util.xxx import ...`` 顶层导入风格,而非 ``src.cli.xxx``。
在测试环境由 ``conftest.py`` 注入 sys.path;在 entry point 调用
时由本模块完成同样的注入,保证 ``bili23`` 命令可直接运行。
"""
import os as _os
import sys as _sys

# 将 src/ 目录加入 sys.path,使 cli / util 顶层包可被导入
_SRC_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _SRC_DIR not in _sys.path:
    _sys.path.insert(0, _SRC_DIR)
