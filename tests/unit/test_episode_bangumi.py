# tests/unit/test_episode_bangumi.py
"""BangumiEpisodeParser 单元测试

覆盖 src/util/parse/episode/bangumi.py:
- parse() 触发 episode_data_parser + sections_parser
- sections_parser 构造 section_node -> episode 树
- update_info_data 过滤预告片、剔除 UP主陪你看
- episode_data_parser 填充 series_title/season_id 等
- determine_season_number 返回 season_id 在 seasons 中的索引+1
- get_bangumi_title 优先 show_title,回退 title
- get_ep_id 优先 current_ep_id,回退 episodes[0].ep_id
- target_episode_info 过滤逻辑
"""
import pytest

from util.parse.episode.bangumi import BangumiEpisodeParser
from util.parse.episode.tree import Attribute, EpisodeData


# ==================================================================
# 公共夹具
# ==================================================================

def _bangumi_info(**overrides):
    """构造 bangumi info_data"""
    data = {
        "season_title": "测试番剧",
        "season_id": 100,
        "media_id": 200,
        "series": {"series_title": "测试系列"},
        "seasons": [{"season_id": 100}, {"season_id": 101}],
        "publish": {"pub_time": "2024-01-01 12:00:00"},
        "evaluate": "番剧简介",
        "styles": ["日常"],
        "cover": "cover.jpg",
        "areas": [{"name": "日本"}, {"name": "中国"}],
        "episodes": [
            {
                "aid": 1, "bvid": "BV1", "cid": 10, "ep_id": 1000,
                "title": "第1话", "show_title": "第一话",
                "badge": "", "cover": "ep1.jpg",
                "duration": 1440000, "pub_time": 1700000000, "link": "https://ep1",
            },
            {
                "aid": 2, "bvid": "BV2", "cid": 20, "ep_id": 1001,
                "title": "第2话", "show_title": "第二话",
                "badge": "", "cover": "ep2.jpg",
                "duration": 1440000, "pub_time": 1700100000, "link": "https://ep2",
            },
        ],
        "section": [
            {
                "title": "预告",
                "episodes": [
                    {
                        "aid": 3, "bvid": "BV3", "cid": 30, "ep_id": 2000,
                        "title": "PV", "show_title": "预告片",
                        "badge": "预告", "cover": "pv.jpg",
                        "duration": 60000, "pub_time": 1699000000, "link": "https://pv",
                    },
                ],
            },
        ],
        "rating": {"score": 9.5, "count": 1000},
        "up_info": {"uname": "up_name", "mid": 999, "avatar": "avatar.jpg"},
    }
    data.update(overrides)
    return {"result": data}


@pytest.fixture(autouse=True)
def _clear_episode_data():
    """每个测试前清理 EpisodeData 全局缓存"""
    EpisodeData.clear_cache()
    yield
    EpisodeData.clear_cache()


@pytest.fixture(autouse=True)
def _patch_emit(monkeypatch):
    """patch signal_bus.parse.update_parse_list.emit"""
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: None,
    )


# ==================================================================
# sections_parser
# ==================================================================

def test_parse_creates_root_with_section_node():
    """parse 后根节点含 1 个 section_node(预告与正片分别成 section)"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    node = parser.parse(update_episode_list=False)
    # 正片 + 预告章节 = 2 sections
    assert node.count() == 2


def test_sections_parser_normal_episodes_in_first_section():
    """正片 section 含 2 个 episode(过滤'预告'后)"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    node = parser.parse(update_episode_list=False)
    # 第一个 section = 正片
    section = node.child(0)
    assert section.title == "正片"
    assert section.count() == 2


def test_sections_parser_episode_data_correct():
    """正片 episode 的 cid/title/url 正确"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    node = parser.parse(update_episode_list=False)
    section = node.child(0)
    ep1 = section.child(0)
    assert ep1.bvid == "BV1"
    assert ep1.cid == 10
    assert ep1.ep_id == 1000
    assert ep1.url == "https://ep1"
    assert ep1.attribute & Attribute.BANGUMI_BIT


def test_sections_parser_filters_preview_episodes():
    """正片中混杂的'预告'不影响 episode_number_map(仅正片分配序号)"""
    info = _bangumi_info(
        episodes=[
            {
                "aid": 1, "bvid": "BV1", "cid": 10, "ep_id": 1000,
                "title": "第1话", "show_title": "第一话",
                "badge": "", "cover": "ep1.jpg",
                "duration": 1440000, "pub_time": 1700000000, "link": "https://ep1",
            },
            {
                "aid": 99, "bvid": "BV99", "cid": 99, "ep_id": 9999,
                "title": "预告混入", "show_title": "预告",
                "badge": "预告", "cover": "pv.jpg",
                "duration": 60000, "pub_time": 1699000000, "link": "https://pv",
            },
            {
                "aid": 2, "bvid": "BV2", "cid": 20, "ep_id": 1001,
                "title": "第2话", "show_title": "第二话",
                "badge": "", "cover": "ep2.jpg",
                "duration": 1440000, "pub_time": 1700100000, "link": "https://ep2",
            },
        ],
    )
    parser = BangumiEpisodeParser(info, "BANGUMI")
    node = parser.parse(update_episode_list=False)
    section = node.child(0)
    # 预告 filter 仅作用于 episode_number_map,正片中仍包含 3 个 episode(含预告)
    assert section.count() == 3
    # episode_number_map 仅正片有,cid=10 -> 1, cid=20 -> 2, cid=99(预告)无
    assert parser.episode_number_map.get(10) == 1
    assert parser.episode_number_map.get(20) == 2
    assert 99 not in parser.episode_number_map


def test_sections_parser_filters_up_with_episodes():
    """'UP主陪你看'章节因无 bvid/cid 被剔除"""
    info = _bangumi_info(
        section=[
            {
                "title": "UP主陪你看",
                "episodes": [
                    {
                        "aid": 99, "cid": None, "ep_id": 9000,
                        "title": "陪你看", "show_title": "",
                        "badge": "", "cover": "",
                        "duration": 0, "pub_time": 0, "link": "",
                        # 注意:无 bvid 字段
                    },
                ],
            },
        ],
    )
    parser = BangumiEpisodeParser(info, "BANGUMI")
    node = parser.parse(update_episode_list=False)
    # 仅正片 section 应存在,UP主陪你看被剔除
    assert node.count() == 1
    assert node.child(0).title == "正片"


# ==================================================================
# target_episode_info 过滤
# ==================================================================

def test_target_episode_info_filters_episodes():
    """target_episode_info 设置时,仅匹配 ep_id 的剧集被收集"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(
        info, "BANGUMI",
        kwargs={"target_episode_info": 1001},
    )
    node = parser.parse(update_episode_list=False)
    section = node.child(0)
    # 仅 ep_id=1001 应被收集
    assert section.count() == 1
    assert section.child(0).ep_id == 1001


# ==================================================================
# episode_data_parser
# ==================================================================

def test_episode_data_parser_fills_fields():
    """episode_data_parser 填充 series_title/season_id/uploader 等"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    parser.parse(update_episode_list=False)

    data = EpisodeData.get_episode_data(parser.episode_id)
    assert data["series_title"] == "测试系列"
    assert data["season_id"] == 100
    assert data["media_id"] == 200
    assert data["premiered"] > 0
    assert data["description"] == "番剧简介"
    assert data["poster"] == "cover.jpg"
    assert data["actors"] == ""
    assert data["rating"] == 9.5
    assert data["rating_votes"] == 1000
    assert data["uploader"] == "up_name"
    assert data["uploader_uid"] == 999


def test_episode_data_parser_areas_extracted():
    """episode_data['areas'] 包含地区名称"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    parser.parse(update_episode_list=False)

    data = EpisodeData.get_episode_data(parser.episode_id)
    assert data["areas"] == ["日本", "中国"]


# ==================================================================
# determine_season_number
# ==================================================================

def test_determine_season_number_returns_index_plus_one():
    """determine_season_number 返回 season_id 在 seasons 中的索引+1"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    parser.parse(update_episode_list=False)
    # season_id=100,在 seasons[0] -> 索引 0+1=1
    assert parser.determine_season_number() == 1


def test_determine_season_number_returns_none_when_not_found():
    """determine_season_number 在 season_id 不在 seasons 中时返回 None"""
    info = _bangumi_info(season_id=999)
    parser = BangumiEpisodeParser(info, "BANGUMI")
    parser.parse(update_episode_list=False)
    assert parser.determine_season_number() is None


# ==================================================================
# get_bangumi_title
# ==================================================================

def test_get_bangumi_title_prefers_show_title():
    """get_bangumi_title 优先返回 show_title"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMUMI")
    title = parser.get_bangumi_title({
        "show_title": "show", "title": "fallback",
    })
    assert title == "show"


def test_get_bangumi_title_falls_back_to_title():
    """get_bangumi_title 在无 show_title 时回退到 title"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    title = parser.get_bangumi_title({"title": "fallback"})
    assert title == "fallback"


def test_get_bangumi_title_returns_empty_when_no_title():
    """get_bangumi_title 在无任何 title 时返回空字符串"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    title = parser.get_bangumi_title({})
    assert title == ""


# ==================================================================
# get_ep_id
# ==================================================================

def test_get_ep_id_returns_current_ep_id_when_set():
    """get_ep_id 优先返回 current_ep_id"""
    info = _bangumi_info(current_ep_id=555)
    parser = BangumiEpisodeParser(info, "BANGUMI")
    parser.parse(update_episode_list=False)
    assert parser.get_ep_id() == 555


def test_get_ep_id_returns_first_episode_ep_id():
    """get_ep_id 在无 current_ep_id 时返回第一个 episode 的 ep_id"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    parser.parse(update_episode_list=False)
    assert parser.get_ep_id() == 1000  # episodes[0].ep_id


# ==================================================================
# update_info_data
# ==================================================================

def test_update_info_data_creates_default_section():
    """update_info_data 在无 section 时,创建默认'正片'section"""
    info = _bangumi_info()
    info["result"].pop("section")
    parser = BangumiEpisodeParser(info, "BANGUMI")
    # __init__ 中已调用 update_info_data
    assert parser.info_data["sections"][0]["title"] == "正片"


def test_update_info_data_extends_with_existing_section():
    """update_info_data 在已有 section 时,追加到默认正片之后"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")
    sections = parser.info_data["sections"]
    assert len(sections) == 2  # 正片 + section 中的预告章节
    assert sections[0]["title"] == "正片"
    assert sections[1]["title"] == "预告"


# ==================================================================
# parse(update_episode_list=True)
# ==================================================================

def test_parse_with_update_triggers_emit(monkeypatch):
    """parse(update_episode_list=True) 触发 emit"""
    info = _bangumi_info()
    parser = BangumiEpisodeParser(info, "BANGUMI")

    emit_calls = []
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: emit_calls.append((a, kw)),
    )
    parser.parse(update_episode_list=True)
    assert len(emit_calls) == 1
    assert emit_calls[0][0][0] == "测试番剧"
    assert emit_calls[0][0][1] == "BANGUMI"
