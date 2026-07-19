# src/util/parse/worker.py
"""解析 Worker - 去除 Qt 依赖

改造要点:
- 移除 `from PySide6.QtCore import QObject, Signal, Slot`
- 原 PySide6 Signal 改为 `util.common.signal_bus.Signal`(纯 Python 回调)
- ParseWorker / ProgressParseWorker 继承 `util.thread.worker_base.WorkerBase`
- 文件内原有的解析器分发基类(原也命名为 WorkerBase)重命名为
  `ParserDispatcher`,以避免与 util.thread.worker_base.WorkerBase 命名冲突
- EpisodeData 改为延迟导入,避免触发 episode/tree.py 的 PySide6 传递依赖
- 移除 `@Slot()` 装饰器(纯 Python 无需信号槽机制)
- 移除 `self.deleteLater()`(QObject 专用,WorkerBase 不再支持)
"""
import logging
from threading import Event

from ..common.data.auto_parse import AutoParsePayload
from ..common.translator import Translator
from ..common.data import url_patterns
from ..common.enum import ParserType
from ..common.signal_bus import Signal
from ..thread.worker_base import WorkerBase

logger = logging.getLogger(__name__)


class ParserDispatcher:
    """解析器分发基类,提供 get_parser / get_parser_type"""

    def get_parser(self, parser_type: str):
        match parser_type:
            case "video":
                from .parser.video import VideoParser
                return VideoParser()

            case "bangumi":
                from .parser.bangumi import BangumiParser
                return BangumiParser()

            case "cheese":
                from .parser.cheese import CheeseParser
                return CheeseParser()

            case "space":
                from .parser.space import SpaceParser
                return SpaceParser()

            case "favlist":
                from .parser.favlist import FavlistParser
                return FavlistParser()

            case "list":
                from .parser.list import ListParser
                return ListParser()

            case "popular":
                from .parser.popular import PopularParser
                return PopularParser()

            case "watch_later":
                from .parser.watch_later import WatchLaterParser
                return WatchLaterParser()

            case "history":
                from .parser.history import HistoryParser
                return HistoryParser()

            case "audio":
                from .parser.audio import AudioParser
                return AudioParser()

            case _:
                raise ValueError("未知的解析类型")

    def get_parser_type(self, url: str):
        for parser_type, pattern in url_patterns:
            if pattern.search(url):
                return parser_type

        raise ValueError(Translator.ERROR_MESSAGES("INVALID_LINK"))


class ParseWorker(ParserDispatcher, WorkerBase):
    """解析 Worker,继承 ParserDispatcher(分发能力) + WorkerBase(信号/停止)"""

    def __init__(self, url: str, pn: int = 1):
        # 显式调用 WorkerBase.__init__ 初始化 success/error/finished 信号
        WorkerBase.__init__(self)

        self.url = url
        self.pn = pn
        self.parser_type = ""

    def run(self):
        # 延迟导入 EpisodeData,避免触发 episode/tree.py 的 PySide6 传递依赖
        from .episode.tree import EpisodeData

        EpisodeData.clear_cache()

        try:
            self.parser_type = self.get_parser_type(self.url)

            self.get_redirect_url()

            parser = self.get_parser(self.parser_type)

            parser.parse(self.url, self.pn)

            self.success.emit(parser.get_category_name(), parser.get_extra_data())

        except Exception as e:
            self.on_error()

            self.error.emit(str(e))

        finally:
            self.finished.emit()

    def get_redirect_url(self):
        from .parser.festival import FestivalParser
        from .parser.b23 import B23Parser

        _parsers = {
            "b23": B23Parser(),
            "festival": FestivalParser()
        }

        for parser_type, parser in _parsers.items():
            if parser_type in self.url:
                self.url = parser.parse(self.url)

                self.parser_type = self.get_parser_type(self.url)

    def on_error(self):
        logger.exception("解析失败")


class ProgressParseWorker(ParserDispatcher, WorkerBase):
    """后台解析线程,负责自动解析流程中的进度回传"""

    def __init__(self, info_data: AutoParsePayload):
        WorkerBase.__init__(self)

        self.data: AutoParsePayload = info_data
        self.stop_event = Event()
        # 额外的进度回调信号(WorkerBase 仅提供 success/error/finished)
        self.update_progress = Signal()

    def run(self):
        try:
            parser = self._get_parser()
            parser.parse()

            self.success.emit(parser.get_category_name(), {})

            logger.info("自动解析完成")

        except Exception as e:
            logger.exception("解析失败")

            self.error.emit(str(e))

        finally:
            self.finished.emit()

    def _get_parser(self):
        match self.data.parser_type:
            case ParserType.INTERACTIVE_VIDEO:
                return self._get_interactive_video_parser()

            case ParserType.DYNAMIC:
                return self._get_dynamic_parser()

            case ParserType.BATCH:
                return self._get_dynamic_parser()

        raise ValueError(f"Unsupported parser type: {self.data.parser_type}")

    def _get_interactive_video_parser(self):
        from .parser.video import InteractiveVideoParser

        return InteractiveVideoParser(self.data.data, self._update_progress_callback, self.stop_event)

    def _get_dynamic_parser(self):
        from .parser.dynamic import DynamicParser

        parser_type = self.get_parser_type(self.data.url)

        base_parser = self.get_parser(parser_type)

        return DynamicParser(self.data, base_parser, self._update_progress_callback, self.stop_event)

    def _update_progress_callback(self, text: str):
        self.update_progress.emit(text)

    def trigger_stop(self):
        self.stop_event.set()
