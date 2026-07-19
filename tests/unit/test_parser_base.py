# tests/unit/test_parser_base.py
"""ParserBase 单元测试 - enc_wbi / find_str / check_response / on_error / check_login

覆盖 src/util/parse/parser/base.py:
- find_str 匹配 / 不匹配 / check=False 返回 None
- enc_wbi WBI 签名算法(参数排序、字符过滤、md5)
- check_response 在 code=0 时通过 / 在 code!=0 时抛 RuntimeError
- check_response 在有 error_message 时抛 RuntimeError
- on_error 记录错误消息
- get_extra_data / get_parser_type / get_category_name 默认返回值
- check_login 在 is_login=False 时抛 RuntimeError
"""
import pytest


# ==================================================================
# find_str
# ==================================================================

def test_find_str_returns_first_match():
    """find_str 返回首个匹配"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    result = parser.find_str(r"\d+", "abc123def456")
    assert result == "123"


def test_find_str_no_match_raises_with_check():
    """find_str 在无匹配且 check=True 时抛 ValueError"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    with pytest.raises(ValueError, match="无效的链接"):
        parser.find_str(r"\d+", "no_digits_here")


def test_find_str_no_match_returns_none_without_check():
    """find_str 在无匹配且 check=False 时返回 None"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    result = parser.find_str(r"\d+", "no_digits_here", check=False)
    assert result is None


# ==================================================================
# enc_wbi (WBI 签名)
# ==================================================================

def test_enc_wbi_returns_signed_query_string(monkeypatch):
    """enc_wbi 返回带 w_rid 签名的查询字符串"""
    from util.parse.parser.base import ParserBase

    # 提供 img_key 和 sub_key,模拟 config 中的 wbi keys
    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: {
            "img_key": "7cd084941338484aae1ad9425b84077c",
            "sub_key": "4932caff0ff746eab6f01bf08b130ac1",
        }.get(key, default),
    )

    parser = ParserBase()
    params = {"foo": "bar", "baz": 1}
    signed = parser.enc_wbi(params)

    # 结果应是 URL-encoded 字符串,包含 w_rid 与 wts
    assert "w_rid=" in signed
    assert "wts=" in signed
    assert "foo=bar" in signed
    assert "baz=1" in signed


def test_enc_wbi_sorts_params(monkeypatch):
    """enc_wbi 对参数按键字典序排序(a < m < wts < z)"""
    from util.parse.parser.base import ParserBase

    # img_key + sub_key 拼接后需 >= 64 字符,这里使用足够长的字符串
    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: {
            "img_key": "7cd084941338484aae1ad9425b84077c",
            "sub_key": "4932caff0ff746eab6f01bf08b130ac1",
        }.get(key, default),
    )

    parser = ParserBase()
    params = {"z": "1", "a": "2", "m": "3"}
    signed = parser.enc_wbi(params)
    # 参数按键字典序排序:a < m < wts < z
    a_pos = signed.index("a=")
    m_pos = signed.index("m=")
    wts_pos = signed.index("wts=")
    z_pos = signed.index("z=")
    assert a_pos < m_pos < wts_pos < z_pos


def test_enc_wbi_filters_special_chars(monkeypatch):
    """enc_wbi 过滤参数值中的 !'()* 字符"""
    from util.parse.parser.base import ParserBase

    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: {
            "img_key": "7cd084941338484aae1ad9425b84077c",
            "sub_key": "4932caff0ff746eab6f01bf08b130ac1",
        }.get(key, default),
    )

    parser = ParserBase()
    params = {"name": "hello!'()*world"}
    signed = parser.enc_wbi(params)
    # !'()* 应被过滤
    assert "hello!'()*world" not in signed
    assert "name=helloworld" in signed


# ==================================================================
# on_error / check_response
# ==================================================================

def test_on_error_records_message():
    """on_error 记录错误消息到 self.error_message"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    assert parser.error_message == ""
    parser.on_error("something went wrong")
    assert parser.error_message == "something went wrong"


def test_check_response_passes_when_code_zero():
    """check_response 在 code=0 时不抛异常"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    # 不抛异常即通过
    parser.check_response({"code": 0, "data": {}})


def test_check_response_passes_when_no_code():
    """check_response 在无 code 字段时,默认 -1 != 0,抛异常"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    # response.get("code", -1) 默认 -1 != 0 -> 抛异常
    with pytest.raises(RuntimeError):
        parser.check_response({})


def test_check_response_raises_on_error_code():
    """check_response 在 code!=0 时抛 RuntimeError"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    with pytest.raises(RuntimeError, match="接口错误"):
        parser.check_response({"code": -101, "message": "接口错误"})


def test_check_response_raises_unknown_error_when_no_message():
    """check_response 在 code!=0 且无 message 时抛 '未知错误'"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    with pytest.raises(RuntimeError, match="未知错误"):
        parser.check_response({"code": -1})


def test_check_response_raises_when_error_message_set():
    """check_response 在 error_message 已设置时优先抛该消息"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    parser.on_error("custom error from upstream")
    with pytest.raises(RuntimeError, match="custom error from upstream"):
        parser.check_response({"code": 0})


# ==================================================================
# get_extra_data / get_parser_type / get_category_name
# ==================================================================

def test_get_extra_data_default_empty_dict():
    """get_extra_data 默认返回空 dict"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    assert parser.get_extra_data() == {}


def test_get_parser_type_default_unknown():
    """get_parser_type 默认返回 UNKNOWN"""
    from util.parse.parser.base import ParserBase
    from util.common.enum import ParserType

    parser = ParserBase()
    assert parser.get_parser_type() == ParserType.UNKNOWN


def test_get_category_name_returns_parser_type_value():
    """get_category_name 返回 get_parser_type().value"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    assert parser.get_category_name() == "UNKNOWN"


# ==================================================================
# check_login
# ==================================================================

def test_check_login_raises_when_not_logged_in(monkeypatch):
    """check_login 在 is_login=False 时抛 RuntimeError"""
    from util.parse.parser.base import ParserBase

    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: {"is_login": False}.get(key, default),
    )
    monkeypatch.setattr(
        "util.common.config.config.is_expired", False, raising=False
    )

    parser = ParserBase()
    with pytest.raises(RuntimeError, match="log in"):
        parser.check_login()


def test_check_login_passes_when_logged_in(monkeypatch):
    """check_login 在 is_login=True 且未过期时不抛异常"""
    from util.parse.parser.base import ParserBase

    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: {"is_login": True}.get(key, default),
    )
    monkeypatch.setattr(
        "util.common.config.config.is_expired", False, raising=False
    )

    parser = ParserBase()
    parser.check_login()  # 不抛异常即通过


def test_check_login_raises_when_session_expired(monkeypatch):
    """check_login 在 session 过期时抛 RuntimeError"""
    from util.parse.parser.base import ParserBase

    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: {"is_login": True}.get(key, default),
    )
    monkeypatch.setattr(
        "util.common.config.config.is_expired", True, raising=False
    )

    parser = ParserBase()
    with pytest.raises(RuntimeError):
        parser.check_login()


# ==================================================================
# ParserBase __init__ 默认状态
# ==================================================================

def test_parser_base_init_defaults():
    """ParserBase.__init__ 设置默认状态"""
    from util.parse.parser.base import ParserBase

    parser = ParserBase()
    assert parser.url == ""
    assert parser.info_data == {}
    assert parser.stop_flag is False
    assert parser.raise_for_status is True
    assert parser.error_message == ""
