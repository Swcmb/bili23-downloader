# tests/unit/test_timestamp.py
"""时间戳工具单元测试 - get_timestamp / get_timestamp_ms / get_timestamp_next_day

关键覆盖点:
- get_timestamp 返回 int 类型
- get_timestamp_ms 单调递增(快速连续调用必须递增)
- get_timestamp_next_day 返回明天 00:00:00 的 Unix 时间戳
"""
import time
from datetime import datetime, date, timedelta


def test_get_timestamp_is_int_seconds():
    """get_timestamp 返回秒级整数时间戳"""
    from util.common.timestamp import get_timestamp

    ts = get_timestamp()
    assert isinstance(ts, int)
    now = int(datetime.now().timestamp())
    assert abs(ts - now) < 5  # 容忍 5 秒漂移


def test_get_timestamp_ms_is_int_milliseconds():
    """get_timestamp_ms 返回毫秒级整数时间戳"""
    from util.common.timestamp import get_timestamp_ms

    ts_ms = get_timestamp_ms()
    assert isinstance(ts_ms, int)
    now_ms = int(datetime.now().timestamp() * 1000)
    assert abs(ts_ms - now_ms) < 5000  # 容忍 5 秒漂移


def test_get_timestamp_ms_monotonic_increment():
    """快速连续调用 get_timestamp_ms 必须单调递增(避免 ID 冲突)"""
    from util.common.timestamp import get_timestamp_ms

    samples = [get_timestamp_ms() for _ in range(100)]
    # 严格大于:每个样本都应大于前一个
    for prev, cur in zip(samples, samples[1:]):
        assert cur > prev, f"非单调递增: prev={prev}, cur={cur}"


def test_get_timestamp_ms_after_reset_module():
    """模块重新加载后,_last_timestamp_ms 重置为 0,首返回当前时间"""
    import importlib
    import util.common.timestamp as ts_module

    # 强制重置内部状态
    ts_module._last_timestamp_ms = 0
    ts1 = ts_module.get_timestamp_ms()
    now_ms = int(datetime.now().timestamp() * 1000)
    assert abs(ts1 - now_ms) < 5000


def test_get_timestamp_next_day():
    """get_timestamp_next_day 返回明天 00:00:00 的 Unix 时间戳"""
    from util.common.timestamp import get_timestamp_next_day

    ts_tomorrow = get_timestamp_next_day()
    # 计算预期值:今天 00:00 + 1 天
    today_midnight = datetime.combine(date.today(), datetime.min.time())
    expected = int((today_midnight + timedelta(days=1)).timestamp())
    assert ts_tomorrow == expected


def test_get_timestamp_next_day_is_at_midnight():
    """get_timestamp_next_day 返回的时间戳对应明天 00:00:00(本地时区)"""
    from util.common.timestamp import get_timestamp_next_day

    ts = get_timestamp_next_day()
    tomorrow_midnight = datetime.fromtimestamp(ts)
    assert tomorrow_midnight.hour == 0
    assert tomorrow_midnight.minute == 0
    assert tomorrow_midnight.second == 0
    # 与今天日期相差 1 天
    assert tomorrow_midnight.date() == date.today() + timedelta(days=1)
