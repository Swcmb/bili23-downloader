# tests/cli/test_parse_cmd.py
"""T5.2 测试 - bili23 parse 命令

测试覆盖:
- test_parse_command_registered: 命令注册到 app
- test_parse_help: `bili23 parse --help` 退出码 0
- test_parse_invalid_url: 无效 URL 退出码 4(ParseError)
- test_parse_json_output: `--json` 输出有效 JSON 字符串
- test_parse_table_output: 默认输出包含表格(标题/分集)
- test_parse_no_color: `--no-color` 选项不报错
"""
import json

from typer.testing import CliRunner

from cli.commands import parse as parse_module


def _fake_parse_result() -> dict:
    """测试用固定解析结果,供 monkeypatch 替换 parse_url 使用"""
    return {
        "title": "测试视频标题",
        "uploader": "测试UP主",
        "category": "USER_UPLOADS",
        "episodes": [
            {"number": 1, "title": "第一集", "duration": 120, "bvid": "BV1xxx", "cid": 100},
            {"number": 2, "title": "第二集", "duration": 180, "bvid": "BV1xxx", "cid": 101},
        ],
        "video_qualities": [80, 64],
        "audio_qualities": [30216],
    }


def test_parse_command_registered():
    """parse 命令应被注册到 app.registered_commands"""
    from cli.app import app
    import cli.commands.parse  # noqa: F401 - 触发命令注册
    names = [cmd.name for cmd in app.registered_commands]
    assert "parse" in names


def test_parse_help():
    """bili23 parse --help 退出码 0,且帮助文本包含 URL"""
    from cli.app import app
    import cli.commands.parse  # noqa: F401
    result = CliRunner().invoke(app, ["parse", "--help"])
    assert result.exit_code == 0
    assert "URL" in result.stdout


def test_parse_invalid_url_exit_code_4():
    """AC: 无效 URL 触发 ParseError,退出码 4"""
    from cli.app import app
    import cli.commands.parse  # noqa: F401
    # "not-a-url" 不匹配 url_patterns 中任何模式,ParseWorker 会失败
    result = CliRunner().invoke(app, ["parse", "not-a-url"])
    assert result.exit_code == 4


def test_parse_json_output(monkeypatch):
    """--json 输出有效 JSON 字符串,可被 json.loads 解析"""
    from cli.app import app
    import cli.commands.parse  # noqa: F401

    # mock parse_url 返回固定数据,避免实际网络调用
    monkeypatch.setattr(parse_module, "parse_url", lambda url: _fake_parse_result())

    result = CliRunner().invoke(
        app, ["parse", "https://www.bilibili.com/video/BV1xxx", "--json"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout.strip())
    assert data["title"] == "测试视频标题"
    assert data["uploader"] == "测试UP主"
    assert data["category"] == "USER_UPLOADS"
    assert len(data["episodes"]) == 2
    assert data["episodes"][0]["title"] == "第一集"
    assert data["episodes"][1]["title"] == "第二集"


def test_parse_table_output(monkeypatch):
    """默认输出包含 Panel 元信息与分集表格"""
    from cli.app import app
    import cli.commands.parse  # noqa: F401

    monkeypatch.setattr(parse_module, "parse_url", lambda url: _fake_parse_result())

    result = CliRunner().invoke(
        app, ["parse", "https://www.bilibili.com/video/BV1xxx"]
    )
    assert result.exit_code == 0, result.output
    # Panel 元信息
    assert "测试视频标题" in result.stdout
    assert "测试UP主" in result.stdout
    # 分集表格
    assert "第一集" in result.stdout
    assert "第二集" in result.stdout


def test_parse_no_color(monkeypatch):
    """--no-color 选项不报错,退出码 0"""
    from cli.app import app
    import cli.commands.parse  # noqa: F401

    monkeypatch.setattr(parse_module, "parse_url", lambda url: _fake_parse_result())

    result = CliRunner().invoke(
        app, ["parse", "https://www.bilibili.com/video/BV1xxx", "--no-color"]
    )
    assert result.exit_code == 0, result.output
