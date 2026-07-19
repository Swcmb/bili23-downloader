# src/cli/commands/login.py
"""bili23 login qr/sms/cookie/status 命令组

提供三种登录方式与登录状态查询:
- qr:     扫码登录(终端渲染二维码)
- sms:    短信验证码登录
- cookie: Cookie 字符串导入
- status: 查询当前登录状态

设计要点:
- 每个子命令拆为独立的 _do_xxx 函数,便于单元测试与维护
- 同步封装类(QRCodeLogin/SMSLogin/CookieLogin)在模块内定义,
  便于测试通过 monkeypatch 整体替换
- Cookie 文件以 JSON 持久化,POSIX 上权限 600
- 所有网络请求通过 util.network.request.client 完成

异常映射(对应规格 7.1 节):
- 登录失败/Cookie 失效 → AuthRequiredError(exit_code=5)
- 用户取消(Ctrl+C)   → UserCancelledError(exit_code=3)
- 手机号/验证码格式错误 → ConfigError(exit_code=9)
- 网络请求失败         → NetworkError(exit_code=6)
- Cookie 文件写入失败  → Bili23Error(exit_code=70)
"""
import json
import logging
import os
import re
import time
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import typer
from rich.console import Console
from rich.prompt import Prompt

from cli.app import app
from cli.exceptions import (
    AuthRequiredError,
    Bili23Error,
    ConfigError,
    NetworkError,
    UserCancelledError,
)
from cli.interact.qr_terminal import print_qr
from cli.render.toast import toast
from util.common.io.directory import directory

logger = logging.getLogger(__name__)
console = Console()

# 子命令组:login_app 注册为 `bili23 login` 的子命令入口
login_app = typer.Typer(help="登录管理")
app.add_typer(login_app, name="login")

# B 站登录相关接口
_NAV_API = "https://api.bilibili.com/x/web-interface/nav"
_QR_GENERATE_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
_QR_POLL_API = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
_SMS_SEND_API = "https://passport.bilibili.com/x/passport-login/web/sms/send"
_SMS_LOGIN_API = "https://passport.bilibili.com/x/passport-login/web/login/sms"

# 登录 Cookie 字段(与 util.auth.cookie_login.LOGIN_COOKIE_KEYS 对齐)
_LOGIN_COOKIE_KEYS = ("SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5")

# 中国大陆手机号格式:1 开头,第二位 3-9,共 11 位
_PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")

# 扫码轮询间隔(秒)
_POLL_INTERVAL = 1.0


# ---------- Cookie 文件读写 ----------

def _save_cookies(cookies: dict) -> None:
    """保存 Cookie 到 cookie_path,文件权限 600(POSIX)

    :param cookies: 待保存的 Cookie 字典
    :raises Bili23Error: 写入失败
    """
    path = directory.cookie_path
    tmp_path = f"{path}.tmp"
    try:
        # 临时文件 + rename 实现原子写入,避免崩溃产生半截文件
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
        # POSIX 上设置权限 600,仅所有者可读写,防止 Cookie 泄漏
        if os.name == "posix":
            os.chmod(path, 0o600)
    except OSError as exc:
        # 清理可能残留的临时文件
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise Bili23Error(f"保存 Cookie 文件失败: {exc}") from exc


def _load_cookies() -> Optional[dict]:
    """从 cookie_path 加载 Cookie

    :return: Cookie 字典;文件不存在或损坏时返回 None
    """
    path = directory.cookie_path
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        logger.warning("Cookie 文件根节点非 dict,已忽略")
        return None
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Cookie 文件读取失败: %s", exc)
        return None


def _apply_cookies_to_client(cookies: dict) -> None:
    """将 Cookie 应用到 request 模块的 httpx client(供后续请求使用)

    仅应用 _LOGIN_COOKIE_KEYS 中的字段,避免污染客户端 Cookie 状态。
    """
    from util.network.request import client as http_client

    for key in _LOGIN_COOKIE_KEYS:
        value = cookies.get(key)
        if value:
            http_client.cookies.set(
                name=key,
                value=str(value),
                domain=".bilibili.com",
                path="/",
            )


def _fetch_user_info(cookies: Optional[dict] = None) -> Tuple[bool, str, int]:
    """通过 nav 接口验证 Cookie 有效性并返回用户信息

    :param cookies: 待验证的 Cookie(已应用到 client);None 则使用 client 当前 Cookie
    :return: (is_logged_in, username, uid)
    :raises NetworkError: 网络请求失败
    """
    from util.network.request import client as http_client

    try:
        response = http_client.get(_NAV_API)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise NetworkError(f"获取用户信息失败: {exc}") from exc

    nav_data = data.get("data", {}) if isinstance(data, dict) else {}
    if not nav_data.get("isLogin"):
        return (False, "", 0)
    return (
        True,
        nav_data.get("uname", ""),
        nav_data.get("mid", 0),
    )


# ---------- Cookie 字符串解析 ----------

def _parse_cookie_header(text: str) -> dict:
    """从 Cookie 字符串、URL 或 JSON 中解析登录 Cookie 字段

    支持以下输入形式:
    - "SESSDATA=xxx; bili_jct=yyy"
    - "Cookie: SESSDATA=xxx; ..."
    - "https://...?SESSDATA=xxx&bili_jct=yyy" (跨域回跳 URL)
    - '{"SESSDATA": "xxx", "bili_jct": "yyy"}'

    仅返回 _LOGIN_COOKIE_KEYS 中的字段,其余字段忽略。
    """
    if not text:
        return {}

    text = text.strip()
    # 移除 Cookie: 前缀
    if text.lower().startswith("cookie:"):
        text = text[len("cookie:"):].strip()

    # 情况 1:URL 形式,从 query/fragment 中提取
    if text.lower().startswith(("http://", "https://")):
        parsed = urlparse(text)
        result = {}
        for k, v in parse_qs(parsed.query).items():
            if k in _LOGIN_COOKIE_KEYS and v:
                result[k] = v[0]
        for k, v in parse_qs(parsed.fragment).items():
            if k in _LOGIN_COOKIE_KEYS and v:
                result[k] = v[0]
        return result

    # 情况 2:JSON 字符串
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return {
                k: v for k, v in data.items()
                if k in _LOGIN_COOKIE_KEYS and isinstance(v, str)
            }
    except (json.JSONDecodeError, ValueError):
        pass

    # 情况 3:分号分隔的 k=v 字符串
    result = {}
    for part in text.replace("\n", ";").split(";"):
        key, sep, value = part.partition("=")
        key, value = key.strip(), value.strip().strip('"')
        if sep and key in _LOGIN_COOKIE_KEYS:
            result[key] = value
    return result


# ---------- 扫码登录封装(同步) ----------

class QRCodeLogin:
    """同步扫码登录封装

    将 B 站二维码登录的异步流程封装为同步调用,便于 CLI 使用。
    每个实例代表一次完整的扫码登录会话。
    """

    def __init__(self, timeout: int = 180):
        self.timeout = timeout
        self.qrcode_url = ""
        self.qrcode_key = ""
        self.cookies: dict = {}

    def generate(self) -> str:
        """请求二维码生成接口,返回二维码 URL

        :raises NetworkError: 网络请求失败或响应异常
        """
        from util.network.request import client as http_client

        try:
            response = http_client.get(
                _QR_GENERATE_API,
                params={
                    "source": "main-fe-header",
                    "go_url": "https://www.bilibili.com/",
                    "web_location": "333.1007",
                },
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise NetworkError(f"获取二维码失败: {exc}") from exc

        if data.get("code") != 0:
            raise NetworkError(
                f"获取二维码失败: {data.get('message', 'unknown')}"
            )

        payload = data.get("data", {})
        self.qrcode_url = payload.get("url", "")
        self.qrcode_key = payload.get("qrcode_key", "")
        return self.qrcode_url

    def poll(self) -> int:
        """单次轮询扫码状态,返回 B 站状态码

        状态码含义见 QRCodeScanStatus:
        - 0:     登录成功(此时 cookies 字段已填充)
        - 86101: 等待扫码
        - 86090: 等待确认
        - 86038: 二维码过期

        :raises NetworkError: 网络请求失败
        """
        from util.network.request import client as http_client

        try:
            response = http_client.get(
                _QR_POLL_API, params={"qrcode_key": self.qrcode_key}
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise NetworkError(f"查询扫码状态失败: {exc}") from exc

        payload = data.get("data", {})
        code = payload.get("code", 0)
        # 登录成功时,url 字段中携带跨域 Cookie 参数
        if code == 0:
            self.cookies = _parse_cookie_header(payload.get("url", ""))
        return code

    def wait_for_scan(self) -> dict:
        """阻塞等待扫码完成,返回 Cookie 字典

        :raises AuthRequiredError: 超时未完成扫码
        :raises NetworkError: 网络请求失败
        """
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            code = self.poll()
            if code == 0:
                return self.cookies
            time.sleep(_POLL_INTERVAL)
        raise AuthRequiredError(f"扫码超时({self.timeout} 秒)")


def _do_qr_login(timeout: int, invert: bool, mode: str) -> None:
    """扫码登录核心逻辑

    :raises AuthRequiredError: 扫码超时或登录后 Cookie 验证失败
    :raises UserCancelledError: 用户 Ctrl+C
    :raises NetworkError: 网络错误
    :raises Bili23Error: Cookie 文件写入失败
    """
    qr_login = QRCodeLogin(timeout=timeout)
    url = qr_login.generate()

    # 在终端渲染二维码
    print_qr(url, mode=mode, invert=invert, console=console)
    console.print(
        f"[cyan]请使用手机哔哩哔哩客户端扫码(超时 {timeout} 秒)[/]"
    )

    try:
        cookies = qr_login.wait_for_scan()
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消[/]")
        raise UserCancelledError("用户取消扫码登录")

    if not cookies.get("SESSDATA"):
        raise AuthRequiredError("扫码成功但未获取到有效 Cookie")

    _save_cookies(cookies)
    _apply_cookies_to_client(cookies)

    # 二次验证 Cookie 有效性并打印用户信息
    is_login, username, uid = _fetch_user_info()
    if not is_login:
        raise AuthRequiredError("扫码登录后 Cookie 验证失败")

    toast(f"登录成功: {username} (UID: {uid})", level="success")


# ---------- 短信登录封装(同步) ----------

class SMSLogin:
    """同步短信验证码登录封装"""

    def __init__(
        self,
        phone: str,
        country_code: str = "86",
        timeout: int = 180,
    ):
        self.phone = phone
        self.country_code = country_code
        self.timeout = timeout
        self.captcha_key = ""
        self.cookies: dict = {}

    def send_code(self) -> None:
        """发送短信验证码

        :raises NetworkError: 网络请求失败
        :raises AuthRequiredError: B 站返回发送失败
        """
        from util.network.request import client as http_client

        params = {
            "cid": self.country_code,
            "tel": self.phone,
            "source": "main-fe-header",
            "go_url": "https://www.bilibili.com/",
        }
        try:
            response = http_client.post(_SMS_SEND_API, data=params)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise NetworkError(f"发送验证码失败: {exc}") from exc

        if data.get("code") != 0:
            raise AuthRequiredError(
                f"发送验证码失败: {data.get('message', 'unknown')}"
            )

        self.captcha_key = data.get("data", {}).get("captcha_key", "")

    def verify(self, code: str) -> dict:
        """验证短信验证码,成功返回 Cookie 字典

        :raises AuthRequiredError: 验证码错误或登录失败
        :raises NetworkError: 网络请求失败
        """
        from util.network.request import client as http_client

        params = {
            "cid": self.country_code,
            "tel": self.phone,
            "code": code,
            "source": "main-fe-header",
            "captcha_key": self.captcha_key,
            "go_url": "https://www.bilibili.com/",
        }
        try:
            response = http_client.post(_SMS_LOGIN_API, data=params)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            raise NetworkError(f"验证短信验证码失败: {exc}") from exc

        if data.get("code") != 0:
            raise AuthRequiredError(
                f"短信验证失败: {data.get('message', '验证码错误')}"
            )

        self.cookies = _parse_cookie_header(
            data.get("data", {}).get("url", "")
        )
        return self.cookies


def _do_sms_login(phone: str, country_code: str, timeout: int) -> None:
    """短信验证码登录核心逻辑

    :raises ConfigError: 手机号或验证码格式错误
    :raises AuthRequiredError: 发送/验证失败
    :raises UserCancelledError: 用户 Ctrl+C
    :raises NetworkError: 网络错误
    """
    # 提前返回:校验手机号格式(避免无效请求消耗 B 站接口配额)
    if not _PHONE_PATTERN.match(phone):
        raise ConfigError(
            f"手机号格式错误: {phone!r}(应为 11 位数字,1 开头)"
        )

    sms = SMSLogin(
        phone=phone, country_code=country_code, timeout=timeout
    )
    sms.send_code()
    console.print(
        f"[cyan]验证码已发送到 {phone},请输入 6 位验证码:[/]"
    )

    try:
        code = Prompt.ask("验证码")
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消[/]")
        raise UserCancelledError("用户取消短信登录")

    code = code.strip()
    if not (code.isdigit() and len(code) == 6):
        raise ConfigError(
            f"验证码格式错误: {code!r}(应为 6 位数字)"
        )

    cookies = sms.verify(code)
    if not cookies.get("SESSDATA"):
        raise AuthRequiredError("短信登录成功但未获取到有效 Cookie")

    _save_cookies(cookies)
    _apply_cookies_to_client(cookies)

    is_login, username, uid = _fetch_user_info()
    if not is_login:
        raise AuthRequiredError("短信登录后 Cookie 验证失败")

    toast(f"登录成功: {username} (UID: {uid})", level="success")


# ---------- Cookie 导入登录封装(同步) ----------

class CookieLogin:
    """同步 Cookie 导入登录封装"""

    def __init__(self, cookies: dict):
        self.cookies = cookies

    def verify(self) -> Tuple[bool, str, int]:
        """验证 Cookie 有效性,返回 (is_login, username, uid)

        :raises NetworkError: 网络请求失败
        """
        # 临时应用 Cookie 到 client 后调用 nav 接口校验
        _apply_cookies_to_client(self.cookies)
        return _fetch_user_info()


def _do_cookie_login(
    cookie: str,
    sessdata: Optional[str],
    bili_jct: Optional[str],
    dedeuserid: Optional[str],
) -> None:
    """Cookie 导入登录核心逻辑

    合并 -c 字符串与 --sessdata/--bili-jct/--dedeuserid 单独字段,
    优先级:单独字段 > -c 字符串(便于覆盖)。

    :raises ConfigError: Cookie 缺少 SESSDATA
    :raises AuthRequiredError: Cookie 无效或已失效
    :raises Bili23Error: Cookie 文件写入失败
    """
    cookies = _parse_cookie_header(cookie) if cookie else {}

    # 单独字段优先,覆盖 -c 字符串中的同名字段
    if sessdata:
        cookies["SESSDATA"] = sessdata
    if bili_jct:
        cookies["bili_jct"] = bili_jct
    if dedeuserid:
        cookies["DedeUserID"] = dedeuserid

    if not cookies.get("SESSDATA"):
        raise ConfigError("Cookie 缺少 SESSDATA 字段")

    cookie_login = CookieLogin(cookies)
    is_login, username, uid = cookie_login.verify()
    if not is_login:
        raise AuthRequiredError("Cookie 无效或已失效")

    _save_cookies(cookies)
    toast(f"登录成功: {username} (UID: {uid})", level="success")


# ---------- 状态查询 ----------

def _check_status() -> None:
    """查询当前登录状态

    :raises AuthRequiredError: Cookie 已失效
    :raises NetworkError: 网络错误
    """
    cookies = _load_cookies()
    if not cookies:
        toast("未登录", level="warning")
        return

    _apply_cookies_to_client(cookies)
    is_login, username, uid = _fetch_user_info()
    if not is_login:
        raise AuthRequiredError("Cookie 已失效")

    toast(f"已登录: {username} (UID: {uid})", level="success")


# ---------- 异常退出辅助 ----------

def _exit_with_error(exc: Bili23Error) -> None:
    """打印错误并按 exc.exit_code 退出"""
    console.print(f"[red]✗ {exc}[/]")
    raise typer.Exit(code=exc.exit_code) from exc


# ---------- 命令注册 ----------

@login_app.command("qr")
def login_qr(
    timeout: int = typer.Option(180, "--timeout", help="扫码超时(秒)"),
    invert: bool = typer.Option(False, "--invert", help="反转二维码黑白(深色终端)"),
    mode: str = typer.Option("unicode", "--mode", help="二维码模式(unicode/ascii)"),
):
    """扫码登录"""
    try:
        _do_qr_login(timeout=timeout, invert=invert, mode=mode)
    except Bili23Error as exc:
        _exit_with_error(exc)


@login_app.command("sms")
def login_sms(
    phone: str = typer.Option(..., "-p", "--phone", help="手机号(11 位)"),
    country_code: str = typer.Option("86", "-c", "--country-code", help="国家代码"),
    timeout: int = typer.Option(180, "--timeout", help="登录超时(秒)"),
):
    """短信验证码登录"""
    try:
        _do_sms_login(phone=phone, country_code=country_code, timeout=timeout)
    except Bili23Error as exc:
        _exit_with_error(exc)


@login_app.command("cookie")
def login_cookie(
    cookie: str = typer.Option(
        ...,
        "-c",
        "--cookie",
        help="Cookie 字符串(SESSDATA=xxx; bili_jct=xxx; ...)",
    ),
    sessdata: str = typer.Option(None, "--sessdata", help="仅 SESSDATA(可选)"),
    bili_jct: str = typer.Option(None, "--bili-jct", help="仅 bili_jct(可选)"),
    dedeuserid: str = typer.Option(
        None, "--dedeuserid", help="仅 DedeUserID(可选)"
    ),
):
    """Cookie 导入登录"""
    try:
        _do_cookie_login(cookie, sessdata, bili_jct, dedeuserid)
    except Bili23Error as exc:
        _exit_with_error(exc)


@login_app.command("status")
def login_status():
    """查询当前登录状态"""
    try:
        _check_status()
    except Bili23Error as exc:
        _exit_with_error(exc)
