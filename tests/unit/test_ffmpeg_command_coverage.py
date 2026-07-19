# tests/unit/test_ffmpeg_command_coverage.py
"""ffmpeg/command.py 覆盖率补强测试

覆盖 FFmpegCommand 的所有方法:
- 实例方法:add_input / add_output / add_param / build(返回链式调用 + 命令顺序)
- 类方法工厂:merge_video_audio (有/无封面)
                merge_video_parts (有/无封面)
                convert_m4a_to_mp3
                fix_mp4_box
"""
from util.ffmpeg.command import FFmpegCommand


# ==================================================================
# 实例方法 - 链式调用与 build
# ==================================================================

def test_add_input_returns_self_for_chaining():
    cmd = FFmpegCommand()
    assert cmd.add_input("a.mp4") is cmd


def test_add_output_returns_self_for_chaining():
    cmd = FFmpegCommand()
    assert cmd.add_output("o.mp4") is cmd


def test_add_param_returns_self_for_chaining():
    cmd = FFmpegCommand()
    assert cmd.add_param("-c", "copy") is cmd


def test_build_empty_command():
    """空命令仅包含 ['ffmpeg', '-y']"""
    cmd = FFmpegCommand()
    assert cmd.build() == ["ffmpeg", "-y"]


def test_build_with_single_input_and_output():
    cmd = FFmpegCommand().add_input("input.mp4").add_output("output.mp4")
    assert cmd.build() == ["ffmpeg", "-y", "-i", "input.mp4", "output.mp4"]


def test_build_with_multiple_inputs():
    """多输入按顺序追加"""
    cmd = (
        FFmpegCommand()
        .add_input("a.mp4")
        .add_input("b.m4a")
        .add_output("out.mp4")
    )
    assert cmd.build() == [
        "ffmpeg", "-y",
        "-i", "a.mp4",
        "-i", "b.m4a",
        "out.mp4",
    ]


def test_build_with_params_inserted_before_output():
    """params 在 inputs 之后、outputs 之前"""
    cmd = (
        FFmpegCommand()
        .add_input("in.mp4")
        .add_param("-c", "copy")
        .add_output("out.mp4")
    )
    assert cmd.build() == [
        "ffmpeg", "-y",
        "-i", "in.mp4",
        "-c", "copy",
        "out.mp4",
    ]


def test_add_param_multiple_args_extend_in_order():
    """add_param 一次性接收多个参数,按顺序 extend 到 params"""
    cmd = FFmpegCommand().add_param("-f", "concat", "-safe", "0")
    assert cmd.params == ["-f", "concat", "-safe", "0"]


# ==================================================================
# merge_video_audio - 无封面
# ==================================================================

def test_merge_video_audio_without_cover():
    cmd = FFmpegCommand.merge_video_audio("v.mp4", "a.m4a", "out.mp4")
    assert cmd.build() == [
        "ffmpeg", "-y",
        "-i", "v.mp4",
        "-i", "a.m4a",
        "-c:v", "copy",
        "-c:a", "copy",
        "out.mp4",
    ]


# ==================================================================
# merge_video_audio - 有封面
# ==================================================================

def test_merge_video_audio_with_cover():
    cmd = FFmpegCommand.merge_video_audio("v.mp4", "a.m4a", "out.mp4", cover_path="c.png")
    built = cmd.build()
    # 命令结构:ffmpeg -y -i v -i a -i c [params] out
    assert built[:6] == ["ffmpeg", "-y", "-i", "v.mp4", "-i", "a.m4a"]
    assert built[6:8] == ["-i", "c.png"]
    assert built[-1] == "out.mp4"
    # 关键参数成对存在
    param_pairs = list(zip(built[8:-1:2], built[9:-1:2]))
    assert ("-map", "0:v:0") in param_pairs
    assert ("-map", "1:a:0") in param_pairs
    assert ("-map", "2:v:0") in param_pairs
    assert ("-c:v", "copy") in param_pairs
    assert ("-c:a", "copy") in param_pairs
    assert ("-c:v:1", "png") in param_pairs
    assert ("-disposition:v:1", "attached_pic") in param_pairs
    assert ("-pix_fmt:v:1", "rgba") in param_pairs


# ==================================================================
# merge_video_parts - concat 模式
# ==================================================================

def test_merge_video_parts_without_cover():
    cmd = FFmpegCommand.merge_video_parts("list.txt", "out.mp4")
    assert cmd.build() == [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "list.txt",
        "-c:v", "copy",
        "-c:a", "copy",
        "out.mp4",
    ]


def test_merge_video_parts_with_cover():
    cmd = FFmpegCommand.merge_video_parts("list.txt", "out.mp4", cover_path="c.png")
    built = cmd.build()
    # 命令结构:ffmpeg -y -i c -f concat -safe 0 -i list [params] out
    assert built[:4] == ["ffmpeg", "-y", "-i", "c.png"]
    assert built[4:8] == ["-f", "concat", "-safe", "0"]
    assert built[8:10] == ["-i", "list.txt"]
    assert built[-1] == "out.mp4"
    # 关键参数
    param_pairs = list(zip(built[10:-1:2], built[11:-1:2]))
    assert ("-c:v", "copy") in param_pairs
    assert ("-c:a", "copy") in param_pairs
    assert ("-map", "1:v:0") in param_pairs
    assert ("-map", "0:v:0") in param_pairs
    assert ("-c:v:1", "png") in param_pairs
    assert ("-disposition:v:1", "attached_pic") in param_pairs
    assert ("-pix_fmt:v:1", "rgba") in param_pairs


# ==================================================================
# convert_m4a_to_mp3
# ==================================================================

def test_convert_m4a_to_mp3():
    cmd = FFmpegCommand.convert_m4a_to_mp3("in.m4a", "out.mp3")
    assert cmd.build() == [
        "ffmpeg", "-y",
        "-i", "in.m4a",
        "-c:a", "libmp3lame",
        "-q:a", "2",
        "out.mp3",
    ]


# ==================================================================
# fix_mp4_box
# ==================================================================

def test_fix_mp4_box():
    cmd = FFmpegCommand.fix_mp4_box("in.mp4", "out.mp4")
    assert cmd.build() == [
        "ffmpeg", "-y",
        "-i", "in.mp4",
        "-c", "copy",
        "-movflags", "+faststart",
        "out.mp4",
    ]


# ==================================================================
# 链式调用与多次 build 不互相影响
# ==================================================================

def test_build_can_be_called_multiple_times():
    """build 不修改内部状态,可多次调用"""
    cmd = FFmpegCommand().add_input("a.mp4").add_output("o.mp4")
    first = cmd.build()
    second = cmd.build()
    assert first == second
