from ...thread.worker_base import WorkerBase

from urllib.parse import urlencode
import base64
import httpx
import logging

logger = logging.getLogger(__name__)


class CoverQueryWorker(WorkerBase):
    """封面查询 Worker(继承 WorkerBase,纯 Python 实现)

    直接保留下载的原始字节流,不做裁剪/格式转换。
    """
    def __init__(self, model, query_id: str, cover_id: str, cover_url: str, cover_size = None, query_param: dict = None):
        super().__init__()

        self.model = model
        self.query_id = query_id
        self.cover_id = cover_id

        self.cover_url = cover_url
        # cover_size 保留以兼容原 API,CLI 版不再使用(无图片裁剪)
        self.cover_size = cover_size

        self.query_param = query_param

    def run(self):
        from ..cover.manager import cover_manager

        if self.query_param:
            try:
                self.query_url()

            except Exception:
                # 查询封面 URL 失败，无法继续后续流程
                return

        result = cover_manager.query(self.cover_id)

        if result:
            # 数据库中存的是 base64 字符串,解码为原始字节流
            cover_data = base64.b64decode(result)

        else:
            for i in range(3):
                try:
                    cover_data, base64_data = self.download_cover()
                    break
                except httpx.HTTPError:
                    if i == 2:
                        raise
            else:
                return

            cover_manager.create(self.cover_id, base64_data)

        self.return_to_model(cover_data)

    def return_to_model(self, cover_data: bytes):
        """将封面字节流回传给 model(直接同步调用,无跨线程机制)

        直接调用 model.updateRowCover(query_id, cover_data)。
        """
        self.model.updateRowCover(self.query_id, cover_data)

    def download_cover(self):
        """下载封面图片,返回 (原始字节流, base64 字符串)"""
        # 延迟导入:network.request 顶部含 GUI 框架依赖,需避免传递依赖
        from ...network.request import SyncNetWorkRequest, ResponseType

        # 数据库中没有封面数据，下载封面图片
        request = SyncNetWorkRequest(self.cover_url, response_type = ResponseType.BYTES)
        response = request.run()

        # 直接保留原始字节流,不再做图片裁剪/缩放
        base64_data = base64.b64encode(response).decode("utf-8")

        return response, base64_data

    def query_url(self):
        from ..cover.manager import cover_manager

        api_url = self.query_param.get("api_url")
        params = self.query_param.get("params")

        url = f"{api_url}?{urlencode(params)}"

        # 延迟导入:network.request 顶部含 GUI 框架依赖
        from ...network.request import SyncNetWorkRequest
        request = SyncNetWorkRequest(url)
        response = request.run()

        cover_url = response.get("data", {}).get("cover", "")

        if not cover_url:
            raise ValueError("获取封面 URL 失败")

        self.cover_id = cover_manager.arrange_cover_id(cover_url)
        self.cover_url = cover_url
