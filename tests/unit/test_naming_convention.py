# tests/unit/test_naming_convention.py
"""命名规范工厂单元测试 - VariableListFactory.build / 反向映射表

覆盖:
- convention_type_map 与 reversed_convention_type_map 互逆
- VariableListFactory.build(每种 ConventionType) 返回非空列表
- build 返回的每个变量字典都包含必要字段(name/variable/description/example/type)
- 特殊情形:FAVORITE / SPACE 在 base+normal 之上叠加各自变量
"""
import pytest

from util.common.enum import ConventionType, VariableType
from util.common.data.naming_convention import (
    convention_type_map,
    reversed_convention_type_map,
    VariableListFactory,
)


# ==================================================================
# convention_type_map / reversed_convention_type_map
# ==================================================================

def test_convention_type_map_roundtrip():
    """正向与反向映射表互逆"""
    for str_key, enum_val in convention_type_map.items():
        assert reversed_convention_type_map[enum_val] == str_key


def test_convention_type_map_contains_all_types():
    """convention_type_map 覆盖所有 ConventionType"""
    expected = {
        ConventionType.NORMAL,
        ConventionType.PART,
        ConventionType.COLLECTION,
        ConventionType.INTERACTIVE_VIDEO,
        ConventionType.BANGUMI,
        ConventionType.CHEESE,
        ConventionType.FAVORITE,
        ConventionType.SPACE,
        ConventionType.HISTORY,
        ConventionType.WATCH_LATER,
        ConventionType.WEEKLY,
        ConventionType.AUDIO,
    }
    assert set(convention_type_map.values()) == expected


# ==================================================================
# _assert_variables_well_formed 公共断言
# ==================================================================

def _assert_variables_well_formed(variables, *, require_type: bool = False):
    """断言每个变量字典字段完整

    注意:仅 _base_variable 中的项目带 type 字段,
    其他子列表(_normal_variable 等)不带 type,因此默认不要求。
    """
    assert variables, "变量列表不能为空"
    for v in variables:
        assert "name" in v and isinstance(v["name"], str) and v["name"]
        assert "variable" in v and isinstance(v["variable"], str) and v["variable"]
        assert "description" in v and isinstance(v["description"], str) and v["description"]
        assert "example" in v  # example 可为 str 或 int
        if require_type:
            assert "type" in v
            assert isinstance(v["type"], VariableType)


# ==================================================================
# 每种 ConventionType 的 build()
# ==================================================================

def test_build_normal():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.NORMAL)
    _assert_variables_well_formed(variables)
    # NORMAL 应包含 base + aid/bvid/cid/leaf_title
    names = [v["name"] for v in variables]
    assert "aid" in names and "bvid" in names and "cid" in names
    assert "leaf_title" in names


def test_build_part():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.PART)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "parent_title" in names and "p" in names


def test_build_collection():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.COLLECTION)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "collection_title" in names
    assert "section_title" in names
    assert "parent_title" in names


def test_build_interactive_video():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.INTERACTIVE_VIDEO)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "leaf_title" in names
    assert "parent_title" in names


def test_build_bangumi():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.BANGUMI)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "series_title" in names
    assert "season_title" in names
    assert "episode_title" in names
    assert "ep_id" in names
    assert "season_id" in names


def test_build_cheese():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.CHEESE)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "series_title" in names
    assert "episode_title" in names
    assert "ep_id" in names


def test_build_favorite_includes_normal_variables():
    """FAVORITE = base + normal + favorite 三个分组"""
    factory = VariableListFactory()
    variables = factory.build(ConventionType.FAVORITE)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    # 来自 base
    assert "uploader" in names
    # 来自 normal
    assert "aid" in names and "bvid" in names
    # 来自 favorite
    assert "favorites_name" in names
    assert "favorites_id" in names
    assert "fav_time" in names


def test_build_space_includes_normal_variables():
    """SPACE = base + normal + space"""
    factory = VariableListFactory()
    variables = factory.build(ConventionType.SPACE)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "aid" in names  # 来自 normal
    assert "space_owner" in names
    assert "space_owner_id" in names


def test_build_history():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.HISTORY)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "last_watched_time" in names
    assert "last_watched_ts" in names


def test_build_watch_later():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.WATCH_LATER)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "fav_time" in names  # watch_later 用的是 fav_time
    assert "parent_title" in names


def test_build_weekly():
    factory = VariableListFactory()
    variables = factory.build(ConventionType.WEEKLY)
    _assert_variables_well_formed(variables)
    names = [v["name"] for v in variables]
    assert "parent_title" in names
    assert "leaf_title" in names


def test_build_audio_uses_audio_only_variable_set():
    """AUDIO 不叠加 base,使用独立 _audio_variable 列表"""
    factory = VariableListFactory()
    variables = factory.build(ConventionType.AUDIO)
    # audio 变量无 type 字段,所以走 require_type=False 路径
    _assert_variables_well_formed(variables, require_type=False)
    names = [v["name"] for v in variables]
    # audio 自带 pub_time/uploader/leaf_title 等
    assert "pub_time" in names
    assert "uploader" in names
    assert "audio_quality" in names
    # audio 不应包含 base 中的 video_quality / video_codec
    assert "video_quality" not in names
    assert "video_codec" not in names


# ==================================================================
# 私有 property 直接验证(覆盖每个 _xxx_variable 的 return)
# ==================================================================

def test_base_variable_contains_pub_time_and_quality_fields():
    factory = VariableListFactory()
    base = factory._base_variable
    names = [v["name"] for v in base]
    assert "pub_time" in names
    assert "create_time" in names
    assert "uploader" in names
    assert "video_quality" in names
    assert "audio_quality" in names
    assert "video_codec" in names


def test_audio_variable_does_not_have_type_field():
    """_audio_variable 中的字典不含 type 字段(与 base 不同)"""
    factory = VariableListFactory()
    audio_vars = factory._audio_variable
    for v in audio_vars:
        assert "type" not in v
