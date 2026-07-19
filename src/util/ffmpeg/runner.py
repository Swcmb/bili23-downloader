# src/util/ffmpeg/runner.py
"""FFmpeg 命令执行器 - 纯 Python 实现,替代原 Qt 线程化执行器

改造要点:
- 移除 PySide6 导入
- FFmpegRunner 继承 object(原 Qt 线程类)
- finished_signal/error_signal 从 Qt 类级 Signal 改为实例级 Signal
- start() 用 threading.Thread 在后台调用 run()(替代原 Qt 线程启动)
- terminate() 仅终止子进程(原 Qt 线程 terminate 已移除)
"""
from ..common.translator import Translator
from ..common.signal_bus import Signal

from .command import FFmpegCommand

from typing import Optional, List
import subprocess
import os
import threading


class FFmpegRunner:
    """FFmpeg 命令执行器,基于 subprocess.Popen

    原为 Qt 线程子类,改造为纯 Python 类:
    - finished_signal/error_signal 为实例级 Signal(原 Qt 类级 Signal)
    - start() 在后台线程执行 run()(替代原 Qt 线程自动建线程)
    - terminate() 终止子进程(原 Qt 线程 terminate 已移除)
    """

    def __init__(self, cmd: List[str], parent=None):
        # parent 参数保留以兼容原 API(Qt 对象父子关系已移除)
        self._cmd = cmd
        self._cwd = None
        self._proc: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        # 实例级 Signal(原 Qt 类级 Signal 的纯 Python 等价)
        self.finished_signal = Signal(int, str, str)  # return_code, stdout, stderr
        self.error_signal = Signal(Exception, str, str)  # exception, stdout, stderr

    @classmethod
    def from_command(cls, command: FFmpegCommand, parent=None):
        return cls(command.build(), parent=parent)

    def set_cwd(self, cwd: str):
        self._cwd = cwd
        return self

    def start(self):
        """在后台线程中执行 run()(替代原 Qt 线程自动建线程)"""
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()

    def run(self):
        return_code = -1
        stdout = ""
        stderr = ""
        exception = None

        try:
            kwargs = {}

            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            self._proc = subprocess.Popen(
                self._cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self._cwd,
                text=True,
                encoding="utf-8",
                errors="replace",
                **kwargs
            )

            stdout, stderr = self._proc.communicate()
            return_code = self._proc.returncode

        except Exception as e:
            exception = e
            stdout = ""
            stderr = str(e)

        finally:
            if self._proc and self._proc.poll() is None:
                self._proc.terminate()

            self._proc = None

        if exception:
            self.error_signal.emit(RuntimeError(Translator.ERROR_MESSAGES("FFMPEG_FAILED")), stdout, stderr)
            return

        if return_code == 0:
            self.finished_signal.emit(return_code, stdout, stderr)
        else:
            self.error_signal.emit(RuntimeError(Translator.ERROR_MESSAGES("FFMPEG_FAILED_WITH_CODE").format(code=return_code)), stdout, stderr)

    def terminate(self):
        """终止子进程(原 super().terminate() 已移除)"""
        if self._proc:
            self._proc.terminate()
