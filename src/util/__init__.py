# util 包初始化
# 注意:不在此处显式 import util.ffmpeg,避免在 import util.* 时
# 触发 ffmpeg/directory 等链式 Qt 依赖导入。
# 需要 ffmpeg 功能的代码应直接 `from util.ffmpeg import xxx`。
