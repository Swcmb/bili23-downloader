# tests/cli/test_quality_selector.py
"""T5.9 测试:画质/音质/编码选择交互组件

验证点:
- test_select_non_interactive_all_specified:三个参数都指定,返回相同
- test_select_non_interactive_default:不指定,使用列表第一项
- test_select_non_interactive_invalid_video_id:画质 ID 不在列表抛 ParseError
- test_select_non_interactive_invalid_audio_id:音质 ID 不在列表抛 ParseError
- test_select_non_interactive_invalid_codec:编码不在列表抛 ParseError
- test_select_interactive_default:模拟空回车三次,返回列表第一项
- test_select_interactive_select:模拟输入 "2", "3", "1",返回对应项
- test_select_interactive_cancel:模拟输入 "q",抛 UserCancelledError
- test_select_interactive_invalid_then_valid:输入 "abc" 重新提示,再输入 "1"
- test_quality_names_dict:常量映射正确
"""
import pytest


def _sample_video_qualities():
    """测试用画质列表(从高到低)"""
    return [
        {"id": 127, "name": "8K 超高清"},
        {"id": 120, "name": "4K 超清"},
        {"id": 80, "name": "1080P 高清"},
        {"id": 64, "name": "720P 高清"},
    ]


def _sample_audio_qualities():
    """测试用音质列表"""
    return [
        {"id": 30280, "name": "Hi-Res 128K"},
        {"id": 30232, "name": "132K"},
        {"id": 30240, "name": "64K"},
    ]


def _sample_codecs():
    """测试用编码列表"""
    return ["AVC", "HEVC", "AV1"]


def _silence_console(monkeypatch):
    """抑制 Rich 表格输出,避免污染测试输出"""
    from cli.interact import quality_selector as qs_module
    monkeypatch.setattr(qs_module.console, "print", lambda *a, **kw: None)


def test_select_non_interactive_all_specified():
    """AC-031: --video-quality 127 --audio-quality 30280 --video-codec HEVC 非交互模式"""
    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=_sample_video_qualities(),
        audio_qualities=_sample_audio_qualities(),
        video_codecs=_sample_codecs(),
        video_quality_id=120,
        audio_quality_id=30232,
        video_codec="HEVC",
        interactive=False,
    )
    assert result == {
        "video_quality_id": 120,
        "audio_quality_id": 30232,
        "video_codec": "HEVC",
    }


def test_select_non_interactive_default():
    """不指定参数时使用列表第一项(最高)"""
    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=_sample_video_qualities(),
        audio_qualities=_sample_audio_qualities(),
        video_codecs=_sample_codecs(),
        interactive=False,
    )
    assert result == {
        "video_quality_id": 127,
        "audio_quality_id": 30280,
        "video_codec": "AVC",
    }


def test_select_non_interactive_partial_default():
    """部分未指定:未指定的字段使用默认(列表第一项)"""
    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=_sample_video_qualities(),
        audio_qualities=_sample_audio_qualities(),
        video_codecs=_sample_codecs(),
        video_quality_id=80,
        interactive=False,
    )
    # 音质与编码未指定,使用默认
    assert result == {
        "video_quality_id": 80,
        "audio_quality_id": 30280,
        "video_codec": "AVC",
    }


def test_select_non_interactive_invalid_video_id():
    """画质 ID 不在列表抛 ParseError"""
    from cli.interact.quality_selector import select_quality
    from cli.exceptions import ParseError

    with pytest.raises(ParseError):
        select_quality(
            video_qualities=_sample_video_qualities(),
            audio_qualities=_sample_audio_qualities(),
            video_codecs=_sample_codecs(),
            video_quality_id=999,
            audio_quality_id=30232,
            video_codec="AVC",
            interactive=False,
        )


def test_select_non_interactive_invalid_audio_id():
    """音质 ID 不在列表抛 ParseError"""
    from cli.interact.quality_selector import select_quality
    from cli.exceptions import ParseError

    with pytest.raises(ParseError):
        select_quality(
            video_qualities=_sample_video_qualities(),
            audio_qualities=_sample_audio_qualities(),
            video_codecs=_sample_codecs(),
            video_quality_id=80,
            audio_quality_id=99999,
            video_codec="AVC",
            interactive=False,
        )


def test_select_non_interactive_invalid_codec():
    """编码不在列表抛 ParseError"""
    from cli.interact.quality_selector import select_quality
    from cli.exceptions import ParseError

    with pytest.raises(ParseError):
        select_quality(
            video_qualities=_sample_video_qualities(),
            audio_qualities=_sample_audio_qualities(),
            video_codecs=_sample_codecs(),
            video_quality_id=80,
            audio_quality_id=30232,
            video_codec="MPEG2",
            interactive=False,
        )


def test_select_interactive_default(monkeypatch):
    """模拟空回车三次,返回列表第一项(最高)"""
    _silence_console(monkeypatch)
    inputs = iter(["", "", ""])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=_sample_video_qualities(),
        audio_qualities=_sample_audio_qualities(),
        video_codecs=_sample_codecs(),
    )
    assert result == {
        "video_quality_id": 127,
        "audio_quality_id": 30280,
        "video_codec": "AVC",
    }


def test_select_interactive_select(monkeypatch):
    """模拟输入 "2" / "3" / "1",返回对应项"""
    _silence_console(monkeypatch)
    inputs = iter(["2", "3", "1"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=_sample_video_qualities(),
        audio_qualities=_sample_audio_qualities(),
        video_codecs=_sample_codecs(),
    )
    # 索引 2 -> 4K(120); 索引 3 -> 64K(30240); 索引 1 -> AVC
    assert result == {
        "video_quality_id": 120,
        "audio_quality_id": 30240,
        "video_codec": "AVC",
    }


def test_select_interactive_cancel(monkeypatch):
    """模拟输入 "q",抛 UserCancelledError"""
    _silence_console(monkeypatch)
    inputs = iter(["q"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    from cli.interact.quality_selector import select_quality
    from cli.exceptions import UserCancelledError

    with pytest.raises(UserCancelledError):
        select_quality(
            video_qualities=_sample_video_qualities(),
            audio_qualities=_sample_audio_qualities(),
            video_codecs=_sample_codecs(),
        )


def test_select_interactive_invalid_then_valid(monkeypatch):
    """输入 "abc" 重新提示,再输入 "1" 接受;剩余两步使用默认"""
    _silence_console(monkeypatch)
    inputs = iter(["abc", "1", "", ""])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=_sample_video_qualities(),
        audio_qualities=_sample_audio_qualities(),
        video_codecs=_sample_codecs(),
    )
    # 画质: "abc" 无效 -> 重新提示 -> "1" 接受(第一项 8K, 127)
    # 音质: "" 默认(第一项 Hi-Res 128K, 30280)
    # 编码: "" 默认(第一项 AVC)
    assert result == {
        "video_quality_id": 127,
        "audio_quality_id": 30280,
        "video_codec": "AVC",
    }


def test_select_interactive_out_of_range_then_valid(monkeypatch):
    """输入超范围数字(如 "99")重新提示,再输入 "1" 接受"""
    _silence_console(monkeypatch)
    inputs = iter(["99", "1", "1", "1"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    from cli.interact.quality_selector import select_quality

    result = select_quality(
        video_qualities=_sample_video_qualities(),
        audio_qualities=_sample_audio_qualities(),
        video_codecs=_sample_codecs(),
    )
    assert result == {
        "video_quality_id": 127,
        "audio_quality_id": 30280,
        "video_codec": "AVC",
    }


def test_quality_names_dict():
    """常量映射正确"""
    from cli.interact.quality_selector import QUALITY_NAMES, AUDIO_QUALITY_NAMES

    assert QUALITY_NAMES[127] == "8K 超高清"
    assert QUALITY_NAMES[126] == "杜比视界"
    assert QUALITY_NAMES[125] == "HDR"
    assert QUALITY_NAMES[120] == "4K 超清"
    assert QUALITY_NAMES[116] == "1080P60 高帧率"
    assert QUALITY_NAMES[112] == "1080P 高码率"
    assert QUALITY_NAMES[80] == "1080P 高清"
    assert QUALITY_NAMES[74] == "720P60 高帧率"
    assert QUALITY_NAMES[64] == "720P 高清"
    assert QUALITY_NAMES[32] == "480P 清晰"
    assert QUALITY_NAMES[16] == "360P 流畅"

    assert AUDIO_QUALITY_NAMES[30280] == "Hi-Res 128K"
    assert AUDIO_QUALITY_NAMES[30232] == "132K"
    assert AUDIO_QUALITY_NAMES[30255] == "杜比音频"
    assert AUDIO_QUALITY_NAMES[30250] == "杜比全景声"
    assert AUDIO_QUALITY_NAMES[30240] == "64K"
