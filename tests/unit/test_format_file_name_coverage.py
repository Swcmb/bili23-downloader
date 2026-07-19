# tests/unit/test_format_file_name_coverage.py
"""format/file_name.py 覆盖率补强测试

覆盖 FileNameFormatter 的所有公开方法 + 私有 sanitize/normalize 分支:
- set_type_id / set_rule / set_variable_data (list 路径 + TaskInfo 路径)
- format (规则缺失/有 attribute/异常路径)
- get_special_rule (有/无 DOWNLOAD_AS_SINGLE_VIDEO_BIT)
- get_rule_from_config / get_rule_by_id / get_rule_list_from_attribute
- get_variable_data_from_task_info (number=int/str)
- get_type_id_from_task_info / get_type_id_from_attribute (各种 Attribute)
"""
from util.common.enum import ConventionType
from util.common.config import config
from util.download.task.info import TaskInfo
from util.format.file_name import FileNameFormatter
from util.parse.episode.tree import Attribute


# ==================================================================
# 测试夹具:在 config 中放置命名规则
# ==================================================================

def _setup_naming_rules():
    """在 config 中预置命名规则,避免依赖文件系统加载状态"""
    config.set("naming_rule_list", [
        {"id": 1, "type": ConventionType.NORMAL, "default": True, "rule": "{leaf_title}"},
        {"id": 2, "type": ConventionType.NORMAL, "default": False, "rule": "{bvid}"},
        {"id": 3, "type": ConventionType.BANGUMI, "default": True, "rule": "{episode_title}"},
        {"id": 4, "type": ConventionType.FAVORITE, "default": True, "rule": "{favorites_name}/{leaf_title}"},
        {"id": 5, "type": ConventionType.PART, "default": True, "rule": "{parent_title}_{p}"},
        {"id": 6, "type": ConventionType.COLLECTION, "default": True, "rule": "{collection_title}/{leaf_title}"},
        {"id": 7, "type": ConventionType.INTERACTIVE_VIDEO, "default": True, "rule": "{leaf_title}"},
        {"id": 8, "type": ConventionType.CHEESE, "default": True, "rule": "{series_title}"},
        {"id": 9, "type": ConventionType.SPACE, "default": True, "rule": "{space_owner}/{leaf_title}"},
        {"id": 10, "type": ConventionType.HISTORY, "default": True, "rule": "{leaf_title}"},
        {"id": 11, "type": ConventionType.WATCH_LATER, "default": True, "rule": "{leaf_title}"},
        {"id": 12, "type": ConventionType.WEEKLY, "default": True, "rule": "{leaf_title}"},
        {"id": 13, "type": ConventionType.AUDIO, "default": True, "rule": "{leaf_title}"},
    ])


def _build_task_info(attribute: int, *, number="1", pubtime=1700000000) -> TaskInfo:
    """构造一个填满字段的 TaskInfo,便于多场景测试"""
    info = TaskInfo()
    info.Episode.attribute = attribute
    info.Episode.aid = 100
    info.Episode.bvid = "BV1xxx"
    info.Episode.cid = 200
    info.Episode.ep_id = 300
    info.Episode.season_id = 400
    info.Episode.season_number = 1
    info.Episode.episode_number = 1
    info.Episode.part_number = 1
    info.Episode.leaf_title = "leaf"
    info.Episode.parent_title = "parent"
    info.Episode.section_title = "section"
    info.Episode.collection_title = "collection"
    info.Episode.series_title = "series"
    info.Episode.season_title = "season"
    info.Episode.episode_title = "episode"
    info.Episode.favorites_name = "favs"
    info.Episode.favorites_id = 500
    info.Episode.favorites_owner = "owner"
    info.Episode.favorites_owner_id = 600
    info.Episode.space_owner = "space_owner"
    info.Episode.space_owner_id = 700
    info.Episode.uploader = "uploader"
    info.Episode.uploader_uid = 800
    info.Episode.video_quality = "1080P"
    info.Episode.audio_quality = "192K"
    info.Episode.video_codec = "HEVC"
    info.Episode.pubtime = pubtime
    info.Episode.favtime = pubtime
    info.Episode.viewtime = pubtime
    info.Episode.number = number
    info.Basic.created_time = pubtime
    return info


# ==================================================================
# set_type_id / set_rule / set_variable_data(list)
# ==================================================================

def test_set_type_id_stores_value():
    f = FileNameFormatter()
    f.set_type_id(42)
    assert f.type_id == 42


def test_set_rule_stores_value():
    f = FileNameFormatter()
    f.set_rule("{leaf_title}")
    assert f.rule == "{leaf_title}"


def test_set_variable_data_from_list_basic():
    """从 list[dict] 设置变量数据,非时间字段直接保留"""
    f = FileNameFormatter()
    data = [
        {"name": "leaf_title", "example": "test_title"},
        {"name": "aid", "example": 12345},
    ]
    f.set_variable_data(data)
    assert f.variable_data["leaf_title"] == "test_title"
    assert f.variable_data["aid"] == 12345


def test_set_variable_data_from_list_replaces_time_with_formatted():
    """list 路径中时间字段会被 Time.from_timestamp 转换"""
    f = FileNameFormatter()
    data = [
        {"name": "pub_time", "example": "raw"},
        {"name": "create_time", "example": "raw"},
        {"name": "last_watched_time", "example": "raw"},
        {"name": "fav_time", "example": "raw"},
    ]
    f.set_variable_data(data)
    # 时间字段的 example 被替换为 Time.from_timestamp(1772841600) 返回的 datetime
    from datetime import datetime
    expected = datetime.fromtimestamp(1772841600)
    for key in ("pub_time", "create_time", "last_watched_time", "fav_time"):
        assert f.variable_data[key] == expected


# ==================================================================
# set_variable_data(TaskInfo) - 走 get_variable_data_from_task_info
# ==================================================================

def test_set_variable_data_from_task_info_normal_attribute():
    """TaskInfo 路径:同时设置 variable_data 与 type_id"""
    _setup_naming_rules()
    f = FileNameFormatter()
    info = _build_task_info(Attribute.NORMAL_BIT)
    f.set_variable_data(info)
    assert f.variable_data["leaf_title"] == "leaf"
    assert f.variable_data["bvid"] == "BV1xxx"
    assert f.variable_data["number"] == 1  # 数字字符串已转 int
    # type_id 从 attribute 推断:NORMAL_BIT -> ConventionType.NORMAL
    assert f.type_id == ConventionType.NORMAL


def test_set_variable_data_from_task_info_with_string_number():
    """number 为文本标签(如 "EP1")时保留为字符串"""
    _setup_naming_rules()
    f = FileNameFormatter()
    info = _build_task_info(Attribute.NORMAL_BIT, number="EP1")
    f.set_variable_data(info)
    # int("EP1") 抛 ValueError -> 保留原字符串
    assert f.variable_data["number"] == "EP1"


# ==================================================================
# get_variable_data_from_task_info - 直接调用,验证所有字段
# ==================================================================

def test_get_variable_data_from_task_info_all_fields_present():
    f = FileNameFormatter()
    info = _build_task_info(Attribute.NORMAL_BIT)
    data = f.get_variable_data_from_task_info(info)
    expected_keys = {
        "pub_time", "pub_ts", "create_time", "create_ts",
        "fav_time", "fav_ts", "last_watched_time", "last_watched_ts",
        "number", "uploader", "uploader_uid",
        "video_quality", "audio_quality", "video_codec",
        "aid", "bvid", "cid", "ep_id", "season_id",
        "leaf_title", "parent_title", "section_title", "collection_title",
        "series_title", "season_title", "episode_title",
        "season_number", "episode_number", "p",
        "favorites_name", "favorites_id", "favorites_owner", "favorites_owner_id",
        "space_owner", "space_owner_id",
    }
    assert expected_keys.issubset(data.keys())
    # pub_ts 字段为原始时间戳
    assert data["pub_ts"] == 1700000000
    # p 字段从 part_number 取
    assert data["p"] == 1


# ==================================================================
# get_type_id_from_attribute - 各 Attribute 映射
# ==================================================================

def test_get_type_id_from_attribute_normal():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.NORMAL_BIT) == ConventionType.NORMAL


def test_get_type_id_from_attribute_part():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.PART_BIT) == ConventionType.PART


def test_get_type_id_from_attribute_collection():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.COLLECTION_BIT) == ConventionType.COLLECTION


def test_get_type_id_from_attribute_interactive():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.INTERACTIVE_BIT) == ConventionType.INTERACTIVE_VIDEO


def test_get_type_id_from_attribute_bangumi():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.BANGUMI_BIT) == ConventionType.BANGUMI


def test_get_type_id_from_attribute_cheese():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.CHEESE_BIT) == ConventionType.CHEESE


def test_get_type_id_from_attribute_favorite():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.FAVLIST_BIT) == ConventionType.FAVORITE


def test_get_type_id_from_attribute_space():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.SPACE_BIT) == ConventionType.SPACE


def test_get_type_id_from_attribute_history():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.HISTORY_BIT) == ConventionType.HISTORY


def test_get_type_id_from_attribute_watch_later():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.WATCH_LATER_BIT) == ConventionType.WATCH_LATER


def test_get_type_id_from_attribute_weekly():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.WEEKLY_BIT) == ConventionType.WEEKLY


def test_get_type_id_from_attribute_audio():
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(Attribute.AUDIO_BIT) == ConventionType.AUDIO


def test_get_type_id_from_attribute_combined():
    """多个 attribute 同时设置时,匹配第一个非零位"""
    f = FileNameFormatter()
    # FAVLIST_BIT (1<<6=64) + NORMAL_BIT (1<<8=256)
    attr = Attribute.FAVLIST_BIT | Attribute.NORMAL_BIT
    # type_map 的迭代顺序:FAVLIST_BIT 在 NORMAL_BIT 之前,因此返回 FAVORITE
    assert f.get_type_id_from_attribute(attr) == ConventionType.FAVORITE


def test_get_type_id_from_attribute_no_match_returns_none():
    """attribute 为 0 时返回 None"""
    f = FileNameFormatter()
    assert f.get_type_id_from_attribute(0) is None


# ==================================================================
# get_type_id_from_task_info
# ==================================================================

def test_get_type_id_from_task_info_sets_attribute():
    """get_type_id_from_task_info 同时缓存 attribute 到 self.attribute"""
    f = FileNameFormatter()
    info = _build_task_info(Attribute.BANGUMI_BIT)
    type_id = f.get_type_id_from_task_info(info)
    assert type_id == ConventionType.BANGUMI
    assert f.attribute == Attribute.BANGUMI_BIT


# ==================================================================
# get_rule_from_config / get_rule_by_id / get_rule_list_from_attribute
# ==================================================================

def test_get_rule_from_config_default_rule():
    _setup_naming_rules()
    f = FileNameFormatter()
    rule = f.get_rule_from_config(ConventionType.NORMAL)
    assert rule == "{leaf_title}"


def test_get_rule_from_config_no_match_returns_none():
    """type_id 不在列表中时返回 None"""
    _setup_naming_rules()
    f = FileNameFormatter()
    # ConventionType 取一个未配置的值,如 PART 但 PART 已配置 -> 用一个未在表中的值
    # 这里改用 9999 模拟未命中
    assert f.get_rule_from_config(9999) is None


def test_get_rule_by_id():
    _setup_naming_rules()
    f = FileNameFormatter()
    assert f.get_rule_by_id(2) == "{bvid}"
    # 不存在 id 返回 None
    assert f.get_rule_by_id(999) is None


def test_get_rule_list_from_attribute():
    """按 attribute 反查所有同 type 的规则"""
    _setup_naming_rules()
    f = FileNameFormatter()
    rules = f.get_rule_list_from_attribute(Attribute.NORMAL_BIT)
    # NORMAL 类型有 2 条(id=1 default,id=2 非 default)
    assert len(rules) == 2
    types = {r["type"] for r in rules}
    assert types == {ConventionType.NORMAL}


# ==================================================================
# get_special_rule
# ==================================================================

def test_get_special_rule_with_download_as_single_video_bit():
    """DOWNLOAD_AS_SINGLE_VIDEO_BIT -> 返回 str(Path('{leaf_title}'))"""
    f = FileNameFormatter()
    f.set_rule("{bvid}")
    f.attribute = Attribute.DOWNLOAD_AS_SINGLE_VIDEO_BIT
    # 源码:str(Path("{leaf_title}")) -> "{leaf_title}"(Path 不剥离花括号)
    assert f.get_special_rule() == "{leaf_title}"


def test_get_special_rule_without_special_attribute_returns_original_rule():
    """无特殊 attribute 时返回原 rule"""
    f = FileNameFormatter()
    f.set_rule("{leaf_title}")
    f.attribute = Attribute.NORMAL_BIT
    assert f.get_special_rule() == "{leaf_title}"


def test_get_special_rule_with_none_rule_initializes_empty():
    """rule 为 None 时初始化为空字符串"""
    f = FileNameFormatter()
    f.rule = None
    f.attribute = Attribute.NORMAL_BIT
    assert f.get_special_rule() == ""


# ==================================================================
# format - 公开入口
# ==================================================================

def test_format_basic_substitution():
    """简单变量替换"""
    f = FileNameFormatter()
    f.set_rule("{leaf_title}")
    f.set_variable_data([{"name": "leaf_title", "example": "video_title"}])
    assert f.format() == "video_title"


def test_format_sanitize_illegal_chars():
    """非法字符替换为下划线"""
    f = FileNameFormatter()
    f.set_rule("{leaf_title}")
    f.set_variable_data([{"name": "leaf_title", "example": 'a<b>c:"d/e\\e|f?g*h'}])
    result = f.format()
    # a < b > c : " d / e \ e | f ? g * h
    # a _ b _ c _ _ d _ e _ e _ f _ g _ h
    assert result == "a_b_c__d_e_e_f_g_h"


def test_format_normalize_strips_leading_slash():
    """开头的 / 被剥离"""
    f = FileNameFormatter()
    f.set_rule("/{leaf_title}")
    f.set_variable_data([{"name": "leaf_title", "example": "title"}])
    assert f.format() == "title"


def test_format_normalize_strips_trailing_dots_and_spaces():
    """结尾的点和空格被剥离"""
    f = FileNameFormatter()
    f.set_rule("{leaf_title}")
    f.set_variable_data([{"name": "leaf_title", "example": "title. "}])
    assert f.format() == "title"


def test_format_normalize_empty_result_returns_underscore():
    """全部归一化后为空时返回 '_'"""
    f = FileNameFormatter()
    f.set_rule("{leaf_title}")
    f.set_variable_data([{"name": "leaf_title", "example": "."}])
    assert f.format() == "_"


def test_format_loads_rule_from_config_when_missing():
    """未设置 rule 时,从 config 按 type_id 加载默认规则"""
    _setup_naming_rules()
    f = FileNameFormatter()
    f.set_type_id(ConventionType.NORMAL)
    f.set_variable_data([{"name": "leaf_title", "example": "loaded"}])
    assert f.format() == "loaded"


def test_format_with_special_attribute():
    """attribute 为 DOWNLOAD_AS_SINGLE_VIDEO_BIT 时走 get_special_rule 分支"""
    _setup_naming_rules()
    f = FileNameFormatter()
    f.set_rule("{bvid}")  # 原规则
    f.attribute = Attribute.DOWNLOAD_AS_SINGLE_VIDEO_BIT
    f.set_variable_data([
        {"name": "leaf_title", "example": "single_video"},
        {"name": "bvid", "example": "BV1xxx"},
    ])
    assert f.format() == "single_video"


def test_format_with_path_components():
    """多级路径正确归一化"""
    f = FileNameFormatter()
    f.set_rule("{parent}/{child}")
    f.set_variable_data([
        {"name": "parent", "example": "dir1"},
        {"name": "child", "example": "file1"},
    ])
    assert f.format() == "dir1/file1"


def test_format_exception_returns_none():
    """格式化异常时返回 None(不抛出)"""
    f = FileNameFormatter()
    # 引用不存在的占位符 -> KeyError -> 捕获返回 None
    f.set_rule("{nonexistent_var}")
    f.set_variable_data([{"name": "leaf_title", "example": "title"}])
    assert f.format() is None


# ==================================================================
# set_variable_data(TaskInfo) 覆盖更多 attribute 路径
# ==================================================================

def test_set_variable_data_from_task_info_bangumi_attribute():
    _setup_naming_rules()
    f = FileNameFormatter()
    info = _build_task_info(Attribute.BANGUMI_BIT)
    f.set_variable_data(info)
    assert f.type_id == ConventionType.BANGUMI


def test_set_variable_data_from_task_info_audio_attribute():
    _setup_naming_rules()
    f = FileNameFormatter()
    info = _build_task_info(Attribute.AUDIO_BIT)
    f.set_variable_data(info)
    assert f.type_id == ConventionType.AUDIO
