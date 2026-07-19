# src/util/download/cover/cache.py
"""封面缓存 - 纯 Python 实现

缓存值为原始图片字节流,供 GUI/CLI 共用。
"""
from typing import Dict


class CoverCache:
    # 缓存值类型为 bytes(原始图片字节流)
    cache: Dict[str, bytes] = {}
