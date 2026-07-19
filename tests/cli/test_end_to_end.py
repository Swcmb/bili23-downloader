# tests/cli/test_end_to_end.py
"""T5.11 端到端测试 - 验证 CLI 整体可工作

测试覆盖:
- 命令注册:7 类命令(download/parse/login/logout/config/task/history)
  全部出现在 ``bili23 --help`` 与 ``app.registered_*`` 中
- 入口命令:``--version`` / ``--help`` 正常退出
- 完整下载流程:``bili23 download <url> --dry-run --non-interactive --episodes all``
  通过 monkeypatch mock parse_url + select_quality,验证 dry_run 计划打印
- 三种登录方式:qr(渲染二维码)/ cookie(保存 Cookie 文件)/ logout(删除)
- 配置 set+get 端到端
- 空数据库下的 history list / task list 输出"暂无..."
- 交互组件:episode_selector / quality_selector / qr_terminal
- 完整工作流:config set + download --dry-run

所有外部依赖(parse_url / select_quality / select_episodes / QRCodeLogin /
CookieLogin / TaskDatabase 等)均通过 monkeypatch + MagicMock 替换,
不依赖网络、文件系统(除 tmp_path 外)与数据库。

注意:``app`` 在每个测试函数内通过 ``from src.main import app`` 导入,
而非模块级别导入 - 这样可避免 collection 阶段触发 register_callbacks()
影响其他测试(如 test_callbacks.py 中需要观察信号连接数量变化)。
src.main 显式 import 各 commands 模块,确保 app 已挂载全部 7 类命令。
"""
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner


runner = CliRunner()


# ==================================================================
# 公共夹具:隔离 cookie 路径与配置,避免污染用户家目录
# ==================================================================

@pytest.fixture
def isolated_cookie_path(tmp_path, monkeypatch):
    """将 directory.cookie_path 重定向到 tmp_path,并返回路径"""
    from util.common.io.directory import directory
    path = str(tmp_path / "cookie.json")
    monkeypatch.setattr(directory, "cookie_path", path)
    return path


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """在 tmp_path 下隔离 config 单例与 directory.config_dir

    :return: 新建的 Config 实例,供断言验证
    """
    from util.common.config import Config
    cfg = Config(config_path=str(tmp_path / "config.json"))
    monkeypatch.setattr("cli.commands.config_cmd.config", cfg)
    monkeypatch.setattr(
        "cli.commands.config_cmd.directory",
        SimpleNamespace(config_dir=str(tmp_path)),
    )
    return cfg


def _fake_parsed_result(num_episodes: int = 3) -> dict:
    """构造测试用解析结果(含分集、画质、音质、编码)"""
    return {
        "title": "E2E 测试视频",
        "uploader": "E2E UP主",
        "category": "USER_UPLOADS",
        "episodes": [
            {
                "number": i, "id": i, "title": f"第 {i} 集",
                "duration": 60 * i, "bvid": "BV1xxx", "cid": 100 + i,
            }
            for i in range(1, num_episodes + 1)
        ],
        "video_qualities": [
            {"id": 127, "name": "8K 超高清"},
            {"id": 80, "name": "1080P 高清"},
        ],
        "audio_qualities": [
            {"id": 30280, "name": "Hi-Res 128K"},
            {"id": 30232, "name": "132K"},
        ],
        "video_codecs": ["AVC", "HEVC", "AV1"],
    }


def _patch_download_deps(monkeypatch, *, parsed=None,
                         selected_episodes=None, quality_result=None):
    """统一 patch download 命令的所有外部依赖

    :return: dict 含各 mock 实例,便于断言
    """
    import cli.commands.download as download_module

    if parsed is None:
        parsed = _fake_parsed_result()
    if selected_episodes is None:
        selected_episodes = [1, 2, 3]
    if quality_result is None:
        quality_result = {
            "video_quality_id": 80,
            "audio_quality_id": 30232,
            "video_codec": "AVC",
        }

    mocks = {
        "parse_url": MagicMock(return_value=parsed),
        "select_episodes": MagicMock(return_value=selected_episodes),
        "select_quality": MagicMock(return_value=quality_result),
        "task_manager": MagicMock(),
        "Downloader": MagicMock(),
        "ProgressRender": MagicMock(),
        "_process_extras": MagicMock(),
    }
    monkeypatch.setattr(download_module, "parse_url", mocks["parse_url"])
    monkeypatch.setattr(
        download_module, "select_episodes", mocks["select_episodes"]
    )
    monkeypatch.setattr(download_module, "select_quality", mocks["select_quality"])
    monkeypatch.setattr(download_module, "task_manager", mocks["task_manager"])
    monkeypatch.setattr(download_module, "Downloader", mocks["Downloader"])
    monkeypatch.setattr(download_module, "ProgressRender", mocks["ProgressRender"])
    monkeypatch.setattr(
        download_module, "_process_extras", mocks["_process_extras"]
    )
    return mocks


def _patch_db_empty(monkeypatch, *, module_path: str):
    """将指定模块的 TaskDatabase 替换为返回空列表的 mock"""
    instance = MagicMock()
    instance.list_tasks.return_value = []
    instance.get_history.return_value = []
    instance.count_history.return_value = 0
    monkeypatch.setattr(
        module_path, MagicMock(return_value=instance)
    )
    return instance


# ==================================================================
# 1. 命令注册与入口
# ==================================================================

def test_all_commands_registered():
    """验证所有 7 类命令注册到 app(AC-028 / M5-3)"""
    from src.main import app
    # 直接命令:download / parse / logout
    direct_names = {cmd.name for cmd in app.registered_commands}
    # 命令组:login / config / task / history
    group_names = {grp.name for grp in app.registered_groups}

    expected_direct = {"download", "parse", "logout"}
    expected_group = {"login", "config", "task", "history"}

    assert expected_direct.issubset(direct_names), \
        f"缺少直接命令: {expected_direct - direct_names}"
    assert expected_group.issubset(group_names), \
        f"缺少命令组: {expected_group - group_names}"


def test_bili23_version():
    """bili23 --version 输出 'bili23 3.0.0'(M5-2)"""
    from src.main import app
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "bili23" in result.stdout
    assert "3.0.0" in result.stdout


def test_bili23_help():
    """bili23 --help 退出码 0,且列出所有 7 类命令(M5-3)"""
    from src.main import app
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # 7 类命令名都应出现在 --help 输出中
    for name in ("download", "parse", "login", "logout",
                 "config", "task", "history"):
        assert name in result.stdout, f"--help 缺少命令: {name}"


# ==================================================================
# 2. download --dry-run 端到端
# ==================================================================

def test_download_dry_run_e2e(monkeypatch):
    """端到端:download --dry-run --non-interactive --episodes all <url>

    mock parse_url + select_quality,验证完整流程不报错且打印下载计划。
    """
    from src.main import app
    mocks = _patch_download_deps(monkeypatch)

    result = runner.invoke(
        app,
        [
            "download", "https://www.bilibili.com/video/BV1xxx",
            "--dry-run",
            "--non-interactive",
            "--episodes", "all",
        ],
    )

    assert result.exit_code == 0, result.output
    # 验证关键调用链
    mocks["parse_url"].assert_called_once()
    mocks["select_episodes"].assert_called_once()
    mocks["select_quality"].assert_called_once()
    # dry_run 不应触达 task_manager / Downloader
    mocks["task_manager"].create.assert_not_called()
    mocks["Downloader"].assert_not_called()
    # 应打印下载计划(包含标题)
    assert "E2E 测试视频" in result.output
    assert "下载计划" in result.output


# ==================================================================
# 3. 三种登录方式与登出
# ==================================================================

def test_login_qr_e2e(monkeypatch, isolated_cookie_path):
    """端到端:login qr 渲染二维码,mock QRCodeLogin,验证 print_qr 被调用"""
    import cli.commands.login as login_module
    from src.main import app

    # mock QRCodeLogin 实例:generate 返回 URL,wait_for_scan 返回 Cookie
    mock_instance = MagicMock()
    mock_instance.generate.return_value = "https://passport.bilibili.com/x/passport-login/web/qrcode"
    mock_instance.wait_for_scan.return_value = {
        "SESSDATA": "qr_sess",
        "bili_jct": "qr_jct",
        "DedeUserID": "11111",
        "DedeUserID__ckMd5": "abc",
    }
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr(login_module, "QRCodeLogin", mock_class)
    monkeypatch.setattr(
        login_module, "_apply_cookies_to_client", lambda cookies: None
    )
    monkeypatch.setattr(
        login_module, "_fetch_user_info",
        lambda *a, **kw: (True, "qr_user", 11111),
    )
    # spy print_qr,确认二维码渲染被调用
    print_qr_spy = MagicMock(wraps=login_module.print_qr)
    monkeypatch.setattr(login_module, "print_qr", print_qr_spy)

    result = runner.invoke(app, ["login", "qr", "--timeout", "5"])

    assert result.exit_code == 0, result.output
    assert "登录成功" in result.stdout
    # 验证 print_qr 被调用(二维码渲染)
    print_qr_spy.assert_called_once()
    # 验证 Cookie 文件已保存
    assert os.path.exists(isolated_cookie_path)
    with open(isolated_cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["SESSDATA"] == "qr_sess"


def test_login_cookie_e2e(monkeypatch, isolated_cookie_path):
    """端到端:login cookie -c 'SESSDATA=xxx',mock CookieLogin,验证 cookie 保存"""
    import cli.commands.login as login_module
    from src.main import app

    mock_instance = MagicMock()
    mock_instance.verify.return_value = (True, "cookie_user", 22222)
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr(login_module, "CookieLogin", mock_class)
    monkeypatch.setattr(
        login_module, "_apply_cookies_to_client", lambda cookies: None
    )

    result = runner.invoke(
        app,
        ["login", "cookie", "-c", "SESSDATA=xxx; bili_jct=yyy"],
    )

    assert result.exit_code == 0, result.output
    assert "登录成功" in result.stdout
    # 验证 Cookie 文件已保存,且内容正确
    assert os.path.exists(isolated_cookie_path)
    with open(isolated_cookie_path, "r", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["SESSDATA"] == "xxx"
    assert saved["bili_jct"] == "yyy"


def test_logout_e2e(monkeypatch, isolated_cookie_path):
    """端到端:先 login cookie,然后 logout,验证 cookie 文件被删除"""
    import cli.commands.login as login_module
    from src.main import app

    # Step 1: login cookie 写入 Cookie 文件
    mock_login_instance = MagicMock()
    mock_login_instance.verify.return_value = (True, "user", 33333)
    monkeypatch.setattr(login_module, "CookieLogin",
                       MagicMock(return_value=mock_login_instance))
    monkeypatch.setattr(
        login_module, "_apply_cookies_to_client", lambda cookies: None
    )

    login_result = runner.invoke(
        app, ["login", "cookie", "-c", "SESSDATA=zzz; bili_jct=www"]
    )
    assert login_result.exit_code == 0, login_result.output
    assert os.path.exists(isolated_cookie_path)

    # Step 2: logout --yes 删除 Cookie 文件
    logout_result = runner.invoke(app, ["logout", "--yes"])
    assert logout_result.exit_code == 0, logout_result.output
    assert "已登出" in logout_result.stdout
    assert not os.path.exists(isolated_cookie_path)


# ==================================================================
# 4. config set + get 端到端
# ==================================================================

def test_config_set_get_e2e(isolated_config):
    """端到端:config set download_threads 16,然后 config get download_threads"""
    from src.main import app
    # set
    set_result = runner.invoke(
        app, ["config", "set", "download_threads", "16"]
    )
    assert set_result.exit_code == 0, set_result.output
    assert "已设置 download_threads = 16" in set_result.stdout

    # get:验证持久化(重新加载配置以确认落盘)
    isolated_config.reload()
    assert isolated_config.get("download_threads") == 16

    # 通过 CLI get 命令读取
    get_result = runner.invoke(app, ["config", "get", "download_threads"])
    assert get_result.exit_code == 0, get_result.output
    assert get_result.stdout.strip() == "16"


# ==================================================================
# 5. 空数据库下的 history list / task list
# ==================================================================

def test_history_list_empty_e2e(monkeypatch):
    """端到端:history list 在空数据库下打印'暂无历史记录'"""
    _patch_db_empty(monkeypatch, module_path="cli.commands.history.TaskDatabase")
    from src.main import app
    result = runner.invoke(app, ["history", "list"])
    assert result.exit_code == 0, result.output
    assert "暂无历史记录" in result.stdout


def test_task_list_empty_e2e(monkeypatch):
    """端到端:task list 在空数据库下打印'暂无任务'"""
    _patch_db_empty(monkeypatch, module_path="cli.commands.task.TaskDatabase")
    from src.main import app
    result = runner.invoke(app, ["task", "list"])
    assert result.exit_code == 0, result.output
    assert "暂无任务" in result.stdout


# ==================================================================
# 6. 交互组件端到端
# ==================================================================

def test_interactive_episode_selector_e2e(monkeypatch):
    """端到端:episode_selector 接收 input '1-3' 返回 [1,2,3]"""
    monkeypatch.setattr("builtins.input", lambda _prompt: "1-3")
    from cli.interact.episode_selector import select_episodes

    episodes = [
        {"id": i, "title": f"第 {i} 集", "duration": 60 * i}
        for i in range(1, 6)
    ]
    result = select_episodes(episodes, interactive=True)
    assert result == [1, 2, 3]


def test_interactive_quality_selector_e2e(monkeypatch):
    """端到端:quality_selector 接收三次 input '2','1','1'"""
    # 抑制 Rich 表格输出
    from cli.interact import quality_selector as qs_module
    monkeypatch.setattr(qs_module.console, "print", lambda *a, **kw: None)

    inputs = iter(["2", "1", "1"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=[
            {"id": 127, "name": "8K 超高清"},
            {"id": 80, "name": "1080P 高清"},
        ],
        audio_qualities=[
            {"id": 30280, "name": "Hi-Res 128K"},
            {"id": 30232, "name": "132K"},
        ],
        video_codecs=["AVC", "HEVC", "AV1"],
    )
    # 输入 "2" -> 1080P(80);"1" -> Hi-Res(30280);"1" -> AVC
    assert result == {
        "video_quality_id": 80,
        "audio_quality_id": 30280,
        "video_codec": "AVC",
    }


def test_qr_terminal_render_e2e():
    """端到端:qr_terminal render_qr 输出包含二维码字符"""
    from cli.interact.qr_terminal import render_qr

    result = render_qr(
        "https://passport.bilibili.com/x/passport-login/web/qrcode",
        mode="unicode",
    )
    assert isinstance(result, str)
    assert "\n" in result
    # Unicode 模式应使用 █ ▀ ▄ 半块字符
    assert "█" in result or "▀" in result or "▄" in result


# ==================================================================
# 7. 完整工作流(config set + download --dry-run)
# ==================================================================

def test_full_workflow_dry_run(monkeypatch, isolated_config):
    """完整工作流:dry_run 模式下

    1. config set download_threads 16
    2. download <url> --dry-run --non-interactive --episodes all --video-quality 80
    3. 验证打印下载计划,无副作用
    """
    from src.main import app
    # Step 1: config set
    set_result = runner.invoke(
        app, ["config", "set", "download_threads", "16"]
    )
    assert set_result.exit_code == 0, set_result.output

    # Step 2: download --dry-run
    _patch_download_deps(monkeypatch)
    download_result = runner.invoke(
        app,
        [
            "download", "https://www.bilibili.com/video/BV1xxx",
            "--dry-run",
            "--non-interactive",
            "--episodes", "all",
            "--video-quality", "80",
        ],
    )
    assert download_result.exit_code == 0, download_result.output
    # 验证打印下载计划
    assert "下载计划" in download_result.output
    assert "E2E 测试视频" in download_result.output

    # Step 3: 验证 config 已持久化(无副作用验证)
    isolated_config.reload()
    assert isolated_config.get("download_threads") == 16
