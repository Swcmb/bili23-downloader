# src/util/auth/cookie_login.py
"""Cookie 登录 - 纯 Python 实现

T2.9 改造:
- 移除 GUI 框架依赖
- Signal 改用 common.signal_bus 中的纯 Python Signal
- AsyncTask.run() 旧 API 改为新实例 API: AsyncTask(func).start()
- network.request 改为延迟导入避免传递 GUI 框架依赖
"""
from ..common.signal_bus import Signal
from ..common.translator import Translator

from .base import AuthBase

import json

# 登录相关的 Cookie 字段
LOGIN_COOKIE_KEYS = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5")


class CookieLogin(AuthBase, object):
    """Cookie 导入登录流程

    用户粘贴 Cookie 字符串(JSON 或 `k=v; k=v` 格式),本类解析后
    应用到 httpx 客户端,并通过 nav 接口校验有效性。
    """

    login_success = Signal()

    error = Signal(str)

    def __init__(self, parent = None):
        AuthBase.__init__(self)

        self._cleaned_up = False
        self._pending_restore = False  # 已应用待验证的 Cookie,尚未确认有效

    def cleanup(self):
        self._cleaned_up = True

        # 验证未完成时回滚
        if self._pending_restore:
            self.restore_cookies()

    def on_error(self, message: str):
        if self._cleaned_up:
            return

        super().on_error(message)

    @staticmethod
    def parse_cookies(text: str) -> dict:
        """解析用户粘贴的 Cookie 请求头字符串(如 SESSDATA=xxx; bili_jct=xxx)或 json 格式对象

        支持分号或换行分隔。无法解析出有效字段时返回空字典。
        """
        text = text.strip()

        if text.lower().startswith("cookie:"):
            text = text[len("cookie:"):]

        cookies = {}

        try:
            # 尝试解析为 JSON 对象
            data = json.loads(text)

            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(key, str) and isinstance(value, str):
                        cookies[key] = value

                return cookies
        except Exception:
            pass

        for part in text.replace("\n", ";").split(";"):
            key, sep, value = part.partition("=")
            key, value = key.strip(), value.strip().strip('"')

            # 合法的 Cookie 名不含空白字符,借此过滤随意粘贴的无效文本
            if sep and key and not any(char.isspace() for char in key):
                cookies[key] = value

        return cookies

    def login(self, text: str):
        cookies = self.parse_cookies(text)

        if not cookies:
            self.on_error(Translator.ERROR_MESSAGES("COOKIE_FORMAT_INVALID"))
            return

        if not cookies.get("SESSDATA"):
            self.on_error(Translator.ERROR_MESSAGES("COOKIE_MISSING_SESSDATA"))
            return

        self.apply_login_cookies(cookies)

        self._pending_restore = True

        def on_success(response: dict):
            if self._cleaned_up:
                return

            data: dict = response.get("data", {})

            if data.get("isLogin"):
                self._pending_restore = False

                self.update_cookies()

                self.login_success.emit()

            else:
                self.restore_cookies()

                self.on_error(Translator.ERROR_MESSAGES("COOKIE_INVALID"))

        def on_verify_error(error_message: str):
            if self._cleaned_up:
                return

            self.restore_cookies()

            self.on_error(error_message)

        # 通过 nav 接口校验 Cookie 是否有效
        url = "https://api.bilibili.com/x/web-interface/nav"

        # 延迟导入:network.request 顶部仍含 Qt 依赖,避免传递触发 GUI 框架加载
        from ..network.request import NetworkRequestWorker
        from ..thread.async_ import AsyncTask

        worker = NetworkRequestWorker(url)
        worker.success.connect(on_success)
        worker.error.connect(on_verify_error)

        AsyncTask(worker.run).start()

    def apply_login_cookies(self, cookies: dict):
        # 延迟导入同上
        from ..network.request import client

        for key in LOGIN_COOKIE_KEYS:
            value = cookies.get(key, "")

            if value:
                client.cookies.set(
                    name = key,
                    value = value,
                    domain = ".bilibili.com",
                    path = "/"
                )

    def restore_cookies(self):
        # 移除已应用的登录 Cookie,并恢复为配置中保存的 Cookie
        # 延迟导入同上
        from ..network.request import client, update_cookies as sync_cookies_from_config

        self._pending_restore = False

        for key in LOGIN_COOKIE_KEYS:
            try:
                client.cookies.delete(key, domain = ".bilibili.com", path = "/")
            except KeyError:
                pass

        sync_cookies_from_config()
