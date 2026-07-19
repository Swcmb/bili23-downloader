from .query_worker import CoverQueryWorker
from .db import CoverDatabase
from .cache import CoverCache

from ...thread.pool import GlobalThreadPoolTask
from functools import lru_cache


class CoverManager:
    """封面管理器(T2.5 移除 Qt 依赖)

    原线程池改为 GlobalThreadPoolTask;placeholder() 在 CLI 版
    无图片资源系统,返回 None(调用方按需处理)。
    """
    def __init__(self):
        self.db_manager = CoverDatabase()

    @lru_cache(maxsize = None)
    def arrange_cover_id(self, cover_url: str):
        from hashlib import md5

        # 使用 cover_url 的 md5 作为 cover_id
        hash = md5(cover_url.encode("utf-8")).hexdigest()

        return hash

    def create(self, cover_id: str, cover_data: bytes):
        self.db_manager.add_cover(cover_id, cover_data)

    def query(self, cover_id: str):
        return self.db_manager.query_cover(cover_id)

    def request(self, model, query_id: str, cover_id: str, cover_url: str, cover_size = None, query_param: dict = None):
        """发起封面查询请求

        cover_size 参数保留以兼容原 API,CLI 版不再使用(无图片裁剪)。
        """
        worker = CoverQueryWorker(model, query_id, cover_id, cover_url, cover_size, query_param)

        # 原线程池 start(worker) 改为 GlobalThreadPoolTask.run(worker.run)
        GlobalThreadPoolTask.run(worker.run)

    def placeholder(self, cover_size = None):
        """占位封面,CLI 版无图片资源系统,返回 None"""
        return None

    def updateCache(self, cover_id: str, cover_data: bytes):
        if cover_id not in CoverCache.cache:
            CoverCache.cache[cover_id] = cover_data

    def getCache(self, cover_id: str):
        return CoverCache.cache.get(cover_id, None)

cover_manager = CoverManager()
