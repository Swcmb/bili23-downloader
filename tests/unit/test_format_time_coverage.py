# tests/unit/test_format_time_coverage.py
"""format/time.py 覆盖率补强测试

覆盖 Time 类的静态方法:
- format_timestamp / from_timestamp / from_string / to_timestamp / timestamp_from_string
- format_srt_time / format_ass_time_by_ms / format_ass_time_by_seconds

异常路径通过 monkeypatch datetime.fromtimestamp / datetime.timestamp 触发。
"""
from datetime import datetime, timedelta, timezone

import pytest

from util.format.time import Time, _EPOCH, _normalize_timestamp, _normalize_datetime


# ==================================================================
# _normalize_timestamp
# ==================================================================

def test_normalize_timestamp_below_threshold_returns_unchanged():
    """秒级时间戳(绝对值 < 10^10)原样返回"""
    assert _normalize_timestamp(1700000000) == 1700000000
    assert _normalize_timestamp(-1000) == -1000


def test_normalize_timestamp_above_threshold_divides_by_1000():
    """毫秒级时间戳(绝对值 >= 10^10)除以 1000"""
    assert _normalize_timestamp(11_000_000_000) == 11_000_000
    assert _normalize_timestamp(-11_000_000_000) == -11_000_000


def test_normalize_timestamp_boundary_value_unchanged():
    """边界值 9_999_999_999 仍按秒处理"""
    assert _normalize_timestamp(9_999_999_999) == 9_999_999_999


# ==================================================================
# _normalize_datetime
# ==================================================================

def test_normalize_datetime_naive_returns_unchanged():
    """无时区信息的 datetime 原样返回"""
    naive = datetime(2026, 1, 1, 12, 0, 0)
    assert _normalize_datetime(naive) is naive


def test_normalize_datetime_aware_strips_tzinfo():
    """带时区信息的 datetime 移除 tzinfo"""
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = _normalize_datetime(aware)
    assert result.tzinfo is None
    assert result.year == 2026 and result.hour == 12


# ==================================================================
# Time.format_timestamp / from_timestamp
# ==================================================================

def test_format_timestamp_default_format():
    """默认格式 %Y-%m-%d %H:%M:%S"""
    # 1700000000 = 2023-11-14 22:13:20 UTC(本地时区不影响结构)
    formatted = Time.format_timestamp(1700000000)
    # 校验长度与分隔符结构
    assert len(formatted) == 19
    assert formatted[4] == "-" and formatted[7] == "-"
    assert formatted[10] == " " and formatted[13] == ":" and formatted[16] == ":"


def test_format_timestamp_custom_format():
    """自定义格式生效"""
    formatted = Time.format_timestamp(1700000000, fmt="%Y/%m/%d")
    assert formatted[4] == "/" and formatted[7] == "/"


def test_from_timestamp_seconds_path():
    """秒级时间戳返回 datetime 对象"""
    result = Time.from_timestamp(0)
    assert isinstance(result, datetime)
    assert result == datetime.fromtimestamp(0)


def test_from_timestamp_milliseconds_path():
    """毫秒级时间戳自动归一化为秒"""
    ts_ms = 1_700_000_000_000
    result = Time.from_timestamp(ts_ms)
    assert result == datetime.fromtimestamp(ts_ms / 1000)


def test_from_timestamp_fallback_on_overflow(monkeypatch):
    """fromtimestamp 抛 OverflowError 时回退到 _EPOCH + timedelta"""
    # datetime 是不可变类型,需替换整个类引用
    class _FakeDateTime:
        @staticmethod
        def fromtimestamp(_ts):
            raise OverflowError("overflow")

    monkeypatch.setattr("util.format.time.datetime", _FakeDateTime)
    result = Time.from_timestamp(100)
    # 回退分支:_EPOCH + 100 秒(_EPOCH 在导入时已构造,不受替换影响)
    assert result == _EPOCH + timedelta(seconds=100)


def test_from_timestamp_fallback_on_oserror(monkeypatch):
    """fromtimestamp 抛 OSError 时也走回退分支"""
    class _FakeDateTime:
        @staticmethod
        def fromtimestamp(_ts):
            raise OSError("os error")

    monkeypatch.setattr("util.format.time.datetime", _FakeDateTime)
    result = Time.from_timestamp(50)
    assert result == _EPOCH + timedelta(seconds=50)


def test_from_timestamp_fallback_on_value_error(monkeypatch):
    """fromtimestamp 抛 ValueError 时也走回退分支"""
    class _FakeDateTime:
        @staticmethod
        def fromtimestamp(_ts):
            raise ValueError("bad value")

    monkeypatch.setattr("util.format.time.datetime", _FakeDateTime)
    result = Time.from_timestamp(50)
    assert result == _EPOCH + timedelta(seconds=50)


# ==================================================================
# Time.from_string / to_timestamp / timestamp_from_string
# ==================================================================

def test_from_string_default_format():
    """默认格式 %Y-%m-%d %H:%M:%S 解析字符串"""
    result = Time.from_string("2026-03-07 12:00:00")
    assert result == datetime(2026, 3, 7, 12, 0, 0)


def test_from_string_custom_format():
    """自定义格式解析"""
    result = Time.from_string("2026/03/07", fmt="%Y/%m/%d")
    assert result == datetime(2026, 3, 7)


def test_to_timestamp_naive_datetime():
    """无时区 datetime 调用 timestamp()"""
    dt = datetime(2026, 1, 1, 0, 0, 0)
    assert Time.to_timestamp(dt) == dt.timestamp()


def test_to_timestamp_fallback_on_overflow(monkeypatch):
    """timestamp() 抛 OverflowError 时回退到 (_normalize_datetime - _EPOCH)"""
    # datetime 实例方法不可直接 patch,用一个子类替换
    original_datetime = datetime

    class _FakeDateTime(original_datetime):
        def timestamp(self):
            raise OverflowError("overflow")

    monkeypatch.setattr("util.format.time.datetime", _FakeDateTime)
    # 构造实例必须用 _FakeDateTime 才会触发 timestamp 异常
    dt = _FakeDateTime(2026, 1, 1, 0, 0, 0)
    result = Time.to_timestamp(dt)
    expected = (original_datetime(2026, 1, 1, 0, 0, 0) - _EPOCH).total_seconds()
    assert result == expected


def test_timestamp_from_string_roundtrip():
    """字符串 -> datetime -> 时间戳"""
    ts = Time.timestamp_from_string("2026-03-07 12:00:00")
    expected_dt = datetime(2026, 3, 7, 12, 0, 0)
    assert ts == expected_dt.timestamp()


# ==================================================================
# Time.format_srt_time
# ==================================================================

def test_format_srt_time_zero():
    """零秒 -> 00:00:00,000"""
    assert Time.format_srt_time(0) == "00:00:00,000"


def test_format_srt_time_simple():
    """普通秒数"""
    # 1h 2m 3.456s
    assert Time.format_srt_time(3723.456) == "01:02:03,456"


def test_format_srt_time_millisecond_rounding_rolls_seconds():
    """ms 四舍五入到 1000 时进位到秒"""
    # 1.9995s -> ms=2000(实际四舍五入后),需进位 -> 00:00:02,000
    assert Time.format_srt_time(1.9995) == "00:00:02,000"


def test_format_srt_time_minute_rollover():
    """秒数累计到 60 时进位到分钟"""
    # 59.9999s -> ms 四舍五入为 1000 -> s+=1=60 -> m+=1
    assert Time.format_srt_time(59.9999) == "00:01:00,000"


def test_format_srt_time_hour_rollover():
    """分钟累计到 60 时进位到小时"""
    # 3599.9999s -> ms 四舍五入为 1000 -> s/m/h 连续进位
    assert Time.format_srt_time(3599.9999) == "01:00:00,000"


# ==================================================================
# Time.format_ass_time_by_ms
# ==================================================================

def test_format_ass_time_by_ms_zero():
    """0 ms -> 0:00:00.00"""
    assert Time.format_ass_time_by_ms(0) == "0:00:00.00"


def test_format_ass_time_by_ms_simple():
    """1h 2m 3s 456ms -> 1:02:03.46(centis=46)"""
    ms = 3600 * 1000 + 2 * 60 * 1000 + 3 * 1000 + 456
    assert Time.format_ass_time_by_ms(ms) == "1:02:03.46"


def test_format_ass_time_by_ms_centis_clamped_to_99():
    """ms 末位四舍五入后等于 100 时,clamp 到 99"""
    # 995ms -> centis = round(995/10) = 100 -> clamp 99
    assert Time.format_ass_time_by_ms(995) == "0:00:00.99"


def test_format_ass_time_by_ms_with_hours():
    """超过 1 小时"""
    # 1h30m -> 5400000 ms
    assert Time.format_ass_time_by_ms(5400000) == "1:30:00.00"


# ==================================================================
# Time.format_ass_time_by_seconds
# ==================================================================

def test_format_ass_time_by_seconds_zero():
    """0 秒 -> 0:00:00.00"""
    assert Time.format_ass_time_by_seconds(0) == "0:00:00.00"


def test_format_ass_time_by_seconds_with_centis():
    """带厘秒的格式"""
    # 1.25s -> 0:00:01.25
    assert Time.format_ass_time_by_seconds(1.25) == "0:00:01.25"


def test_format_ass_time_by_seconds_rollover_minute():
    """秒数进位到分钟"""
    # 59.9999s -> cs=100 -> 进位 s=60 -> m=1, s=0, cs=0
    assert Time.format_ass_time_by_seconds(59.9999) == "0:01:00.00"


def test_format_ass_time_by_seconds_rollover_hour():
    """分钟进位到小时"""
    # 3599.9999s -> 1:00:00.00
    assert Time.format_ass_time_by_seconds(3599.9999) == "1:00:00.00"
