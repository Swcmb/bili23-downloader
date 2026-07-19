# tests/unit/test_format_units_coverage.py
"""format/units.py 覆盖率补强测试

覆盖 Units 类所有静态/类方法,包含边界条件:
- format_episode_duration (None / 0 / 正常)
- unformat_episode_duration (3/2/1/其他 段)
- format_duration (有/无小时)
- format_file_size (B/KB/MB/GB/TB/PB/EB 边界)
- format_bitrate (0 / 1 / Kbps / Mbps / Gbps 边界)
- format_frame_rate (0 / 普通)
- format_speed (0 / 普通)
"""
from util.format.units import Units


# ==================================================================
# format_episode_duration
# ==================================================================

def test_format_episode_duration_none_returns_placeholder():
    assert Units.format_episode_duration(None) == "--:--"


def test_format_episode_duration_zero_returns_empty():
    assert Units.format_episode_duration(0) == ""


def test_format_episode_duration_positive_delegates_to_format_duration():
    assert Units.format_episode_duration(125) == "02:05"
    assert Units.format_episode_duration(3725) == "01:02:05"


# ==================================================================
# unformat_episode_duration
# ==================================================================

def test_unformat_episode_duration_three_parts():
    """HH:MM:SS -> 总秒数"""
    assert Units.unformat_episode_duration("01:02:03") == 3723


def test_unformat_episode_duration_two_parts():
    """MM:SS -> 总秒数"""
    assert Units.unformat_episode_duration("05:30") == 330


def test_unformat_episode_duration_one_part():
    """SS -> 总秒数"""
    assert Units.unformat_episode_duration("45") == 45


def test_unformat_episode_duration_zero_value():
    """单段为 0 时返回 0"""
    assert Units.unformat_episode_duration("0") == 0


def test_unformat_episode_duration_many_parts_falls_through():
    """超过 3 段时 fall through 到 else 返回 0"""
    assert Units.unformat_episode_duration("01:02:03:04") == 0


# ==================================================================
# format_duration
# ==================================================================

def test_format_duration_under_one_hour():
    """不足 1 小时 -> MM:SS"""
    assert Units.format_duration(125) == "02:05"
    assert Units.format_duration(0) == "00:00"


def test_format_duration_above_one_hour():
    """超过 1 小时 -> HH:MM:SS"""
    assert Units.format_duration(3725) == "01:02:05"


def test_format_duration_pads_with_zeros():
    """单数字补 0"""
    assert Units.format_duration(5) == "00:05"
    assert Units.format_duration(65) == "01:05"


# ==================================================================
# format_file_size
# ==================================================================

def test_format_file_size_bytes():
    assert Units.format_file_size(0) == "0.00 B"
    assert Units.format_file_size(512) == "512.00 B"


def test_format_file_size_kb_boundary():
    """1023 B 仍是 B,1024 B 升 KB"""
    assert Units.format_file_size(1023) == "1023.00 B"
    assert Units.format_file_size(1024) == "1.00 KB"


def test_format_file_size_mb():
    assert Units.format_file_size(1024 * 1024) == "1.00 MB"
    assert Units.format_file_size(1536 * 1024) == "1.50 MB"


def test_format_file_size_gb():
    assert Units.format_file_size(1024 ** 3) == "1.00 GB"


def test_format_file_size_tb():
    assert Units.format_file_size(1024 ** 4) == "1.00 TB"


def test_format_file_size_pb():
    assert Units.format_file_size(1024 ** 5) == "1.00 PB"


def test_format_file_size_eb_upper_bound():
    """超过 PB 范围继续进位到 EB(已是最大单位)"""
    assert Units.format_file_size(1024 ** 6) == "1.00 EB"
    # 远超 EB 不再升位
    assert Units.format_file_size(1024 ** 8).endswith(" EB")


# ==================================================================
# format_bitrate
# ==================================================================

def test_format_bitrate_zero_returns_empty():
    assert Units.format_bitrate(0) == ""


def test_format_bitrate_below_kbps():
    assert Units.format_bitrate(500) == "500.00 bps"


def test_format_bitrate_kbps_boundary():
    assert Units.format_bitrate(999) == "999.00 bps"
    assert Units.format_bitrate(1000) == "1.00 Kbps"


def test_format_bitrate_mbps():
    assert Units.format_bitrate(1_500_000) == "1.50 Mbps"


def test_format_bitrate_gbps():
    assert Units.format_bitrate(1_000_000_000) == "1.00 Gbps"


def test_format_bitrate_ebps_upper_bound():
    """超过 Tbps/Pbps/Ebps 进位到 Ebps(已是最大单位)"""
    large = 1000 ** 6
    assert Units.format_bitrate(large) == "1.00 Ebps"
    assert Units.format_bitrate(large * 1000).endswith(" Ebps")


# ==================================================================
# format_frame_rate
# ==================================================================

def test_format_frame_rate_zero_returns_empty():
    assert Units.format_frame_rate(0) == ""


def test_format_frame_rate_float():
    assert Units.format_frame_rate(29.97) == "30.0 fps"
    assert Units.format_frame_rate(60) == "60.0 fps"


# ==================================================================
# format_speed
# ==================================================================

def test_format_speed_zero_returns_empty():
    assert Units.format_speed(0) == ""


def test_format_speed_byte_per_second():
    assert Units.format_speed(1024) == "1.00 KB/s"


def test_format_speed_mb_per_second():
    assert Units.format_speed(2 * 1024 * 1024) == "2.00 MB/s"
