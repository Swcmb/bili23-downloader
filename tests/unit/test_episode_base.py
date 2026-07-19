# tests/unit/test_episode_base.py
"""EpisodeParserBase 单元测试

覆盖 src/util/parse/episode/base.py:
- __init__ 默认字段
- get_display_number 优先 target_number
- update_episode_list 在不同模式下的行为
- get_episode_duration 三种字段提取(duration/arc/length)
- _init_episode_data 创建并填充全局 EpisodeData 表
- _video_episode_data_parser 填充 description/tid/uploader 等
"""
import pytest

from util.parse.episode.base import EpisodeParserBase
from util.parse.episode.tree import EpisodeData


# ==================================================================
# 公共夹具
# ==================================================================

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
# __init__ 默认值
# ==================================================================

def test_init_defaults():
    """EpisodeParserBase.__init__ 设置默认字段"""
    parser = EpisodeParserBase()
    assert parser.episode_id == ""
    assert parser.category_name == ""
    assert parser.info_data == {}
    assert parser.target_episode_info is None
    assert parser.target_episode_data_id is None
    assert parser.target_attribute is None
    assert parser.target_number is None
    assert parser.episode_count == 0


def test_init_with_kwargs():
    """EpisodeParserBase.__init__ 接受 kwargs 设置 target_*"""
    parser = EpisodeParserBase(
        target_episode_info="BV1xx",
        target_episode_data_id="data-id",
        target_attribute=1,
        target_number=5,
    )
    assert parser.target_episode_info == "BV1xx"
    assert parser.target_episode_data_id == "data-id"
    assert parser.target_attribute == 1
    assert parser.target_number == 5


# ==================================================================
# get_display_number
# ==================================================================

def test_get_display_number_returns_target_when_set():
    """get_display_number 在 target_number 设置时返回 target_number"""
    parser = EpisodeParserBase(target_number=42)
    assert parser.get_display_number(1) == 42


def test_get_display_number_returns_default_when_target_empty_string():
    """get_display_number 在 target_number='' 时返回默认值"""
    parser = EpisodeParserBase(target_number="")
    assert parser.get_display_number(7) == 7


def test_get_display_number_returns_default_when_target_none():
    """get_display_number 在 target_number=None 时返回默认值"""
    parser = EpisodeParserBase(target_number=None)
    assert parser.get_display_number(3) == 3


# ==================================================================
# get_episode_duration
# ==================================================================

def test_get_episode_duration_from_duration_field():
    """get_episode_duration 优先使用 duration 字段"""
    parser = EpisodeParserBase()
    assert parser.get_episode_duration({"duration": 120}) == 120


def test_get_episode_duration_from_arc_duration():
    """get_episode_duration 在无 duration 时使用 arc.duration"""
    parser = EpisodeParserBase()
    assert parser.get_episode_duration({"arc": {"duration": 90}}) == 90


def test_get_episode_duration_from_length_via_units(monkeypatch):
    """get_episode_duration 在仅有 length 时通过 Units.unformat_episode_duration"""
    from util.format.units import Units
    parser = EpisodeParserBase()

    # monkeypatch Units.unformat_episode_duration 避免依赖具体格式
    monkeypatch.setattr(
        Units, "unformat_episode_duration",
        staticmethod(lambda s: 100),
    )
    assert parser.get_episode_duration({"length": "01:40"}) == 100


def test_get_episode_duration_returns_zero_when_no_field():
    """get_episode_duration 在无任何字段时返回 0"""
    parser = EpisodeParserBase()
    assert parser.get_episode_duration({}) == 0


# ==================================================================
# _init_episode_data
# ==================================================================

def test_init_episode_data_creates_new_id_when_absent():
    """_init_episode_data 在 episode_id 为空时创建新 ID"""
    parser = EpisodeParserBase()
    assert parser.episode_id == ""
    data = parser._init_episode_data()
    assert parser.episode_id != ""  # 已创建
    assert data == {}


def test_init_episode_data_returns_existing_data_when_id_set():
    """_init_episode_data 在 episode_id 已设置时返回对应数据"""
    parser = EpisodeParserBase()
    parser.episode_id = EpisodeData.add_episode()
    EpisodeData.get_episode_data(parser.episode_id)["title"] = "preset"
    data = parser._init_episode_data()
    assert data["title"] == "preset"


# ==================================================================
# update_episode_list
# ==================================================================

def test_update_episode_list_with_title(monkeypatch):
    """update_episode_list 在 node.title 存在时使用之"""
    from util.parse.episode.tree import TreeItem
    parser = EpisodeParserBase()
    parser.category_name = "TEST"  # category_name 不在 __init__ kwargs 中,需手动设
    node = TreeItem({"title": "节目标题"})

    emit_calls = []
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: emit_calls.append((a, kw)),
    )
    parser.update_episode_list(node, ("cid", 100))
    assert len(emit_calls) == 1
    # 第一个参数是 title
    assert emit_calls[0][0][0] == "节目标题"
    assert emit_calls[0][0][1] == "TEST"
    # 第三个参数是 root_node(包了一层)
    assert emit_calls[0][0][2].child(0) is node
    # 第四个参数是 current_episode_data
    assert emit_calls[0][0][3] == ("cid", 100)


def test_update_episode_list_passes_none_in_manual_mode(monkeypatch):
    """update_episode_list 在 MANUAL 模式下 current_episode_data 传 None"""
    from util.common.enum import AutoSelectMode
    from util.parse.episode.tree import TreeItem
    parser = EpisodeParserBase()
    parser.category_name = "TEST"
    node = TreeItem({"title": "x"})

    monkeypatch.setattr(
        "util.common.config.config.get",
        lambda key, default=None: AutoSelectMode.MANUAL
        if key == "auto_select_mode"
        else default,
    )
    emit_calls = []
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: emit_calls.append((a, kw)),
    )
    parser.update_episode_list(node, ("cid", 100))
    # MANUAL 模式下 current_episode_data 应为 None
    assert emit_calls[0][0][3] is None


def test_update_episode_list_uses_child_title_when_node_title_empty(monkeypatch):
    """update_episode_list 在 node.title 为空时使用 child 的 title(VIDEO_BIT/AUDIO_BIT)"""
    from util.parse.episode.tree import TreeItem, Attribute
    parser = EpisodeParserBase()
    parser.category_name = "TEST"

    # 构造一个无 title 的 node,带 VIDEO_BIT 子节点
    node = TreeItem({"title": ""})
    leaf = TreeItem({"title": "leaf-title"})
    leaf.set_attribute(Attribute.VIDEO_BIT)
    node.add_child(leaf)

    emit_calls = []
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: emit_calls.append((a, kw)),
    )
    parser.update_episode_list(node)
    # title 应来自 leaf
    assert emit_calls[0][0][0] == "leaf-title"


def test_update_episode_list_uses_number_for_history_bit(monkeypatch):
    """update_episode_list 在节点为 HISTORY_BIT/WATCH_LATER_BIT 时使用 number"""
    from util.parse.episode.tree import TreeItem, Attribute
    parser = EpisodeParserBase()
    parser.category_name = "TEST"

    node = TreeItem({"title": "", "number": 5})
    leaf = TreeItem({"title": "leaf", "number": 5})
    leaf.set_attribute(Attribute.HISTORY_BIT)
    node.add_child(leaf)

    emit_calls = []
    monkeypatch.setattr(
        "util.common.signal_bus.signal_bus.parse.update_parse_list.emit",
        lambda *a, **kw: emit_calls.append((a, kw)),
    )
    parser.update_episode_list(node)
    # title 应来自 number 字段
    assert emit_calls[0][0][0] == 5


# ==================================================================
# _video_episode_data_parser
# ==================================================================

def test_video_episode_data_parser_fills_fields():
    """_video_episode_data_parser 填充 description/tid/uploader 等"""
    from util.parse.episode.base import EpisodeParserBase
    parser = EpisodeParserBase()
    parser.info_data = {
        "desc": "video desc",
        "tid": 7,
        "tid_v2": 8,
        "owner": {"name": "uploader", "mid": 111, "face": "face.jpg"},
    }
    parser._video_episode_data_parser()

    data = EpisodeData.get_episode_data(parser.episode_id)
    assert data["description"] == "video desc"
    assert data["tid"] == 7
    assert data["tid_v2"] == 8
    assert data["uploader"] == "uploader"
    assert data["uploader_uid"] == 111
    assert data["uploader_face"] == "face.jpg"


def test_video_episode_data_parser_with_target_episode_data_id():
    """_video_episode_data_parser 在 target_episode_data_id 设置时合并已有数据"""
    target_id = EpisodeData.add_episode()
    EpisodeData.get_episode_data(target_id)["custom"] = "preserved"

    parser = EpisodeParserBase(target_episode_data_id=target_id)
    parser.info_data = {
        "desc": "", "tid": 0, "tid_v2": 0,
        "owner": {"name": "x", "mid": 0, "face": ""},
    }
    parser._video_episode_data_parser()
    data = EpisodeData.get_episode_data(parser.episode_id)
    assert data["custom"] == "preserved"
    assert data["description"] == ""
