# tests/unit/test_subprocess_replacement.py
"""T2.3 验证 - merger.py 与 ffmpeg/runner.py 移除 Qt 依赖

测试目标:
- import merger 与 runner 模块不触发 PySide6 导入
- FFmpegRunner 使用 subprocess.Popen(而非 QProcess)
- Merger 不再继承 QObject
- FFmpegRunner 不再继承 QThread
"""
import sys


def _purge_pyside6():
    """清除已加载的 PySide6 模块,确保测试从干净状态开始"""
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]


def test_no_pyside6_import():
    """导入 merger 与 runner 模块时不应触发 PySide6 导入"""
    _purge_pyside6()
    # 同时清除已加载的相关模块,确保重新触发导入
    for mod in list(sys.modules.keys()):
        if mod.startswith("util.download") or mod.startswith("util.ffmpeg"):
            del sys.modules[mod]
    import util.download.downloader.merger  # noqa: F401
    import util.ffmpeg.runner  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules), \
        f"PySide6 模块被意外加载: {[m for m in sys.modules if m.startswith('PySide6')]}"


def test_ffmpeg_runner_uses_subprocess():
    """验证 ffmpeg 调用走 subprocess.Popen(而非 QProcess)"""
    import util.ffmpeg.runner as runner
    import inspect
    src = inspect.getsource(runner)
    assert "subprocess.Popen" in src or "subprocess.run" in src
    assert "QProcess" not in src
    assert "QThread" not in src


def test_merger_not_inherit_qobject():
    """Merger 不再继承 QObject"""
    from util.download.downloader.merger import Merger
    # 确保 MRO 中没有 QObject(通过类名检查,避免导入 PySide6)
    for base in Merger.__mro__:
        assert "QObject" not in type(base).__name__
        assert "QThread" not in type(base).__name__
    # Merger 应直接继承 object(纯 Python 类)
    assert object in Merger.__mro__


def test_ffmpeg_runner_not_inherit_qthread():
    """FFmpegRunner 不再继承 QThread"""
    from util.ffmpeg.runner import FFmpegRunner
    # 确保基类列表中不含 QThread
    for base in FFmpegRunner.__mro__:
        assert "QThread" not in type(base).__name__
    # 直接继承 object(纯 Python 类)
    assert object in FFmpegRunner.__mro__


def test_ffmpeg_runner_has_signals():
    """FFmpegRunner 实例应具有 finished_signal 与 error_signal 属性"""
    from util.ffmpeg.runner import FFmpegRunner
    from util.common.signal_bus import Signal
    runner = FFmpegRunner(["echo", "hello"])
    assert isinstance(runner.finished_signal, Signal)
    assert isinstance(runner.error_signal, Signal)
