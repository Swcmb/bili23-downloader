# src/util/auth/server.py
"""本地 HTTP 服务器 - 纯 Python 实现

T2.9 改造:
- 移除事件总线引用,改用回调函数
- ServerManager 暴露 on_captcha_success 回调,由调用方(captcha.py)注册
- start()/stop() 改为直接调用,不再通过事件总线自动连接
"""
from ..common._json import json_dumps, json_loads
from .captcha import CaptchaInfo

from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Event, Thread
from urllib.parse import urlparse
from typing import Callable, Optional
import logging
import queue

logger = logging.getLogger(__name__)


def run_server(host, port, req_queue, res_queue, stop_event, on_captcha_success: Optional[Callable] = None):
    """HTTP 服务器主循环

    :param on_captcha_success: 验证码完成回调(由 ServerManager 注入)
    """

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            parsed_url = urlparse(self.path)

            if parsed_url.path == "/geetest/captcha/init":
                # 请求主进程获取最新的 CaptchaInfo
                req_queue.put({"action": "get_geetest_info"})

                # 阻塞等待主进程响应
                while not stop_event.is_set():
                    try:
                        msg = res_queue.get(timeout=0.1)
                        if msg.get("action") == "geetest_info":
                            data = {
                                "challenge": msg["challenge"],
                                "gt": msg["gt"],
                            }
                            self.make_response(200, json_dumps(data), is_json = True)
                            break
                    except queue.Empty:
                        continue
            else:
                self.make_response(404, "Not Found")

        def do_POST(self):
            parsed_url = urlparse(self.path)

            if parsed_url.path == "/geetest/captcha/callback":
                content_length = int(self.headers.get("Content-Length", 0))

                if self.headers.get("Content-Type") == "application/json;charset=UTF-8":
                    post_data = self.rfile.read(content_length).decode("utf-8")
                    json_data = json_loads(post_data)

                    # 发送回主进程保存,并触发回调
                    req_queue.put({
                        "action": "captcha_success",
                        "seccode": json_data["seccode"],
                        "validate": json_data["validate"]
                    })

                self.make_response(200, "OK")
            else:
                self.make_response(404, "Not Found")

        def make_response(self, code: int, content: str, is_json: bool = False):
            self.send_response(code)
            self.send_header("Content-Type", "application/json" if is_json else "text/html")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))

        def log_message(self, format, *args):
            pass

    server = HTTPServer((host, port), CallbackHandler)
    server.timeout = 0.5  # 使得 handle_request 不会无限阻塞

    while not stop_event.is_set():
        server.handle_request()

    server.server_close()


class QueueListenerThread(Thread):
    """队列监听线程:处理来自 HTTP 服务器的请求并触发回调"""

    def __init__(self, req_queue, res_queue, on_captcha_success: Optional[Callable] = None):
        super().__init__(daemon = True)
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.on_captcha_success = on_captcha_success
        self.running = True

    def run(self):
        while self.running:
            try:
                msg = self.req_queue.get(timeout=0.1)
                action = msg.get("action")

                if action == "get_geetest_info":
                    self.res_queue.put({
                        "action": "geetest_info",
                        "challenge": CaptchaInfo.challenge,
                        "gt": CaptchaInfo.gt
                    })
                elif action == "captcha_success":
                    CaptchaInfo.seccode = msg["seccode"]
                    CaptchaInfo.validate = msg["validate"]
                    # 验证码完成,触发外部注册的回调(替代原事件总线 emit)
                    if self.on_captcha_success is not None:
                        try:
                            self.on_captcha_success()
                        except Exception as e:
                            logger.exception("on_captcha_success 回调异常: %s", e)
            except queue.Empty:
                pass

    def stop(self):
        self.running = False
        self.join(timeout = 1.0)


class ServerThread(Thread):
    def __init__(self, host, port, req_queue, res_queue, stop_event, on_captcha_success: Optional[Callable] = None):
        super().__init__(daemon = True)
        self.host = host
        self.port = port
        self.req_queue = req_queue
        self.res_queue = res_queue
        self.stop_event = stop_event
        self.on_captcha_success = on_captcha_success

    def run(self):
        run_server(self.host, self.port, self.req_queue, self.res_queue, self.stop_event, self.on_captcha_success)


class ServerManager:
    """本地验证码服务器管理器

    改用回调机制替代事件总线:
    - on_captcha_success: 验证码完成回调,由调用方注册
    - start()/stop() 由调用方直接调用,不再通过事件自动连接
    """

    def __init__(self, host="127.0.0.1", port=2333):
        self.host = host
        self.port = port

        self.server_thread = None
        self.req_queue = None
        self.res_queue = None
        self.stop_event = None
        self.listener_thread = None
        self.running = False

        # 验证码完成回调(替代原事件总线 emit)
        self.on_captcha_success: Optional[Callable] = None

    def start(self):
        if not self.running:
            self.req_queue = queue.Queue()
            self.res_queue = queue.Queue()
            self.stop_event = Event()

            # 启动监听线程(注入 on_captcha_success 回调)
            self.listener_thread = QueueListenerThread(self.req_queue, self.res_queue, self.on_captcha_success)
            self.listener_thread.start()

            # 启动后台服务线程
            self.server_thread = ServerThread(
                self.host,
                self.port,
                self.req_queue,
                self.res_queue,
                self.stop_event,
                self.on_captcha_success,
            )
            self.server_thread.start()

            self.running = True
            logger.info("验证码服务器已启动: %s:%s", self.host, self.port)

    def stop(self):
        if self.running:
            self.stop_event.set()
            self.running = False

            server_thread = self.server_thread
            listener_thread = self.listener_thread

            self.server_thread = None
            self.req_queue = None
            self.res_queue = None
            self.stop_event = None
            self.listener_thread = None

            def cleanup():
                if listener_thread:
                    listener_thread.stop()

                if server_thread:
                    server_thread.join(timeout = 1.0)

            Thread(target = cleanup, daemon = True).start()


server_manager = ServerManager()
