# src/util/common/io/directory.py
"""目录路径管理 - platformdirs 替代 QStandardPaths

原 Directory 类含 GUI 工具方法(browse_directory/open_directory_in_explorer
等),CLI 版仅保留路径属性,GUI 工具方法已移除(待 Task 2 按需重新实现)。
"""
import os
import logging

try:
    from platformdirs import user_config_dir, user_data_dir
except ImportError:
    # 兜底,避免 platformdirs 未安装时 import 失败
    def user_config_dir(app: str) -> str:
        return os.path.expanduser(f"~/.config/{app}")

    def user_data_dir(app: str) -> str:
        return os.path.expanduser(f"~/.local/share/{app}")


logger = logging.getLogger(__name__)

_APP_NAME = "Bili23-Downloader"


class Directory:
    """跨平台目录路径管理

    提供 config_dir/data_dir/log_dir/cookie_path/task_db_path 等路径属性,
    __init__ 中确保所有目录存在。原 GUI 工具方法(browse_directory 等)已移除。
    """

    def __init__(self):
        # platformdirs 根据平台返回标准路径(Linux: ~/.config/、~/.local/share/;
        # Windows: %APPDATA%;macOS: ~/Library/Application Support)
        self.config_dir = user_config_dir(_APP_NAME)
        self.data_dir = user_data_dir(_APP_NAME)
        self.log_dir = os.path.join(self.data_dir, "logs")
        self.cookie_path = os.path.join(self.data_dir, "cookie.json")
        self.task_db_path = os.path.join(self.data_dir, "tasks.db")
        # 确保目录存在(文件路径的父目录也一并创建)
        for d in (self.config_dir, self.data_dir, self.log_dir):
            os.makedirs(d, exist_ok=True)


# 模块级单例,保持与原代码 `from util.common.io.directory import directory` 兼容
directory = Directory()
