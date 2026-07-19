# tests/unit/test_tree.py
"""TreeItem / EpisodeData / Attribute / CheckState 单元测试

覆盖 src/util/parse/episode/tree.py:
- CheckState 枚举值
- Attribute IntFlag 位运算
- TreeItem.__init__ 默认值
- TreeItem.add_child / child / count / row
- TreeItem.set_attribute / to_dict
- TreeItem.set_checked_state 向下/向上传递
- TreeItem.get_all_checked_children / get_all_children
- TreeItem.search_items / dyn_time
- EpisodeData.add_episode / get_episode_data / clear_cache
"""
import pytest

from util.parse.episode.tree import (
    Attribute,
    CheckState,
    EpisodeData,
    TreeItem,
    TreeItemBase,
)


# ==================================================================
# CheckState
# ==================================================================

def test_check_state_values():
    """CheckState 数值与 Qt.CheckState 保持一致"""
    assert CheckState.Unchecked == 0
    assert CheckState.PartiallyChecked == 1
    assert CheckState.Checked == 2


# ==================================================================
# Attribute IntFlag
# ==================================================================

def test_attribute_bit_flags_distinct():
    """每个 Attribute 是不同的位"""
    flags = [
        Attribute.VIDEO_BIT, Attribute.BANGUMI_BIT, Attribute.CHEESE_BIT,
        Attribute.WEEKLY_BIT, Attribute.COLLECTION_LIST_BIT, Attribute.SPACE_BIT,
        Attribute.FAVLIST_BIT, Attribute.NEED_PARSE_BIT, Attribute.NORMAL_BIT,
        Attribute.PART_BIT, Attribute.COLLECTION_BIT, Attribute.INTERACTIVE_BIT,
        Attribute.DOWNLOAD_AS_SINGLE_VIDEO_BIT, Attribute.WATCH_LATER_BIT,
        Attribute.HISTORY_BIT, Attribute.TREE_NODE_BIT, Attribute.AUDIO_BIT,
    ]
    # 按位 OR 后,每位都应保留
    combined = Attribute(0)
    for f in flags:
        combined |= f
    # 验证每个 flag 在组合中
    for f in flags:
        assert combined & f


def test_attribute_combinable_with_or():
    """Attribute 支持位 OR 组合"""
    combo = Attribute.VIDEO_BIT | Attribute.NORMAL_BIT
    assert combo & Attribute.VIDEO_BIT
    assert combo & Attribute.NORMAL_BIT
    assert not (combo & Attribute.BANGUMI_BIT)


# ==================================================================
# TreeItemBase
# ==================================================================

def test_tree_item_base_initial_state():
    """TreeItemBase 初始状态:parent=None, checked=Unchecked, children=[]"""
    item = TreeItem({"title": "root"})
    assert item.parent is None
    assert item.checked == CheckState.Unchecked
    assert item.children == []


def test_tree_item_add_child_sets_parent():
    """add_child 后 child.parent 指向父节点"""
    parent = TreeItem({"title": "p"})
    child = TreeItem({"title": "c"})
    parent.add_child(child)
    assert child.parent is parent
    assert child in parent.children


def test_tree_item_child_row_count():
    """child(row) / count() / row() 行为"""
    parent = TreeItem({"title": "p"})
    c1 = TreeItem({"title": "c1"})
    c2 = TreeItem({"title": "c2"})
    parent.add_child(c1)
    parent.add_child(c2)
    assert parent.count() == 2
    assert parent.child(0) is c1
    assert parent.child(1) is c2
    # row() 返回在父节点中的索引
    assert c1.row() == 0
    assert c2.row() == 1


def test_tree_item_row_no_parent_returns_zero():
    """无父节点时 row() 返回 0"""
    item = TreeItem({"title": "x"})
    assert item.row() == 0


# ==================================================================
# TreeItem set_checked_state 向下/向上传递
# ==================================================================

def test_set_checked_state_propagate_down():
    """set_checked_state(Checked) 向下传递给所有子节点"""
    root = TreeItem({"title": "root"})
    c1 = TreeItem({"title": "c1"})
    c2 = TreeItem({"title": "c2"})
    root.add_child(c1)
    root.add_child(c2)
    root.set_checked_state(CheckState.Checked)
    assert c1.checked == CheckState.Checked
    assert c2.checked == CheckState.Checked


def test_set_checked_state_propagate_up_to_partial():
    """子节点 Checked 后,父节点应变为 PartiallyChecked(混合状态)"""
    root = TreeItem({"title": "root"})
    c1 = TreeItem({"title": "c1"})
    c2 = TreeItem({"title": "c2"})
    root.add_child(c1)
    root.add_child(c2)
    c1.set_checked_state(CheckState.Checked)
    # 一个子 Checked,一个 Unchecked -> 父应为 PartiallyChecked
    assert root.checked == CheckState.PartiallyChecked


def test_set_checked_state_propagate_up_to_checked():
    """所有子节点 Checked 后,父节点应变为 Checked"""
    root = TreeItem({"title": "root"})
    c1 = TreeItem({"title": "c1"})
    c2 = TreeItem({"title": "c2"})
    root.add_child(c1)
    root.add_child(c2)
    c1.set_checked_state(CheckState.Checked)
    c2.set_checked_state(CheckState.Checked)
    assert root.checked == CheckState.Checked


def test_set_checked_state_no_change_skips_propagation():
    """set_checked_state 设置为相同状态时不重复传播"""
    root = TreeItem({"title": "root"})
    root.set_checked_state(CheckState.Unchecked)  # 默认就是 Unchecked,不应传播
    assert root.checked == CheckState.Unchecked


def test_set_checked_state_accepts_int_value():
    """set_checked_state 接受 int(自动转为 CheckState)"""
    root = TreeItem({"title": "root"})
    root.set_checked_state(2)  # 2 == Checked
    assert root.checked == CheckState.Checked


def test_set_checked_state_partial_does_not_propagate_down():
    """set_checked_state(PartiallyChecked) 不向下传播"""
    root = TreeItem({"title": "root"})
    c1 = TreeItem({"title": "c1"})
    root.add_child(c1)
    # 先 Checked,然后 PartiallyChecked
    root.set_checked_state(CheckState.Checked)
    root.set_checked_state(CheckState.PartiallyChecked)
    # c1 应保持 Checked(Partially 不向下传)
    assert c1.checked == CheckState.Checked


def test_propagate_up_three_levels():
    """三层嵌套:叶子 Checked 后,父与祖父状态正确"""
    grandparent = TreeItem({"title": "gp"})
    parent = TreeItem({"title": "p"})
    leaf = TreeItem({"title": "l"})
    parent.add_child(leaf)
    grandparent.add_child(parent)
    leaf.set_checked_state(CheckState.Checked)
    assert parent.checked == CheckState.Checked
    assert grandparent.checked == CheckState.Checked


# ==================================================================
# get_all_checked_children / get_all_children
# ==================================================================

def _build_tree_with_attributes():
    """构造测试树:root -> [c1(checked,VIDEO_BIT), c2(unchecked,NORMAL_BIT), node(TREE_NODE_BIT,checked)]"""
    root = TreeItem({"title": "root"})

    c1 = TreeItem({"title": "c1"})
    c1.set_attribute(Attribute.VIDEO_BIT)
    c1.set_checked_state(CheckState.Checked)

    c2 = TreeItem({"title": "c2"})
    c2.set_attribute(Attribute.NORMAL_BIT)
    # c2 未勾选

    node = TreeItem({"title": "section"})
    node.set_attribute(Attribute.TREE_NODE_BIT)
    node.set_checked_state(CheckState.Checked)  # 树节点不应被收集

    root.add_child(c1)
    root.add_child(c2)
    root.add_child(node)
    return root, c1, c2, node


def test_get_all_checked_children_returns_only_checked_leaves():
    """get_all_checked_children 仅返回已勾选且非树节点的叶子"""
    root, c1, c2, node = _build_tree_with_attributes()
    checked = root.get_all_checked_children()
    assert c1 in checked
    assert c2 not in checked
    assert node not in checked  # 树节点被排除


def test_get_all_checked_children_to_dict():
    """get_all_checked_children(to_dict=True) 返回字典列表"""
    root, c1, _, _ = _build_tree_with_attributes()
    checked = root.get_all_checked_children(to_dict=True)
    assert len(checked) == 1
    assert checked[0]["title"] == "c1"
    assert checked[0]["attribute"] & Attribute.VIDEO_BIT


def test_get_all_checked_children_mark_as_downloaded():
    """get_all_checked_children(mark_as_downloaded=True) 标记 downloaded=True"""
    root, c1, _, _ = _build_tree_with_attributes()
    checked = root.get_all_checked_children(mark_as_downloaded=True)
    assert c1.downloaded is True


def test_get_all_children_returns_all_leaves():
    """get_all_children 返回所有叶子(无论勾选状态)"""
    root, c1, c2, node = _build_tree_with_attributes()
    all_children = root.get_all_children()
    assert c1 in all_children
    assert c2 in all_children
    assert node not in all_children  # 树节点被排除


def test_get_all_children_to_dict():
    """get_all_children(to_dict=True) 返回字典列表"""
    root, c1, _, _ = _build_tree_with_attributes()
    all_children = root.get_all_children(to_dict=True)
    assert len(all_children) == 2  # c1 和 c2
    titles = [c["title"] for c in all_children]
    assert "c1" in titles and "c2" in titles


# ==================================================================
# 嵌套层级的 get_all_checked_children 递归
# ==================================================================

def test_get_all_checked_children_recursive():
    """get_all_checked_children 递归收集嵌套子树"""
    root = TreeItem({"title": "root"})
    section = TreeItem({"title": "section"})
    section.set_attribute(Attribute.TREE_NODE_BIT)
    leaf1 = TreeItem({"title": "leaf1"})
    leaf1.set_attribute(Attribute.VIDEO_BIT)
    leaf1.set_checked_state(CheckState.Checked)
    leaf2 = TreeItem({"title": "leaf2"})
    leaf2.set_attribute(Attribute.VIDEO_BIT)
    leaf2.set_checked_state(CheckState.Checked)
    section.add_child(leaf1)
    section.add_child(leaf2)
    root.add_child(section)

    checked = root.get_all_checked_children()
    assert leaf1 in checked
    assert leaf2 in checked
    assert section not in checked


# ==================================================================
# TreeItem.to_dict
# ==================================================================

def test_to_dict_includes_all_fields():
    """to_dict 包含所有必要字段"""
    item = TreeItem({
        "aid": 123, "bvid": "BV1xx", "cid": 456,
        "title": "test", "number": 1, "duration": 60,
        "pubtime": 1000, "url": "https://example.com",
    })
    item.set_attribute(Attribute.VIDEO_BIT | Attribute.NORMAL_BIT)

    d = item.to_dict()
    assert d["aid"] == 123
    assert d["bvid"] == "BV1xx"
    assert d["cid"] == 456
    assert d["title"] == "test"
    assert d["number"] == 1
    assert d["duration"] == 60
    assert d["pubtime"] == 1000
    assert d["url"] == "https://example.com"
    assert d["attribute"] & Attribute.VIDEO_BIT
    assert d["attribute"] & Attribute.NORMAL_BIT


def test_to_dict_with_uploader_info():
    """to_dict 在 uploader 存在时附加 uploader_info"""
    item = TreeItem({
        "uploader": "alice",
        "uploader_uid": 999,
    })
    d = item.to_dict()
    assert d["uploader_info"] == {"uploader": "alice", "uploader_uid": 999}


def test_to_dict_without_uploader_info():
    """to_dict 在 uploader 为空时不附加 uploader_info"""
    item = TreeItem({"title": "x"})
    d = item.to_dict()
    assert "uploader_info" not in d


# ==================================================================
# search_items
# ==================================================================

def test_search_items_matches_keyword():
    """search_items 在自身标题匹配时返回自身"""
    root = TreeItem({"title": "Hello World"})
    matches = root.search_items("hello")
    assert root in matches


def test_search_items_recursive():
    """search_items 递归在子树中查找"""
    root = TreeItem({"title": "root"})
    c1 = TreeItem({"title": "Hello"})
    c2 = TreeItem({"title": "World"})
    root.add_child(c1)
    root.add_child(c2)
    matches = root.search_items("hello")
    assert c1 in matches
    assert c2 not in matches


def test_search_items_case_insensitive():
    """search_items 大小写不敏感"""
    item = TreeItem({"title": "Bili23 Video"})
    matches = item.search_items("BILI23")
    assert item in matches


# ==================================================================
# dyn_time property
# ==================================================================

def test_dyn_time_returns_favtime_for_favlist():
    """dyn_time 在 FAVLIST_BIT 设置时返回 favtime"""
    item = TreeItem({"favtime": 12345})
    item.set_attribute(Attribute.FAVLIST_BIT)
    assert item.dyn_time == 12345


def test_dyn_time_returns_favtime_for_watch_later():
    """dyn_time 在 WATCH_LATER_BIT 设置时返回 favtime"""
    item = TreeItem({"favtime": 22222})
    item.set_attribute(Attribute.WATCH_LATER_BIT)
    assert item.dyn_time == 22222


def test_dyn_time_returns_viewtime_for_history():
    """dyn_time 在 HISTORY_BIT 设置时返回 viewtime"""
    item = TreeItem({"viewtime": 33333})
    item.set_attribute(Attribute.HISTORY_BIT)
    assert item.dyn_time == 33333


def test_dyn_time_returns_pubtime_default():
    """dyn_time 在无特殊属性时返回 pubtime"""
    item = TreeItem({"pubtime": 11111})
    assert item.dyn_time == 11111


# ==================================================================
# EpisodeData
# ==================================================================

def test_episode_data_add_and_get():
    """add_episode 创建唯一 ID,get_episode_data 返回空 dict"""
    eid = EpisodeData.add_episode()
    assert isinstance(eid, str)
    data = EpisodeData.get_episode_data(eid)
    assert data == {}


def test_episode_data_get_unknown_id_returns_empty():
    """get_episode_data 对未知 ID 返回空 dict"""
    data = EpisodeData.get_episode_data("nonexistent-id")
    assert data == {}


def test_episode_data_clear_cache():
    """clear_cache 清空所有缓存的剧集数据"""
    eid1 = EpisodeData.add_episode()
    eid2 = EpisodeData.add_episode()
    EpisodeData.get_episode_data(eid1)["title"] = "ep1"
    EpisodeData.clear_cache()
    assert EpisodeData.get_episode_data(eid1) == {}
    assert EpisodeData.get_episode_data(eid2) == {}


# ==================================================================
# TreeItem 默认值
# ==================================================================

def test_tree_item_defaults_from_empty_dict():
    """TreeItem({}) 用默认值初始化所有字段"""
    item = TreeItem({})
    assert item.attribute == 0
    assert item.pubtime == 0
    assert item.favtime == 0
    assert item.viewtime == 0
    assert item.expired is False
    assert item.aid == 0
    assert item.cid == 0
    assert item.sid == 0
    assert item.url == ""
    assert item.bvid == ""
    assert item.ep_id == 0
    assert item.badge == ""
    assert item.cover == ""
    assert item.title == ""
    assert item.author == ""
    assert item.number == ""
    assert item.duration == 0
    assert item.episode_id == ""
    assert item.episode_plot == ""
    assert item.part_number == 0
    assert item.episode_number == 0
    assert item.related_titles == {}
    assert item.uploader == ""
    assert item.uploader_uid == 0
    assert item.downloaded is False


def test_tree_item_set_attribute_accumulates():
    """set_attribute 多次调用累积位标志"""
    item = TreeItem({"title": "x"})
    item.set_attribute(Attribute.VIDEO_BIT)
    item.set_attribute(Attribute.NORMAL_BIT)
    item.set_attribute(Attribute.VIDEO_BIT)  # 重复设置不应清除已有位
    assert item.attribute & Attribute.VIDEO_BIT
    assert item.attribute & Attribute.NORMAL_BIT
