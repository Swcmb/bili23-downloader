# src/cli/exceptions.py
"""异常类与退出码定义(对应规格 7.1 节)

退出码约定:
- 3:  用户取消(Ctrl+C / 交互式取消)
- 4:  解析失败(URL 不识别 / 无可用分P)
- 5:  需要登录(Cookie 失效 / 未登录访问会员内容)
- 6:  网络错误(请求超时 / DNS 失败)
- 7:  磁盘空间不足
- 8:  FFmpeg 缺失
- 9:  配置错误(配置文件解析失败 / 字段非法)
- 70: 未分类的 Bili23 内部错误(基类默认)
"""


class Bili23Error(Exception):
    """所有 Bili23 CLI 内部异常的基类,退出码 70"""
    exit_code = 70


class ParseError(Bili23Error):
    """解析失败:URL 不识别或无可用分P"""
    exit_code = 4


class AuthRequiredError(Bili23Error):
    """需要登录:Cookie 失效或访问会员内容未登录"""
    exit_code = 5


class NetworkError(Bili23Error):
    """网络错误:请求超时或 DNS 失败"""
    exit_code = 6


class DiskFullError(Bili23Error):
    """磁盘空间不足"""
    exit_code = 7


class FFmpegMissingError(Bili23Error):
    """FFmpeg 缺失,无法合并音视频"""
    exit_code = 8


class ConfigError(Bili23Error):
    """配置错误:配置文件解析失败或字段非法"""
    exit_code = 9


class UserCancelledError(Bili23Error):
    """用户取消(Ctrl+C 或交互式取消)"""
    exit_code = 3
