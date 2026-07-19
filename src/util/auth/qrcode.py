# src/util/auth/qrcode.py
"""二维码登录 - 纯 Python 实现

T2.7 改造:
- 移除 GUI 框架依赖
- QR 码渲染改用 qrcode 库 + PIL 生成 PNG 字节流
- 轮询改用 threading.Timer 替代原事件循环定时器
- 信号(Signal)改用 common.signal_bus 中的纯 Python Signal
"""
from ..common.signal_bus import Signal
from ..common.enum import QRCodeScanStatus
from .base import AuthBase

from qrcode import QRCode as QRCodeGenerator
from urllib.parse import urlencode
from threading import Timer
import io

# PIL 用于将 QR 矩阵渲染为 PNG 字节流
from PIL import Image, ImageDraw


class QRCode(AuthBase, object):
    """二维码登录流程封装

    信号:
    - qrcode_generated(bytes): 二维码生成完成,emit PNG 字节流
    - update_scan_status(int): 扫码状态变更
    - error(str): 出错信息
    """

    qrcode_generated = Signal(bytes)
    update_scan_status = Signal(int)

    error = Signal(str)

    def __init__(self, parent = None):
        AuthBase.__init__(self)

        self._cleaned_up = False

        self.qrcode_url = ""
        self.qrcode_key = ""

        # 轮询定时器:threading.Timer 递归调用,daemon=True 避免阻塞主进程退出
        self._timer: Timer = None

    def cleanup(self):
        self._cleaned_up = True

        self.stop_polling()

    def on_error(self, message: str):
        if self._cleaned_up:
            return

        super().on_error(message)

    def _build_qrcode_pixmap(self, data: str) -> bytes:
        """生成二维码 PNG 字节流

        方法名保留 pixmap 后缀以兼容外部调用,实际返回 PNG 字节流。

        :param data: 二维码内容(URL)
        :return: PNG 字节流(bytes)
        """
        # 生成 QR 码矩阵
        qr_code = QRCodeGenerator(border = 4)
        qr_code.add_data(data)
        qr_code.make(fit = True)

        matrix = qr_code.get_matrix()
        module_count = len(matrix)
        box_size = max(1, 160 // module_count)
        image_size = module_count * box_size

        # 用 PIL 绘制黑白二维码
        image = Image.new("RGB", (image_size, image_size), "white")
        draw = ImageDraw.Draw(image)

        for row_index, row in enumerate(matrix):
            y = row_index * box_size
            for column_index, is_dark in enumerate(row):
                if is_dark:
                    draw.rectangle(
                        (column_index * box_size, y, (column_index + 1) * box_size - 1, y + box_size - 1),
                        fill = "black",
                    )

        # 输出为 PNG 字节流
        buffer = io.BytesIO()
        image.save(buffer, format = "PNG")
        return buffer.getvalue()

    def generate(self):
        def on_success(response: dict):
            if self._cleaned_up:
                return

            self.check_response(response)

            self.qrcode_url = response["data"]["url"]
            self.qrcode_key = response["data"]["qrcode_key"]

            self.qrcode_generated.emit(self._build_qrcode_pixmap(self.qrcode_url))

        params = {
            "source": "main-fe-header",
            "go_url": "https://www.bilibili.com/",
            "web_location": "333.1007"
        }

        url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/generate?{urlencode(params)}"

        # 延迟导入:network.request 顶部仍含 Qt 依赖,避免传递触发 GUI 框架加载
        from ..network.request import NetworkRequestWorker
        from ..thread.async_ import AsyncTask

        worker = NetworkRequestWorker(url)
        worker.success.connect(on_success)
        worker.error.connect(self.on_error)

        AsyncTask(worker.run).start()

    def check_scan_status(self):
        def on_success(response: dict):
            if self._cleaned_up:
                return

            self.check_response(response)

            code = response["data"]["code"]

            if code == QRCodeScanStatus.SUCCESS:
                self.update_cookies()

            if self._timer is not None:
                self.update_scan_status.emit(code)

        url = f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={self.qrcode_key}"

        # 延迟导入同上
        from ..network.request import NetworkRequestWorker
        from ..thread.async_ import AsyncTask

        worker = NetworkRequestWorker(url)
        worker.success.connect(on_success)
        worker.error.connect(self.on_error)

        AsyncTask(worker.run).start()

    def start_polling(self):
        """启动轮询:用 threading.Timer 递归调用替代原事件循环定时器"""
        if self._cleaned_up:
            return

        self._timer = Timer(1.0, self._poll_once)
        self._timer.daemon = True
        self._timer.start()

    def _poll_once(self):
        """单次轮询回调,执行后自动重新调度"""
        if self._cleaned_up:
            return

        self.check_scan_status()

        # 递归调度下一次轮询(1 秒后)
        self._timer = Timer(1.0, self._poll_once)
        self._timer.daemon = True
        self._timer.start()

    def stop_polling(self):
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
