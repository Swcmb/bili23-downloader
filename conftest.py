# conftest.py
"""pytest 根级配置 - 将 src/ 加入 sys.path,使 `util.*` 与 `cli.*` 可被测试导入"""
import os
import sys

_SRC_DIR = os.path.join(os.path.dirname(__file__), "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)
