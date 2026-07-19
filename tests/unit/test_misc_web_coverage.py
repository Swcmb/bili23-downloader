# tests/unit/test_misc_web_coverage.py
"""misc/web.py 覆盖率补强测试

覆盖 WebPage 的两个静态方法 + 多分支:
- ensure_file_exists:文件已存在 / 不存在但源文件存在 / 源文件不存在 / 写入失败
- open:file_path 为 None / webbrowser.open 返回 True / 返回 False
"""
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from util.misc import web


# ==================================================================
# ensure_file_exists - 文件已存在
# ==================================================================

def test_ensure_file_exists_returns_uri_when_file_exists(tmp_path, monkeypatch):
    """临时目录中已存在文件时,直接返回 file:// URI"""
    target = tmp_path / "captcha.html"
    target.write_text("<html></html>")

    monkeypatch.setattr(web.tempfile, "gettempdir", lambda: str(tmp_path))

    uri = web.WebPage.ensure_file_exists("captcha.html")
    assert uri == target.as_uri()


# ==================================================================
# ensure_file_exists - 文件不存在,从资源目录拷贝
# ==================================================================

def test_ensure_file_exists_copies_from_resource(tmp_path, monkeypatch):
    """临时目录无文件时,从 _RES_HTML_DIR 拷贝"""
    res_dir = tmp_path / "res"
    res_dir.mkdir()
    (res_dir / "test.html").write_text("<html>resource</html>", encoding="utf-8")

    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()

    monkeypatch.setattr(web, "_RES_HTML_DIR", res_dir)
    monkeypatch.setattr(web.tempfile, "gettempdir", lambda: str(temp_dir))

    uri = web.WebPage.ensure_file_exists("test.html")
    target = temp_dir / "test.html"
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "<html>resource</html>"
    assert uri == target.as_uri()


def test_ensure_file_exists_returns_none_when_source_missing(tmp_path, monkeypatch):
    """源资源文件不存在时返回 None"""
    res_dir = tmp_path / "res"
    res_dir.mkdir()
    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()

    monkeypatch.setattr(web, "_RES_HTML_DIR", res_dir)
    monkeypatch.setattr(web.tempfile, "gettempdir", lambda: str(temp_dir))

    uri = web.WebPage.ensure_file_exists("missing.html")
    assert uri is None


def test_ensure_file_exists_returns_none_on_write_failure(tmp_path, monkeypatch):
    """读取源文件后写入临时目录失败时返回 None"""
    res_dir = tmp_path / "res"
    res_dir.mkdir()
    (res_dir / "test.html").write_text("<html></html>", encoding="utf-8")
    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()

    monkeypatch.setattr(web, "_RES_HTML_DIR", res_dir)
    monkeypatch.setattr(web.tempfile, "gettempdir", lambda: str(temp_dir))

    # patch builtins.open 抛 OSError(仅写入模式,需排除读取)
    real_open = open

    def _fake_open(path, mode="r", *args, **kwargs):
        if "w" in mode:
            raise OSError("write failed")
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", _fake_open)

    uri = web.WebPage.ensure_file_exists("test.html")
    assert uri is None


# ==================================================================
# open - webbrowser.open 成功路径
# ==================================================================

def test_open_calls_webbrowser_open_with_uri(tmp_path, monkeypatch):
    """open 成功调用 webbrowser.open 并返回 True"""
    target = tmp_path / "captcha.html"
    target.write_text("<html></html>")
    monkeypatch.setattr(web.tempfile, "gettempdir", lambda: str(tmp_path))

    open_calls = []
    monkeypatch.setattr(web.webbrowser, "open", lambda url: open_calls.append(url) or True)

    web.WebPage.open("captcha.html")

    assert len(open_calls) == 1
    assert open_calls[0] == target.as_uri()


def test_open_logs_error_when_webbrowser_returns_false(tmp_path, monkeypatch, caplog):
    """webbrowser.open 返回 False 时记录错误日志"""
    target = tmp_path / "captcha.html"
    target.write_text("<html></html>")
    monkeypatch.setattr(web.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(web.webbrowser, "open", lambda url: False)

    import logging
    with caplog.at_level(logging.ERROR, logger="util.misc.web"):
        web.WebPage.open("captcha.html")

    # 应有 ERROR 级别日志(无法打开文件)
    assert any("无法打开文件" in rec.message for rec in caplog.records)


# ==================================================================
# open - file_path 为 None(源文件不存在场景)
# ==================================================================

def test_open_returns_none_when_file_path_is_none(tmp_path, monkeypatch):
    """源文件不存在 -> ensure_file_exists 返回 None -> 不调用 webbrowser.open"""
    res_dir = tmp_path / "res"
    res_dir.mkdir()
    temp_dir = tmp_path / "tmp"
    temp_dir.mkdir()

    monkeypatch.setattr(web, "_RES_HTML_DIR", res_dir)
    monkeypatch.setattr(web.tempfile, "gettempdir", lambda: str(temp_dir))

    open_calls = []
    monkeypatch.setattr(web.webbrowser, "open", lambda url: open_calls.append(url) or True)

    web.WebPage.open("missing.html")
    # 源文件不存在,ensure_file_exists 返回 None,webbrowser.open 不应被调用
    assert open_calls == []
