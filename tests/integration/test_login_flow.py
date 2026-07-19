# tests/integration/test_login_flow.py
"""集成测试 - 登录流程

覆盖范围:
- 扫码登录(QRCodeLogin):generate → poll → wait_for_scan → 保存 Cookie
- 短信登录(SMSLogin):send_code → verify → 保存 Cookie
- Cookie 导入登录(CookieLogin):verify → 保存 Cookie
- 登录后 status 显示已登录
- 登录后 logout 清除 Cookie

集成策略:
- 使用真实的 QRCodeLogin / SMSLogin / CookieLogin 类(不 mock 这些类本身)
- mock httpx client.get / client.post 的响应数据,模拟 B 站 API 返回
- 通过 isolated_cookie_path 隔离 Cookie 文件,避免污染真实环境
- _apply_cookies_to_client 替换为 no-op,避免触发 httpx 客户端初始化
"""
import json
import os
from unittest.mock import MagicMock

import pytest


# ==================================================================
# 公共夹具
# ==================================================================

@pytest.fixture
def isolated_cookie_path(tmp_path, monkeypatch):
    """将 directory.cookie_path 重定向到 tmp_path 下"""
    from util.common.io.directory import directory
    path = str(tmp_path / "cookie.json")
    monkeypatch.setattr(directory, "cookie_path", path)
    return path


@pytest.fixture
def patch_apply_cookies(monkeypatch):
    """_apply_cookies_to_client 替换为 no-op,避免触发 httpx 客户端初始化"""
    import cli.commands.login as login_module
    monkeypatch.setattr(
        login_module, "_apply_cookies_to_client", lambda cookies: None
    )


# ==================================================================
# 1. 扫码登录(QRCodeLogin)
# ==================================================================

def test_login_qr_flow(monkeypatch, isolated_cookie_path, patch_apply_cookies):
    """扫码登录完整流程:generate → poll(等待) → poll(确认) → 保存 Cookie

    通过 mock httpx client.get 模拟 B 站 qrcode/generate 与 qrcode/poll 接口,
    第一次 poll 返回 86101(等待扫码),第二次返回 0(登录成功)。
    """
    import cli.commands.login as login_module

    # mock httpx client.get 的响应序列
    poll_call_count = {"count": 0}

    def fake_get(url, params=None, **kwargs):
        # 构造一个简单的 Mock response
        response = MagicMock()
        response.raise_for_status = MagicMock()

        if "qrcode/generate" in url:
            response.json.return_value = {
                "code": 0,
                "data": {
                    "url": "https://passport.bilibili.com/x/passport-login/web/qrcode?key=test",
                    "qrcode_key": "test_qrcode_key_12345",
                },
            }
        elif "qrcode/poll" in url:
            poll_call_count["count"] += 1
            if poll_call_count["count"] == 1:
                # 第一次轮询:等待扫码
                response.json.return_value = {
                    "code": 0,
                    "data": {"code": 86101, "url": ""},
                }
            else:
                # 第二次轮询:登录成功,返回跨域 URL 携带 Cookie
                response.json.return_value = {
                    "code": 0,
                    "data": {
                        "code": 0,
                        "url": (
                            "https://passport.biligame.com/crossDomain?"
                            "SESSDATA=qr_sess_data&bili_jct=qr_jct&"
                            "DedeUserID=12345&DedeUserID__ckMd5=abcdef"
                        ),
                    },
                }
        elif "nav" in url:
            # 二次验证 Cookie 有效性
            response.json.return_value = {
                "code": 0,
                "data": {"isLogin": True, "uname": "qr_user", "mid": 12345},
            }
        else:
            response.json.return_value = {"code": -1, "message": "unknown"}

        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    # 让 _fetch_user_info 直接返回登录成功(避免依赖 nav 接口的 mock 复杂性)
    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies=None: (True, "qr_user", 12345),
    )

    # 调用 _do_qr_login,验证流程完整执行
    login_module._do_qr_login(timeout=10, invert=False, mode="unicode")

    # 验证 Cookie 已保存到文件
    assert os.path.exists(isolated_cookie_path)
    with open(isolated_cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert saved["SESSDATA"] == "qr_sess_data"
    assert saved["bili_jct"] == "qr_jct"
    assert saved["DedeUserID"] == "12345"
    assert saved["DedeUserID__ckMd5"] == "abcdef"


def test_qrcode_login_class_generate(monkeypatch):
    """单元级验证 QRCodeLogin.generate 返回二维码 URL

    直接调用真实 QRCodeLogin 类,mock httpx client。
    """
    import cli.commands.login as login_module

    qr_login = login_module.QRCodeLogin(timeout=5)

    def fake_get(url, params=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {
                "url": "https://passport.bilibili.com/x/passport-login/web/qrcode",
                "qrcode_key": "test_key_abc",
            },
        }
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    url = qr_login.generate()
    assert url == "https://passport.bilibili.com/x/passport-login/web/qrcode"
    assert qr_login.qrcode_key == "test_key_abc"


def test_qrcode_login_class_poll_success(monkeypatch):
    """单元级验证 QRCodeLogin.poll 在登录成功时解析 cookies"""
    import cli.commands.login as login_module

    qr_login = login_module.QRCodeLogin(timeout=5)
    qr_login.qrcode_key = "fake_key"

    def fake_get(url, params=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {
                "code": 0,
                "url": (
                    "https://passport.biligame.com/crossDomain?"
                    "SESSDATA=poll_sess&bili_jct=poll_jct&"
                    "DedeUserID=99999"
                ),
            },
        }
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    code = qr_login.poll()
    assert code == 0
    assert qr_login.cookies["SESSDATA"] == "poll_sess"
    assert qr_login.cookies["bili_jct"] == "poll_jct"
    assert qr_login.cookies["DedeUserID"] == "99999"


def test_qrcode_login_class_poll_waiting(monkeypatch):
    """单元级验证 QRCodeLogin.poll 在等待扫码时返回 86101"""
    import cli.commands.login as login_module

    qr_login = login_module.QRCodeLogin(timeout=5)
    qr_login.qrcode_key = "fake_key"

    def fake_get(url, params=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {"code": 86101, "url": ""},
        }
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    code = qr_login.poll()
    assert code == 86101
    # 等待扫码时 cookies 应为空
    assert qr_login.cookies == {}


def test_qrcode_login_generate_failure(monkeypatch):
    """QRCodeLogin.generate 在 B 站返回错误 code 时抛 NetworkError"""
    import cli.commands.login as login_module

    qr_login = login_module.QRCodeLogin(timeout=5)

    def fake_get(url, params=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"code": -101, "message": "频率过快"}
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    from cli.exceptions import NetworkError
    with pytest.raises(NetworkError):
        qr_login.generate()


# ==================================================================
# 2. 短信登录(SMSLogin)
# ==================================================================

def test_login_sms_flow(monkeypatch, isolated_cookie_path, patch_apply_cookies):
    """短信登录完整流程:send_code → 用户输入 → verify → 保存 Cookie

    mock httpx client.post 与 Prompt.ask,模拟用户输入 6 位验证码。
    """
    import cli.commands.login as login_module

    # mock httpx client.post 返回验证码发送与登录响应
    def fake_post(url, data=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()

        if "sms/send" in url:
            response.json.return_value = {
                "code": 0,
                "data": {"captcha_key": "sms_captcha_key_12345"},
            }
        elif "login/sms" in url:
            response.json.return_value = {
                "code": 0,
                "data": {
                    "url": (
                        "https://passport.biligame.com/crossDomain?"
                        "SESSDATA=sms_sess&bili_jct=sms_jct&"
                        "DedeUserID=88888"
                    ),
                },
            }
        else:
            response.json.return_value = {"code": -1, "message": "unknown"}

        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(post=fake_post))
    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies=None: (True, "sms_user", 88888),
    )

    # mock Prompt.ask 返回 6 位验证码
    monkeypatch.setattr(login_module.Prompt, "ask", lambda *a, **kw: "123456")

    # 调用 _do_sms_login,验证流程完整执行
    login_module._do_sms_login(
        phone="13800138000", country_code="86", timeout=10
    )

    # 验证 Cookie 已保存
    assert os.path.exists(isolated_cookie_path)
    with open(isolated_cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert saved["SESSDATA"] == "sms_sess"
    assert saved["bili_jct"] == "sms_jct"
    assert saved["DedeUserID"] == "88888"


def test_sms_login_class_send_code(monkeypatch):
    """单元级验证 SMSLogin.send_code 提取 captcha_key"""
    import cli.commands.login as login_module

    sms = login_module.SMSLogin(phone="13800138000", country_code="86")

    def fake_post(url, data=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {"captcha_key": "fake_captcha_key_xyz"},
        }
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(post=fake_post))

    sms.send_code()
    assert sms.captcha_key == "fake_captcha_key_xyz"


def test_sms_login_class_verify_success(monkeypatch):
    """单元级验证 SMSLogin.verify 成功返回 cookies"""
    import cli.commands.login as login_module

    sms = login_module.SMSLogin(phone="13800138000", country_code="86")
    sms.captcha_key = "fake_captcha_key"

    def fake_post(url, data=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {
                "url": (
                    "https://passport.biligame.com/crossDomain?"
                    "SESSDATA=verify_sess&bili_jct=verify_jct"
                ),
            },
        }
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(post=fake_post))

    cookies = sms.verify("123456")
    assert cookies["SESSDATA"] == "verify_sess"
    assert cookies["bili_jct"] == "verify_jct"


def test_sms_login_send_code_failure(monkeypatch):
    """SMSLogin.send_code 在 B 站返回错误时抛 AuthRequiredError"""
    import cli.commands.login as login_module

    sms = login_module.SMSLogin(phone="13800138000", country_code="86")

    def fake_post(url, data=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"code": -105, "message": "手机号无效"}
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(post=fake_post))

    from cli.exceptions import AuthRequiredError
    with pytest.raises(AuthRequiredError):
        sms.send_code()


def test_sms_login_verify_failure(monkeypatch):
    """SMSLogin.verify 验证码错误时抛 AuthRequiredError"""
    import cli.commands.login as login_module

    sms = login_module.SMSLogin(phone="13800138000", country_code="86")
    sms.captcha_key = "fake_captcha_key"

    def fake_post(url, data=None, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {"code": -106, "message": "验证码错误"}
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(post=fake_post))

    from cli.exceptions import AuthRequiredError
    with pytest.raises(AuthRequiredError):
        sms.verify("000000")


# ==================================================================
# 3. Cookie 导入登录(CookieLogin)
# ==================================================================

def test_login_cookie_flow(monkeypatch, isolated_cookie_path, patch_apply_cookies):
    """Cookie 导入登录完整流程:解析 Cookie → 验证 → 保存"""
    import cli.commands.login as login_module

    # 直接 mock _fetch_user_info 返回登录成功(避开 nav 接口的复杂性)
    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies=None: (True, "cookie_user", 77777),
    )

    cookie_str = "SESSDATA=cookie_sess; bili_jct=cookie_jct; DedeUserID=77777"

    login_module._do_cookie_login(
        cookie=cookie_str,
        sessdata=None,
        bili_jct=None,
        dedeuserid=None,
    )

    # 验证 Cookie 文件已保存
    assert os.path.exists(isolated_cookie_path)
    with open(isolated_cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)

    assert saved["SESSDATA"] == "cookie_sess"
    assert saved["bili_jct"] == "cookie_jct"
    assert saved["DedeUserID"] == "77777"


def test_cookie_login_class_verify_success(monkeypatch):
    """单元级验证 CookieLogin.verify 调用 _fetch_user_info 返回用户信息"""
    import cli.commands.login as login_module

    cookies = {
        "SESSDATA": "test_sess",
        "bili_jct": "test_jct",
        "DedeUserID": "12345",
    }

    cookie_login = login_module.CookieLogin(cookies)

    # mock _fetch_user_info 返回登录成功
    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies_arg=None: (True, "test_user", 12345),
    )

    is_login, username, uid = cookie_login.verify()
    assert is_login is True
    assert username == "test_user"
    assert uid == 12345


def test_cookie_login_missing_sessdata(monkeypatch, isolated_cookie_path):
    """Cookie 缺少 SESSDATA 时抛 ConfigError"""
    import cli.commands.login as login_module

    from cli.exceptions import ConfigError

    with pytest.raises(ConfigError):
        login_module._do_cookie_login(
            cookie="bili_jct=yyy",  # 缺少 SESSDATA
            sessdata=None,
            bili_jct=None,
            dedeuserid=None,
        )


def test_cookie_login_invalid(monkeypatch, isolated_cookie_path, patch_apply_cookies):
    """Cookie 验证失败时抛 AuthRequiredError"""
    import cli.commands.login as login_module

    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies=None: (False, "", 0),
    )

    from cli.exceptions import AuthRequiredError

    with pytest.raises(AuthRequiredError):
        login_module._do_cookie_login(
            cookie="SESSDATA=invalid_sess",
            sessdata=None,
            bili_jct=None,
            dedeuserid=None,
        )


def test_cookie_login_with_separate_fields(monkeypatch, isolated_cookie_path, patch_apply_cookies):
    """通过 --sessdata/--bili-jct/--dedeuserid 单独字段覆盖 -c 中的同名字段"""
    import cli.commands.login as login_module

    captured_cookies = {}

    def fake_apply(cookies):
        captured_cookies.update(cookies)

    monkeypatch.setattr(login_module, "_apply_cookies_to_client", fake_apply)
    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies=None: (True, "user", 1),
    )

    login_module._do_cookie_login(
        cookie="SESSDATA=orig_sess; bili_jct=orig_jct",
        sessdata="override_sess",
        bili_jct="override_jct",
        dedeuserid="override_uid",
    )

    assert captured_cookies["SESSDATA"] == "override_sess"
    assert captured_cookies["bili_jct"] == "override_jct"
    assert captured_cookies["DedeUserID"] == "override_uid"


# ==================================================================
# 4. 登录后 status 显示已登录
# ==================================================================

def test_login_status_after_login(
    monkeypatch, isolated_cookie_path, patch_apply_cookies
):
    """登录后 status 显示已登录,且包含用户名与 UID"""
    import cli.commands.login as login_module

    # 写入 Cookie 文件
    with open(isolated_cookie_path, "w", encoding="utf-8") as f:
        json.dump({
            "SESSDATA": "valid_sess",
            "bili_jct": "valid_jct",
            "DedeUserID": "12345",
        }, f)

    # mock _fetch_user_info 返回登录成功
    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies=None: (True, "logged_in_user", 12345),
    )

    # _check_status 不应抛异常
    login_module._check_status()


def test_login_status_not_logged_in(monkeypatch, isolated_cookie_path):
    """无 Cookie 文件时 status 提示未登录,不抛异常"""
    import cli.commands.login as login_module

    # isolated_cookie_path 指向不存在的文件(默认 tmp_path/cookie.json)
    assert not os.path.exists(isolated_cookie_path)

    # 不应抛异常
    login_module._check_status()


def test_login_status_expired(
    monkeypatch, isolated_cookie_path, patch_apply_cookies
):
    """Cookie 存在但失效时抛 AuthRequiredError"""
    import cli.commands.login as login_module

    with open(isolated_cookie_path, "w", encoding="utf-8") as f:
        json.dump({"SESSDATA": "expired_sess"}, f)

    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda cookies=None: (False, "", 0),
    )

    from cli.exceptions import AuthRequiredError
    with pytest.raises(AuthRequiredError):
        login_module._check_status()


# ==================================================================
# 5. 登录后 logout 清除 Cookie
# ==================================================================

def test_logout_after_login(
    monkeypatch, isolated_cookie_path, patch_apply_cookies
):
    """先 login cookie,然后 logout,验证 Cookie 文件被删除"""
    import cli.commands.login as login_module
    import cli.commands.logout as logout_module

    # Step 1: 写入 Cookie 文件(模拟登录后状态)
    with open(isolated_cookie_path, "w", encoding="utf-8") as f:
        json.dump({
            "SESSDATA": "test_sess",
            "bili_jct": "test_jct",
        }, f)
    assert os.path.exists(isolated_cookie_path)

    # Step 2: logout --yes 删除 Cookie 文件
    monkeypatch.setattr(logout_module, "_clear_request_cookies", lambda: None)
    logout_module._perform_logout(force=True)

    # 验证 Cookie 文件已被删除
    assert not os.path.exists(isolated_cookie_path)


def test_logout_idempotent_when_not_logged_in(
    monkeypatch, isolated_cookie_path
):
    """未登录时 logout 幂等返回,不抛异常"""
    import cli.commands.logout as logout_module

    # 未创建 Cookie 文件
    assert not os.path.exists(isolated_cookie_path)

    # _perform_logout 不应抛异常
    logout_module._perform_logout(force=True)


def test_logout_clears_request_cookies(
    monkeypatch, isolated_cookie_path, patch_apply_cookies
):
    """logout 调用 _clear_request_cookies 清除 httpx client 中的 Cookie"""
    import cli.commands.logout as logout_module

    # 写入 Cookie 文件
    with open(isolated_cookie_path, "w", encoding="utf-8") as f:
        json.dump({"SESSDATA": "test"}, f)

    # mock _clear_request_cookies 验证被调用
    clear_called = {"called": False}

    def fake_clear():
        clear_called["called"] = True

    monkeypatch.setattr(logout_module, "_clear_request_cookies", fake_clear)

    logout_module._perform_logout(force=True)

    assert clear_called["called"] is True
    assert not os.path.exists(isolated_cookie_path)


# ==================================================================
# 6. Cookie 字符串解析(_parse_cookie_header)
# ==================================================================

def test_parse_cookie_header_semicolon_format():
    """分号分隔的 Cookie 字符串正确解析"""
    import cli.commands.login as login_module

    text = "SESSDATA=abc; bili_jct=def; DedeUserID=12345; DedeUserID__ckMd5=md5"
    result = login_module._parse_cookie_header(text)

    assert result == {
        "SESSDATA": "abc",
        "bili_jct": "def",
        "DedeUserID": "12345",
        "DedeUserID__ckMd5": "md5",
    }


def test_parse_cookie_header_with_prefix():
    """Cookie: 前缀正确去除"""
    import cli.commands.login as login_module

    text = "Cookie: SESSDATA=abc; bili_jct=def"
    result = login_module._parse_cookie_header(text)

    assert result == {"SESSDATA": "abc", "bili_jct": "def"}


def test_parse_cookie_header_url_format():
    """URL 形式的 Cookie 字符串(query + fragment)正确解析"""
    import cli.commands.login as login_module

    text = (
        "https://passport.biligame.com/crossDomain?"
        "SESSDATA=url_sess&bili_jct=url_jct"
    )
    result = login_module._parse_cookie_header(text)

    assert result == {"SESSDATA": "url_sess", "bili_jct": "url_jct"}


def test_parse_cookie_header_json_format():
    """JSON 字符串形式的 Cookie 正确解析"""
    import cli.commands.login as login_module

    text = '{"SESSDATA": "json_sess", "bili_jct": "json_jct"}'
    result = login_module._parse_cookie_header(text)

    assert result == {"SESSDATA": "json_sess", "bili_jct": "json_jct"}


def test_parse_cookie_header_ignores_unknown_keys():
    """非登录字段被忽略(仅返回 _LOGIN_COOKIE_KEYS 中的字段)"""
    import cli.commands.login as login_module

    text = "SESSDATA=keep; other_field=drop; bili_jct=keep2"
    result = login_module._parse_cookie_header(text)

    assert result == {"SESSDATA": "keep", "bili_jct": "keep2"}
    assert "other_field" not in result


def test_parse_cookie_header_empty_returns_empty():
    """空字符串返回空 dict"""
    import cli.commands.login as login_module

    assert login_module._parse_cookie_header("") == {}
    assert login_module._parse_cookie_header("   ") == {}


# ==================================================================
# 7. Cookie 文件读写辅助(_save_cookies / _load_cookies)
# ==================================================================

def test_save_and_load_cookies_roundtrip(monkeypatch, isolated_cookie_path):
    """_save_cookies 写入的 Cookie 文件可被 _load_cookies 正确读回"""
    import cli.commands.login as login_module

    cookies = {
        "SESSDATA": "roundtrip_sess",
        "bili_jct": "roundtrip_jct",
        "DedeUserID": "99999",
        "DedeUserID__ckMd5": "md5hash",
    }

    login_module._save_cookies(cookies)

    # 验证文件存在
    assert os.path.exists(isolated_cookie_path)

    # 读回验证
    loaded = login_module._load_cookies()
    assert loaded == cookies


def test_load_cookies_returns_none_when_missing(monkeypatch, isolated_cookie_path):
    """Cookie 文件不存在时 _load_cookies 返回 None"""
    import cli.commands.login as login_module

    assert not os.path.exists(isolated_cookie_path)
    assert login_module._load_cookies() is None


def test_load_cookies_returns_none_when_corrupted(
    monkeypatch, isolated_cookie_path
):
    """Cookie 文件损坏(非 JSON)时 _load_cookies 返回 None"""
    import cli.commands.login as login_module

    with open(isolated_cookie_path, "w", encoding="utf-8") as f:
        f.write("{invalid json content")

    assert login_module._load_cookies() is None


def test_load_cookies_returns_none_when_not_dict(
    monkeypatch, isolated_cookie_path
):
    """Cookie 文件根节点非 dict(如 JSON 数组)时返回 None"""
    import cli.commands.login as login_module

    with open(isolated_cookie_path, "w", encoding="utf-8") as f:
        json.dump(["not", "a", "dict"], f)

    assert login_module._load_cookies() is None


# ==================================================================
# 8. _fetch_user_info 通过 nav 接口验证 Cookie
# ==================================================================

def test_fetch_user_info_logged_in(monkeypatch):
    """_fetch_user_info 在 nav 接口返回 isLogin=true 时返回用户信息"""
    import cli.commands.login as login_module

    def fake_get(url, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {"isLogin": True, "uname": "nav_user", "mid": 55555},
        }
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    is_login, username, uid = login_module._fetch_user_info()
    assert is_login is True
    assert username == "nav_user"
    assert uid == 55555


def test_fetch_user_info_not_logged_in(monkeypatch):
    """_fetch_user_info 在 nav 接口返回 isLogin=false 时返回 (False, '', 0)"""
    import cli.commands.login as login_module

    def fake_get(url, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "code": 0,
            "data": {"isLogin": False},
        }
        return response

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    is_login, username, uid = login_module._fetch_user_info()
    assert is_login is False
    assert username == ""
    assert uid == 0


def test_fetch_user_info_network_error(monkeypatch):
    """_fetch_user_info 在网络请求失败时抛 NetworkError"""
    import cli.commands.login as login_module

    def fake_get(url, **kwargs):
        raise ConnectionError("network down")

    monkeypatch.setattr("util.network.request.client", MagicMock(get=fake_get))

    from cli.exceptions import NetworkError
    with pytest.raises(NetworkError):
        login_module._fetch_user_info()
