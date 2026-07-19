# src/util/parse/additional/worker.py
"""附加文件解析 Worker - 去除 Qt 依赖

改造要点:
- 移除 `from PySide6.QtCore import QObject, Signal`
- AdditionalParseWorker 继承 `util.thread.worker_base.WorkerBase`
- SubtitlesParser / MetadataParser / DanmakuParser / CoverParser 改为延迟导入,
  避免触发 additional/file/danmaku_ass.py 与 network/request.py 的 PySide6 传递依赖
"""
import logging

from ...common.signal_bus import signal_bus
from ...common.translator import Translator
from ...common.enum import DownloadType
from ...thread.worker_base import WorkerBase

from ...download.task.info import TaskInfo

logger = logging.getLogger(__name__)


class AdditionalParseWorker(WorkerBase):
    """附加文件(弹幕/字幕/封面/元数据)解析 Worker"""

    def __init__(self, task_info: TaskInfo):
        WorkerBase.__init__(self)

        self.task_info = task_info

    def run(self):
        try:
            self.__parse()
            self.success.emit()

        except Exception as e:
            self.error.emit(str(e))

            logging.exception("附加文件解析失败")

        finally:
            self.finished.emit()

    def __parse(self):
        # 延迟导入附加解析器:它们通过 network.request / danmaku_ass 间接依赖 Qt
        from .subtitles import SubtitlesParser
        from .metadata import MetadataParser
        from .danmaku import DanmakuParser
        from .cover import CoverParser

        # 读取 Download Type 标志位，决定下载哪种类型的附加文件
        attr = self.task_info.Download.type

        if attr & DownloadType.DANMAKU != 0:
            # 下载弹幕
            self.update_status_label(Translator.TIP_MESSAGES("DOWNLOADING_DANMAKU"))

            parser = DanmakuParser(self.task_info)
            parser.parse()

        if attr & DownloadType.SUBTITLE != 0:
            # 下载字幕
            self.update_status_label(Translator.TIP_MESSAGES("DOWNLOADING_SUBTITLES"))

            parser = SubtitlesParser(self.task_info)
            parser.parse()

        if attr & DownloadType.COVER != 0:
            # 下载封面
            self.update_status_label(Translator.TIP_MESSAGES("DOWNLOADING_COVER"))

            parser = CoverParser(self.task_info)
            parser.parse()

        if attr & DownloadType.METADATA != 0:
            # 下载元数据
            self.update_status_label(Translator.TIP_MESSAGES("SCRAPING_METADATA"))

            parser = MetadataParser(self.task_info)
            parser.parse()

        self.update_status_label("")

    def update_status_label(self, label: str):
        self.task_info.Download.status_label = label

        # 发送信号通知界面更新下载项的显示信息
        signal_bus.download.update_downloading_item.emit(self.task_info)
