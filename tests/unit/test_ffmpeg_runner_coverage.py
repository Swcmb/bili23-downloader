# tests/unit/test_ffmpeg_runner_coverage.py
"""ffmpeg/runner.py 覆盖率补强测试

覆盖 FFmpegRunner 的所有方法 + 异常路径:
- __init__ / from_command
- set_cwd (链式返回 self)
- start (后台线程启动,触发 run)
- run:成功(return_code=0) / 失败(return_code!=0) / Popen 抛异常
- terminate:有 proc / 无 proc
"""
import subprocess
import threading

import pytest

from util.common.signal_bus import Signal
from util.ffmpeg.command import FFmpegCommand
from util.ffmpeg.runner import FFmpegRunner


# ==================================================================
# __init__ / from_command
# ==================================================================

def test_init_defaults():
    runner = FFmpegRunner(["ffmpeg", "-version"])
    assert runner._cmd == ["ffmpeg", "-version"]
    assert runner._cwd is None
    assert runner._proc is None
    assert runner._thread is None
    # finished_signal / error_signal 为 Signal 实例
    assert isinstance(runner.finished_signal, Signal)
    assert isinstance(runner.error_signal, Signal)


def test_init_accepts_parent_kwarg():
    """parent 参数仅用于兼容,不影响实例状态"""
    runner = FFmpegRunner(["echo"], parent="anything")
    assert runner._cmd == ["echo"]


def test_from_command_builds_cmd_from_ffmpeg_command():
    """from_command 接受 FFmpegCommand 实例并提取其 build 结果"""
    fc = FFmpegCommand().add_input("a.mp4").add_output("o.mp4")
    runner = FFmpegRunner.from_command(fc)
    assert runner._cmd == fc.build()


# ==================================================================
# set_cwd
# ==================================================================

def test_set_cwd_returns_self_for_chaining():
    runner = FFmpegRunner(["echo"])
    assert runner.set_cwd("/tmp") is runner
    assert runner._cwd == "/tmp"


# ==================================================================
# run - 成功路径 (return_code = 0)
# ==================================================================

class _FakePopen:
    """模拟 subprocess.Popen,可控 returncode / stdout / stderr"""

    def __init__(self, returncode=0, stdout="ok", stderr="", exc=None):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._exc = exc
        self._terminated = False

    def communicate(self):
        if self._exc:
            raise self._exc
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode

    def terminate(self):
        self._terminated = True


def _install_fake_popen(monkeypatch, returncode=0, stdout="ok", stderr="", exc=None):
    """安装 _FakePopen 到 runner 模块的 subprocess.Popen"""

    def _fake_popen(cmd, *args, **kwargs):
        return _FakePopen(returncode=returncode, stdout=stdout, stderr=stderr, exc=exc)

    monkeypatch.setattr("util.ffmpeg.runner.subprocess.Popen", _fake_popen)


def test_run_success_emits_finished_signal(monkeypatch):
    """return_code=0 触发 finished_signal"""
    _install_fake_popen(monkeypatch, returncode=0, stdout="done", stderr="")

    runner = FFmpegRunner(["ffmpeg"])
    received = []
    runner.finished_signal.connect(lambda code, out, err: received.append((code, out, err)))

    runner.run()

    assert len(received) == 1
    code, out, err = received[0]
    assert code == 0
    assert out == "done"
    assert err == ""
    # run 完成后 _proc 应被重置为 None
    assert runner._proc is None


def test_run_non_zero_return_code_emits_error_signal(monkeypatch):
    """return_code != 0 触发 error_signal"""
    _install_fake_popen(monkeypatch, returncode=1, stdout="", stderr="oops")

    runner = FFmpegRunner(["ffmpeg"])
    received = []
    runner.error_signal.connect(lambda exc, out, err: received.append((exc, out, err)))

    runner.run()

    assert len(received) == 1
    exc, out, err = received[0]
    assert isinstance(exc, RuntimeError)
    # conftest 中 Translator.ERROR_MESSAGES 被 patch 为返回首参,
    # 因此错误消息就是 "FFMPEG_FAILED_WITH_CODE" 字面值
    assert "FFMPEG_FAILED_WITH_CODE" in str(exc)
    assert err == "oops"
    assert runner._proc is None


def test_run_popen_raises_emits_error_signal(monkeypatch):
    """Popen 构造抛异常时触发 error_signal,stderr 含异常字符串"""
    _install_fake_popen(monkeypatch, exc=FileNotFoundError("ffmpeg not found"))

    runner = FFmpegRunner(["ffmpeg"])
    received = []
    runner.error_signal.connect(lambda exc, out, err: received.append((exc, out, err)))

    runner.run()

    assert len(received) == 1
    exc, out, err = received[0]
    assert isinstance(exc, RuntimeError)
    assert "ffmpeg not found" in err
    assert out == ""


# ==================================================================
# run - terminate 路径(proc 仍存活时调用 terminate)
# ==================================================================

class _FakePopenAlive:
    """模拟 Popen,communicate 后 poll 返回 None 表示仍在运行"""

    def __init__(self):
        self.returncode = 0
        self.terminated = False

    def communicate(self):
        return "ok", ""

    def poll(self):
        # 模拟 communicate 完成后进程仍在(异常场景)
        return None

    def terminate(self):
        self.terminated = True


def test_run_terminates_alive_proc_in_finally(monkeypatch):
    """finally 中若 _proc.poll() 仍为 None,则调用 terminate"""
    fake_proc = _FakePopenAlive()
    monkeypatch.setattr(
        "util.ffmpeg.runner.subprocess.Popen",
        lambda *a, **kw: fake_proc,
    )

    runner = FFmpegRunner(["ffmpeg"])
    runner.run()
    # 应被 terminate
    assert fake_proc.terminated
    # run 结束后 _proc 应为 None
    assert runner._proc is None


# ==================================================================
# terminate
# ==================================================================

def test_terminate_with_proc_calls_proc_terminate():
    """_proc 不为 None 时调用其 terminate"""
    fake_proc = _FakePopen()
    runner = FFmpegRunner(["ffmpeg"])
    runner._proc = fake_proc
    runner.terminate()
    assert fake_proc._terminated


def test_terminate_without_proc_is_noop():
    """_proc 为 None 时 terminate 不抛异常"""
    runner = FFmpegRunner(["ffmpeg"])
    # 不应抛异常
    runner.terminate()
    assert runner._proc is None


# ==================================================================
# start - 后台线程
# ==================================================================

def test_start_runs_in_background_thread(monkeypatch):
    """start 在后台线程中触发 run,主线程不阻塞"""
    _install_fake_popen(monkeypatch, returncode=0, stdout="ok")

    runner = FFmpegRunner(["ffmpeg"])
    received = []
    runner.finished_signal.connect(lambda *a: received.append(a))

    runner.start()
    # 主线程立即返回,_thread 应被设置
    assert runner._thread is not None
    # 等待后台线程结束(避免测试间竞争)
    runner._thread.join(timeout=5)
    assert not runner._thread.is_alive()
    assert len(received) == 1


def test_start_thread_is_daemon(monkeypatch):
    """后台线程应为 daemon,主进程退出时不阻塞"""
    _install_fake_popen(monkeypatch, returncode=0)
    runner = FFmpegRunner(["ffmpeg"])
    runner.start()
    assert runner._thread.daemon is True
    runner._thread.join(timeout=5)


# ==================================================================
# run 在 Windows 平台时设置 creationflags
# ==================================================================

def test_run_windows_sets_creationflags(monkeypatch):
    """os.name == 'nt' 时为 Popen 添加 creationflags"""
    captured = {}

    class _FakePopenWin:
        def __init__(self, cmd, *args, **kwargs):
            captured["kwargs"] = kwargs
            self.returncode = 0

        def communicate(self):
            return "ok", ""

        def poll(self):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr("util.ffmpeg.runner.subprocess.Popen", _FakePopenWin)
    monkeypatch.setattr("util.ffmpeg.runner.os.name", "nt")
    # CREATE_NO_WINDOW 常量在非 Windows 上仍可访问
    runner = FFmpegRunner(["ffmpeg"])
    runner.run()
    assert "creationflags" in captured["kwargs"]


def test_run_non_windows_does_not_set_creationflags(monkeypatch):
    """非 Windows 时 kwargs 不含 creationflags"""
    captured = {}

    class _FakePopenPosix:
        def __init__(self, cmd, *args, **kwargs):
            captured["kwargs"] = kwargs
            self.returncode = 0

        def communicate(self):
            return "ok", ""

        def poll(self):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr("util.ffmpeg.runner.subprocess.Popen", _FakePopenPosix)
    monkeypatch.setattr("util.ffmpeg.runner.os.name", "posix")
    runner = FFmpegRunner(["ffmpeg"])
    runner.run()
    assert "creationflags" not in captured["kwargs"]


# ==================================================================
# set_cwd + run 联动
# ==================================================================

def test_run_passes_cwd_to_popen(monkeypatch):
    """set_cwd 设置的目录被传入 Popen 的 cwd 参数"""
    captured = {}

    class _FakePopenCwd:
        def __init__(self, cmd, *args, **kwargs):
            captured["cwd"] = kwargs.get("cwd")
            self.returncode = 0

        def communicate(self):
            return "ok", ""

        def poll(self):
            return 0

        def terminate(self):
            pass

    monkeypatch.setattr("util.ffmpeg.runner.subprocess.Popen", _FakePopenCwd)
    runner = FFmpegRunner(["ffmpeg"]).set_cwd("/custom/dir")
    runner.run()
    assert captured["cwd"] == "/custom/dir"
