# tests/unit/test_danmaku_ass_coverage.py
"""T6 覆盖率补强 - src/util/parse/additional/file/danmaku_ass.py

覆盖目标:
- _load_pil_font(候选字体存在/不存在/truetype 异常/全失败回退)
- _measure_text_width(空文本/getlength/getbbox 回退/无属性回退 0)
- ScrollTrack.can_fit / push(首次 + cond1/cond2 计算)
- StaticTrack.can_fit / push
- DanmakuLayoutEngine.__init__ / _load_config / alloc_scroll / alloc_top / alloc_bottom
- DanmakuASS.__init__(按 stime 排序)
- DanmakuASS.generate(端到端)
- DanmakuASS._get_style_info
- DanmakuASS._convert_dialogues(各 mode 分支 + 颜色标签 + 满屏丢弃 + 无效条目跳过)
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from util.parse.additional.file.danmaku_ass import (
    DanmakuASS,
    DanmakuLayoutEngine,
    ScrollTrack,
    StaticTrack,
    _load_pil_font,
    _measure_text_width,
    _FONT_CANDIDATES,
)


# ---------------------------------------------------------------------------
# 公共 fixture:danmaku_style 配置
# ---------------------------------------------------------------------------
_DANMAKU_STYLE = {
    "font": {
        "name": "TestFont",
        "size": 24,
        "bold": False,
        "italic": False,
        "underline": False,
        "strike": False,
    },
    "resolution": {"width": 1280, "height": 720},
    "advanced": {
        "display_area": 100,
        "opacity": 100,
        "minimum_gap": 10,
    },
    "border": {"border": 1, "shadow": 0},
}


@pytest.fixture
def mock_danmaku_style():
    """patch config.get 返回完整 danmaku_style 配置字典"""
    with patch("util.parse.additional.file.danmaku_ass.config") as fake_config:
        fake_config.get.return_value = _DANMAKU_STYLE
        yield fake_config


# ---------------------------------------------------------------------------
# _load_pil_font
# ---------------------------------------------------------------------------
def test_load_pil_font_returns_truetype_when_candidate_exists():
    """存在可用字体文件时应返回 ImageFont.truetype 实例"""
    # linux 候选最后一个 DejaVuSans.ttf 在测试环境通常存在
    font = _load_pil_font("test", 16, False)
    # 应返回非 None 对象,且具备 getlength 或 getbbox
    assert font is not None
    assert hasattr(font, "getlength") or hasattr(font, "getbbox")


def test_load_pil_font_unknown_platform_falls_back_to_linux_candidates():
    """未知平台应回退到 linux 候选列表"""
    with patch("util.parse.additional.file.danmaku_ass.sys.platform", "unknown_os"):
        with patch("os.path.exists", return_value=False), \
             patch("PIL.ImageFont.load_default", return_value="default_font") as default_fn:
            font = _load_pil_font("test", 16, False)
            default_fn.assert_called_once()
            assert font == "default_font"


def test_load_pil_font_falls_back_to_default_when_all_candidates_missing():
    """所有候选字体都不存在时应回退到 ImageFont.load_default"""
    with patch("os.path.exists", return_value=False), \
         patch("PIL.ImageFont.load_default", return_value="default_font") as default_fn, \
         patch("PIL.ImageFont.truetype") as truetype_fn:
        font = _load_pil_font("test", 16, False)
        assert font == "default_font"
        default_fn.assert_called_once()
        truetype_fn.assert_not_called()


def test_load_pil_font_skips_failing_truetype_and_tries_next():
    """truetype 抛异常时应跳过该候选,继续尝试后续候选"""
    def fake_exists(path):
        # 仅放行第一个候选以触发 truetype 调用
        return path == _FONT_CANDIDATES["linux"][0]

    with patch("os.path.exists", side_effect=fake_exists), \
         patch("PIL.ImageFont.truetype", side_effect=RuntimeError("bad font")), \
         patch("PIL.ImageFont.load_default", return_value="default_font") as default_fn:
        # 第一个候选存在但 truetype 抛异常 -> continue;其余候选不存在 -> 跳过
        # 最终回退到 load_default
        font = _load_pil_font("test", 16, False)
        assert font == "default_font"
        default_fn.assert_called_once()


def test_load_pil_font_bold_param_does_not_crash():
    """bold=True 时不应抛异常(当前实现仅用于日志,不分支)"""
    font = _load_pil_font("test", 16, True)
    assert font is not None


# ---------------------------------------------------------------------------
# _measure_text_width
# ---------------------------------------------------------------------------
def test_measure_text_width_empty_text_returns_zero():
    """空文本应返回 0"""
    font = _load_pil_font("test", 16, False)
    assert _measure_text_width(font, "") == 0


def test_measure_text_width_uses_getlength_when_available():
    """font 有 getlength 时应优先使用"""
    font = MagicMock()
    font.getlength.return_value = 42.7
    # getlength 优先,getbbox 不应被调用
    font.getbbox = MagicMock(return_value=(0, 0, 50, 10))
    result = _measure_text_width(font, "hello")
    assert result == 42  # int(42.7) = 42
    font.getlength.assert_called_once_with("hello")


def test_measure_text_width_falls_back_to_getbbox_when_getlength_fails():
    """getlength 抛异常时应回退到 getbbox"""
    font = MagicMock()
    font.getlength.side_effect = RuntimeError("no getlength")
    font.getbbox.return_value = (5, 0, 55, 10)
    result = _measure_text_width(font, "hello")
    assert result == 50  # 55 - 5 = 50
    font.getbbox.assert_called_once_with("hello")


def test_measure_text_width_returns_zero_when_both_methods_fail():
    """getlength 与 getbbox 都抛异常时应返回 0"""
    font = MagicMock()
    font.getlength.side_effect = RuntimeError("fail")
    font.getbbox.side_effect = RuntimeError("fail")
    assert _measure_text_width(font, "hello") == 0


def test_measure_text_width_returns_zero_when_no_methods_available():
    """font 无 getlength/getbbox 属性时应返回 0"""
    font = MagicMock()
    del font.getlength
    del font.getbbox
    assert _measure_text_width(font, "hello") == 0


# ---------------------------------------------------------------------------
# ScrollTrack
# ---------------------------------------------------------------------------
def test_scroll_track_init_defaults():
    """ScrollTrack 应初始化为空轨道(last_stime=-1)"""
    track = ScrollTrack(1920, 10)
    assert track.screen_width == 1920
    assert track.min_gap == 10
    assert track.last_stime == -1
    assert track.last_duration == 0
    assert track.last_width == 0
    assert track.last_speed == 0.0


def test_scroll_track_can_fit_first_call_returns_true():
    """首次调用 can_fit 应返回 True(last_stime == -1)"""
    track = ScrollTrack(1920, 10)
    assert track.can_fit(1000, 0.5) is True


def test_scroll_track_can_fit_returns_false_when_too_close():
    """前一条弹幕未离开右边缘时,当前弹幕不应分配到该轨道"""
    track = ScrollTrack(1920, 10)
    track.push(0, 10000, 200, 0.5)
    # 立即下一条:stime=0 时 cond1 = 0 >= 0 + (200+10)/0.5 = 420 -> False
    assert track.can_fit(0, 0.5) is False


def test_scroll_track_can_fit_returns_true_after_enough_delay():
    """足够延迟后 can_fit 应返回 True"""
    track = ScrollTrack(1920, 10)
    track.push(0, 10000, 200, 0.5)
    # 大幅延后 stime,cond1/cond2 都满足
    assert track.can_fit(100000, 0.5) is True


def test_scroll_track_push_updates_state():
    """push 应更新 last_stime/last_duration/last_width/last_speed"""
    track = ScrollTrack(1920, 10)
    track.push(500, 10000, 200, 0.5)
    assert track.last_stime == 500
    assert track.last_duration == 10000
    assert track.last_width == 200
    assert track.last_speed == 0.5


# ---------------------------------------------------------------------------
# StaticTrack
# ---------------------------------------------------------------------------
def test_static_track_init_defaults():
    """StaticTrack 应初始化 end_time=-1"""
    track = StaticTrack()
    assert track.end_time == -1


def test_static_track_can_fit_first_call_returns_true():
    """首次 can_fit(stime=-1) 应返回 True"""
    track = StaticTrack()
    assert track.can_fit(0) is True


def test_static_track_can_fit_returns_false_before_end_time():
    """stime < end_time 时不应分配"""
    track = StaticTrack()
    track.push(5000)
    assert track.can_fit(4000) is False


def test_static_track_can_fit_returns_true_at_end_time():
    """stime >= end_time 时应可分配"""
    track = StaticTrack()
    track.push(5000)
    assert track.can_fit(5000) is True
    assert track.can_fit(6000) is True


def test_static_track_push_updates_end_time():
    """push 应更新 end_time"""
    track = StaticTrack()
    track.push(9999)
    assert track.end_time == 9999


# ---------------------------------------------------------------------------
# DanmakuLayoutEngine
# ---------------------------------------------------------------------------
def test_danmaku_layout_engine_init_loads_config_and_creates_tracks(mock_danmaku_style):
    """init 应加载 config 并按计算行数创建 scroll/top/bottom 轨道"""
    engine = DanmakuLayoutEngine(1280, 720)
    assert engine.screen_width == 1280
    assert engine.screen_height == 720
    # line_height = int(24 * 1.4) + 4 = 33 + 4 = 37
    assert engine.line_height == 37
    # display_area = 100/100 = 1.0
    assert engine.display_area == 1.0
    assert engine.opacity == 1.0
    assert engine.min_gap == 10
    # max_scroll_rows = max(1, int(720 * 1.0 / 37)) = int(19.45) = 19
    assert engine.max_scroll_rows >= 1
    assert len(engine.scroll_tracks) == engine.max_scroll_rows
    assert len(engine.top_tracks) == engine.max_static_rows
    assert len(engine.bottom_tracks) == engine.max_static_rows


def test_danmaku_layout_engine_min_one_row_when_display_area_zero():
    """display_area=0 时仍应保证至少 1 行"""
    style = {**_DANMAKU_STYLE}
    style = {
        **style,
        "advanced": {**style["advanced"], "display_area": 0},
    }
    with patch("util.parse.additional.file.danmaku_ass.config") as fake_config:
        fake_config.get.return_value = style
        engine = DanmakuLayoutEngine(1280, 720)
    assert engine.max_scroll_rows == 1
    assert engine.max_static_rows == 1


def test_alloc_scroll_returns_row_index_on_success(mock_danmaku_style):
    """alloc_scroll 在有可用轨道时应返回行号"""
    engine = DanmakuLayoutEngine(1280, 720)
    row = engine.alloc_scroll(0, 100, 10000)
    assert row is not None
    assert 0 <= row < engine.max_scroll_rows


def test_alloc_scroll_returns_none_when_all_tracks_full(mock_danmaku_style):
    """所有轨道占满后 alloc_scroll 应返回 None"""
    engine = DanmakuLayoutEngine(1280, 720)
    # 用相同 stime 反复分配,直到占满
    rows = []
    for _ in range(engine.max_scroll_rows):
        rows.append(engine.alloc_scroll(0, 100, 10000))
    # 再分配应返回 None
    overflow = engine.alloc_scroll(0, 100, 10000)
    assert all(r is not None for r in rows)
    assert overflow is None


def test_alloc_top_returns_row_index_on_success(mock_danmaku_style):
    """alloc_top 应返回行号"""
    engine = DanmakuLayoutEngine(1280, 720)
    row = engine.alloc_top(1000, 5000)
    assert row is not None
    assert 0 <= row < engine.max_static_rows


def test_alloc_top_returns_none_when_all_tracks_full(mock_danmaku_style):
    """所有 top 轨道占满后应返回 None"""
    engine = DanmakuLayoutEngine(1280, 720)
    for _ in range(engine.max_static_rows):
        engine.alloc_top(0, 5000)
    assert engine.alloc_top(0, 5000) is None


def test_alloc_bottom_returns_row_index_on_success(mock_danmaku_style):
    """alloc_bottom 应返回行号"""
    engine = DanmakuLayoutEngine(1280, 720)
    row = engine.alloc_bottom(2000, 5000)
    assert row is not None


def test_alloc_bottom_returns_none_when_all_tracks_full(mock_danmaku_style):
    """所有 bottom 轨道占满后应返回 None"""
    engine = DanmakuLayoutEngine(1280, 720)
    for _ in range(engine.max_static_rows):
        engine.alloc_bottom(0, 5000)
    assert engine.alloc_bottom(0, 5000) is None


# ---------------------------------------------------------------------------
# DanmakuASS.__init__
# ---------------------------------------------------------------------------
def test_danmaku_ass_init_sorts_by_stime():
    """__init__ 应按 stime 升序排序"""
    raw = [
        {"stime": 300, "mode": 1, "text": "c"},
        {"stime": 100, "mode": 1, "text": "a"},
        {"stime": 200, "mode": 1, "text": "b"},
    ]
    ass = DanmakuASS(raw, "title")
    assert [e["text"] for e in ass.dict_list] == ["a", "b", "c"]


def test_danmaku_ass_init_default_stime_for_missing_key():
    """缺失 stime 字段时应使用默认 0(不抛异常)"""
    raw = [
        {"mode": 1, "text": "no_stime"},
        {"stime": 0, "mode": 1, "text": "zero"},
    ]
    ass = DanmakuASS(raw, "title")
    assert len(ass.dict_list) == 2


def test_danmaku_ass_duration_map():
    """duration_map 应包含滚动/顶部/底部模式的时长"""
    ass = DanmakuASS([], "title")
    assert ass.duration_map[1] == 10000
    assert ass.duration_map[2] == 10000
    assert ass.duration_map[3] == 10000
    assert ass.duration_map[4] == 5000
    assert ass.duration_map[5] == 5000


# ---------------------------------------------------------------------------
# DanmakuASS._get_style_info
# ---------------------------------------------------------------------------
def test_get_style_info_returns_style_string_and_resolution(mock_danmaku_style):
    """_get_style_info 应返回 (style_str, width, height) 三元组"""
    ass = DanmakuASS([], "title")
    style_str, w, h = ass._get_style_info()
    assert w == 1280
    assert h == 720
    assert "Style: Default,TestFont,24," in style_str
    # opacity=100 -> alpha=0 -> "00"
    assert "&H00FFFFFF" in style_str


def test_get_style_info_with_partial_opacity():
    """opacity=50 时 alpha 应为 128(int(0.5*255)=127)"""
    style = {**_DANMAKU_STYLE, "advanced": {**_DANMAKU_STYLE["advanced"], "opacity": 50}}
    with patch("util.parse.additional.file.danmaku_ass.config") as fake_config:
        fake_config.get.return_value = style
        ass = DanmakuASS([], "title")
        style_str, _, _ = ass._get_style_info()
    # int((1.0 - 0.5) * 255) = int(127.5) = 127 -> "7F"
    assert "&H7FFFFFFF" in style_str


# ---------------------------------------------------------------------------
# DanmakuASS._convert_dialogues
# ---------------------------------------------------------------------------
def test_convert_dialogues_skips_empty_text(mock_danmaku_style):
    """空文本的条目应被跳过"""
    ass = DanmakuASS([{"stime": 0, "mode": 1, "text": ""}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    assert ass._convert_dialogues(engine) == []


def test_convert_dialogues_skips_unknown_mode(mock_danmaku_style):
    """未知 mode 应被跳过"""
    ass = DanmakuASS([{"stime": 0, "mode": 99, "text": "hello"}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    assert ass._convert_dialogues(engine) == []


def test_convert_dialogues_scroll_mode_produces_move_label(mock_danmaku_style):
    """滚动模式(1/2/3)应生成含 \\move 的 dialogue"""
    ass = DanmakuASS([{"stime": 0, "mode": 1, "text": "scroll"}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    dialogues = ass._convert_dialogues(engine)
    assert len(dialogues) == 1
    assert "\\move(" in dialogues[0]
    assert "scroll" in dialogues[0]


def test_convert_dialogues_top_mode_produces_an8_pos_label(mock_danmaku_style):
    """顶部模式(5)应生成含 \\an8\\pos 的 dialogue"""
    ass = DanmakuASS([{"stime": 0, "mode": 5, "text": "top"}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    dialogues = ass._convert_dialogues(engine)
    assert len(dialogues) == 1
    assert "\\an8\\pos(" in dialogues[0]


def test_convert_dialogues_bottom_mode_produces_an2_pos_label(mock_danmaku_style):
    """底部模式(4)应生成含 \\an2\\pos 的 dialogue"""
    ass = DanmakuASS([{"stime": 0, "mode": 4, "text": "bottom"}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    dialogues = ass._convert_dialogues(engine)
    assert len(dialogues) == 1
    assert "\\an2\\pos(" in dialogues[0]


def test_convert_dialogues_drops_when_track_full(mock_danmaku_style):
    """轨道占满时新弹幕应被丢弃(不出现在 dialogues)"""
    engine = DanmakuLayoutEngine(1280, 720)
    # 占满所有滚动轨道
    entries = []
    for i in range(engine.max_scroll_rows + 5):
        entries.append({"stime": 0, "mode": 1, "text": f"danmu{i}"})
    ass = DanmakuASS(entries, "title")
    dialogues = ass._convert_dialogues(engine)
    # 最多保留 max_scroll_rows 条
    assert len(dialogues) == engine.max_scroll_rows


def test_convert_dialogues_includes_color_tag_when_color_present(mock_danmaku_style):
    """条目带非默认颜色(非 16777215)时应生成 \\c&H 颜色标签"""
    # 0xFFFFFF = 16777215(默认白),不应生成颜色标签;用 0xFF0000(蓝)测试 BGR 转换
    ass = DanmakuASS([{"stime": 0, "mode": 1, "text": "colored", "color": 0xFF0000}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    dialogues = ass._convert_dialogues(engine)
    assert len(dialogues) == 1
    # 0xFF0000 -> bgr = (0x00 << 16) | (0x00 << 0) | 0xFF = 0x0000FF
    assert "\\c&H0000FF&" in dialogues[0]


def test_convert_dialogues_skips_color_tag_for_default_white(mock_danmaku_style):
    """color=16777215(白)时不应生成颜色标签"""
    ass = DanmakuASS([{"stime": 0, "mode": 1, "text": "white", "color": 16777215}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    dialogues = ass._convert_dialogues(engine)
    assert len(dialogues) == 1
    assert "\\c&H" not in dialogues[0]


def test_convert_dialogues_invalid_color_value_does_not_crash(mock_danmaku_style):
    """color 字段非整数时应静默跳过颜色标签(try/except 兜底)"""
    ass = DanmakuASS([{"stime": 0, "mode": 1, "text": "bad", "color": "not_a_number"}], "title")
    engine = DanmakuLayoutEngine(1280, 720)
    # 不抛异常
    dialogues = ass._convert_dialogues(engine)
    assert len(dialogues) == 1
    assert "\\c&H" not in dialogues[0]


# ---------------------------------------------------------------------------
# DanmakuASS.generate(端到端)
# ---------------------------------------------------------------------------
def test_generate_returns_full_ass_content(mock_danmaku_style):
    """generate 应返回完整的 ASS 文本(含 Script Info/Styles/Events 三段)"""
    raw = [
        {"stime": 1000, "mode": 1, "text": "scroll"},
        {"stime": 2000, "mode": 4, "text": "bottom"},
        {"stime": 3000, "mode": 5, "text": "top"},
    ]
    ass = DanmakuASS(raw, "My Video Title")
    content = ass.generate()
    assert "[Script Info]" in content
    assert "Title: My Video Title" in content
    assert "[V4+ Styles]" in content
    assert "[Events]" in content
    # 应包含 3 条 dialogue
    assert content.count("Dialogue: 0,") == 3


def test_generate_empty_dict_list_returns_template_only(mock_danmaku_style):
    """空弹幕列表时 generate 应返回模板内容,不含 dialogue"""
    ass = DanmakuASS([], "Empty")
    content = ass.generate()
    assert "[Script Info]" in content
    assert "Title: Empty" in content
    assert "Dialogue: 0," not in content


def test_generate_includes_resolution_in_script_info(mock_danmaku_style):
    """generate 应在 Script Info 中填入分辨率"""
    ass = DanmakuASS([], "title")
    content = ass.generate()
    assert "PlayResX: 1280" in content
    assert "PlayResY: 720" in content
    assert "Aspect Ratio: 1280:720" in content
