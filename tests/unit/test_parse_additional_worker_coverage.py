# tests/unit/test_parse_additional_worker_coverage.py
"""T6 覆盖率补强 - src/util/parse/additional/worker.py

覆盖目标:
- AdditionalParseWorker.__init__
- AdditionalParseWorker.run(成功路径 + 异常路径 + signal emit)
- AdditionalParseWorker._AdditionalParseWorker__parse(各 DownloadType 分支组合)
- AdditionalParseWorker.update_status_label(更新状态标签 + emit 信号)

注意:source 中的 __parse 通过 `from .subtitles import SubtitlesParser` 等延迟导入,
而 .subtitles/.metadata/.danmaku/.cover 子模块本身依赖 network/protobuf 等无法在
测试环境加载。这里通过 `patch.dict(sys.modules, ...)` 注入 mock 模块来绕开。
"""
import sys
from unittest.mock import MagicMock, patch

from util.common.enum import DownloadType
from util.download.task.info import TaskInfo
from util.parse.additional.worker import AdditionalParseWorker


def _build_parser_mocks():
    """构造 4 个 fake parser 模块 + 实例,统一返回

    :return: (modules_dict, instances_dict) 二元组
        modules_dict: 用于 patch.dict(sys.modules)
        instances_dict: 各 parser 类对应的 mock 实例,用于断言
    """
    instances = {
        "danmaku": MagicMock(),
        "subtitles": MagicMock(),
        "cover": MagicMock(),
        "metadata": MagicMock(),
    }
    classes = {name: MagicMock(return_value=inst) for name, inst in instances.items()}

    modules = {
        "util.parse.additional.danmaku": MagicMock(DanmakuParser=classes["danmaku"]),
        "util.parse.additional.subtitles": MagicMock(SubtitlesParser=classes["subtitles"]),
        "util.parse.additional.cover": MagicMock(CoverParser=classes["cover"]),
        "util.parse.additional.metadata": MagicMock(MetadataParser=classes["metadata"]),
    }
    return modules, classes, instances


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------
def test_additional_parse_worker_init_defaults():
    """__init__ 应保存 task_info 并初始化三个信号"""
    task = TaskInfo()
    worker = AdditionalParseWorker(task)

    assert worker.task_info is task
    assert hasattr(worker, "success")
    assert hasattr(worker, "error")
    assert hasattr(worker, "finished")


# ---------------------------------------------------------------------------
# update_status_label
# ---------------------------------------------------------------------------
def test_update_status_label_sets_label_and_emits_signal():
    """update_status_label 应更新 task_info.Download.status_label 并 emit 信号"""
    task = TaskInfo()
    worker = AdditionalParseWorker(task)

    emitted = []
    with patch("util.parse.additional.worker.signal_bus") as fake_bus:
        fake_bus.download.update_downloading_item.emit.side_effect = lambda t: emitted.append(t)
        worker.update_status_label("downloading danmaku")

    assert task.Download.status_label == "downloading danmaku"
    assert emitted == [task]


def test_update_status_label_with_empty_string():
    """update_status_label 应支持空字符串(用于清空状态)"""
    task = TaskInfo()
    worker = AdditionalParseWorker(task)
    task.Download.status_label = "non-empty"

    with patch("util.parse.additional.worker.signal_bus") as fake_bus:
        worker.update_status_label("")

    assert task.Download.status_label == ""
    fake_bus.download.update_downloading_item.emit.assert_called_once_with(task)


# ---------------------------------------------------------------------------
# __parse - 各 DownloadType 分支
# ---------------------------------------------------------------------------
def test_parse_no_download_type_does_nothing_but_clears_label():
    """type=0 时不应实例化任何 parser,但应清空状态标签"""
    task = TaskInfo()
    task.Download.type = 0
    worker = AdditionalParseWorker(task)

    modules, classes, _ = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus") as fake_bus, \
         patch.dict(sys.modules, modules):
        worker._AdditionalParseWorker__parse()

    for cls in classes.values():
        cls.assert_not_called()
    assert task.Download.status_label == ""
    fake_bus.download.update_downloading_item.emit.assert_called_with(task)


def test_parse_danmaku_only():
    """仅 DANMAKU 标志位时应只实例化 DanmakuParser"""
    task = TaskInfo()
    task.Download.type = DownloadType.DANMAKU
    worker = AdditionalParseWorker(task)

    modules, classes, instances = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker._AdditionalParseWorker__parse()

    classes["danmaku"].assert_called_once_with(task)
    instances["danmaku"].parse.assert_called_once_with()
    for name in ("subtitles", "cover", "metadata"):
        classes[name].assert_not_called()


def test_parse_subtitle_only():
    """仅 SUBTITLE 标志位时应只实例化 SubtitlesParser"""
    task = TaskInfo()
    task.Download.type = DownloadType.SUBTITLE
    worker = AdditionalParseWorker(task)

    modules, classes, instances = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker._AdditionalParseWorker__parse()

    classes["subtitles"].assert_called_once_with(task)
    instances["subtitles"].parse.assert_called_once_with()
    for name in ("danmaku", "cover", "metadata"):
        classes[name].assert_not_called()


def test_parse_cover_only():
    """仅 COVER 标志位时应只实例化 CoverParser"""
    task = TaskInfo()
    task.Download.type = DownloadType.COVER
    worker = AdditionalParseWorker(task)

    modules, classes, instances = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker._AdditionalParseWorker__parse()

    classes["cover"].assert_called_once_with(task)
    instances["cover"].parse.assert_called_once_with()
    for name in ("danmaku", "subtitles", "metadata"):
        classes[name].assert_not_called()


def test_parse_metadata_only():
    """仅 METADATA 标志位时应只实例化 MetadataParser"""
    task = TaskInfo()
    task.Download.type = DownloadType.METADATA
    worker = AdditionalParseWorker(task)

    modules, classes, instances = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker._AdditionalParseWorker__parse()

    classes["metadata"].assert_called_once_with(task)
    instances["metadata"].parse.assert_called_once_with()
    for name in ("danmaku", "subtitles", "cover"):
        classes[name].assert_not_called()


def test_parse_all_four_types_combined():
    """同时启用 4 种类型时应依次实例化 4 个 parser 并执行 parse"""
    task = TaskInfo()
    task.Download.type = (
        DownloadType.DANMAKU | DownloadType.SUBTITLE
        | DownloadType.COVER | DownloadType.METADATA
    )
    worker = AdditionalParseWorker(task)

    modules, classes, instances = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker._AdditionalParseWorker__parse()

    for name, cls in classes.items():
        cls.assert_called_once_with(task)
    for inst in instances.values():
        inst.parse.assert_called_once_with()
    # 最终清空 status_label
    assert task.Download.status_label == ""


def test_parse_ignores_video_audio_flags():
    """VIDEO/AUDIO 标志位不应触发任何附加 parser"""
    task = TaskInfo()
    task.Download.type = DownloadType.VIDEO | DownloadType.AUDIO
    worker = AdditionalParseWorker(task)

    modules, classes, _ = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker._AdditionalParseWorker__parse()

    for cls in classes.values():
        cls.assert_not_called()


# ---------------------------------------------------------------------------
# run - 成功路径
# ---------------------------------------------------------------------------
def test_run_success_emits_success_and_finished():
    """run 成功路径应 emit success/finished"""
    task = TaskInfo()
    task.Download.type = 0  # 无附加任务,直接 success
    worker = AdditionalParseWorker(task)

    success_count = {"n": 0}
    finished_count = {"n": 0}
    worker.success.connect(lambda *a, **kw: success_count.__setitem__("n", success_count["n"] + 1))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    modules, _, _ = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker.run()

    assert success_count["n"] == 1
    assert finished_count["n"] == 1


def test_run_exception_emits_error_and_finished():
    """run 异常路径应 emit error/finished,不向上抛"""
    task = TaskInfo()
    task.Download.type = DownloadType.DANMAKU
    worker = AdditionalParseWorker(task)

    error_payload = []
    finished_count = {"n": 0}
    worker.error.connect(lambda e: error_payload.append(e))
    worker.finished.connect(lambda *a, **kw: finished_count.__setitem__("n", finished_count["n"] + 1))

    modules, classes, instances = _build_parser_mocks()
    instances["danmaku"].parse.side_effect = RuntimeError("danmaku failed")
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker.run()

    assert error_payload == ["danmaku failed"]
    assert finished_count["n"] == 1


def test_run_invokes_all_parsers_when_all_flags_set():
    """run + 4 标志位应依次调用 4 个 parser.parse"""
    task = TaskInfo()
    task.Download.type = (
        DownloadType.DANMAKU | DownloadType.SUBTITLE
        | DownloadType.COVER | DownloadType.METADATA
    )
    worker = AdditionalParseWorker(task)

    modules, classes, instances = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker.run()

    for cls in classes.values():
        cls.assert_called_once_with(task)
    for inst in instances.values():
        inst.parse.assert_called_once_with()


def test_run_status_label_transitions():
    """run 过程中 status_label 应经历各阶段后清空为 ''"""
    task = TaskInfo()
    task.Download.type = (
        DownloadType.DANMAKU | DownloadType.METADATA
    )
    worker = AdditionalParseWorker(task)
    labels_seen = []

    # 包装 update_status_label 以记录调用顺序
    original = worker.update_status_label

    def record(label):
        labels_seen.append(label)
        original(label)

    worker.update_status_label = record

    modules, _, _ = _build_parser_mocks()
    with patch("util.parse.additional.worker.signal_bus"), \
         patch.dict(sys.modules, modules):
        worker.run()

    # 期望:danmaku 阶段标签 -> metadata 阶段标签 -> 清空
    assert labels_seen == ["DOWNLOADING_DANMAKU", "SCRAPING_METADATA", ""]
