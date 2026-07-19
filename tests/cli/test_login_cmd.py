# tests/cli/test_login_cmd.py
"""T5.3 测试:bili23 login qr/sms/cookie/status 命令组

覆盖 AC-024(登录)与 AC-025(状态查询):
- 命令组注册成功
- 各子命令 --help 退出码 0
- qr 登录:成功保存 Cookie、超时退出码 5
- sms 登录:手机号格式校验、模拟输入验证码成功、验证失败退出码 5
- cookie 登录:解析 Cookie 字符串、验证成功保存、无效退出码 5
- status 查询:未登录、已登录、Cookie 失效

测试中 mock 所有网络调用和 input() 函数,不真实联网。
"""
import json
import os
from unittest.mock import MagicMock

from typer.testing import CliRunner

# 导入即触发 login 命令注册到 app
import cli.commands.login  # noqa: F401
from cli.app import app


runner = CliRunner()


# ---- 工具函数 ----

def _make_cookie_file(tmp_path, content: str) -> str:
    """在 tmp_path 下创建 cookie 文件,返回路径"""
    path = tmp_path / "cookie.json"
    path.write_text(content, encoding="utf-8")
    return str(path)


def _patch_cookie_path(monkeypatch, path: str) -> str:
    """将 directory.cookie_path 重定向到指定路径"""
    from util.common.io.directory import directory
    monkeypatch.setattr(directory, "cookie_path", path)
    return path


def _mock_user_info_ok(*_a, **_kw):
    """伪造用户信息查询返回成功"""
    return (True, "test_user", 12345)


def _mock_user_info_failed(*_a, **_kw):
    """伪造用户信息查询返回未登录"""
    return (False, "", 0)


# ---- 注册与帮助 ----

def test_login_registered():
    """命令组注册成功:login 出现在 app.registered_groups"""
    names = [grp.name for grp in app.registered_groups]
    assert "login" in names


def test_login_help():
    """bili23 login --help 退出码 0"""
    result = runner.invoke(app, ["login", "--help"])
    assert result.exit_code == 0
    assert "login" in result.stdout


def test_login_qr_help():
    """bili23 login qr --help 退出码 0"""
    result = runner.invoke(app, ["login", "qr", "--help"])
    assert result.exit_code == 0
    assert "qr" in result.stdout


def test_login_sms_help():
    """bili23 login sms --help 退出码 0"""
    result = runner.invoke(app, ["login", "sms", "--help"])
    assert result.exit_code == 0
    assert "sms" in result.stdout


def test_login_cookie_help():
    """bili23 login cookie --help 退出码 0"""
    result = runner.invoke(app, ["login", "cookie", "--help"])
    assert result.exit_code == 0
    assert "cookie" in result.stdout


def test_login_status_help():
    """bili23 login status --help 退出码 0"""
    result = runner.invoke(app, ["login", "status", "--help"])
    assert result.exit_code == 0
    assert "status" in result.stdout


# ---- QR 登录 ----

def test_login_qr_success(monkeypatch, tmp_path):
    """mock QRCodeLogin 返回成功,验证 cookie 保存"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    # Mock QRCodeLogin 实例:generate 返回 URL,wait_for_scan 返回 Cookie
    mock_instance = MagicMock()
    mock_instance.generate.return_value = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate?qrcode_key=test_key"
    mock_instance.wait_for_scan.return_value = {
        "SESSDATA": "test_sessdata",
        "bili_jct": "test_jct",
        "DedeUserID": "12345",
        "DedeUserID__ckMd5": "abc",
    }
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.QRCodeLogin", mock_class)

    # 屏蔽真实网络与 httpx client
    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )
    monkeypatch.setattr(
        "cli.commands.login._fetch_user_info", _mock_user_info_ok
    )

    result = runner.invoke(app, ["login", "qr", "--timeout", "5"])
    assert result.exit_code == 0
    assert "登录成功" in result.stdout

    # 验证 Cookie 文件已保存
    cookie_path = str(tmp_path / "cookie.json")
    assert os.path.exists(cookie_path)
    with open(cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["SESSDATA"] == "test_sessdata"
    assert saved["bili_jct"] == "test_jct"

    # 验证 generate 和 wait_for_scan 被调用
    mock_instance.generate.assert_called_once()
    mock_instance.wait_for_scan.assert_called_once()


def test_login_qr_timeout(monkeypatch, tmp_path):
    """mock QRCodeLogin 超时,exit_code=5"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    from cli.exceptions import AuthRequiredError

    mock_instance = MagicMock()
    mock_instance.generate.return_value = "https://example.com/qr"
    mock_instance.wait_for_scan.side_effect = AuthRequiredError("扫码超时")
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.QRCodeLogin", mock_class)

    result = runner.invoke(app, ["login", "qr", "--timeout", "1"])
    assert result.exit_code == 5


def test_login_qr_cancel(monkeypatch, tmp_path):
    """用户 Ctrl+C 取消扫码,exit_code=3"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    mock_instance = MagicMock()
    mock_instance.generate.return_value = "https://example.com/qr"
    mock_instance.wait_for_scan.side_effect = KeyboardInterrupt()
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.QRCodeLogin", mock_class)

    result = runner.invoke(app, ["login", "qr", "--timeout", "1"])
    assert result.exit_code == 3
    assert "已取消" in result.stdout


# ---- SMS 登录 ----

def test_login_sms_invalid_phone(monkeypatch, tmp_path):
    """--phone 12345 exit_code=9(配置错误)"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))
    result = runner.invoke(app, ["login", "sms", "-p", "12345"])
    assert result.exit_code == 9


def test_login_sms_invalid_phone_short(monkeypatch, tmp_path):
    """--phone 1234567890(10 位) exit_code=9"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))
    result = runner.invoke(app, ["login", "sms", "-p", "1234567890"])
    assert result.exit_code == 9


def test_login_sms_invalid_phone_non_digit(monkeypatch, tmp_path):
    """--phone 13800abc1234 exit_code=9"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))
    result = runner.invoke(app, ["login", "sms", "-p", "13800abc1234"])
    assert result.exit_code == 9


def test_login_sms_success(monkeypatch, tmp_path):
    """mock SMSLogin,模拟 input() 输入验证码,登录成功"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    mock_instance = MagicMock()
    mock_instance.verify.return_value = {
        "SESSDATA": "sms_sess",
        "bili_jct": "sms_jct",
        "DedeUserID": "99999",
    }
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.SMSLogin", mock_class)

    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )
    monkeypatch.setattr(
        "cli.commands.login._fetch_user_info", _mock_user_info_ok
    )

    result = runner.invoke(
        app, ["login", "sms", "-p", "13800138000"], input="123456\n"
    )
    assert result.exit_code == 0
    assert "登录成功" in result.stdout

    # 验证 verify 收到 6 位验证码
    mock_instance.verify.assert_called_once()
    args, _ = mock_instance.verify.call_args
    assert args[0] == "123456"

    # 验证 Cookie 文件已保存
    cookie_path = str(tmp_path / "cookie.json")
    assert os.path.exists(cookie_path)
    with open(cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["SESSDATA"] == "sms_sess"


def test_login_sms_wrong_code(monkeypatch, tmp_path):
    """mock SMSLogin 返回错误,exit_code=5"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    from cli.exceptions import AuthRequiredError

    mock_instance = MagicMock()
    mock_instance.verify.side_effect = AuthRequiredError("验证码错误")
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.SMSLogin", mock_class)

    result = runner.invoke(
        app, ["login", "sms", "-p", "13800138000"], input="000000\n"
    )
    assert result.exit_code == 5


def test_login_sms_invalid_code_format(monkeypatch, tmp_path):
    """输入非 6 位数字验证码,exit_code=9"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    mock_instance = MagicMock()
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.SMSLogin", mock_class)

    result = runner.invoke(
        app, ["login", "sms", "-p", "13800138000"], input="abc\n"
    )
    assert result.exit_code == 9
    # 验证未走到 verify 流程
    mock_instance.verify.assert_not_called()


# ---- Cookie 登录 ----

def test_login_cookie_success(monkeypatch, tmp_path):
    """mock CookieLogin 验证成功,保存 cookie"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    mock_instance = MagicMock()
    mock_instance.verify.return_value = (True, "cookie_user", 88888)
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.CookieLogin", mock_class)

    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )

    result = runner.invoke(
        app, ["login", "cookie", "-c", "SESSDATA=xxx; bili_jct=yyy"]
    )
    assert result.exit_code == 0
    assert "登录成功" in result.stdout

    # 验证 Cookie 文件已保存
    cookie_path = str(tmp_path / "cookie.json")
    assert os.path.exists(cookie_path)
    with open(cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["SESSDATA"] == "xxx"
    assert saved["bili_jct"] == "yyy"


def test_login_cookie_invalid(monkeypatch, tmp_path):
    """mock CookieLogin 无效,exit_code=5"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    mock_instance = MagicMock()
    mock_instance.verify.return_value = (False, "", 0)
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.CookieLogin", mock_class)

    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )

    result = runner.invoke(
        app, ["login", "cookie", "-c", "SESSDATA=invalid"]
    )
    assert result.exit_code == 5


def test_login_cookie_parse(monkeypatch, tmp_path):
    """--cookie "SESSDATA=xxx; bili_jct=yyy" 正确解析并传入 CookieLogin"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    mock_instance = MagicMock()
    mock_instance.verify.return_value = (True, "user", 1)
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.CookieLogin", mock_class)

    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )

    result = runner.invoke(
        app, ["login", "cookie", "-c", "SESSDATA=xxx; bili_jct=yyy"]
    )
    assert result.exit_code == 0

    # 验证传入 CookieLogin 构造函数的 cookies 包含解析出的字段
    args, kwargs = mock_class.call_args
    cookies_arg = args[0] if args else kwargs.get("cookies")
    assert cookies_arg.get("SESSDATA") == "xxx"
    assert cookies_arg.get("bili_jct") == "yyy"


def test_login_cookie_missing_sessdata(monkeypatch, tmp_path):
    """Cookie 缺少 SESSDATA,exit_code=9(配置错误)"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    result = runner.invoke(
        app, ["login", "cookie", "-c", "bili_jct=yyy"]
    )
    assert result.exit_code == 9


def test_login_cookie_separate_fields(monkeypatch, tmp_path):
    """通过 --sessdata/--bili-jct/--dedeuserid 单独传入"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    mock_instance = MagicMock()
    mock_instance.verify.return_value = (True, "user", 1)
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr("cli.commands.login.CookieLogin", mock_class)

    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )

    # -c 必填,这里给空字符串触发单独字段解析;实际中要求 -c 必填,
    # 因此本测试用例跳过单独字段场景,改为合并 -c 与 --sessdata 验证覆盖
    result = runner.invoke(
        app,
        [
            "login", "cookie",
            "-c", "bili_jct=yyy",
            "--sessdata", "from_sessdata",
        ],
    )
    assert result.exit_code == 0
    args, _ = mock_class.call_args
    cookies_arg = args[0]
    assert cookies_arg.get("SESSDATA") == "from_sessdata"
    assert cookies_arg.get("bili_jct") == "yyy"


# ---- 状态查询 ----

def test_login_status_not_logged_in(monkeypatch, tmp_path):
    """无 cookie 文件,打印"未登录\",exit_code=0"""
    _patch_cookie_path(monkeypatch, str(tmp_path / "cookie.json"))

    result = runner.invoke(app, ["login", "status"])
    assert result.exit_code == 0
    assert "未登录" in result.stdout


def test_login_status_logged_in(monkeypatch, tmp_path):
    """cookie 文件存在且有效,打印用户信息"""
    cookie_path = _make_cookie_file(
        tmp_path,
        json.dumps({
            "SESSDATA": "valid_sess",
            "bili_jct": "valid_jct",
            "DedeUserID": "12345",
        }),
    )
    _patch_cookie_path(monkeypatch, cookie_path)

    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )
    monkeypatch.setattr(
        "cli.commands.login._fetch_user_info", _mock_user_info_ok
    )

    result = runner.invoke(app, ["login", "status"])
    assert result.exit_code == 0
    assert "已登录" in result.stdout
    assert "test_user" in result.stdout
    assert "12345" in result.stdout


def test_login_status_expired(monkeypatch, tmp_path):
    """cookie 文件存在但失效,exit_code=5"""
    cookie_path = _make_cookie_file(
        tmp_path, json.dumps({"SESSDATA": "expired"})
    )
    _patch_cookie_path(monkeypatch, cookie_path)

    monkeypatch.setattr(
        "cli.commands.login._apply_cookies_to_client", lambda cookies: None
    )
    monkeypatch.setattr(
        "cli.commands.login._fetch_user_info", _mock_user_info_failed
    )

    result = runner.invoke(app, ["login", "status"])
    assert result.exit_code == 5
    assert "失效" in result.stdout
