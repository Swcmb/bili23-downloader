# src/util/auth/sms.py
"""短信登录 - 纯 Python 实现

T2.8 改造:
- 移除 GUI 框架依赖
- Signal 改用 common.signal_bus 中的纯 Python Signal
- AsyncTask.run() 旧 API 改为新实例 API: AsyncTask(func).start()
- network.request 改为延迟导入避免传递 GUI 框架依赖
"""
from ..common.signal_bus import signal_bus, Signal
from .base import AuthBase


class SMSInfo:
    cid = ""
    tel = ""

    verification_code = ""

    countdown = 60


class SMS(AuthBase, object):
    """短信验证码登录流程封装"""

    sms_sent = Signal()
    sms_login_success = Signal()

    error = Signal(str)

    def __init__(self, parent = None):
        AuthBase.__init__(self)

        self._cleaned_up = False

        signal_bus.login.send_sms.connect(self.send)

    def cleanup(self):
        self._cleaned_up = True

        try:
            signal_bus.login.send_sms.disconnect(self.send)
        except Exception:
            pass

    def on_error(self, message: str):
        if self._cleaned_up:
            return

        super().on_error(message)

    def send(self):
        def on_success(response: dict):
            if self._cleaned_up:
                return

            self.check_response(response)

            CaptchaInfo.captcha_key = response["data"]["captcha_key"]

            self.sms_sent.emit()

        params = {
                "cid": SMSInfo.cid,
                "tel": SMSInfo.tel,
                "source": "main-fe-header",
                "token": CaptchaInfo.token,
                "challenge": CaptchaInfo.challenge,
                "validate": CaptchaInfo.validate,
                "seccode": CaptchaInfo.seccode
            }

        url = "https://passport.bilibili.com/x/passport-login/web/sms/send"

        # 延迟导入:network.request 顶部仍含 Qt 依赖,避免传递触发 GUI 框架加载
        from ..network.request import NetworkRequestWorker, RequestType
        from ..thread.async_ import AsyncTask
        from .captcha import CaptchaInfo

        worker = NetworkRequestWorker(url, request_type = RequestType.POST, params = params)
        worker.success.connect(on_success)
        worker.error.connect(self.on_error)

        AsyncTask(worker.run).start()

    def login(self):
        def on_success(response: dict):
            if self._cleaned_up:
                return

            self.check_response(response)

            self.update_cookies()

            self.sms_login_success.emit()

        params = {
                "cid": SMSInfo.cid,
                "tel": SMSInfo.tel,
                "code": SMSInfo.verification_code,
                "source": "main-fe-header",
                "captcha_key": CaptchaInfo.captcha_key,
                "go_url": "https://www.bilibili.com/"
            }

        url = "https://passport.bilibili.com/x/passport-login/web/login/sms"

        # 延迟导入同上
        from ..network.request import NetworkRequestWorker, RequestType
        from ..thread.async_ import AsyncTask
        from .captcha import CaptchaInfo

        worker = NetworkRequestWorker(url, request_type = RequestType.POST, params = params)
        worker.success.connect(on_success)
        worker.error.connect(self.on_error)

        AsyncTask(worker.run).start()

    def update_cid_tel(self, cid: str, tel: str):
        SMSInfo.cid = cid
        SMSInfo.tel = tel

    def update_verification_code(self, code: str):
        SMSInfo.verification_code = code
