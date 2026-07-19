# tests/unit/test_episode_cheese.py
"""CheeseEpisodeParser 单元测试

覆盖 src/util/parse/episode/cheese.py:
- parse() 触发 episode_data_parser + sections_parser
- sections_parser 构造 cheese section/episode 树
- get_episode_badge 通过 label 字段或 status 返回
- get_premiered 正则提取 release_date
- get_ep_id 优先 current_ep_id,回退第一个 episode.id
"""
import pytest

from util.parse.episode.cheese import CheeseEpisodeParser
from util.parse.episode.tree import Attribute, EpisodeData


# ==================================================================
# 公共夹具
# ==================================================================

def _cheese_info(**overrides):
    """构造 cheese 课程 info_data"""
    data = {
        "title": "测试课程",
        "subtitle": "课程描述",
        "cover": "cover.jpg",
        "season_id": 500,
        "up_info": {"uname": "讲师", "mid": 888, "avatar": "avatar.jpg"},
        "sections": [
            {
                "title": "第一章",
                "episodes": [
                    {
                        "aid": 1, "cid": 100, "id": 5001,
                        "title": "lesson-1", "cover": "ep1.jpg",
                        "duration": 600, "release_date": 1700000000,
                        "play_way_subtitle": "playway", "subtitle": "ep1 subtitle",
                        "status": 1,
                    },
                    {
                        "aid": 2, "cid": 200, "id": 5002,
                        "title": "lesson-2", "cover": "ep2.jpg",
                        "duration": 900, "release_date": 1700100000,
                        "play_way_subtitle": "playway", "subtitle": "ep2 subtitle",
                        "status": 2,
                    },
                ],
            },
        ],
    }
    data.update(overrides)
    return {"data": data}


@pytest.fixture(autouse=True)
def _clear_episode_data():
    EpisodeData.clear_cache()
    yield
    EpisodeData.clear_cache()


@pytest.fixture(autouse=True)
def _patch_emit(monkeypatch):
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: None,
    )


# ==================================================================
# sections_parser
# ==================================================================

def test_parse_creates_section_with_two_episodes():
    """parse 后根节点含 1 个 section,2 个 episode"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    node = parser.parse(update_episode_list=False)

    assert node.count() == 1
    section = node.child(0)
    assert section.title == "第一章"
    assert section.count() == 2
    ep1 = section.child(0)
    assert ep1.cid == 100
    assert ep1.ep_id == 5001
    assert ep1.attribute & Attribute.CHEESE_BIT
    assert ep1.url == "https://www.bilibili.com/cheese/play/5001"


def test_parse_skips_empty_section():
    """sections_parser 在 section.episodes 为空时跳过该 section"""
    info = _cheese_info(
        sections=[
            {"title": "empty", "episodes": []},
            {
                "title": "正片",
                "episodes": [
                    {
                        "aid": 1, "cid": 100, "id": 5001,
                        "title": "ep1", "cover": "c.jpg",
                        "duration": 60, "release_date": 1700000000,
                        "play_way_subtitle": "p", "subtitle": "s", "status": 1,
                    },
                ],
            },
        ],
    )
    parser = CheeseEpisodeParser(info, "COURSE")
    node = parser.parse(update_episode_list=False)
    # 仅非空 section 应被收集
    assert node.count() == 1
    assert node.child(0).title == "正片"


def test_target_attribute_applied_to_episodes():
    """target_attribute 设置时,episode 额外加该 attribute"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(
        info, "COURSE",
        kwargs={"target_attribute": Attribute.VIDEO_BIT},
    )
    node = parser.parse(update_episode_list=False)
    section = node.child(0)
    ep1 = section.child(0)
    # CHEESE_BIT + target_attribute (VIDEO_BIT)
    assert ep1.attribute & Attribute.CHEESE_BIT
    assert ep1.attribute & Attribute.VIDEO_BIT


# ==================================================================
# episode_data_parser
# ==================================================================

def test_episode_data_parser_fills_fields():
    """episode_data_parser 填充 poster/description/season_id/uploader"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    parser.parse(update_episode_list=False)
    data = EpisodeData.get_episode_data(parser.episode_id)
    assert data["poster"] == "cover.jpg"
    assert data["description"] == "课程描述"
    assert data["styles"] == ["Bilibili 课堂"]
    assert data["premiered"] > 0
    assert data["season_id"] == 500
    assert data["uploader"] == "讲师"
    assert data["uploader_uid"] == 888
    assert data["uploader_face"] == "avatar.jpg"


# ==================================================================
# get_episode_badge
# ==================================================================

def test_get_episode_badge_prefers_label():
    """get_episode_badge 在有 label 字段时返回 label"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    badge = parser.get_episode_badge({"label": "VIP限定", "status": 1})
    assert badge == "VIP限定"


def test_get_episode_badge_status_one_returns_试看():
    """get_episode_badge 在 status=1 时返回 '全集试看'"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    badge = parser.get_episode_badge({"status": 1})
    assert badge == "全集试看"


def test_get_episode_badge_status_two_returns_付费():
    """get_episode_badge 在 status=2 时返回 '付费'"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    badge = parser.get_episode_badge({"status": 2})
    assert badge == "付费"


def test_get_episode_badge_status_three_returns_部分试看():
    """get_episode_badge 在 status=3 时返回 '部分试看'"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    badge = parser.get_episode_badge({"status": 3})
    assert badge == "部分试看"


def test_get_episode_badge_unknown_status_returns_none():
    """get_episode_badge 在 status 不在 1/2/3 时返回 None"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    badge = parser.get_episode_badge({"status": 99})
    assert badge is None


# ==================================================================
# get_premiered
# ==================================================================

def test_get_premiered_extracts_release_date():
    """get_premiered 从 info_data 中正则提取 release_date"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    premiered = parser.get_premiered()
    # 应返回 info_data 中第一个 release_date 字段的值
    assert premiered == 1700000000


def test_get_premiered_returns_zero_when_no_match():
    """get_premiered 在无 release_date 时返回 0"""
    info = _cheese_info()
    # 移除 release_date 字段
    for section in info["data"]["sections"]:
        for ep in section["episodes"]:
            ep.pop("release_date", None)
    parser = CheeseEpisodeParser(info, "COURSE")
    premiered = parser.get_premiered()
    assert premiered == 0


# ==================================================================
# get_ep_id
# ==================================================================

def test_get_ep_id_returns_current_ep_id_when_set():
    """get_ep_id 优先返回 current_ep_id"""
    info = _cheese_info(current_ep_id=7777)
    parser = CheeseEpisodeParser(info, "COURSE")
    parser.parse(update_episode_list=False)
    assert parser.get_ep_id() == 7777


def test_get_ep_id_returns_first_episode_id():
    """get_ep_id 在无 current_ep_id 时返回第一个 episode.id"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    parser.parse(update_episode_list=False)
    assert parser.get_ep_id() == 5001


def test_get_ep_id_returns_empty_when_no_episodes():
    """get_ep_id 在所有 section 都为空时返回空串"""
    info = _cheese_info(sections=[{"title": "empty", "episodes": []}])
    parser = CheeseEpisodeParser(info, "COURSE")
    parser.parse(update_episode_list=False)
    assert parser.get_ep_id() == ""


# ==================================================================
# parse(update_episode_list=True)
# ==================================================================

def test_parse_with_update_triggers_emit(monkeypatch):
    """parse(update_episode_list=True) 触发 emit"""
    info = _cheese_info()
    parser = CheeseEpisodeParser(info, "COURSE")
    emit_calls = []
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: emit_calls.append((a, kw)),
    )
    parser.parse(update_episode_list=True)
    assert len(emit_calls) == 1
    assert emit_calls[0][0][0] == "测试课程"
    assert emit_calls[0][0][1] == "COURSE"
