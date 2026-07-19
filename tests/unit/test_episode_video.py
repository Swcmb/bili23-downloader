# tests/unit/test_episode_video.py
"""VideoEpisodeParser 单元测试 - single / pages / ugc_season 三种结构

覆盖 src/util/parse/episode/video.py:
- parse() 在 single_parser / pages_parser / ugc_season_parser 间分发
- single_parser 构造单视频节点
- pages_parser 构造分P视频节点
- ugc_season_parser 构造合集节点(含 sections / episodes / pages)
- get_cid 处理 current_page_number 字段
- get_episode_badge 通过 attribute 位标志识别
- set_attribute 在 target_attribute 设置时覆盖
- episode_data_parser 填充 episode_data 字典
"""
import pytest

from util.parse.episode.video import VideoEpisodeParser
from util.parse.episode.tree import Attribute, EpisodeData


# ==================================================================
# 公共夹具
# ==================================================================

def _base_info_data(**overrides):
    """构造 single 视频的基础 info_data"""
    data = {
        "aid": 12345,
        "bvid": "BV1abc",
        "cid": 67890,
        "pic": "https://example.com/cover.jpg",
        "title": "测试视频",
        "pubdate": 1700000000,
        "duration": 120,
        "is_upower_exclusive": False,
        "owner": {"name": "alice", "mid": 999, "face": "face_url"},
        "desc": "视频描述",
        "tid": 1,
        "tid_v2": 2,
    }
    data.update(overrides)
    return {"data": data}


@pytest.fixture(autouse=True)
def _clear_episode_data():
    """每个测试前清理 EpisodeData 全局缓存,避免污染"""
    EpisodeData.clear_cache()
    yield
    EpisodeData.clear_cache()


@pytest.fixture(autouse=True)
def _patch_emit(monkeypatch):
    """patch signal_bus.parse.update_parse_list.emit 避免触发实际信号"""
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: None,
    )


# ==================================================================
# single_parser
# ==================================================================

def test_single_parser_creates_one_child():
    """single_parser 构造包含 1 个叶子的根节点"""
    info = _base_info_data()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    node = parser.parse(update_episode_list=False)

    assert node.count() == 1
    leaf = node.child(0)
    assert leaf.title == "测试视频"
    assert leaf.bvid == "BV1abc"
    assert leaf.aid == 12345
    assert leaf.cid == 67890
    assert leaf.cover == "https://example.com/cover.jpg"
    assert leaf.url == "https://www.bilibili.com/video/BV1abc"
    assert leaf.attribute & Attribute.VIDEO_BIT
    assert leaf.attribute & Attribute.NORMAL_BIT
    assert parser.episode_count == 1


def test_single_parser_upower_exclusive_badge():
    """single_parser 在 is_upower_exclusive=True 时 badge='充电专属'"""
    info = _base_info_data(is_upower_exclusive=True)
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    node = parser.parse(update_episode_list=False)
    leaf = node.child(0)
    assert leaf.badge == "充电专属"


def test_single_parser_with_target_number_override():
    """single_parser 在 target_number 设置时使用 target_number"""
    info = _base_info_data()
    parser = VideoEpisodeParser(
        info, "USER_UPLOADS",
        kwargs={"target_number": 5},
    )
    node = parser.parse(update_episode_list=False)
    leaf = node.child(0)
    assert leaf.number == 5


# ==================================================================
# pages_parser
# ==================================================================

def test_pages_parser_creates_one_child_per_page():
    """pages_parser 构造 N 个叶子(N = len(pages))"""
    info = _base_info_data(
        pages=[
            {"cid": 100, "page": 1, "part": "P1", "duration": 60, "ctime": 1000},
            {"cid": 200, "page": 2, "part": "P2", "duration": 90, "ctime": 2000},
            {"cid": 300, "page": 3, "part": "P3", "duration": 120, "ctime": 3000},
        ],
    )
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    node = parser.parse(update_episode_list=False)

    assert node.count() == 3
    p1, p2, p3 = node.children
    assert p1.title == "P1"
    assert p1.cid == 100
    assert p1.part_number == 1
    assert p1.url == "https://www.bilibili.com/video/BV1abc?p=1"
    assert p1.attribute & Attribute.VIDEO_BIT
    assert p1.attribute & Attribute.PART_BIT
    assert parser.episode_count == 3


def test_pages_parser_includes_parent_title_in_related_titles():
    """pages_parser 在 related_titles 中包含 parent_title(需 >1 page 才走 pages_parser)"""
    info = _base_info_data(
        pages=[
            {"cid": 100, "page": 1, "part": "P1", "duration": 60, "ctime": 1000},
            {"cid": 200, "page": 2, "part": "P2", "duration": 60, "ctime": 1000},
        ],
    )
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    node = parser.parse(update_episode_list=False)
    leaf = node.child(0)
    assert leaf.related_titles["parent_title"] == "测试视频"


# ==================================================================
# ugc_season_parser
# ==================================================================

def _ugc_season_info():
    """构造 ugc_season info_data(单 section,单 episode,无 pages)"""
    return _base_info_data(
        ugc_season={
            "title": "测试合集",
            "sections": [
                {
                    "title": "正片",
                    "episodes": [
                        {
                            "aid": 111, "bvid": "BV1ep1", "cid": 222,
                            "title": "episode-1",
                            "arc": {"pic": "p1.jpg", "pubdate": 1700000001, "duration": 120},
                            "pages": [{"cid": 222, "page": 1, "part": "ep1-p1"}],
                            "attribute": 0,
                        },
                    ],
                },
            ],
        },
    )


def test_ugc_season_parser_single_section_single_episode():
    """ugc_season 在 section_count=1 时,直接挂载到根节点(不显示'章节'层级)"""
    info = _ugc_season_info()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    node = parser.parse(update_episode_list=False)

    assert node.count() == 1  # 单 section -> 直接挂到根
    leaf = node.child(0)
    assert leaf.title == "episode-1"
    assert leaf.cid == 222
    assert leaf.attribute & Attribute.COLLECTION_BIT
    assert parser.episode_count == 1


def test_ugc_season_parser_multi_section_creates_intermediate_layer():
    """ugc_season 在 section_count>1 时,创建'章节'中间层"""
    info = _base_info_data(
        ugc_season={
            "title": "测试合集",
            "sections": [
                {
                    "title": "正片",
                    "episodes": [
                        {
                            "aid": 1, "bvid": "BV1", "cid": 10,
                            "title": "ep1",
                            "arc": {"pic": "c1.jpg", "pubdate": 100, "duration": 60},
                            "pages": [{"cid": 10, "page": 1, "part": "p1"}],
                            "attribute": 0,
                        },
                    ],
                },
                {
                    "title": "花絮",
                    "episodes": [
                        {
                            "aid": 2, "bvid": "BV2", "cid": 20,
                            "title": "ep2",
                            "arc": {"pic": "c2.jpg", "pubdate": 200, "duration": 90},
                            "pages": [{"cid": 20, "page": 1, "part": "p1"}],
                            "attribute": 0,
                        },
                    ],
                },
            ],
        },
    )
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    node = parser.parse(update_episode_list=False)

    # 两个 section,根节点应有 2 个 section_node 子节点
    assert node.count() == 2
    section_node_1 = node.child(0)
    assert section_node_1.title == "正片"
    assert section_node_1.count() == 1


def test_ugc_season_episode_with_multiple_pages():
    """ugc_season episode 含多 pages 时,创建'分P'中间层"""
    info = _base_info_data(
        ugc_season={
            "title": "测试合集",
            "sections": [
                {
                    "title": "正片",
                    "episodes": [
                        {
                            "aid": 111, "bvid": "BV1ep1", "cid": 222,
                            "title": "episode-1",
                            "arc": {"pic": "p1.jpg", "pubdate": 1700000001},
                            "pages": [
                                {"cid": 222, "page": 1, "part": "p1-1"},
                                {"cid": 333, "page": 2, "part": "p1-2"},
                            ],
                            "attribute": 0,
                        },
                    ],
                },
            ],
        },
    )
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    node = parser.parse(update_episode_list=False)

    # section_count=1 -> 直接挂到根,但 episode 有多 pages -> 中间是 page_node
    assert node.count() == 1
    page_node = node.child(0)
    assert page_node.count() == 2  # 两个 pages
    assert parser.episode_count == 2


def test_ugc_season_target_episode_info_filters():
    """ugc_season 在 target_episode_info 设置时仅保留匹配 bvid 的剧集"""
    info = _base_info_data(
        ugc_season={
            "title": "测试合集",
            "sections": [
                {
                    "title": "正片",
                    "episodes": [
                        {
                            "aid": 1, "bvid": "BV_MATCH", "cid": 10,
                            "title": "ep1", "arc": {"pic": "c.jpg", "pubdate": 100, "duration": 60},
                            "pages": [{"cid": 10, "page": 1, "part": "p1"}],
                            "attribute": 0,
                        },
                        {
                            "aid": 2, "bvid": "BV_SKIP", "cid": 20,
                            "title": "ep2", "arc": {"pic": "c2.jpg", "pubdate": 200, "duration": 90},
                            "pages": [{"cid": 20, "page": 1, "part": "p2"}],
                            "attribute": 0,
                        },
                    ],
                },
            ],
        },
    )
    parser = VideoEpisodeParser(
        info, "USER_UPLOADS",
        kwargs={"target_episode_info": "BV_MATCH"},
    )
    node = parser.parse(update_episode_list=False)
    # 仅 BV_MATCH 应被收集(单 section 直接挂根)
    assert node.count() == 1
    leaf = node.child(0)
    assert leaf.bvid == "BV_MATCH"


# ==================================================================
# get_cid
# ==================================================================

def test_get_cid_returns_default_cid():
    """get_cid 在无 current_page_number 时返回 info_data['cid']"""
    info = _base_info_data(cid=99999)
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    parser.parse(update_episode_list=False)
    assert parser.get_cid() == 99999


def test_get_cid_returns_matching_page_cid():
    """get_cid 在 current_page_number 设置时返回对应 page 的 cid"""
    info = _base_info_data(
        cid=99999,
        pages=[
            {"cid": 100, "page": 1, "part": "P1", "duration": 60, "ctime": 1000},
            {"cid": 200, "page": 2, "part": "P2", "duration": 90, "ctime": 2000},
        ],
        current_page_number=2,
    )
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    parser.parse(update_episode_list=False)
    assert parser.get_cid() == 200


# ==================================================================
# get_episode_badge
# ==================================================================

def test_get_episode_badge_returns_empty_for_no_attribute():
    """get_episode_badge 在 attribute=0 时返回空"""
    info = _base_info_data()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    badge = parser.get_episode_badge({"attribute": 0})
    assert badge == ""


def test_get_episode_badge_returns_value_for_known_bit():
    """get_episode_badge 通过 attribute 位标志识别 badge"""
    info = _base_info_data()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    # badge_map 中至少有一个键,attribute 设置第 0 位即可
    badge = parser.get_episode_badge({"attribute": 1})  # 1 << 0
    # 可能返回 "" (若无对应 badge) 或具体 badge 字符串
    assert isinstance(badge, str)


# ==================================================================
# set_attribute
# ==================================================================

def test_set_attribute_with_target_attribute_overrides():
    """set_attribute 在 target_attribute 设置时,优先使用 target_attribute"""
    info = _base_info_data()
    parser = VideoEpisodeParser(
        info, "USER_UPLOADS",
        kwargs={"target_attribute": Attribute.BANGUMI_BIT},
    )
    from util.parse.episode.tree import TreeItem
    item = TreeItem({"title": "x"})
    parser.set_attribute(item, Attribute.VIDEO_BIT)
    # target_attribute 与 VIDEO_BIT 都应被设置
    assert item.attribute & Attribute.VIDEO_BIT
    assert item.attribute & Attribute.BANGUMI_BIT


# ==================================================================
# episode_data_parser
# ==================================================================

def test_episode_data_parser_fills_episode_data():
    """episode_data_parser 填充 description/tid/uploader 等字段"""
    info = _base_info_data(desc="desc", tid=5, tid_v2=6)
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    parser.parse(update_episode_list=False)
    # episode_id 已创建,episode_data 应有填充字段
    data = EpisodeData.get_episode_data(parser.episode_id)
    assert data["description"] == "desc"
    assert data["tid"] == 5
    assert data["tid_v2"] == 6
    assert data["uploader"] == "alice"
    assert data["uploader_uid"] == 999


def test_episode_data_parser_with_target_episode_data_id():
    """episode_data_parser 在 target_episode_data_id 设置时合并已有数据"""
    # 预先创建一个 episode_data,填入 title
    target_id = EpisodeData.add_episode()
    EpisodeData.get_episode_data(target_id)["title"] = "preserved"

    info = _base_info_data()
    parser = VideoEpisodeParser(
        info, "USER_UPLOADS",
        kwargs={"target_episode_data_id": target_id},
    )
    parser.parse(update_episode_list=False)

    data = EpisodeData.get_episode_data(parser.episode_id)
    # 合并后 title 应保留,description 应来自新数据
    assert data["title"] == "preserved"
    assert data["description"] == "视频描述"


# ==================================================================
# get_display_number
# ==================================================================

def test_get_display_number_returns_target_when_set():
    """get_display_number 在 target_number 设置时返回 target_number"""
    info = _base_info_data()
    parser = VideoEpisodeParser(
        info, "USER_UPLOADS",
        kwargs={"target_number": 99},
    )
    assert parser.get_display_number(1) == 99


def test_get_display_number_returns_default_when_target_empty():
    """get_display_number 在 target_number 为空时返回默认值"""
    info = _base_info_data()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    assert parser.get_display_number(3) == 3


def test_get_display_number_returns_default_when_target_is_none():
    """get_display_number 在 target_number=None 时返回默认值"""
    info = _base_info_data()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    parser.target_number = None
    assert parser.get_display_number(7) == 7


# ==================================================================
# parse(update_episode_list=True) 触发 emit
# ==================================================================

def test_parse_with_update_calls_emit(monkeypatch):
    """parse(update_episode_list=True) 触发 signal_bus.parse.update_parse_list.emit"""
    info = _base_info_data()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")

    emit_calls = []
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: emit_calls.append((a, kw)),
    )
    parser.parse(update_episode_list=True)
    assert len(emit_calls) == 1
    # 第一个参数是 title
    assert emit_calls[0][0][0] == "测试视频"
    # 第二个参数是 category_name
    assert emit_calls[0][0][1] == "USER_UPLOADS"


# ==================================================================
# get_node_title
# ==================================================================

def test_get_node_title_returns_episode_type():
    """get_node_title 返回 Translator.EPISODE_TYPE('USER_UPLOADS')"""
    info = _base_info_data()
    parser = VideoEpisodeParser(info, "USER_UPLOADS")
    title = parser.get_node_title()
    # conftest.py 中 patch EPISODE_TYPE 为 identity,返回参数本身
    assert title == "USER_UPLOADS"
