# src/util/misc/web.py
"""本地 HTML 文件浏览器打开工具 - 纯 Python 实现

T2.11 改造:
- 移除 GUI 框架依赖(原标准路径/文件/文本流工具)
- 临时目录改用 tempfile.gettempdir()
- 资源文件读取改用 Python 内置 open()(原资源系统 :/ 已移除)
- 浏览器打开仍用 webbrowser.open
"""
from pathlib import Path
import tempfile
import webbrowser
import logging
import os

logger = logging.getLogger(__name__)

# 资源 HTML 文件所在目录(相对当前模块定位)
# 当前模块路径:src/util/misc/web.py
# 资源路径:src/res/html/
_RES_HTML_DIR = Path(__file__).resolve().parent.parent.parent / "res" / "html"


class WebPage:
    """调用系统默认浏览器打开本地 HTML 文件的工具类"""

    @staticmethod
    def ensure_file_exists(file_name: str):
        """确保临时目录中存在指定的 HTML 文件,不存在则从包资源中复制

        :param file_name: 文件名(如 captcha.html)
        :return: 文件 file:// URI 字符串,失败返回 None
        """
        temp_dir = tempfile.gettempdir()
        file_path = Path(temp_dir, file_name)

        if not file_path.exists():
            # 从包内资源目录读取原文件
            source_path = _RES_HTML_DIR / file_name

            if not source_path.exists():
                logger.error("资源文件不存在: %s", source_path)
                return None

            try:
                content = source_path.read_text(encoding = "utf-8")
                with open(file_path, "w", encoding = "utf-8") as f:
                    f.write(content)
                logger.info("已将资源文件 %s 写入临时目录: %s", file_name, file_path)
            except OSError as e:
                logger.error("写入临时文件失败: %s,错误: %s", file_path, e)
                return None

        return file_path.as_uri()

    @staticmethod
    def open(file_name: str):
        """调用系统默认浏览器打开对应的 HTML 文件"""
        file_path = WebPage.ensure_file_exists(file_name)

        if file_path:
            result = webbrowser.open(file_path)

            if not result:
                logger.error("无法打开文件: %s", file_path)
