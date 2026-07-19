# src/util/auth/captcha.py
"""验证码流程 - 纯 Python 实现

T2.9 改造:
- 移除 GUI 框架依赖
- AsyncTask.run() 旧 API 改为新实例 API: AsyncTask(func).start()
- network.request / misc.web / server 改为延迟导入避免传递 GUI 框架依赖与循环导入
- 改用 server_manager 直接调用 + on_captcha_success 回调(替代事件总线)
"""
from .base import AuthBase

from ..common.signal_bus import signal_bus
from ..thread.async_ import AsyncTask


class CaptchaInfo:
    token = ""
    challenge = ""
    gt = ""

    seccode = ""
    validate = ""

    captcha_key = ""


class Captcha(AuthBase, object):
    """极验验证码流程封装

    通过本地 HTTP 服务器接收前端验证码回调,完成后通过
    signal_bus.login.send_sms 触发 SMS 发送流程。
    """

    def __init__(self):
        super().__init__()

        self.server_running = False
        self._cleaned_up = False

    def cleanup(self):
        self._cleaned_up = True

        if not self.server_running:
            return

        # 延迟导入:server 模块在加载时会回导入 captcha.CaptchaInfo
        from .server import server_manager

        server_manager.stop()
        self.server_running = False

    def init_geetest(self):
        def on_success(response: dict):
            if self._cleaned_up:
                return

            self.check_response(response)

            CaptchaInfo.token = response["data"]["token"]
            CaptchaInfo.challenge = response["data"]["geetest"]["challenge"]
            CaptchaInfo.gt = response["data"]["geetest"]["gt"]

            if not self.server_running:
                # 延迟启动服务器,确保在获取到验证码信息后才启动,避免不必要的资源占用
                from .server import server_manager

                # 注册验证码完成回调:验证码完成后触发短信发送流程
                server_manager.on_captcha_success = lambda: signal_bus.login.send_sms.emit()
                server_manager.start()

                self.server_running = True

            # 延迟导入:misc.web 顶部含 Qt 依赖,避免传递触发 GUI 框架加载
            from ..misc.web import WebPage

            WebPage.open("captcha.html")

        url = "https://passport.bilibili.com/x/passport-login/captcha?source=main-fe-header&t=0.1867987009754133"

        # 延迟导入:network.request 顶部含 Qt 依赖,避免传递触发 GUI 框架加载
        from ..network.request import NetworkRequestWorker

        worker = NetworkRequestWorker(url)
        worker.success.connect(on_success)
        worker.error.connect(self.on_error)

        AsyncTask(worker.run).start()
