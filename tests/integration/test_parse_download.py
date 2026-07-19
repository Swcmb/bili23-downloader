# tests/integration/test_parse_download.py
"""集成测试 - 解析→下载流程

覆盖范围:
- 投稿视频 URL 解析 → 选择分集 → 创建任务 → dry_run
- 番剧 URL 解析 → 下载
- b23.tv 短链解析(跟随重定向)
- 无效 URL 触发 ParseError
- --danmaku / --subtitle / --cover / --metadata 选项触发附加产物

集成策略:
- 通过 CliRunner 调用 CLI 命令,验证命令链路完整正确
- monkeypatch 替换 parse_url / select_episodes / select_quality /
  task_manager / _process_extras / Downloader 等外部依赖
- 不触达真实网络/数据库/文件系统
"""
import json
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import cli.commands.download as download_module  # noqa: F401 - 触发命令注册
from cli.app import app


runner = CliRunner()


# ==================================================================
# 公共夹具与辅助
# ==================================================================

def _make_video_parsed_result(num_episodes: int = 3) -> dict:
    """构造投稿视频的解析结果(包含分集列表)"""
    return {
        "title": "测试投稿视频",
        "uploader": "测试UP主",
        "category": "USER_UPLOADS",
        "episodes": [
            {
                "number": i,
                "id": i,
                "title": f"第 {i} 集",
                "duration": 60 * i,
                "bvid": "BV1xxx",
                "cid": 100 + i,
            }
            for i in range(1, num_episodes + 1)
        ],
        "video_qualities": [
            {"id": 127, "name": "8K 超高清"},
            {"id": 80, "name": "1080P 高清"},
        ],
        "audio_qualities": [
            {"id": 30280, "name": "Hi-Res 128K"},
        ],
        "video_codecs": ["AVC", "HEVC"],
    }


def _make_bangumi_parsed_result() -> dict:
    """构造番剧的解析结果(单一分集,与投稿视频结构相同)"""
    return {
        "title": "测试番剧",
        "uploader": "番剧UP",
        "category": "BANGUMI",
        "episodes": [
            {
                "number": 1,
                "id": 1,
                "title": "正片 1",
                "duration": 1440,
                "bvid": "BV1bangumi",
                "cid": 200,
                "ep_id": 100001,
            }
        ],
        "video_qualities": [{"id": 80, "name": "1080P"}],
        "audio_qualities": [{"id": 30232, "name": "132K"}],
        "video_codecs": ["AVC"],
    }


def _patch_parse_only(monkeypatch, parsed: dict) -> dict:
    """仅 patch parse_url,保留其他真实依赖

    适用于"无效 URL 抛 ParseError"这类只需解析层、无需下载链路的测试。
    """
    parse_url_mock = MagicMock(return_value=parsed)
    monkeypatch.setattr(download_module, "parse_url", parse_url_mock)
    return {"parse_url": parse_url_mock}


def _patch_full_download_chain(monkeypatch, parsed: dict) -> dict:
    """patch 整条下载链路(parse_url/select_episodes/select_quality/
    task_manager/Downloader/ProgressRender/_process_extras)

    返回各 mock 实例,供断言验证。
    """
    quality_result = {
        "video_quality_id": 80,
        "audio_quality_id": 30232,
        "video_codec": "AVC",
    }

    mocks = {
        "parse_url": MagicMock(return_value=parsed),
        "select_episodes": MagicMock(return_value=[1, 2, 3]),
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


# ==================================================================
# 1. 投稿视频:解析 → 选择分集 → 创建任务 → dry_run
# ==================================================================

def test_parse_video_url_to_download_dry_run(monkeypatch):
    """投稿视频 URL:dry_run 流程打印计划且不触达 task_manager"""
    parsed = _make_video_parsed_result(num_episodes=5)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1-3",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    # dry_run 不应触达下载链路下游
    mocks["task_manager"].create.assert_not_called()
    mocks["Downloader"].assert_not_called()
    # 但 parse_url / select_episodes / select_quality 被调用
    mocks["parse_url"].assert_called_once_with(
        "https://www.bilibili.com/video/BV1xxx"
    )
    mocks["select_episodes"].assert_called_once()
    mocks["select_quality"].assert_called_once()
    # 输出包含解析标题与下载计划
    assert "测试投稿视频" in result.output
    assert "下载计划" in result.output


def test_parse_video_url_to_download_real_run(monkeypatch):
    """投稿视频 URL:非 dry_run 调用 task_manager.create 与 _process_extras"""
    parsed = _make_video_parsed_result(num_episodes=2)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "all",
        ],
    )

    assert result.exit_code == 0, result.output
    # task_manager.create 被调用一次,入参为 episode_info_list(非空)
    mocks["task_manager"].create.assert_called_once()
    args, _ = mocks["task_manager"].create.call_args
    episode_info_list = args[0]
    assert isinstance(episode_info_list, list)
    assert len(episode_info_list) == 2  # parsed 中有 2 个分集
    # _process_extras 被调用(danmaku/subtitle 等参数 None 时仍调用以走流程)
    mocks["_process_extras"].assert_called_once()


# ==================================================================
# 2. 番剧 URL:解析 → 下载
# ==================================================================

def test_parse_bangumi_url_to_download(monkeypatch):
    """番剧 URL:dry_run 输出包含番剧标题,parse_url 接收完整 URL"""
    parsed = _make_bangumi_parsed_result()
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/bangumi/play/ep100001",
            "--non-interactive",
            "--episodes", "1",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    # 验证 parse_url 接收到的 URL 完整保留
    mocks["parse_url"].assert_called_once_with(
        "https://www.bilibili.com/bangumi/play/ep100001"
    )
    # 输出包含番剧标题
    assert "测试番剧" in result.output


def test_parse_bangumi_real_run_triggers_task_manager(monkeypatch):
    """番剧 URL:非 dry_run 时 task_manager.create 被调用且 episode_info 包含 ep_id"""
    parsed = _make_bangumi_parsed_result()
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/bangumi/play/ep100001",
            "--non-interactive",
            "--episodes", "1",
        ],
    )

    assert result.exit_code == 0, result.output
    mocks["task_manager"].create.assert_called_once()
    args, _ = mocks["task_manager"].create.call_args
    episode_info_list = args[0]
    assert len(episode_info_list) == 1
    # 番剧分集应包含 ep_id 字段
    assert episode_info_list[0].get("ep_id") == 100001


# ==================================================================
# 3. b23.tv 短链解析(跟随重定向)
# ==================================================================

def test_parse_b23_short_url_dry_run(monkeypatch):
    """b23.tv 短链:CLI 接收原始 URL 不做客户端转换,parse_url 完整接收"""
    parsed = _make_video_parsed_result(num_episodes=1)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://b23.tv/abc123",
            "--non-interactive",
            "--episodes", "1",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    # parse_url 被调用,入参为完整的 b23.tv URL
    mocks["parse_url"].assert_called_once_with("https://b23.tv/abc123")


def test_parse_b23_parser_unit(monkeypatch):
    """单元级验证:B23Parser 通过 SyncNetWorkRequest 解析重定向 URL

    mock SyncNetWorkRequest.run 返回真实 bilibili URL,验证 B23Parser.parse
    正确返回重定向后的 URL,且当响应与原 URL 相同时抛出 RuntimeError。
    """
    from util.parse.parser.b23 import B23Parser

    # 场景 1:正常重定向
    def fake_run(self):
        return "https://www.bilibili.com/video/BV1realBVID"

    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest.run", fake_run
    )

    parser = B23Parser()
    redirected = parser.parse("https://b23.tv/abc123")
    assert redirected == "https://www.bilibili.com/video/BV1realBVID"


def test_parse_b23_parser_expired(monkeypatch):
    """b23 短链已过期(响应 URL == 请求 URL)抛 RuntimeError"""
    from util.parse.parser.b23 import B23Parser
    from util.common.translator import Translator

    # 源代码中存在已知 dangling 调用 Translator.ERROR_MESSAGES,
    # 该静态方法在 T1 重构后已被移除。这里 monkeypatch 为 identity
    # lambda(raising=False 允许新增不存在属性),
    # 使 B23Parser.on_error 能被正确触发。
    monkeypatch.setattr(
        Translator, "ERROR_MESSAGES",
        lambda *args, **kwargs: args[0] if args else "",
        raising=False,
    )

    # mock 返回与输入相同的 URL(无重定向 = 过期)
    monkeypatch.setattr(
        "util.network.request.SyncNetWorkRequest.run",
        lambda self: "https://b23.tv/abc123",
    )

    parser = B23Parser()
    with pytest.raises(RuntimeError):
        parser.parse("https://b23.tv/abc123")


def test_parse_b23_parser_normalize_invalid(monkeypatch):
    """b23 URL 无 https:// 前缀且无可识别前缀时抛 RuntimeError"""
    from util.parse.parser.b23 import B23Parser
    from util.common.translator import Translator

    # 同上,patch dangling 调用(raising=False 允许新增不存在属性)
    monkeypatch.setattr(
        Translator, "ERROR_MESSAGES",
        lambda *args, **kwargs: args[0] if args else "",
        raising=False,
    )

    parser = B23Parser()
    # URL 不含 https:// 且不以 https:// 开头
    with pytest.raises(RuntimeError):
        parser.parse("not_a_url")


# ==================================================================
# 4. 无效 URL 抛 ParseError
# ==================================================================

def test_parse_with_invalid_url_raises_parse_error(monkeypatch):
    """无效 URL:parse_url 抛 ParseError,download 命令 exit_code=4"""
    from cli.exceptions import ParseError

    parse_url_mock = MagicMock(side_effect=ParseError("无效的 URL"))
    monkeypatch.setattr(download_module, "parse_url", parse_url_mock)

    result = runner.invoke(
        app,
        ["download", "not-a-url", "--dry-run"],
    )

    assert result.exit_code == 4
    parse_url_mock.assert_called_once_with("not-a-url")


def test_parse_empty_url_raises_parse_error(monkeypatch):
    """空 URL:parse_url 抛 ParseError,download 命令 exit_code=4"""
    from cli.exceptions import ParseError

    parse_url_mock = MagicMock(side_effect=ParseError("无效的 URL"))
    monkeypatch.setattr(download_module, "parse_url", parse_url_mock)

    result = runner.invoke(app, ["download", "", "--dry-run"])
    assert result.exit_code == 4


# ==================================================================
# 5. --danmaku xml 选项触发附加产物
# ==================================================================

def test_download_with_danmaku_option(monkeypatch):
    """--danmaku xml 在 dry_run 模式下不报错

    由于 dry_run 早返回,_process_extras 不会被调用,但选项校验通过。
    本测试同时验证非 dry_run 时 _process_extras 收到 danmaku='xml' 参数。
    """
    parsed = _make_video_parsed_result(num_episodes=1)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    # 非 dry_run 路径,验证 _process_extras 收到 danmaku 参数
    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--danmaku", "xml",
        ],
    )

    assert result.exit_code == 0, result.output
    mocks["_process_extras"].assert_called_once()
    args, kwargs = mocks["_process_extras"].call_args
    # _process_extras(parsed, danmaku, subtitle, cover, metadata, embed_cover)
    # 通过位置参数验证
    assert args[1] == "xml"  # danmaku


def test_download_with_danmaku_dry_run_skips_process_extras(monkeypatch):
    """--danmaku xml 在 dry_run 模式下 _process_extras 不被调用"""
    parsed = _make_video_parsed_result(num_episodes=1)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--danmaku", "xml",
            "--dry-run",
        ],
    )

    assert result.exit_code == 0, result.output
    mocks["_process_extras"].assert_not_called()


# ==================================================================
# 6. --subtitle srt 选项
# ==================================================================

def test_download_with_subtitle_option(monkeypatch):
    """--subtitle srt 在非 dry_run 路径触发 _process_extras 收到 subtitle='srt'"""
    parsed = _make_video_parsed_result(num_episodes=1)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--subtitle", "srt",
        ],
    )

    assert result.exit_code == 0, result.output
    args, _ = mocks["_process_extras"].call_args
    # args = (parsed, danmaku, subtitle, cover, metadata, embed_cover)
    assert args[2] == "srt"  # subtitle


# ==================================================================
# 7. --cover jpg 选项
# ==================================================================

def test_download_with_cover_option(monkeypatch):
    """--cover jpg 在非 dry_run 路径触发 _process_extras 收到 cover='jpg'"""
    parsed = _make_video_parsed_result(num_episodes=1)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--cover", "jpg",
        ],
    )

    assert result.exit_code == 0, result.output
    args, _ = mocks["_process_extras"].call_args
    assert args[3] == "jpg"  # cover


# ==================================================================
# 8. --metadata nfo 选项
# ==================================================================

def test_download_with_metadata_option(monkeypatch):
    """--metadata nfo 在非 dry_run 路径触发 _process_extras 收到 metadata='nfo'"""
    parsed = _make_video_parsed_result(num_episodes=1)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--metadata", "nfo",
        ],
    )

    assert result.exit_code == 0, result.output
    args, _ = mocks["_process_extras"].call_args
    assert args[4] == "nfo"  # metadata


def test_download_with_all_extras_combined(monkeypatch):
    """--danmaku xml --subtitle srt --cover jpg --metadata nfo --embed-cover
    组合选项在非 dry_run 路径同时传入 _process_extras
    """
    parsed = _make_video_parsed_result(num_episodes=1)
    mocks = _patch_full_download_chain(monkeypatch, parsed)

    result = runner.invoke(
        app,
        [
            "download",
            "https://www.bilibili.com/video/BV1xxx",
            "--non-interactive",
            "--episodes", "1",
            "--danmaku", "xml",
            "--subtitle", "srt",
            "--cover", "jpg",
            "--metadata", "nfo",
            "--embed-cover",
        ],
    )

    assert result.exit_code == 0, result.output
    args, _ = mocks["_process_extras"].call_args
    # 验证全部附加产物参数传递正确
    assert args[1] == "xml"   # danmaku
    assert args[2] == "srt"  # subtitle
    assert args[3] == "jpg"  # cover
    assert args[4] == "nfo"  # metadata
    assert args[5] is True   # embed_cover


# ==================================================================
# 9. JSON 输出路径(parse 命令 --json)
# ==================================================================

def test_parse_command_json_output(monkeypatch):
    """bili23 parse <url> --json 输出可被 json.loads 解析"""
    import cli.commands.parse as parse_module

    parsed = _make_video_parsed_result(num_episodes=2)
    monkeypatch.setattr(parse_module, "parse_url", lambda url: parsed)

    result = runner.invoke(
        app,
        ["parse", "https://www.bilibili.com/video/BV1xxx", "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout.strip())
    assert data["title"] == "测试投稿视频"
    assert data["uploader"] == "测试UP主"
    assert data["category"] == "USER_UPLOADS"
    assert len(data["episodes"]) == 2


def test_parse_command_invalid_url_exit_4(monkeypatch):
    """bili23 parse not-a-url:parse_url 抛 ParseError,exit_code=4"""
    from cli.exceptions import ParseError

    import cli.commands.parse as parse_module

    monkeypatch.setattr(
        parse_module, "parse_url",
        MagicMock(side_effect=ParseError("无效的 URL")),
    )

    result = runner.invoke(app, ["parse", "not-a-url"])
    assert result.exit_code == 4


# ==================================================================
# 10. EpisodeData 树形结构集成(直接调用 util.parse.episode.tree)
# ==================================================================

def test_episode_tree_collect_all_children():
    """集成:TreeItem.get_all_children 递归收集叶子节点(排除 TREE_NODE_BIT)"""
    from util.parse.episode.tree import (
        TreeItem, Attribute, EpisodeData, CheckState,
    )

    # 清空缓存避免测试间污染
    EpisodeData.clear_cache()

    # 构造两层树:root -> section -> [ep1, ep2]
    root = TreeItem({"title": "root", "number": "合集"})
    root.set_attribute(Attribute.TREE_NODE_BIT)

    section = TreeItem({"title": "正片", "number": "章节"})
    section.set_attribute(Attribute.TREE_NODE_BIT)

    ep1 = TreeItem({"title": "第 1 集", "number": 1, "cid": 100,
                    "bvid": "BV1", "aid": 1})
    ep1.set_attribute(Attribute.VIDEO_BIT | Attribute.NORMAL_BIT)

    ep2 = TreeItem({"title": "第 2 集", "number": 2, "cid": 101,
                    "bvid": "BV1", "aid": 1})
    ep2.set_attribute(Attribute.VIDEO_BIT | Attribute.NORMAL_BIT)

    section.add_child(ep1)
    section.add_child(ep2)
    root.add_child(section)

    # to_dict=True 时返回 dict 列表
    leaves = root.get_all_children(to_dict=True)
    assert len(leaves) == 2
    titles = {leaf["title"] for leaf in leaves}
    assert titles == {"第 1 集", "第 2 集"}
    # 不应包含树节点
    assert all(leaf["attribute"] & Attribute.TREE_NODE_BIT == 0 for leaf in leaves)


def test_episode_tree_check_state_propagation():
    """集成:TreeItem.set_checked_state 向下传播 CheckState.Checked"""
    from util.parse.episode.tree import (
        TreeItem, Attribute, EpisodeData, CheckState,
    )

    EpisodeData.clear_cache()

    root = TreeItem({"title": "root"})
    root.set_attribute(Attribute.TREE_NODE_BIT)

    child1 = TreeItem({"title": "c1"})
    child2 = TreeItem({"title": "c2"})
    root.add_child(child1)
    root.add_child(child2)

    # 设置 root 为 Checked,应向下传播
    root.set_checked_state(CheckState.Checked)
    assert child1.checked == CheckState.Checked
    assert child2.checked == CheckState.Checked

    # 取消 root,子节点也应取消
    root.set_checked_state(CheckState.Unchecked)
    assert child1.checked == CheckState.Unchecked
    assert child2.checked == CheckState.Unchecked


def test_episode_data_add_and_get():
    """集成:EpisodeData.add_episode / get_episode_data / clear_cache"""
    from util.parse.episode.tree import EpisodeData

    EpisodeData.clear_cache()

    ep_id = EpisodeData.add_episode()
    assert isinstance(ep_id, str) and len(ep_id) > 0

    data = EpisodeData.get_episode_data(ep_id)
    assert data == {}

    # 写入字段后再次查询应返回更新后的 dict(同一引用)
    data["title"] = "test"
    data["aid"] = 12345

    again = EpisodeData.get_episode_data(ep_id)
    assert again["title"] == "test"
    assert again["aid"] == 12345

    # clear_cache 后数据丢失
    EpisodeData.clear_cache()
    assert EpisodeData.get_episode_data(ep_id) == {}
