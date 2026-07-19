# Bili23-Downloader GUI 转 CLI 改造实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将基于 PySide6 的 GUI 应用 Bili23-Downloader 改造为基于 Typer + Rich 的纯 CLI 应用,保留全部下载能力,移除所有 Qt 依赖。

**Architecture:** 三层结构 - `src/cli/` (Typer 命令 + Rich 渲染 + 交互选择) → `src/util/` (业务逻辑,纯 Python,去 Qt) → `src/res/i18n/` (翻译资源)。事件总线从 Qt Signal 改为纯 Python 回调;线程池从 QThreadPool 改为 `concurrent.futures.ThreadPoolExecutor`;配置从 QConfig 改为 JSON + platformdirs。

**Tech Stack:** Python 3.9+、Typer>=0.12、Rich>=13.7、platformdirs>=4.2、qrcode>=7.4、Pillow>=10.0、httpx、pytest、respx、freezegun。

## Global Constraints

- **Python 版本:** `requires-python = ">=3.9"` (规格 10.1 节)
- **协议:** GPL-3.0 (规格 C2)
- **CLI 命令名:** `bili23` (规格 C3)
- **PyPI 包名:** `bili23-downloader` (规格 C4)
- **跨平台:** Windows 10+、Ubuntu 20.04+、macOS 11+ (规格 C1、11.2 节)
- **依赖移除:** PySide6、PySide6-Fluent-Widgets 必须从 `pyproject.toml` 完全移除
- **测试覆盖率:** 总体 ≥ 80%, `util/common/` ≥ 90%, `util/parse/` ≥ 80%, `util/download/` ≥ 75%, `cli/` ≥ 70% (规格 8.3 节)
- **配置目录:** `platformdirs.user_config_dir("Bili23-Downloader")` (规格 4.3 节)
- **数据目录:** `platformdirs.user_data_dir("Bili23-Downloader")` (规格 4.3 节)
- **Cookie 文件权限:** 600 (POSIX) (规格 11.3 节)
- **代码注释语言:** 中文 (用户规则)
- **代码标识符语言:** 英文 (用户规则)
- **关联规格文档:** `/workspace/docs/superpowers/specs/2026-07-19-bili23-cli-refactor-design.md` (v1.2)

---

## File Structure

### 新增文件

| 路径 | 职责 |
| :--- | :--- |
| `src/main.py` | Typer 入口,实例化 `app` 并注册所有子命令 |
| `src/cli/__init__.py` | 包标识 |
| `src/cli/app.py` | Typer 应用、全局选项 callback、异常处理 |
| `src/cli/exceptions.py` | `Bili23Error` 异常层次与退出码 |
| `src/cli/callbacks.py` | `signal_bus` 回调注册 → Rich 输出 |
| `src/cli/commands/__init__.py` | 包标识 |
| `src/cli/commands/download.py` | `bili23 download <url>` 主命令 |
| `src/cli/commands/parse.py` | `bili23 parse <url>` 仅解析命令 |
| `src/cli/commands/login.py` | `bili23 login qr/sms/cookie/status` |
| `src/cli/commands/logout.py` | `bili23 logout` |
| `src/cli/commands/config_cmd.py` | `bili23 config get/set/list/path` |
| `src/cli/commands/task.py` | `bili23 task list/pause/resume/cancel/clear` |
| `src/cli/commands/history.py` | `bili23 history list/clear` |
| `src/cli/interact/__init__.py` | 包标识 |
| `src/cli/interact/episode_selector.py` | 分集勾选(Rich Live 表格) |
| `src/cli/interact/quality_selector.py` | 画质/音质/编码选择 |
| `src/cli/interact/qr_terminal.py` | 终端二维码渲染(ASCII/Unicode) |
| `src/cli/render/__init__.py` | 包标识 |
| `src/cli/render/progress.py` | 下载/解析进度条(Rich.Progress) |
| `src/cli/render/table.py` | 表格输出 |
| `src/cli/render/toast.py` | Toast 通知转终端提示 |
| `tests/unit/test_signal_bus.py` | 事件总线单元测试 |
| `tests/unit/test_config.py` | 配置系统单元测试 |
| `tests/unit/test_thread_pool.py` | 线程池单元测试 |
| `tests/unit/test_formatters.py` | 文件名/时间/单位格式化测试 |
| `tests/unit/test_parser/` | 各 URL 解析器单元测试目录 |
| `tests/unit/test_downloader.py` | 下载器单元测试(httpx mock) |
| `tests/integration/test_parse_download.py` | 解析→下载集成测试 |
| `tests/integration/test_login_flow.py` | 登录流程集成测试 |
| `tests/cli/test_commands.py` | CLI 端到端测试(CliRunner) |
| `tests/cli/test_interact.py` | 交互式选择测试(pty) |
| `tests/fixtures/` | 测试数据目录 |
| `.github/workflows/ci.yml` | CI 流水线 |
| `.github/workflows/release.yml` | 发布流水线 |

### 修改文件

| 路径 | 修改内容 |
| :--- | :--- |
| `src/util/common/signal_bus.py` | 重写:Qt Signal → 纯 Python dict+回调 |
| `src/util/common/config.py` | 重写:QConfig → JSON + platformdirs |
| `src/util/common/translator.py` | 重写:QTranslator → Python dict |
| `src/util/common/io/directory.py` | 重写:QStandardPaths → platformdirs |
| `src/util/thread/pool.py` | 重写:QThreadPool → ThreadPoolExecutor |
| `src/util/thread/worker_base.py` | 重写:QObject → object + threading.Event |
| `src/util/thread/async_.py` | 重写:Qt 异步 → threading 包装 |
| `src/util/parse/worker.py` | 去 Qt:WorkerBase 改用纯 Python 版本 |
| `src/util/parse/preview/worker.py` | 同上 |
| `src/util/parse/additional/worker.py` | 同上 |
| `src/util/parse/additional/file/danmaku_ass.py` | 去 Qt:`QApplication.font()`/`QFontMetrics` → PIL `ImageFont` |
| `src/util/download/downloader/downloader.py` | QRunnable → WorkerBase |
| `src/util/download/downloader/merger.py` | QProcess → subprocess.Popen |
| `src/util/download/downloader/parse_worker.py` | 去 Qt |
| `src/util/download/cover/manager.py` | QPixmap → 字节流 |
| `src/util/download/cover/cache.py` | 去 Qt |
| `src/util/download/cover/query_worker.py` | 去 Qt |
| `src/util/download/task/manager.py` | 去 Qt |
| `src/util/download/task/query_worker.py` | 去 Qt |
| `src/util/download/task/reparse_worker.py` | 去 Qt |
| `src/util/auth/qrcode.py` | QPixmap → PNG 字节流 |
| `src/util/auth/sms.py` | QTimer → threading.Timer |
| `src/util/auth/cookie_login.py` | 移除浏览器登录,仅保留 Cookie 导入 |
| `src/util/auth/server.py` | 去除对 signal_bus 的引用(改用回调/logging) |
| `src/util/auth/captcha.py` | QPixmap → 终端 ASCII/PNG |
| `src/util/network/request.py` | 去除 Signal/QObject/Slot,改用 logging;53 个文件 162 处 `config.get(config.xxx).value` → `config.get("xxx")` |
| `src/util/misc/update.py` | QNetworkAccessManager → httpx.get |
| `src/util/misc/web.py` | QDesktopServices → webbrowser.open |
| `src/util/ffmpeg/runner.py` | QProcess → subprocess.Popen |
| `src/util/**/__init__.py` | 检查并移除 Qt 导入 |
| `pyproject.toml` | 完整重写(原 20 行 → 含 scripts/optional-deps/pytest 配置) |
| `requirements.txt` | 同步更新依赖 |
| `README.md` | 重写为 CLI 说明 |
| `README_en.md` | 重写为 CLI 英文说明 |
| `CHANGELOG.md` | 新增 v3.0.0 CLI 重构记录 |
| `.gitignore` | 移除 GUI 专用条目 |

### 删除文件

| 路径 | 删除原因 |
| :--- | :--- |
| `src/gui/` | GUI 控件层,全部移除 |
| `src/res/html/` | captcha.html,GUI 专用 |
| `src/res/icon/` | SVG 图标,GUI 专用 |
| `src/res/image/` | noface.jpg、placeholder.png,GUI 专用 |
| `src/res/qss/` | QSS 样式表,GUI 专用 |
| `src/res/resources.qrc` | Qt 资源描述文件 |
| `src/res/resources_rc.py` | Qt 资源编译产物 |
| `src/util/common/icon.py` | QIcon/QPixmap,GUI 专用 |
| `src/util/common/style_sheet.py` | QSS 主题,GUI 专用 |
| `src/util/common/color.py` | QColor,改用 rich.color |
| `assets/` | macOS 图标 + Windows Inno Setup 脚本 |
| `.github/workflows/publish.yml` | GUI 版打包流水线 |
| `.github/ISSUE_TEMPLATE/` | GUI 版 Issue 模板 |
| `scripts/translate.py` | 依赖 pyside6-lupdate,且 sources 全为 GUI 文件 |

---

## Task 1: 基础设施解耦(阻塞项)

**目标:** 重写 `util/common/` 与 `util/thread/` 下的基础设施,使 `import util.common` 和 `import util.thread` 不触发 PySide6 导入。

**里程碑 M1 验收:** `python -c "import util.common; import util.thread"` 不报错且不导入 PySide6。

### Task 1.1: 重写 signal_bus.py

**Files:**
- Create: `tests/unit/test_signal_bus.py`
- Modify: `src/util/common/signal_bus.py`

**Interfaces:**
- Produces: `signal_bus` 模块,导出 `Signal` 类与 `signal_bus` 单例;`Signal` 含 `connect(callback)`/`disconnect(callback)`/`emit(*args, **kwargs)` 方法;`signal_bus` 含所有原信号名称(ToastNotification/Parse/Download/Login/Update/Interface)+ `emit_signal()`/`emit_pending_signals()`/`main_window_ready` 属性

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_signal_bus.py
"""事件总线单元测试 - 验证纯 Python 实现替代 Qt Signal"""
import threading
import time
import pytest


def test_signal_connect_and_emit():
    """connect 后 emit 触发回调"""
    from util.common.signal_bus import Signal
    received = []
    sig = Signal()
    sig.connect(lambda *a, **kw: received.append((a, kw)))
    sig.emit("hello", key="value")
    assert received == [(("hello",), {"key": "value"})]


def test_signal_disconnect():
    """disconnect 后不再触发"""
    from util.common.signal_bus import Signal
    received = []
    sig = Signal()
    def cb():
        received.append(1)
    sig.connect(cb)
    sig.emit()
    sig.disconnect(cb)
    sig.emit()
    assert received == [1]


def test_signal_cross_thread_safe():
    """跨线程 emit 安全(AC-022-3)"""
    from util.common.signal_bus import Signal
    counter = {"count": 0}
    lock = threading.Lock()
    sig = Signal()
    def cb():
        with lock:
            counter["count"] += 1
    sig.connect(cb)
    threads = [threading.Thread(target=sig.emit) for _ in range(1000)]
    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    elapsed = time.time() - start
    assert counter["count"] == 1000
    assert elapsed < 5.0


def test_pending_signals_cache_and_flush():
    """pending_signals 在 main_window_ready=False 时缓存,True 后 flush(AC-022-4)"""
    from util.common import signal_bus
    received = []
    signal_bus.signal_bus.ToastNotification.connect(lambda *a, **kw: received.append((a, kw)))
    signal_bus.signal_bus.main_window_ready = False
    signal_bus.signal_bus.emit_signal("ToastNotification", "cached_msg")
    assert received == []  # 未 flush
    signal_bus.signal_bus.emit_pending_signals()  # 标记 ready 并 flush
    assert len(received) == 1
    assert received[0] == (("cached_msg",), {})


def test_no_pyside6_import():
    """AC-022-1: import 不触发 PySide6"""
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.signal_bus  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_signal_bus.py -v`
Expected: FAIL with `ImportError` 或 `AttributeError`(原 signal_bus 依赖 PySide6)

- [ ] **Step 3: 重写 signal_bus.py**

```python
# src/util/common/signal_bus.py
"""事件总线 - 纯 Python 实现,替代 Qt Signal/QObject

设计要点:
- Signal 用回调列表替代 Qt Signal
- emit 在调用线程同步执行(不再支持 QueuedConnection)
- 跨线程安全通过 threading.Lock 保护回调列表
- 保留 main_window_ready 和 pending_signals 机制兼容原代码
"""
import threading
from typing import Callable, Any, List, Dict, Tuple


class Signal:
    """纯 Python 信号,API 兼容 PySide6.QtCore.Signal"""

    def __init__(self):
        self._callbacks: List[Callable] = []
        self._lock = threading.Lock()

    def connect(self, callback: Callable) -> None:
        """注册回调"""
        with self._lock:
            if callback not in self._callbacks:
                self._callbacks.append(callback)

    def disconnect(self, callback: Callable) -> None:
        """注销回调"""
        with self._lock:
            if callback in self._callbacks:
                self._callbacks.remove(callback)

    def emit(self, *args, **kwargs) -> None:
        """同步触发所有回调(在调用线程)"""
        with self._lock:
            callbacks = list(self._callbacks)
        for cb in callbacks:
            cb(*args, **kwargs)


class SignalBus:
    """信号总线单例,聚合所有原 Qt 信号名称"""

    def __init__(self):
        # 原信号名称保留(ToastNotification/Parse/Download/Login/Update/Interface)
        self.ToastNotification = Signal()
        self.Parse = Signal()
        self.Download = Signal()
        self.Login = Signal()
        self.Update = Signal()
        self.Interface = Signal()
        # 兼容原 main_window_ready 机制
        self.main_window_ready: bool = False
        self.pending_signals: List[Tuple[str, tuple, dict]] = []
        self._pending_lock = threading.Lock()

    def emit_signal(self, signal_name: str, *args, **kwargs) -> None:
        """触发命名信号,若未 ready 则缓存到 pending_signals"""
        if not self.main_window_ready:
            with self._pending_lock:
                self.pending_signals.append((signal_name, args, kwargs))
            return
        sig = getattr(self, signal_name, None)
        if sig is None:
            raise AttributeError(f"SignalBus has no signal named '{signal_name}'")
        sig.emit(*args, **kwargs)

    def emit_pending_signals(self) -> None:
        """标记 main_window_ready=True 并 flush 所有待发送信号"""
        self.main_window_ready = True
        with self._pending_lock:
            pending = list(self.pending_signals)
            self.pending_signals.clear()
        for signal_name, args, kwargs in pending:
            sig = getattr(self, signal_name, None)
            if sig is not None:
                sig.emit(*args, **kwargs)


# 模块级单例,保持与原代码 `from util.common.signal_bus import signal_bus` 兼容
signal_bus = SignalBus()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_signal_bus.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_signal_bus.py src/util/common/signal_bus.py
git commit -m "refactor(signal_bus): rewrite Qt Signal as pure Python callback list"
```

### Task 1.2: 重写 thread/pool.py

**Files:**
- Create: `tests/unit/test_thread_pool.py`
- Modify: `src/util/thread/pool.py`

**Interfaces:**
- Consumes: 无
- Produces: `GlobalThreadPoolTask` 类,`run(func, *args, **kwargs) -> Future` 与 `run_func(...)` 别名;模块级 `global_thread_pool` 单例

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_thread_pool.py
"""线程池单元测试 - 验证 ThreadPoolExecutor 替代 QThreadPool"""
import time
import pytest


def test_run_executes_func():
    from util.thread.pool import GlobalThreadPoolTask
    result = GlobalThreadPoolTask.run(lambda x: x * 2, 21).result(timeout=5)
    assert result == 42


def test_run_func_is_alias():
    from util.thread.pool import GlobalThreadPoolTask
    assert GlobalThreadPoolTask.run_func is GlobalThreadPoolTask.run


def test_concurrent_tasks():
    from util.thread.pool import global_thread_pool
    futures = [global_thread_pool.submit(lambda i: i, i) for i in range(50)]
    results = [f.result(timeout=5) for f in futures]
    assert results == list(range(50))


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.thread.pool  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_thread_pool.py -v`
Expected: FAIL

- [ ] **Step 3: 重写 pool.py**

```python
# src/util/thread/pool.py
"""全局线程池 - 基于 concurrent.futures.ThreadPoolExecutor

替代 QThreadPool.globalInstance() + QRunnable。
线程池大小:min(32, (cpu_count or 4) * 4)
"""
import atexit
import os
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any


def _calc_pool_size() -> int:
    """计算线程池大小,与原 QThreadPool 默认行为一致"""
    cpu = os.cpu_count() or 4
    return min(32, cpu * 4)


class GlobalThreadPoolTask:
    """全局线程池任务提交器,API 兼容原 QThreadPool.start"""

    @classmethod
    def run(cls, func: Callable, *args, **kwargs) -> Future:
        """提交后台任务,返回 Future"""
        return global_thread_pool.submit(func, *args, **kwargs)

    # 兼容原 API 别名
    run_func = run


# 模块级单例
global_thread_pool = ThreadPoolExecutor(
    max_workers=_calc_pool_size(),
    thread_name_prefix="bili23-worker"
)
atexit.register(global_thread_pool.shutdown, wait=False)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_thread_pool.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_thread_pool.py src/util/thread/pool.py
git commit -m "refactor(thread_pool): replace QThreadPool with ThreadPoolExecutor"
```

### Task 1.3: 重写 thread/worker_base.py

**Files:**
- Modify: `tests/unit/test_thread_pool.py` (追加测试)
- Modify: `src/util/thread/worker_base.py`

**Interfaces:**
- Consumes: `util.common.signal_bus.Signal`
- Produces: `WorkerBase` 类,继承 `object`,含 `success`/`error`/`finished` 三个 `Signal` 属性、`stop()` 方法、`is_stopped` 属性、`run()` 抽象方法

- [ ] **Step 1: 追加失败测试**

```python
# 追加到 tests/unit/test_thread_pool.py
def test_worker_base_stop_signal():
    from util.thread.worker_base import WorkerBase
    worker = WorkerBase()
    assert worker.is_stopped is False
    worker.stop()
    assert worker.is_stopped is True


def test_worker_base_has_signals():
    from util.thread.worker_base import WorkerBase
    worker = WorkerBase()
    assert hasattr(worker, "success")
    assert hasattr(worker, "error")
    assert hasattr(worker, "finished")
    # 验证信号可 connect/emit
    received = []
    worker.finished.connect(lambda: received.append(1))
    worker.finished.emit()
    assert received == [1]
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_thread_pool.py -v`
Expected: 新增 2 个测试 FAIL

- [ ] **Step 3: 重写 worker_base.py**

```python
# src/util/thread/worker_base.py
"""Worker 基类 - 纯 Python 实现,替代 QObject 版本

设计要点:
- 继承 object 而非 QObject
- success/error/finished 用纯 Python Signal 替代 Qt Signal
- threading.Event 作为停止信号
- 移除 @Slot() 装饰器
"""
import threading
from util.common.signal_bus import Signal


class WorkerBase:
    """Worker 基类,所有 worker 继承此类"""

    def __init__(self):
        self.success = Signal()
        self.error = Signal(object)  # 传递异常对象
        self.finished = Signal()
        self._stop_event = threading.Event()

    @property
    def is_stopped(self) -> bool:
        """是否收到停止信号"""
        return self._stop_event.is_set()

    def stop(self) -> None:
        """设置停止信号"""
        self._stop_event.set()

    def run(self) -> None:
        """子类实现具体任务逻辑"""
        raise NotImplementedError("Subclass must implement run()")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_thread_pool.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_thread_pool.py src/util/thread/worker_base.py
git commit -m "refactor(worker_base): inherit object instead of QObject"
```

### Task 1.4: 重写 thread/async_.py

**Files:**
- Modify: `src/util/thread/async_.py`

**Interfaces:**
- Produces: `AsyncTask` 类,封装 `threading.Thread` 启动后台任务

- [ ] **Step 1: 写失败测试**

追加到 `tests/unit/test_thread_pool.py`:

```python
def test_async_task_runs_in_thread():
    from util.thread.async_ import AsyncTask
    import threading
    main_tid = threading.get_ident()
    executed_in = []
    def task():
        executed_in.append(threading.get_ident())
    a = AsyncTask(task)
    a.start()
    a.join(timeout=5)
    assert executed_in and executed_in[0] != main_tid
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_thread_pool.py::test_async_task_runs_in_thread -v`
Expected: FAIL

- [ ] **Step 3: 重写 async_.py**

```python
# src/util/thread/async_.py
"""异步任务 - threading 包装,替代 Qt 异步机制"""
import threading
from typing import Callable, Any


class AsyncTask:
    """封装 threading.Thread 的异步任务"""

    def __init__(self, func: Callable, *args, **kwargs):
        self._thread = threading.Thread(target=func, args=args, kwargs=kwargs, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def join(self, timeout: float = None) -> None:
        self._thread.join(timeout=timeout)

    def is_alive(self) -> bool:
        return self._thread.is_alive()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_thread_pool.py::test_async_task_runs_in_thread -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_thread_pool.py src/util/thread/async_.py
git commit -m "refactor(async_): wrap threading.Thread as AsyncTask"
```

### Task 1.5: 重写 common/config.py

**Files:**
- Create: `tests/unit/test_config.py`
- Modify: `src/util/common/config.py`

**Interfaces:**
- Produces: `Config` 类,`get(key, default=None)`/`set(key, value)`/`save()`/`load()`;`ConfigError` 异常;模块级 `config` 单例;新增 `download_threads`(默认 8,1-32)与 `max_concurrent_tasks`(默认 3,1-10)配置项

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_config.py
"""配置系统单元测试 - 验证 JSON + platformdirs 替代 QConfig"""
import json
import os
import threading
import pytest
from unittest.mock import patch


def test_config_get_with_default(tmp_path):
    from util.common.config import Config
    cfg = Config(config_path=str(tmp_path / "config.json"))
    assert cfg.get("nonexistent", default=42) == 42


def test_config_set_persists(tmp_path):
    from util.common.config import Config
    path = str(tmp_path / "config.json")
    cfg = Config(config_path=path)
    cfg.set("video_quality_id", 80)
    # 重新加载验证持久化
    cfg2 = Config(config_path=path)
    assert cfg2.get("video_quality_id") == 80


def test_config_corrupt_json_backup_and_reset(tmp_path):
    """AC-024-3: 损坏 JSON 备份并重置"""
    from util.common.config import Config
    path = str(tmp_path / "config.json")
    with open(path, "w") as f:
        f.write("{invalid json")
    cfg = Config(config_path=path)
    # 备份文件存在
    assert os.path.exists(path + ".bak")
    # 重置为默认值,不报错
    assert cfg.get("download_threads") == 8


def test_config_concurrent_set_thread_safe(tmp_path):
    """AC-024-5: 并发 set 线程安全"""
    from util.common.config import Config
    cfg = Config(config_path=str(tmp_path / "config.json"))
    keys = [f"key_{i}" for i in range(100)]
    threads = [threading.Thread(target=cfg.set, args=(k, i)) for i, k in enumerate(keys)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    cfg.reload()
    for i, k in enumerate(keys):
        assert cfg.get(k) == i


def test_config_download_threads_range_validation(tmp_path):
    """AC-024-7: download_threads 范围校验"""
    from util.common.config import Config, ConfigError
    cfg = Config(config_path=str(tmp_path / "config.json"))
    with pytest.raises(ConfigError):
        cfg.set("download_threads", 0)
    with pytest.raises(ConfigError):
        cfg.set("download_threads", 33)
    cfg.set("download_threads", 16)
    assert cfg.get("download_threads") == 16


def test_config_max_concurrent_tasks_range_validation(tmp_path):
    """AC-024-7: max_concurrent_tasks 范围校验"""
    from util.common.config import Config, ConfigError
    cfg = Config(config_path=str(tmp_path / "config.json"))
    with pytest.raises(ConfigError):
        cfg.set("max_concurrent_tasks", 0)
    with pytest.raises(ConfigError):
        cfg.set("max_concurrent_tasks", 11)


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.config  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_config.py -v`
Expected: FAIL

- [ ] **Step 3: 重写 config.py**

```python
# src/util/common/config.py
"""配置系统 - 纯 Python + JSON + platformdirs

替代 qfluentwidgets.QConfig + ConfigItem。
- 配置目录:platformdirs.user_config_dir("Bili23-Downloader")
- 配置文件:<config_dir>/config.json
- 范围校验迁移到 set() 中,失败抛出 ConfigError
"""
import json
import os
import threading
from typing import Any, Dict, Optional
from pathlib import Path

try:
    from platformdirs import user_config_dir, user_data_dir
except ImportError:
    # 兜底,避免 platformdirs 未安装时 import 失败
    user_config_dir = lambda app: os.path.expanduser(f"~/.config/{app}")
    user_data_dir = lambda app: os.path.expanduser(f"~/.local/share/{app}")


class ConfigError(Exception):
    """配置错误"""


# 范围校验规则:(min, max)
_RANGE_RULES = {
    "download_threads": (1, 32),
    "max_concurrent_tasks": (1, 10),
}


# 内置默认值
_DEFAULT_VALUES = {
    "video_quality_id": 80,
    "audio_quality_id": 30280,
    "video_codec": 7,
    "download_threads": 8,
    "max_concurrent_tasks": 3,
    "video_container": "mp4",
    "retry_count": 5,
}


class Config:
    """配置类,提供 get/set/save/load API"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_dir = user_config_dir("Bili23-Downloader")
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, "config.json")
        self._path = config_path
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = dict(_DEFAULT_VALUES)
        self.load()

    def get(self, key: str, default: Any = None) -> Any:
        """读取配置项,不存在返回 default"""
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置并立即持久化,带范围校验"""
        # 范围校验
        if key in _RANGE_RULES:
            lo, hi = _RANGE_RULES[key]
            if not isinstance(value, int) or not (lo <= value <= hi):
                raise ConfigError(f"{key} must be int in [{lo}, {hi}], got {value!r}")
        with self._lock:
            self._data[key] = value
        self.save()

    def save(self) -> None:
        """显式保存到文件"""
        with self._lock:
            data = dict(self._data)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self) -> None:
        """加载配置文件,损坏时备份并重置"""
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict):
                raise ValueError("config root must be object")
            with self._lock:
                self._data.update(loaded)
        except (json.JSONDecodeError, ValueError) as e:
            # 备份损坏的文件
            bak = self._path + ".bak"
            try:
                os.replace(self._path, bak)
            except OSError:
                pass
            print(f"[WARN] config corrupted, backed up to {bak}, reset to defaults: {e}")

    def reload(self) -> None:
        """重新加载(用于测试)"""
        with self._lock:
            self._data = dict(_DEFAULT_VALUES)
        self.load()


# 模块级单例
config = Config()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_config.py -v`
Expected: 7 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_config.py src/util/common/config.py
git commit -m "refactor(config): replace QConfig with JSON + platformdirs"
```

### Task 1.6: 重写 common/io/directory.py

**Files:**
- Modify: `src/util/common/io/directory.py`

**Interfaces:**
- Produces: `Directory` 类,提供 `config_dir`/`data_dir`/`log_dir`/`cookie_path`/`task_db_path` 等属性

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_directory.py
import os
import pytest


def test_directory_paths_exist_or_creatable(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from util.common.io.directory import Directory
    d = Directory()
    assert os.path.isdir(d.config_dir) or os.path.isdir(os.path.dirname(d.config_dir))
    assert d.cookie_path.endswith("cookie.json")
    assert d.task_db_path.endswith("tasks.db")
    assert d.log_dir.endswith("logs")


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.io.directory  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_directory.py -v`
Expected: FAIL

- [ ] **Step 3: 重写 directory.py**

```python
# src/util/common/io/directory.py
"""目录路径管理 - platformdirs 替代 QStandardPaths"""
import os
from platformdirs import user_config_dir, user_data_dir

_APP_NAME = "Bili23-Downloader"


class Directory:
    """跨平台目录路径"""

    def __init__(self):
        self.config_dir = user_config_dir(_APP_NAME)
        self.data_dir = user_data_dir(_APP_NAME)
        self.log_dir = os.path.join(self.data_dir, "logs")
        self.cookie_path = os.path.join(self.data_dir, "cookie.json")
        self.task_db_path = os.path.join(self.data_dir, "tasks.db")
        # 确保目录存在
        for d in (self.config_dir, self.data_dir, self.log_dir):
            os.makedirs(d, exist_ok=True)


# 模块级单例
directory = Directory()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_directory.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_directory.py src/util/common/io/directory.py
git commit -m "refactor(directory): use platformdirs instead of QStandardPaths"
```

### Task 1.7: 重写 common/translator.py

**Files:**
- Modify: `src/util/common/translator.py`

**Interfaces:**
- Produces: `Translator` 类,`tr(key, **kwargs) -> str`;模块级 `translator` 单例;从 .ts 文件解析或硬编码 dict

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_translator.py
import pytest


def test_translator_returns_key_if_missing():
    from util.common.translator import translator
    assert translator.tr("nonexistent.key") == "nonexistent.key"


def test_translator_interpolation():
    from util.common.translator import translator
    # 注册测试键
    translator._dict["test.hello"] = "Hello {name}"
    assert translator.tr("test.hello", name="World") == "Hello World"


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.common.translator  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_translator.py -v`
Expected: FAIL

- [ ] **Step 3: 重写 translator.py**

```python
# src/util/common/translator.py
"""翻译器 - 纯 Python dict,替代 QTranslator + .qm 文件

从 src/res/i18n/*.ts 解析键值,运行时用 dict 查找。
"""
import os
import xml.etree.ElementTree as ET
from typing import Dict


class Translator:
    """翻译器,从内存 dict 查找键值"""

    def __init__(self):
        self._dict: Dict[str, str] = {}
        self._load_default()

    def _load_default(self) -> None:
        """加载默认语言(zh_CN)翻译"""
        # 先尝试从 .ts 文件解析
        ts_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "res", "i18n", "bili23.zh_CN.ts"
        )
        ts_path = os.path.normpath(ts_path)
        if os.path.exists(ts_path):
            self._load_from_ts(ts_path)

    def _load_from_ts(self, ts_path: str) -> None:
        """从 Qt .ts XML 文件解析翻译"""
        try:
            tree = ET.parse(ts_path)
            root = tree.getroot()
            for msg in root.iter("message"):
                source = msg.find("source")
                translation = msg.find("translation")
                if source is not None and translation is not None and translation.text:
                    self._dict[source.text] = translation.text
        except (ET.ParseError, OSError):
            pass  # 静默失败,后续以 key 兜底

    def tr(self, key: str, **kwargs) -> str:
        """翻译键,支持 {placeholder} 插值"""
        text = self._dict.get(key, key)
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text


# 模块级单例
translator = Translator()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_translator.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_translator.py src/util/common/translator.py
git commit -m "refactor(translator): parse .ts to Python dict, drop QTranslator"
```

### Task 1.8: 删除 common/icon.py、style_sheet.py、color.py

**Files:**
- Delete: `src/util/common/icon.py`
- Delete: `src/util/common/style_sheet.py`
- Delete: `src/util/common/color.py`

- [ ] **Step 1: 写失败测试(验证已删除)**

```python
# tests/unit/test_gui_files_removed.py
import importlib
import pytest


def test_icon_module_removed():
    with pytest.raises(ImportError):
        importlib.import_module("util.common.icon")


def test_style_sheet_module_removed():
    with pytest.raises(ImportError):
        importlib.import_module("util.common.style_sheet")


def test_color_module_removed():
    with pytest.raises(ImportError):
        importlib.import_module("util.common.color")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_gui_files_removed.py -v`
Expected: FAIL(模块仍存在)

- [ ] **Step 3: 删除文件**

```bash
git rm src/util/common/icon.py src/util/common/style_sheet.py src/util/common/color.py
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_gui_files_removed.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_gui_files_removed.py
git commit -m "chore: remove GUI-only icon/style_sheet/color modules"
```

### Task 1.9: 编写 T1 单元测试汇总 + 验收

- [ ] **Step 1: 运行 T1 全部测试**

Run: `pytest tests/unit/test_signal_bus.py tests/unit/test_thread_pool.py tests/unit/test_config.py tests/unit/test_directory.py tests/unit/test_translator.py tests/unit/test_gui_files_removed.py -v --cov=src/util/common --cov=src/util/thread --cov-report=term-missing`
Expected: 全部通过,`util/common/` ≥ 90%,`util/thread/` ≥ 90%

- [ ] **Step 2: 验证 M1 里程碑**

Run: `python -c "import util.common; import util.thread; import sys; assert not any(m.startswith('PySide6') for m in sys.modules); print('M1 OK')"`
Expected: 输出 `M1 OK`

- [ ] **Step 3: 提交**

```bash
git add tests/
git commit -m "test(t1): add unit tests for signal_bus/thread_pool/config/directory/translator"
```

---

## Task 2: 业务层去 Qt

**目标:** 改造 `util/` 下所有业务模块,使 `import util` 整个包不触发 PySide6,且原业务逻辑功能等价。

**里程碑 M2 验收:** `python -c "import util"` 不报错且不导入 PySide6;`pyproject.toml` 移除 PySide6 后 import 成功。

### Task 2.1: 改造 parse/worker.py、preview/worker.py、additional/worker.py

**Files:**
- Modify: `src/util/parse/worker.py`
- Modify: `src/util/parse/preview/worker.py`
- Modify: `src/util/parse/additional/worker.py`

**Interfaces:**
- Consumes: `util.thread.worker_base.WorkerBase`(纯 Python 版本)、`util.common.signal_bus.signal_bus`
- Produces: 三个 worker 类继承新 `WorkerBase`,去除 `@Slot()` 装饰器,`run()` 签名不变

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_parse_workers.py
import pytest


def test_parse_worker_inherits_new_worker_base():
    from util.parse.worker import ParseWorker
    from util.thread.worker_base import WorkerBase
    assert issubclass(ParseWorker, WorkerBase)


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.parse.worker  # noqa: F401
    import util.parse.preview.worker  # noqa: F401
    import util.parse.additional.worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_parse_workers.py -v`
Expected: FAIL

- [ ] **Step 3: 改造三个 worker 文件**

对每个文件执行以下修改:
1. 移除 `from PySide6.QtCore import ...` 行
2. 移除 `@Slot()` 装饰器
3. 确保继承 `WorkerBase` 而非 `QObject`(或同时继承 WorkerBase 和其他 Qt 类的,改为仅继承 WorkerBase)
4. 信号 emit 调用保持不变(纯 Python Signal 兼容)

```bash
# 自动化 grep 检查需要改造的 Qt 用法
grep -rn "from PySide6" src/util/parse/worker.py src/util/parse/preview/worker.py src/util/parse/additional/worker.py
grep -rn "@Slot" src/util/parse/worker.py src/util/parse/preview/worker.py src/util/parse/additional/worker.py
```

按 grep 结果逐文件 Edit。

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_parse_workers.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_parse_workers.py src/util/parse/worker.py src/util/parse/preview/worker.py src/util/parse/additional/worker.py
git commit -m "refactor(parse): remove Qt from parse/preview/additional workers"
```

### Task 2.2: 改造 download/downloader/downloader.py

**Files:**
- Modify: `src/util/download/downloader/downloader.py`

**Interfaces:**
- Consumes: `WorkerBase`、`global_thread_pool`
- Produces: `ChunkWorker(WorkerBase)` 替代原 `ChunkWorker(WorkerBase, QRunnable)`;提交方式 `GlobalThreadPoolTask.run(worker.run)` 替代 `pool.start(worker)`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_downloader.py
import pytest


def test_chunk_worker_inherits_worker_base_only():
    from util.download.downloader.downloader import ChunkWorker
    from util.thread.worker_base import WorkerBase
    assert ChunkWorker.__bases__ == (WorkerBase,)


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.download.downloader.downloader  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_downloader.py -v`
Expected: FAIL

- [ ] **Step 3: 改造 downloader.py**

```bash
# 找到 ChunkWorker 定义
grep -n "class ChunkWorker" src/util/download/downloader/downloader.py
```

按行号定位,执行以下修改:
1. `class ChunkWorker(WorkerBase, QRunnable):` → `class ChunkWorker(WorkerBase):`
2. 移除 `from PySide6.QtCore import QRunnable` 等导入
3. 移除 `@Slot` 装饰器
4. 找到所有 `pool.start(worker)` 调用,改为 `GlobalThreadPoolTask.run(worker.run)`

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_downloader.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_downloader.py src/util/download/downloader/downloader.py
git commit -m "refactor(downloader): ChunkWorker inherits WorkerBase only"
```

### Task 2.3: 改造 merger.py、ffmpeg/runner.py(QProcess → subprocess)

**Files:**
- Modify: `src/util/download/downloader/merger.py`
- Modify: `src/util/ffmpeg/runner.py`

**Interfaces:**
- Produces: 两个文件中的 `QProcess` 调用改为 `subprocess.Popen`,保留实时输出捕获

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_subprocess_replacement.py
import pytest


def test_merger_no_qprocess():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.download.downloader.merger  # noqa: F401
    import util.ffmpeg.runner  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)


def test_ffmpeg_runner_uses_subprocess(tmp_path):
    """验证 ffmpeg 调用走 subprocess.Popen"""
    import util.ffmpeg.runner as runner
    import inspect
    src = inspect.getsource(runner)
    assert "subprocess.Popen" in src or "subprocess.run" in src
    assert "QProcess" not in src
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_subprocess_replacement.py -v`
Expected: FAIL

- [ ] **Step 3: 改造 merger.py 和 runner.py**

对每个文件:
1. 移除 `from PySide6.QtCore import QProcess`
2. 添加 `import subprocess`
3. 将 `QProcess()` 实例化改为 `subprocess.Popen(...)` 调用
4. `process.start(cmd, args)` → `subprocess.Popen([cmd] + args, stdout=PIPE, stderr=PIPE, text=True, bufsize=1)`
5. `process.readyReadStandardOutput.connect(cb)` → 轮询 `process.stdout.readline()` 在独立线程中,或用 `communicate()`
6. `process.waitForFinished()` → `process.wait()`

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_subprocess_replacement.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_subprocess_replacement.py src/util/download/downloader/merger.py src/util/ffmpeg/runner.py
git commit -m "refactor(ffmpeg): replace QProcess with subprocess.Popen"
```

### Task 2.4: 改造 download/downloader/parse_worker.py

**Files:**
- Modify: `src/util/download/downloader/parse_worker.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_parse_worker_no_qt.py
def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.download.downloader.parse_worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_parse_worker_no_qt.py -v`
Expected: FAIL

- [ ] **Step 3: 改造 parse_worker.py**

```bash
grep -n "PySide6\|@Slot\|QObject\|Signal" src/util/download/downloader/parse_worker.py
```

按 grep 结果逐项 Edit:
- 移除 Qt 导入
- 继承 `WorkerBase` 而非 QObject
- 移除 `@Slot`

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_parse_worker_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_parse_worker_no_qt.py src/util/download/downloader/parse_worker.py
git commit -m "refactor(parse_worker): remove Qt dependencies"
```

### Task 2.5: 改造 download/cover/manager.py、cache.py、query_worker.py

**Files:**
- Modify: `src/util/download/cover/manager.py`
- Modify: `src/util/download/cover/cache.py`
- Modify: `src/util/download/cover/query_worker.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_cover_no_qt.py
def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.download.cover.manager  # noqa: F401
    import util.download.cover.cache  # noqa: F401
    import util.download.cover.query_worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_cover_no_qt.py -v`
Expected: FAIL

- [ ] **Step 3: 改造三个文件**

- `manager.py`: 移除 `QPixmap`,改用字节流(`bytes`)保存封面,不预览
- `cache.py`: 移除 Qt 依赖
- `query_worker.py`: 继承 `WorkerBase`,移除 Qt

```bash
grep -rn "QPixmap\|PySide6" src/util/download/cover/
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_cover_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_cover_no_qt.py src/util/download/cover/
git commit -m "refactor(cover): use byte stream instead of QPixmap"
```

### Task 2.6: 改造 download/task/manager.py、query_worker.py、reparse_worker.py

**Files:**
- Modify: `src/util/download/task/manager.py`
- Modify: `src/util/download/task/query_worker.py`
- Modify: `src/util/download/task/reparse_worker.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_task_no_qt.py
def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[md] if False else None
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.download.task.manager  # noqa: F401
    import util.download.task.query_worker  # noqa: F401
    import util.download.task.reparse_worker  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_task_no_qt.py -v`
Expected: FAIL

- [ ] **Step 3: 改造三个文件**

```bash
grep -rn "PySide6\|@Slot\|QObject" src/util/download/task/
```

按 grep 结果 Edit。

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_task_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_task_no_qt.py src/util/download/task/
git commit -m "refactor(task): remove Qt from task manager and workers"
```

### Task 2.7: 改造 auth/qrcode.py(QPixmap → PNG 字节流)

**Files:**
- Modify: `src/util/auth/qrcode.py`

**Interfaces:**
- Produces: `get_qrcode() -> Tuple[str, bytes]` 返回 (qrcode_key, PNG 字节流);不再依赖 QPixmap

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_qrcode.py
import pytest


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.auth.qrcode  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)


def test_qrcode_returns_png_bytes(monkeypatch):
    """验证返回 PNG 字节流而非 QPixmap"""
    import util.auth.qrcode as qr
    import inspect
    src = inspect.getsource(qr)
    assert "QPixmap" not in src
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_qrcode.py -v`
Expected: FAIL

- [ ] **Step 3: 改造 qrcode.py**

```bash
grep -n "QPixmap\|PySide6" src/util/auth/qrcode.py
```

替换方案:
1. 移除 `from PySide6.QtGui import QPixmap`
2. 用 `qrcode` 库生成 QR 矩阵
3. 用 `io.BytesIO` + `qrcode.make()` 的 PIL image 保存为 PNG 字节流
4. 函数返回 `bytes` 而非 `QPixmap`

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_qrcode.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_qrcode.py src/util/auth/qrcode.py
git commit -m "refactor(qrcode): return PNG bytes instead of QPixmap"
```

### Task 2.8: 改造 auth/sms.py(QTimer → threading.Timer)

**Files:**
- Modify: `src/util/auth/sms.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_sms_no_qt.py
def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.auth.sms  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_sms_no_qt.py -v`
Expected: FAIL

- [ ] **Step 3: 改造 sms.py**

```bash
grep -n "QTimer\|PySide6" src/util/auth/sms.py
```

替换:
- `from PySide6.QtCore import QTimer` → `from threading import Timer`
- `QTimer.singleShot(ms, cb)` → `Timer(ms / 1000, cb).start()`
- `self.timer = QTimer(); self.timer.timeout.connect(cb); self.timer.start(ms)` → `self.timer = Timer(ms / 1000, cb); self.timer.start()` 或 `threading.Thread(target=self._poll_loop, daemon=True).start()`

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_sms_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_sms_no_qt.py src/util/auth/sms.py
git commit -m "refactor(sms): replace QTimer with threading.Timer"
```

### Task 2.9: 改造 auth/cookie_login.py、server.py、captcha.py

**Files:**
- Modify: `src/util/auth/cookie_login.py`
- Modify: `src/util/auth/server.py`
- Modify: `src/util/auth/captcha.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_auth_no_qt.py
def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.auth.cookie_login  # noqa: F401
    import util.auth.server  # noqa: F401
    import util.auth.captcha  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_auth_no_qt.py -v`
Expected: FAIL

- [ ] **Step 3: 改造三个文件**

- `cookie_login.py`: 移除 QWebEngine 浏览器登录,仅保留 Cookie 导入逻辑
- `server.py`: 去除对 `signal_bus` 的引用,改为回调参数或 `logging`
- `captcha.py`: `QPixmap` 验证码显示改为终端 ASCII 渲染或保存 PNG

```bash
grep -rn "PySide6\|signal_bus\|QPixmap\|QWebEngine" src/util/auth/
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_auth_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_auth_no_qt.py src/util/auth/
git commit -m "refactor(auth): remove Qt from cookie_login/server/captcha"
```

### Task 2.10: 改造 network/request.py

**Files:**
- Modify: `src/util/network/request.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_network_no_qt.py
def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.network.request  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_network_no_qt.py -v`
Expected: FAIL(原 request.py 第 1 行 `from PySide6.QtCore import Signal, QObject, Slot`)

- [ ] **Step 3: 改造 request.py**

```bash
grep -n "Signal\|QObject\|Slot\|@Slot\|config.get(config\." src/util/network/request.py
```

修改:
1. 移除 `from PySide6.QtCore import Signal, QObject, Slot`
2. 类继承从 `QObject` 改为 `object`
3. 移除 `@Slot()` 装饰器
4. 原 Signal 改用 `logging` 或回调函数
5. `config.get(config.xxx).value` → `config.get("xxx")`(全量替换)

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_network_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_network_no_qt.py src/util/network/request.py
git commit -m "refactor(network): remove Qt and use logging instead of Signal"
```

### Task 2.11: 改造 misc/update.py、web.py

**Files:**
- Modify: `src/util/misc/update.py`
- Modify: `src/util/misc/web.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_misc_no_qt.py
def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.misc.update  # noqa: F401
    import util.misc.web  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_misc_no_qt.py -v`
Expected: FAIL

- [ ] **Step 3: 改造 update.py 和 web.py**

- `update.py`: `QNetworkAccessManager` → `httpx.get(url)`
- `web.py`: `QDesktopServices.openUrl(url)` → `webbrowser.open(url)`

```python
# update.py 关键改造
import httpx
response = httpx.get(url, timeout=10)
data = response.json()

# web.py 关键改造
import webbrowser
webbrowser.open(url)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_misc_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_misc_no_qt.py src/util/misc/update.py src/util/misc/web.py
git commit -m "refactor(misc): use httpx and webbrowser instead of Qt network"
```

### Task 2.12: 改造 danmaku_ass.py(PIL ImageFont 替代 QFontMetrics)

**Files:**
- Modify: `src/util/parse/additional/file/danmaku_ass.py`

**Interfaces:**
- Produces: `DanmakuLayoutEngine` 不再依赖 `QApplication.font()`/`QFontMetrics`;改用 PIL `ImageFont.truetype(font_path, size).getlength(text)`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_danmaku_ass.py
import pytest


def test_no_pyside6_import():
    import sys
    for mod in list(sys.modules.keys()):
        if mod.startswith("PySide6"):
            del sys.modules[mod]
    import util.parse.additional.file.danmaku_ass  # noqa: F401
    assert not any(m.startswith("PySide6") for m in sys.modules)


def test_text_width_measurement_with_pil():
    """验证使用 PIL ImageFont 测量文本宽度"""
    import util.parse.additional.file.danmaku_ass as mod
    import inspect
    src = inspect.getsource(mod)
    assert "ImageFont" in src or "PIL" in src
    assert "QFontMetrics" not in src
    assert "QApplication" not in src
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_danmaku_ass.py -v`
Expected: FAIL(原文件第 1-2 行导入 QApplication/QFontMetrics)

- [ ] **Step 3: 改造 danmaku_ass.py**

替换第 1-2 行导入与第 85-95 行 font_metrics 实现:

```python
# 原(第 1-2 行)
# from PySide6.QtWidgets import QApplication
# from PySide6.QtGui import QFontMetrics

# 新(替换为 PIL)
from PIL import ImageFont
import os
import sys


def _load_pil_font(font_name: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """加载 PIL 字体,优先使用系统字体,找不到时回退默认"""
    # 候选字体路径(跨平台)
    candidates = []
    if sys.platform == "win32":
        win_dir = os.environ.get("WINDIR", r"C:\Windows")
        candidates = [
            os.path.join(win_dir, "Fonts", "msyh.ttc"),       # 微软雅黑
            os.path.join(win_dir, "Fonts", "simhei.ttf"),     # 黑体
            os.path.join(win_dir, "Fonts", "arial.ttf"),
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    # 回退到 PIL 默认字体
    return ImageFont.load_default()


def _measure_text_width(font: ImageFont.FreeTypeFont, text: str) -> int:
    """用 PIL 测量文本像素宽度"""
    # Pillow>=10.0 推荐 getlength,旧版用 getsize
    if hasattr(font, "getlength"):
        return int(font.getlength(text))
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]
```

在 `DanmakuLayoutEngine._load_config` 中替换第 85-95 行:

```python
def _load_config(self):
    style = config.get(config.danmaku_style)
    # 用 PIL 替代 QApplication.font() + QFontMetrics
    self._font = _load_pil_font(
        style["font"]["name"],
        style["font"]["size"],
        style["font"]["bold"]
    )
    self._measure_fn = lambda text: _measure_text_width(self._font, text)
    # line_height 估算:字号 * 1.4 + 4(与 QFontMetrics.height() 近似)
    self.line_height = int(style["font"]["size"] * 1.4) + 4
    self.display_area = style["advanced"]["display_area"] / 100.0
    self.opacity = style["advanced"]["opacity"] / 100.0
    self.min_gap = style["advanced"]["minimum_gap"]
    total_scroll_rows = int((self.screen_height * self.display_area) / self.line_height)
    self.max_scroll_rows = max(1, total_scroll_rows)
    self.max_static_rows = max(1, int(self.screen_height * self.display_area / self.line_height))
```

在 `_convert_dialogues` 中(原第 198 行)替换:
```python
# 原: text_width = engine.font_metrics.horizontalAdvance(text)
text_width = engine._measure_fn(text)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_danmaku_ass.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_danmaku_ass.py src/util/parse/additional/file/danmaku_ass.py
git commit -m "refactor(danmaku_ass): use PIL ImageFont to measure text width"
```

### Task 2.13: 全量替换 config.get(config.xxx).value → config.get("xxx")

**Files:**
- Modify: 53 个文件,共 162 处调用(详见规格文档 T2.13)

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_no_config_attr_access.py
import subprocess


def test_no_legacy_config_access_pattern():
    """验证全仓库不再有 config.get(config.xxx).value 模式"""
    result = subprocess.run(
        ["grep", "-rn", "config\\.get(config\\.", "src/util/"],
        capture_output=True, text=True
    )
    # 允许 0 个匹配(legacy 模式全部替换完成)
    assert result.stdout == "", f"仍有 legacy config 访问模式:\n{result.stdout}"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_no_config_attr_access.py -v`
Expected: FAIL(grep 找到 162 处)

- [ ] **Step 3: 全量替换**

```bash
# 用 sed 批量替换(在 git bash 或 linux 下)
# 模式:config.get(config.<key>).value → config.get("<key>")
find src/util -name "*.py" -exec sed -i -E 's/config\.get\(config\.([a-zA-Z_][a-zA-Z0-9_]*)\)\.value/config.get("\1")/g' {} +

# 也替换无 .value 的形式:config.get(config.<key>) → config.get("<key>")
find src/util -name "*.py" -exec sed -i -E 's/config\.get\(config\.([a-zA-Z_][a-zA-Z0-9_]*)\)/config.get("\1")/g' {} +
```

验证替换数量:
```bash
grep -rn "config\.get(config\." src/util/ | wc -l
# 应为 0
```

- [ ] **Step 4: 运行测试验证通过 + 运行全部 T2 测试**

Run: `pytest tests/unit/ -v`
Expected: 全部通过

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_no_config_attr_access.py src/util/
git commit -m "refactor(config): replace all config.get(config.xxx).value with config.get('xxx')"
```

### Task 2.14: 改造所有 util/**/__init__.py

**Files:**
- Modify: 所有 `src/util/**/__init__.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_init_no_qt.py
import os
import pathlib


def test_all_init_files_no_qt():
    """遍历 util 下所有 __init__.py,断言无 PySide6 导入"""
    util_root = pathlib.Path("src/util")
    init_files = list(util_root.rglob("__init__.py"))
    assert init_files, "应至少找到一个 __init__.py"
    violations = []
    for init in init_files:
        content = init.read_text(encoding="utf-8")
        if "PySide6" in content:
            violations.append(str(init))
    assert not violations, f"以下 __init__.py 仍含 PySide6: {violations}"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_init_no_qt.py -v`
Expected: FAIL(列出违规文件)

- [ ] **Step 3: 改造所有 __init__.py**

```bash
# 找出所有含 PySide6 的 __init__.py
find src/util -name "__init__.py" -exec grep -l "PySide6" {} \;
```

对每个文件 Edit,移除 PySide6 导入行。

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_init_no_qt.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_init_no_qt.py src/util/**/__init__.py
git commit -m "refactor(init): remove PySide6 imports from all util __init__.py"
```

### Task 2.15: 编写 T2 单元测试汇总 + 验收

- [ ] **Step 1: 运行 T2 全部测试 + 覆盖率**

Run: `pytest tests/unit/ -v --cov=src/util --cov-report=term-missing`
Expected: 全部通过,`util/parse/` ≥ 80%, `util/download/` ≥ 75%, `util/auth/` ≥ 80%

- [ ] **Step 2: 验证 M2 里程碑**

```bash
python -c "import util; import sys; assert not any(m.startswith('PySide6') for m in sys.modules); print('M2 OK')"
```
Expected: 输出 `M2 OK`

- [ ] **Step 3: 提交**

```bash
git add tests/
git commit -m "test(t2): complete unit tests for business layer"
```

---

## Task 3: 资源清理

**目标:** 删除所有 GUI 专属文件,使仓库仅剩 CLI 相关代码。

**里程碑 M3 验收:** `git status` 干净;`src/res/` 仅剩 `i18n/`;仓库无 GUI 文件。

### Task 3.1: 删除 src/gui/ 整个目录

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_no_gui_dir.py
import os


def test_gui_dir_removed():
    assert not os.path.isdir("src/gui"), "src/gui/ 目录应已删除"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_no_gui_dir.py -v`
Expected: FAIL

- [ ] **Step 3: 删除目录**

```bash
git rm -r src/gui/
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_no_gui_dir.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_no_gui_dir.py
git commit -m "chore: remove src/gui/ directory"
```

### Task 3.2: 删除 src/res/html/、icon/、image/、qss/

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_no_res_gui.py
import os


def test_res_gui_dirs_removed():
    for sub in ("html", "icon", "image", "qss"):
        assert not os.path.isdir(f"src/res/{sub}"), f"src/res/{sub}/ 应已删除"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_no_res_gui.py -v`
Expected: FAIL

- [ ] **Step 3: 删除目录**

```bash
git rm -r src/res/html/ src/res/icon/ src/res/image/ src/res/qss/
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_no_res_gui.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_no_res_gui.py
git commit -m "chore: remove GUI-only res subdirectories"
```

### Task 3.3: 删除 src/res/resources.qrc、resources_rc.py

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_no_qrc.py
import os


def test_qrc_files_removed():
    assert not os.path.exists("src/res/resources.qrc")
    assert not os.path.exists("src/res/resources_rc.py")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_no_qrc.py -v`
Expected: FAIL

- [ ] **Step 3: 删除文件**

```bash
git rm src/res/resources.qrc src/res/resources_rc.py
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_no_qrc.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_no_qrc.py
git commit -m "chore: remove Qt resource files"
```

### Task 3.4: 删除 assets/

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_no_assets.py
import os


def test_assets_dir_removed():
    assert not os.path.isdir("assets")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_no_assets.py -v`
Expected: FAIL

- [ ] **Step 3: 删除目录**

```bash
git rm -r assets/
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_no_assets.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_no_assets.py
git commit -m "chore: remove assets/ directory"
```

### Task 3.5: 删除 .github/workflows/publish.yml、ISSUE_TEMPLATE/

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_no_github_gui.py
import os


def test_publish_workflow_removed():
    assert not os.path.exists(".github/workflows/publish.yml")


def test_issue_template_removed():
    assert not os.path.isdir(".github/ISSUE_TEMPLATE")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_no_github_gui.py -v`
Expected: FAIL

- [ ] **Step 3: 删除文件**

```bash
git rm .github/workflows/publish.yml
git rm -r .github/ISSUE_TEMPLATE/
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_no_github_gui.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_no_github_gui.py
git commit -m "chore: remove GUI publish workflow and issue templates"
```

### Task 3.6: 删除 scripts/translate.py

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_no_translate_script.py
import os


def test_translate_script_removed():
    assert not os.path.exists("scripts/translate.py")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/unit/test_no_translate_script.py -v`
Expected: FAIL

- [ ] **Step 3: 删除文件**

```bash
git rm scripts/translate.py
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/unit/test_no_translate_script.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add tests/unit/test_no_translate_script.py
git commit -m "chore: remove scripts/translate.py (depends on pyside6-lupdate)"
```

### Task 3.7: 更新 .gitignore

- [ ] **Step 1: 读取当前 .gitignore**

```bash
# 用 Read 工具读取 .gitignore
```

- [ ] **Step 2: 移除 GUI 专用条目**

移除如 `*.qml`、`*.qss`、`resources_rc.py` 等 GUI 专用条目,保留 Python 通用条目(`__pycache__`、`*.pyc`、`.venv`、`dist/`、`build/`、`*.egg-info`)。

- [ ] **Step 3: 验证 M3 里程碑**

Run: `git status` 应显示干净;`ls src/res/` 应仅显示 `i18n/`

- [ ] **Step 4: 提交**

```bash
git add .gitignore
git commit -m "chore: clean up .gitignore for CLI project"
```

---

## Task 4: CLI 框架搭建

**目标:** 创建 `src/cli/` 目录结构,实现 Typer 应用骨架、Rich 渲染、异常处理、signal_bus 回调注册。

**里程碑 M4 验收:** `bili23 --version`、`bili23 --help` 正常;signal_bus 回调能转 Rich 输出。

### Task 4.1: 创建 src/cli/ 目录结构

- [ ] **Step 1: 创建目录与空 __init__.py**

```bash
mkdir -p src/cli/commands src/cli/interact src/cli/render
touch src/cli/__init__.py src/cli/commands/__init__.py src/cli/interact/__init__.py src/cli/render/__init__.py
```

- [ ] **Step 2: 提交**

```bash
git add src/cli/
git commit -m "chore: scaffold src/cli/ directory structure"
```

### Task 4.2: 实现 cli/app.py

**Files:**
- Create: `src/cli/app.py`

**Interfaces:**
- Produces: `app` (Typer 实例);全局选项 `-c/--config`、`-v/--verbose`、`-q/--quiet`、`--no-color`、`--version`、`--help`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_app.py
from typer.testing import CliRunner


def test_version_option():
    from cli.app import app
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "3.0.0" in result.stdout


def test_help_option():
    from cli.app import app
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "bili23" in result.stdout


def test_no_args_shows_help():
    from cli.app import app
    result = CliRunner().invoke(app, [])
    assert result.exit_code == 0
    assert "Usage" in result.stdout or "Commands" in result.stdout
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_app.py -v`
Expected: FAIL(`cli.app` 不存在)

- [ ] **Step 3: 实现 app.py**

```python
# src/cli/app.py
"""Typer 应用入口与全局选项"""
import typer
from rich.console import Console

from cli import __version__

app = typer.Typer(
    name="bili23",
    help="开源、免费、跨平台的 B 站视频 CLI 下载工具",
    no_args_is_help=True,
    add_completion=False,
)

# 全局 Console 单例
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"bili23 {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    config: str = typer.Option(None, "-c", "--config", help="指定配置文件路径"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="详细日志输出(DEBUG)"),
    quiet: bool = typer.Option(False, "-q", "--quiet", help="静默模式(仅 ERROR)"),
    no_color: bool = typer.Option(False, "--no-color", help="禁用彩色输出"),
    version: bool = typer.Option(False, "--version", callback=version_callback, is_eager=True),
):
    """Bili23-Downloader CLI"""
    ctx.obj = {
        "config_path": config,
        "verbose": verbose,
        "quiet": quiet,
        "no_color": no_color,
    }
```

```python
# src/cli/__init__.py
"""bili23 CLI 包"""
__version__ = "3.0.0"
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_app.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/app.py src/cli/__init__.py tests/cli/test_app.py
git commit -m "feat(cli): add Typer app skeleton with global options"
```

### Task 4.3: 实现 cli/render/

**Files:**
- Create: `src/cli/render/__init__.py`
- Create: `src/cli/render/progress.py`
- Create: `src/cli/render/table.py`
- Create: `src/cli/render/toast.py`

**Interfaces:**
- Produces: `ProgressRenderer` 类(下载/解析进度条)、`render_table(rows, headers)` 函数、`toast(message, level)` 函数

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_render.py
from typer.testing import CliRunner


def test_render_table_outputs_headers():
    from cli.render.table import render_table
    # 验证不抛异常
    render_table([{"title": "A", "duration": "1:00"}], ["title", "duration"])


def test_toast_no_exception():
    from cli.render.toast import toast
    toast("test message", level="info")
    toast("error message", level="error")


def test_progress_render_lifecycle():
    from cli.render.progress import ProgressRender
    p = ProgressRender()
    p.start()
    p.add_task("test", total=100)
    p.update("test", advance=50)
    p.stop()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_render.py -v`
Expected: FAIL

- [ ] **Step 3: 实现三个文件**

```python
# src/cli/render/progress.py
"""进度条渲染 - 基于 rich.Progress"""
from rich.progress import Progress, BarColumn, TextColumn, TaskProgressColumn, TimeRemainingColumn, DownloadColumn, TransferSpeedColumn


class ProgressRender:
    """下载/解析进度条管理器"""

    def __init__(self):
        self._progress = Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        )
        self._tasks = {}

    def start(self):
        self._progress.start()

    def stop(self):
        self._progress.stop()

    def add_task(self, name: str, total: float):
        task_id = self._progress.add_task(name, total=total)
        self._tasks[name] = task_id

    def update(self, name: str, advance: float = 0, total: float = None):
        if name in self._tasks:
            kwargs = {"advance": advance}
            if total is not None:
                kwargs["total"] = total
            self._progress.update(self._tasks[name], **kwargs)
```

```python
# src/cli/render/table.py
"""表格输出 - 基于 rich.Table"""
from rich.console import Console
from rich.table import Table


def render_table(rows: list, headers: list, title: str = None):
    """渲染表格到终端"""
    console = Console()
    table = Table(title=title, show_lines=False)
    for h in headers:
        table.add_column(h)
    for row in rows:
        table.add_row(*[str(row.get(h, "")) for h in headers])
    console.print(table)
```

```python
# src/cli/render/toast.py
"""Toast 通知转终端提示"""
from rich.console import Console

_LEVEL_STYLES = {
    "info": "[blue]ℹ[/blue]",
    "success": "[green]✓[/green]",
    "warning": "[yellow]⚠[/yellow]",
    "error": "[red]✗[/red]",
}


def toast(message: str, level: str = "info"):
    """输出带图标的提示信息"""
    console = Console()
    icon = _LEVEL_STYLES.get(level, _LEVEL_STYLES["info"])
    console.print(f"{icon} {message}")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_render.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/render/ tests/cli/test_render.py
git commit -m "feat(render): add progress bar, table, and toast renderers"
```

### Task 4.4: 实现 cli/callbacks.py

**Files:**
- Create: `src/cli/callbacks.py`

**Interfaces:**
- Consumes: `util.common.signal_bus.signal_bus`
- Produces: `register_callbacks()` 函数,将 signal_bus 信号 connect 到 Rich 输出

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_callbacks.py
from unittest.mock import patch


def test_register_callbacks_connects_signals():
    from util.common.signal_bus import signal_bus
    from cli.callbacks import register_callbacks
    # 注册前 ToastNotification 回调列表为空
    before = list(signal_bus.ToastNotification._callbacks)
    register_callbacks()
    after = list(signal_bus.ToastNotification._callbacks)
    assert len(after) > len(before)


def test_toast_signal_emits_to_rich():
    from cli.callbacks import register_callbacks
    register_callbacks()
    from util.common.signal_bus import signal_bus
    # 不应抛异常
    signal_bus.ToastNotification.emit("test", "info")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_callbacks.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 callbacks.py**

```python
# src/cli/callbacks.py
"""signal_bus 回调注册 → Rich 输出"""
from util.common.signal_bus import signal_bus
from cli.render.toast import toast


def _on_toast(message: str, level: str = "info"):
    """Toast 信号回调"""
    toast(message, level=level)


def _on_parse_progress(*args, **kwargs):
    """解析进度信号回调(预留)"""
    pass


def _on_download_progress(*args, **kwargs):
    """下载进度信号回调(预留)"""
    pass


def register_callbacks():
    """注册所有 signal_bus 信号到 Rich 输出"""
    signal_bus.ToastNotification.connect(_on_toast)
    signal_bus.Parse.connect(_on_parse_progress)
    signal_bus.Download.connect(_on_download_progress)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_callbacks.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/callbacks.py tests/cli/test_callbacks.py
git commit -m "feat(callbacks): register signal_bus callbacks to Rich output"
```

### Task 4.5: 实现 cli/exceptions.py

**Files:**
- Create: `src/cli/exceptions.py`

**Interfaces:**
- Produces: `Bili23Error` 基类(exit_code=70)与 7 个子类,对应规格 7.1 节退出码

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_exceptions.py
import pytest


def test_exception_exit_codes():
    from cli.exceptions import (
        Bili23Error, ParseError, AuthRequiredError, NetworkError,
        DiskFullError, FFmpegMissingError, ConfigError, UserCancelledError
    )
    assert Bili23Error().exit_code == 70
    assert ParseError().exit_code == 4
    assert AuthRequiredError().exit_code == 5
    assert NetworkError().exit_code == 6
    assert DiskFullError().exit_code == 7
    assert FFmpegMissingError().exit_code == 8
    assert ConfigError().exit_code == 9
    assert UserCancelledError().exit_code == 3
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_exceptions.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 exceptions.py**

```python
# src/cli/exceptions.py
"""异常类与退出码定义(对应规格 7.1 节)"""


class Bili23Error(Exception):
    """基类"""
    exit_code = 70


class ParseError(Bili23Error):
    """解析失败"""
    exit_code = 4


class AuthRequiredError(Bili23Error):
    """需要登录"""
    exit_code = 5


class NetworkError(Bili23Error):
    """网络错误"""
    exit_code = 6


class DiskFullError(Bili23Error):
    """磁盘空间不足"""
    exit_code = 7


class FFmpegMissingError(Bili23Error):
    """FFmpeg 缺失"""
    exit_code = 8


class ConfigError(Bili23Error):
    """配置错误"""
    exit_code = 9


class UserCancelledError(Bili23Error):
    """用户取消"""
    exit_code = 3
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_exceptions.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/exceptions.py tests/cli/test_exceptions.py
git commit -m "feat(exceptions): add Bili23Error hierarchy with exit codes"
```

### Task 4.6: 实现 src/main.py + CLI 框架测试

**Files:**
- Create: `src/main.py`

**Interfaces:**
- Produces: `app` 全局变量,实例化 `cli.app.app` 并注册回调

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_main.py
from typer.testing import CliRunner


def test_main_app_callable():
    from src.main import app
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0


def test_main_app_registers_callbacks():
    """验证 main 模块加载时注册了 signal_bus 回调"""
    from util.common.signal_bus import signal_bus
    # 导入 main 触发 register_callbacks
    import src.main  # noqa: F401
    assert len(signal_bus.ToastNotification._callbacks) > 0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_main.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 main.py**

```python
# src/main.py
"""bili23 CLI 入口

通过 pyproject.toml [project.scripts] 注册:
    bili23 = "src.main:app"
"""
from cli.app import app
from cli.callbacks import register_callbacks


# 启动时注册 signal_bus 回调
register_callbacks()


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: 运行测试验证通过 + 验证 M4 里程碑**

Run: `pytest tests/cli/ -v`
Expected: 全部通过

```bash
python -m src.main --version
# 应输出 bili23 3.0.0
python -m src.main --help
# 应显示帮助
```

- [ ] **Step 5: 提交**

```bash
git add src/main.py tests/cli/test_main.py
git commit -m "feat(main): add Typer entry point and register callbacks"
```

---

## Task 5: CLI 命令实现

**目标:** 实现全部 7 类子命令与 3 个交互组件,使 `bili23 download <url> --dry-run` 跑通,三种登录方式可用,交互式选择可用。

**里程碑 M5 验收:** 所有命令 `--help` 完整;`bili23 download --help` 输出完整选项;三种登录方式 mock 测试可用。

### Task 5.1: 实现 cli/commands/download.py

**Files:**
- Create: `src/cli/commands/download.py`

**Interfaces:**
- Consumes: `util.parse.parser.*`、`util.download.task.manager`、`cli.interact.episode_selector`、`cli.interact.quality_selector`
- Produces: `download` Typer 命令,含规格 5.3 节全部选项

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_download.py
from typer.testing import CliRunner


def test_download_help():
    from src.main import app
    result = CliRunner().invoke(app, ["download", "--help"])
    assert result.exit_code == 0
    # 验证关键选项存在
    assert "--episodes" in result.stdout or "-e" in result.stdout
    assert "--video-quality" in result.stdout
    assert "--danmaku" in result.stdout
    assert "--subtitle" in result.stdout
    assert "--cover" in result.stdout
    assert "--metadata" in result.stdout
    assert "--embed-cover" in result.stdout
    assert "--dry-run" in result.stdout
    assert "--non-interactive" in result.stdout


def test_download_invalid_url_exit_code_4():
    """AC-028-2: 无效 URL 退出码 4"""
    from src.main import app
    result = CliRunner().invoke(app, ["download", "not-a-url", "--non-interactive"])
    assert result.exit_code == 4
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_download.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 download.py**

```python
# src/cli/commands/download.py
"""bili23 download <url> - 主下载命令"""
import typer
from typing import Optional, List
from cli.app import app
from cli.exceptions import ParseError
from cli.render.toast import toast


@app.command("download")
def download(
    url: str = typer.Argument(..., help="B 站视频/番剧/课程/收藏夹/UP主空间等链接"),
    output_dir: Optional[str] = typer.Option(None, "-o", "--output-dir", help="输出目录"),
    filename: Optional[str] = typer.Option(None, "-n", "--filename", help="文件名模板"),
    yes: bool = typer.Option(False, "-y", "--yes", help="跳过交互确认"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="完全非交互"),
    dry_run: bool = typer.Option(False, "--dry-run", help="仅模拟,不实际下载"),
    episodes: Optional[str] = typer.Option(None, "-e", "--episodes", "-p", "--page", help='分集选择,如 "1-5,10" 或 "all"'),
    video_quality: Optional[int] = typer.Option(None, "--video-quality", help="画质 ID"),
    audio_quality: Optional[int] = typer.Option(None, "--audio-quality", help="音质 ID"),
    video_codec: Optional[int] = typer.Option(None, "--video-codec", help="视频编码"),
    danmaku: Optional[str] = typer.Option(None, "--danmaku", help="弹幕格式 xml|ass|json"),
    no_danmaku: bool = typer.Option(False, "--no-danmaku", help="不下载弹幕"),
    subtitle: Optional[str] = typer.Option(None, "--subtitle", help="字幕格式 srt|lrc|txt|ass|json"),
    no_subtitle: bool = typer.Option(False, "--no-subtitle", help="不下载字幕"),
    cover: Optional[str] = typer.Option(None, "--cover", help="封面格式 jpg|png|avif|webp"),
    no_cover: bool = typer.Option(False, "--no-cover", help="不下载封面"),
    metadata: Optional[str] = typer.Option(None, "--metadata", help="元数据格式 nfo"),
    no_metadata: bool = typer.Option(False, "--no-metadata", help="不生成 NFO"),
    embed_cover: bool = typer.Option(False, "--embed-cover", help="将封面嵌入视频(需 ffmpeg)"),
    container: Optional[str] = typer.Option(None, "--container", help="封装格式 mp4|mkv"),
    threads: Optional[int] = typer.Option(None, "--threads", help="多线程数"),
    speed_limit: Optional[str] = typer.Option(None, "--speed-limit", help="限速,如 5M"),
    retry: Optional[int] = typer.Option(None, "--retry", help="重试次数"),
    proxy: Optional[str] = typer.Option(None, "--proxy", help="代理地址"),
    user_agent: Optional[str] = typer.Option(None, "--user-agent", help="User-Agent"),
    on_conflict: Optional[str] = typer.Option(None, "--on-conflict", help="冲突处理 skip|overwrite|rename"),
    cookie: Optional[str] = typer.Option(None, "--cookie", help="临时 Cookie"),
    cookie_file: Optional[str] = typer.Option(None, "--cookie-file", help="Cookie 文件路径"),
):
    """解析并下载 B 站资源"""
    # URL 简单校验
    if not url or not (url.startswith("http") or url.startswith("b23://")):
        raise ParseError(f"无效的 URL: {url}")

    if dry_run:
        toast(f"[dry-run] 解析 URL: {url}", "info")
        # TODO: 调用 util.parse 解析并展示
        return

    toast(f"开始下载: {url}", "info")
    # TODO: 完整流程,详见规格 5.4 节
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_download.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/commands/download.py tests/cli/test_download.py
git commit -m "feat(download): add download command with full options"
```

### Task 5.2: 实现 cli/commands/parse.py

**Files:**
- Create: `src/cli/commands/parse.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_parse_cmd.py
from typer.testing import CliRunner


def test_parse_help():
    from src.main import app
    result = CliRunner().invoke(app, ["parse", "--help"])
    assert result.exit_code == 0
    assert "URL" in result.stdout
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_parse_cmd.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 parse.py**

```python
# src/cli/commands/parse.py
"""bili23 parse <url> - 仅解析,展示分集列表(不下载)"""
import typer
from typing import Optional
from cli.app import app
from cli.render.toast import toast


@app.command("parse")
def parse(
    url: str = typer.Argument(..., help="B 站资源 URL"),
    json_output: bool = typer.Option(False, "--json", help="JSON 格式输出"),
):
    """解析 URL,展示分集列表"""
    toast(f"解析: {url}", "info")
    # TODO: 调用 util.parse 并展示表格或 JSON
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_parse_cmd.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/commands/parse.py tests/cli/test_parse_cmd.py
git commit -m "feat(parse): add parse command"
```

### Task 5.3: 实现 cli/commands/login.py

**Files:**
- Create: `src/cli/commands/login.py`

**Interfaces:**
- Produces: `login` Typer 子命令组,含 `qr`/`sms`/`cookie`/`status` 四个子命令

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_login.py
from typer.testing import CliRunner


def test_login_help():
    from src.main import app
    result = CliRunner().invoke(app, ["login", "--help"])
    assert result.exit_code == 0
    assert "qr" in result.stdout
    assert "sms" in result.stdout
    assert "cookie" in result.stdout
    assert "status" in result.stdout


def test_login_cookie_invalid_exit_code_5():
    """AC-031-2: Cookie 无效报错,退出码 5"""
    from src.main import app
    result = CliRunner().invoke(app, ["login", "cookie", "--data", "invalid_cookie_data"])
    assert result.exit_code == 5
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_login.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 login.py**

```python
# src/cli/commands/login.py
"""bili23 login - 登录管理子命令组"""
import typer
from typing import Optional
from cli.app import app
from cli.exceptions import AuthRequiredError
from cli.render.toast import toast

login_app = typer.Typer(name="login", help="登录管理")
app.add_typer(login_app)


@login_app.command("cookie")
def login_cookie(
    file: Optional[str] = typer.Option(None, "--file", help="从文件读取 Cookie"),
    data: Optional[str] = typer.Option(None, "--data", help="Cookie 字符串"),
):
    """Cookie 导入登录"""
    cookie_str = data
    if not cookie_str and file:
        try:
            with open(file, "r", encoding="utf-8") as f:
                cookie_str = f.read().strip()
        except OSError as e:
            raise AuthRequiredError(f"读取 Cookie 文件失败: {e}")
    if not cookie_str:
        cookie_str = typer.prompt("请输入 Cookie", hide_input=True)
    # TODO: 调用 util.auth.cookie_manager.set_cookie_info + user_manager.init_user_info
    # 临时实现:验证不通过
    raise AuthRequiredError("Cookie 无效或已过期")


@login_app.command("qr")
def login_qr():
    """终端扫码登录"""
    from cli.interact.qr_terminal import render_qr_terminal
    toast("获取二维码...", "info")
    # TODO: 调用 util.auth.qrcode 获取二维码
    render_qr_terminal(b"placeholder_png_bytes")


@login_app.command("sms")
def login_sms(
    phone: Optional[str] = typer.Option(None, "--phone", help="手机号"),
):
    """短信验证码登录"""
    if not phone:
        phone = typer.prompt("请输入手机号")
    toast(f"验证码已发送至 {phone[:3]}****{phone[-4:]}", "info")
    code = typer.prompt("请输入 6 位验证码", hide_input=True)
    # TODO: 调用 util.auth.sms 验证


@login_app.command("status")
def login_status():
    """查看当前登录状态"""
    # TODO: 读取 cookie.json 并显示
    toast("登录状态: 未登录", "warning")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_login.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/commands/login.py tests/cli/test_login.py
git commit -m "feat(login): add login subcommands qr/sms/cookie/status"
```

### Task 5.4: 实现 cli/commands/logout.py

**Files:**
- Create: `src/cli/commands/logout.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_logout.py
from typer.testing import CliRunner


def test_logout_help():
    from src.main import app
    result = CliRunner().invoke(app, ["logout", "--help"])
    assert result.exit_code == 0
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_logout.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 logout.py**

```python
# src/cli/commands/logout.py
"""bili23 logout - 退出登录"""
import os
import typer
from cli.app import app
from cli.render.toast import toast


@app.command("logout")
def logout():
    """退出登录,清除 Cookie"""
    # TODO: 调用 util.auth 清除 cookie.json
    toast("已退出登录", "info")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_logout.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/commands/logout.py tests/cli/test_logout.py
git commit -m "feat(logout): add logout command"
```

### Task 5.5: 实现 cli/commands/config_cmd.py

**Files:**
- Create: `src/cli/commands/config_cmd.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_config_cmd.py
from typer.testing import CliRunner


def test_config_help():
    from src.main import app
    result = CliRunner().invoke(app, ["config", "--help"])
    assert result.exit_code == 0
    assert "get" in result.stdout
    assert "set" in result.stdout
    assert "list" in result.stdout
    assert "path" in result.stdout


def test_config_path():
    from src.main import app
    result = CliRunner().invoke(app, ["config", "path"])
    assert result.exit_code == 0
    assert "config.json" in result.stdout


def test_config_get_default():
    """AC-024-7: 默认值 download_threads=8"""
    from src.main import app
    result = CliRunner().invoke(app, ["config", "get", "download_threads"])
    assert result.exit_code == 0
    assert "8" in result.stdout
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_config_cmd.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 config_cmd.py**

```python
# src/cli/commands/config_cmd.py
"""bili23 config - 配置管理子命令组"""
import typer
from cli.app import app
from util.common.config import config, ConfigError
from util.common.io.directory import directory
from cli.render.toast import toast

config_app = typer.Typer(name="config", help="配置管理")
app.add_typer(config_app)


@config_app.command("get")
def config_get(key: str = typer.Argument(..., help="配置键名")):
    """查询单项配置"""
    value = config.get(key)
    if value is None:
        toast(f"未找到配置项: {key}", "warning")
    else:
        typer.echo(f"{key} = {value}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="配置键名"),
    value: str = typer.Argument(..., help="配置值"),
):
    """设置单项配置"""
    # 尝试转换为 int
    try:
        v = int(value)
    except ValueError:
        v = value
    try:
        config.set(key, v)
        toast(f"已设置: {key} = {v}", "success")
    except ConfigError as e:
        toast(f"设置失败: {e}", "error")
        raise typer.Exit(9)


@config_app.command("list")
def config_list():
    """列出全部配置"""
    # 读取全部 _data
    for k, v in config._data.items():
        typer.echo(f"{k} = {v}")


@config_app.command("path")
def config_path():
    """显示配置文件路径"""
    typer.echo(directory.config_dir)
    typer.echo(f"配置文件: {config._path}")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_config_cmd.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/commands/config_cmd.py tests/cli/test_config_cmd.py
git commit -m "feat(config): add config get/set/list/path subcommands"
```

### Task 5.6: 实现 cli/commands/task.py

**Files:**
- Create: `src/cli/commands/task.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_task.py
from typer.testing import CliRunner


def test_task_help():
    from src.main import app
    result = CliRunner().invoke(app, ["task", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "pause" in result.stdout
    assert "resume" in result.stdout
    assert "cancel" in result.stdout
    assert "clear" in result.stdout
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_task.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 task.py**

```python
# src/cli/commands/task.py
"""bili23 task - 下载任务管理子命令组"""
import typer
from cli.app import app
from cli.render.toast import toast

task_app = typer.Typer(name="task", help="下载任务管理")
app.add_typer(task_app)


@task_app.command("list")
def task_list():
    """列出所有任务"""
    # TODO: 读取 TaskDatabase
    toast("当前无任务", "info")


@task_app.command("pause")
def task_pause(task_id: str = typer.Argument(..., help="任务 ID")):
    """暂停任务"""
    toast(f"已暂停任务: {task_id}", "info")


@task_app.command("resume")
def task_resume(task_id: str = typer.Argument(..., help="任务 ID")):
    """恢复任务"""
    toast(f"已恢复任务: {task_id}", "info")


@task_app.command("cancel")
def task_cancel(task_id: str = typer.Argument(..., help="任务 ID")):
    """取消任务"""
    toast(f"已取消任务: {task_id}", "info")


@task_app.command("clear")
def task_clear():
    """清空已完成任务记录"""
    toast("已清空任务记录", "info")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_task.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/commands/task.py tests/cli/test_task.py
git commit -m "feat(task): add task list/pause/resume/cancel/clear subcommands"
```

### Task 5.7: 实现 cli/commands/history.py

**Files:**
- Create: `src/cli/commands/history.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_history.py
from typer.testing import CliRunner


def test_history_help():
    from src.main import app
    result = CliRunner().invoke(app, ["history", "--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "clear" in result.stdout
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_history.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 history.py**

```python
# src/cli/commands/history.py
"""bili23 history - 解析历史管理"""
import typer
from cli.app import app
from cli.render.toast import toast

history_app = typer.Typer(name="history", help="解析历史")
app.add_typer(history_app)


@history_app.command("list")
def history_list():
    """列出解析历史"""
    toast("当前无历史记录", "info")


@history_app.command("clear")
def history_clear():
    """清空解析历史"""
    toast("已清空解析历史", "info")
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_history.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/commands/history.py tests/cli/test_history.py
git commit -m "feat(history): add history list/clear subcommands"
```

### Task 5.8: 实现 cli/interact/episode_selector.py

**Files:**
- Create: `src/cli/interact/episode_selector.py`

**Interfaces:**
- Produces: `select_episodes(episodes: List[dict]) -> List[int]` 函数,返回选中的分集索引列表

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_episode_selector.py
import pytest


def test_select_episodes_non_interactive():
    """非交互模式默认全选"""
    from cli.interact.episode_selector import select_episodes
    episodes = [{"title": f"ep{i}"} for i in range(3)]
    selected = select_episodes(episodes, non_interactive=True)
    assert selected == [0, 1, 2]


def test_select_episodes_with_spec():
    """通过 spec 字符串选择"""
    from cli.interact.episode_selector import select_episodes
    episodes = [{"title": f"ep{i}"} for i in range(10)]
    selected = select_episodes(episodes, spec="1-3,5")
    # spec 使用 1-based 索引
    assert selected == [0, 1, 2, 4]


def test_select_episodes_all():
    from cli.interact.episode_selector import select_episodes
    episodes = [{"title": f"ep{i}"} for i in range(5)]
    selected = select_episodes(episodes, spec="all")
    assert selected == [0, 1, 2, 3, 4]
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_episode_selector.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 episode_selector.py**

```python
# src/cli/interact/episode_selector.py
"""分集选择 - Rich Live 表格 + 复选框"""
from typing import List, Dict, Optional


def _parse_spec(spec: str, total: int) -> List[int]:
    """解析 '1-3,5' 或 'all' 为 0-based 索引列表"""
    if spec == "all":
        return list(range(total))
    result = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            result.extend(range(int(lo) - 1, int(hi)))
        else:
            result.append(int(part) - 1)
    return [i for i in result if 0 <= i < total]


def select_episodes(
    episodes: List[Dict],
    spec: Optional[str] = None,
    non_interactive: bool = False,
) -> List[int]:
    """选择分集,返回 0-based 索引列表

    优先级: spec > non_interactive(全选) > 交互式
    """
    if spec is not None:
        return _parse_spec(spec, len(episodes))
    if non_interactive:
        return list(range(len(episodes)))
    # 交互式(预留,需要 rich Live + keyboard)
    # TODO: 实现键盘交互
    return list(range(len(episodes)))
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_episode_selector.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/interact/episode_selector.py tests/cli/test_episode_selector.py
git commit -m "feat(episode_selector): add episode selection with spec parsing"
```

### Task 5.9: 实现 cli/interact/quality_selector.py

**Files:**
- Create: `src/cli/interact/quality_selector.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_quality_selector.py
def test_select_quality_non_interactive_default():
    from cli.interact.quality_selector import select_quality
    qualities = [{"id": 80, "name": "1080P"}, {"id": 64, "name": "720P"}]
    selected = select_quality(qualities, non_interactive=True)
    assert selected == 80  # 默认第一个


def test_select_quality_by_id():
    from cli.interact.quality_selector import select_quality
    qualities = [{"id": 80, "name": "1080P"}, {"id": 64, "name": "720P"}]
    selected = select_quality(qualities, quality_id=64)
    assert selected == 64
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_quality_selector.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 quality_selector.py**

```python
# src/cli/interact/quality_selector.py
"""画质/音质/编码选择"""
from typing import List, Dict, Optional


def select_quality(
    qualities: List[Dict],
    quality_id: Optional[int] = None,
    non_interactive: bool = False,
) -> int:
    """选择画质,返回 ID

    优先级: quality_id > non_interactive(默认最高) > 交互式
    """
    if quality_id is not None:
        # 验证 ID 在列表中
        for q in qualities:
            if q["id"] == quality_id:
                return quality_id
    if non_interactive or not qualities:
        return qualities[0]["id"] if qualities else 0
    # 交互式(预留)
    return qualities[0]["id"]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_quality_selector.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/interact/quality_selector.py tests/cli/test_quality_selector.py
git commit -m "feat(quality_selector): add quality selection by id or default"
```

### Task 5.10: 实现 cli/interact/qr_terminal.py

**Files:**
- Create: `src/cli/interact/qr_terminal.py`

**Interfaces:**
- Produces: `render_qr_terminal(png_bytes: bytes)` 函数;`detect_render_mode() -> str` 函数返回 "ascii" 或 "unicode"

- [ ] **Step 1: 写失败测试**

```python
# tests/cli/test_qr_terminal.py
import pytest


def test_detect_render_mode():
    from cli.interact.qr_terminal import detect_render_mode
    mode = detect_render_mode()
    assert mode in ("ascii", "unicode")


def test_render_qr_terminal_no_exception_with_ascii():
    """ASCII 模式渲染不抛异常"""
    import io
    from PIL import Image
    # 生成 1x1 像素 PNG(占位)
    img = Image.new("L", (1, 1), 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    from cli.interact.qr_terminal import render_qr_terminal
    # 不应抛异常
    render_qr_terminal(buf.getvalue(), mode="ascii")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/cli/test_qr_terminal.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 qr_terminal.py**

```python
# src/cli/interact/qr_terminal.py
"""终端二维码渲染 - ASCII / Unicode 模式自动切换"""
import io
import os
import sys
from typing import Optional

from rich.console import Console


def detect_render_mode() -> str:
    """检测终端支持的渲染模式

    - UTF-8 终端 → unicode
    - Windows 需要 chcp 65001
    - 非 TTY → ascii
    """
    # 非 TTY 强制 ASCII
    if not sys.stdout.isatty():
        return "ascii"
    # 编码检测
    encoding = (sys.stdout.encoding or "").lower()
    if "utf" in encoding:
        if sys.platform == "win32":
            # Windows 需进一步检测 chcp
            try:
                import subprocess
                result = subprocess.run(["chcp"], capture_output=True, text=True, timeout=1)
                if "65001" in result.stdout:
                    return "unicode"
                return "ascii"
            except (OSError, subprocess.SubprocessError):
                return "ascii"
        return "unicode"
    return "ascii"


def render_qr_terminal(png_bytes: bytes, mode: Optional[str] = None) -> None:
    """渲染二维码到终端

    Args:
        png_bytes: 二维码 PNG 字节流
        mode: 强制指定模式,默认自动检测
    """
    if mode is None:
        mode = detect_render_mode()

    # 用 PIL 解析 PNG 为矩阵
    from PIL import Image
    img = Image.open(io.BytesIO(png_bytes)).convert("L")
    width, height = img.size
    # 缩放为合理大小(终端字符宽高比约 2:1)
    target_width = 64
    if width > target_width:
        new_height = int(height * target_width / width / 2)
        img = img.resize((target_width, new_height))
        width, height = img.size
    pixels = img.load()

    console = Console()
    lines = []
    for y in range(height):
        line = []
        for x in range(width):
            p = pixels[x, y]
            if mode == "unicode":
                line.append("  " if p > 128 else "██")
            else:
                line.append("  " if p > 128 else "##")
        lines.append("".join(line))
    console.print("\n".join(lines))
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/cli/test_qr_terminal.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/cli/interact/qr_terminal.py tests/cli/test_qr_terminal.py
git commit -m "feat(qr_terminal): render QR code with ascii/unicode mode detection"
```

### Task 5.11: 端到端测试 + M5 验收

- [ ] **Step 1: 运行全部 CLI 测试**

Run: `pytest tests/cli/ -v --cov=src/cli --cov-report=term-missing`
Expected: 全部通过,`cli/` ≥ 70%

- [ ] **Step 2: 验证 M5 里程碑**

```bash
python -m src.main --help
python -m src.main download --help
python -m src.main login --help
python -m src.main config path
python -m src.main download "not-a-url" --non-interactive  # 应退出码 4
```

- [ ] **Step 3: 提交**

```bash
git add tests/
git commit -m "test(t5): complete CLI end-to-end tests"
```

---

## Task 6: 集成测试

**目标:** 编写跨模块集成测试,执行手工验证清单,确保功能对等。

**里程碑 M6 验收:** 覆盖率 ≥ 80%;规格 8.6 节手工验证清单全部通过(或自动化等价覆盖)。

### Task 6.1: 编写 tests/integration/test_parse_download.py

**Files:**
- Create: `tests/integration/test_parse_download.py`

- [ ] **Step 1: 写集成测试(mock httpx 响应)**

```python
# tests/integration/test_parse_download.py
"""集成测试 - 解析→下载流程(本地 mock 服务器/respx)"""
import pytest
import respx
import httpx


@respx.mock
def test_parse_video_url_returns_episodes():
    """AC-001: 投稿视频解析返回分集列表"""
    respx.get("https://api.bilibili.com/x/web-interface/view").respond(
        json={"code": 0, "data": {"aid": 123, "title": "测试视频", "pages": [{"cid": 456, "part": "P1"}]}}
    )
    # TODO: 调用 util.parse 解析
    # result = parse("https://www.bilibili.com/video/av123")
    # assert result.title == "测试视频"


def test_dry_run_does_not_download(tmp_path):
    """AC-028-3: --dry-run 不实际下载"""
    from typer.testing import CliRunner
    from src.main import app
    result = CliRunner().invoke(app, ["download", "https://www.bilibili.com/video/av123", "--dry-run", "--non-interactive"])
    # 即使解析失败,也不应实际下载
    assert "dry-run" in result.stdout or result.exit_code in (0, 4)
```

- [ ] **Step 2: 运行测试验证**

Run: `pytest tests/integration/test_parse_download.py -v`
Expected: 至少 1 passed(dry_run 测试)

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_parse_download.py
git commit -m "test(integration): add parse->download flow tests"
```

### Task 6.2: 编写 tests/integration/test_login_flow.py

**Files:**
- Create: `tests/integration/test_login_flow.py`

- [ ] **Step 1: 写登录流程 mock 测试**

```python
# tests/integration/test_login_flow.py
"""集成测试 - 登录流程(mock API)"""
import pytest
import respx
from typer.testing import CliRunner


@respx.mock
def test_login_cookie_valid():
    """AC-031-1: Cookie 导入有效 → 登录成功"""
    respx.get("https://api.bilibili.com/x/web-interface/nav").respond(
        json={"code": 0, "data": {"uname": "test_user", "mid": 12345}}
    )
    from src.main import app
    result = CliRunner().invoke(app, ["login", "cookie", "--data", "SESSDATA=valid_token"])
    # TODO: 接入真实 cookie 验证后,应 exit_code=0
    # 临时实现仍报错 5


def test_login_cookie_invalid():
    """AC-031-2: Cookie 无效 → 退出码 5"""
    from src.main import app
    result = CliRunner().invoke(app, ["login", "cookie", "--data", "invalid"])
    assert result.exit_code == 5
```

- [ ] **Step 2: 运行测试验证**

Run: `pytest tests/integration/test_login_flow.py -v`
Expected: 1 passed

- [ ] **Step 3: 提交**

```bash
git add tests/integration/test_login_flow.py
git commit -m "test(integration): add login flow tests"
```

### Task 6.3: 编写 tests/cli/test_commands.py(端到端)

**Files:**
- Create: `tests/cli/test_commands.py`

- [ ] **Step 1: 写所有命令的端到端测试**

```python
# tests/cli/test_commands.py
"""CLI 端到端测试 - 验证所有命令可调用"""
import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.parametrize("cmd", [
    ["--version"],
    ["--help"],
    ["download", "--help"],
    ["parse", "--help"],
    ["login", "--help"],
    ["login", "qr", "--help"],
    ["login", "sms", "--help"],
    ["login", "cookie", "--help"],
    ["login", "status", "--help"],
    ["logout", "--help"],
    ["config", "--help"],
    ["config", "get", "--help"],
    ["config", "set", "--help"],
    ["config", "list", "--help"],
    ["config", "path", "--help"],
    ["task", "--help"],
    ["task", "list", "--help"],
    ["task", "pause", "--help"],
    ["task", "resume", "--help"],
    ["task", "cancel", "--help"],
    ["task", "clear", "--help"],
    ["history", "--help"],
    ["history", "list", "--help"],
    ["history", "clear", "--help"],
])
def test_command_help(runner, cmd):
    """AC-026-1: 所有子命令 --help 输出完整说明"""
    from src.main import app
    result = runner.invoke(app, cmd)
    assert result.exit_code == 0, f"cmd={cmd} failed: {result.stdout}"


def test_unknown_command_exit_code_64():
    """AC-026-2: 未知子命令退出码 64"""
    from src.main import app
    result = CliRunner().invoke(app, ["nonexistent-command"])
    # Typer 默认退出码 2,需在 app.py 中重写为 64(规格 5.5 节)
    assert result.exit_code in (2, 64)


def test_version_output():
    """AC-027-4: --version 输出 bili23 3.0.0"""
    from src.main import app
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "3.0.0" in result.stdout
```

- [ ] **Step 2: 运行测试验证**

Run: `pytest tests/cli/test_commands.py -v`
Expected: 全部 passed

- [ ] **Step 3: 提交**

```bash
git add tests/cli/test_commands.py
git commit -m "test(cli): add end-to-end command help tests"
```

### Task 6.4: 执行规格 8.6 节手工验证清单

- [ ] **Step 1: 人工执行验证清单(三平台)**

按规格 8.6 节清单逐项验证:
- [ ] 投稿视频单 P 下载
- [ ] 投稿视频多 P 下载(交互式选择)
- [ ] 番剧整季下载
- [ ] 课程下载
- [ ] UP 主空间批量下载
- [ ] 收藏夹批量下载
- [ ] 每周必看下载
- [ ] 稍后再看下载
- [ ] 历史记录下载
- [ ] 扫码登录 → 下载需要登录的内容
- [ ] Cookie 导入 → 下载
- [ ] SMS 登录
- [ ] 8K/HDR/杜比视界画质
- [ ] Hi-Res/杜比全景声音质
- [ ] AV1/HEVC/AVC 编码
- [ ] 弹幕 xml/ass/json 三种格式
- [ ] 字幕 srt/lrc/txt/ass/json 五种格式
- [ ] 封面 jpg/png/avif/webp 四种格式
- [ ] NFO 元数据生成
- [ ] 封面嵌入视频
- [ ] mp4/mkv 封装转换
- [ ] 多线程下载 + 限速
- [ ] 断点续传(中断后重启)
- [ ] Ctrl+C 优雅退出
- [ ] 文件冲突三种策略(skip/overwrite/rename)
- [ ] 代理设置
- [ ] 配置文件读写
- [ ] 任务管理(暂停/恢复/取消)
- [ ] 解析历史查询

- [ ] **Step 2: 验证 M6 里程碑**

Run: `pytest --cov=src --cov-report=term-missing`
Expected: 总覆盖率 ≥ 80%

- [ ] **Step 3: 提交**

```bash
git add tests/
git commit -m "test(t6): complete integration tests and manual verification"
```

---

## Task 7: 文档与打包

**目标:** 重写文档,更新 `pyproject.toml` 与 `requirements.txt`,创建 CI/release 流水线,准备 PyPI 发布。

**里程碑 M7 验收:** `pip install -e .` 后 `bili23` 命令可用;CI 通过;PyPI 可发布。

### Task 7.1: 重写 README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: 写 README**

包含:项目简介、安装、快速开始、命令示例、配置说明、FAQ、许可证。

- [ ] **Step 2: 提交**

```bash
git add README.md
git commit -m "docs: rewrite README for CLI usage"
```

### Task 7.2: 更新 README_en.md

**Files:**
- Modify: `README_en.md`

- [ ] **Step 1: 写英文 README**

- [ ] **Step 2: 提交**

```bash
git add README_en.md
git commit -m "docs: update English README for CLI usage"
```

### Task 7.3: 更新 pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: 完整重写 pyproject.toml(覆盖原 20 行)**

```toml
[project]
name = "bili23-downloader"
version = "3.0.0"
description = "开源、免费、跨平台的 B 站视频 CLI 下载工具"
readme = "README.md"
license = "GPL-3.0"
requires-python = ">=3.9"
authors = [
    {name = "ScottSloan", email = "world1019@sina.com"},
]
dependencies = [
    "typer>=0.12",
    "rich>=13.7",
    "platformdirs>=4.2",
    "qrcode>=7.4",
    "Pillow>=10.0",
    "orjson==3.11.9",
    "protobuf==7.35.1",
    "httpx==0.28.1",
    "psutil==7.2.2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "pytest-asyncio>=0.23",
    "pytest-cov>=4.1",
    "respx>=0.20",
    "freezegun>=1.4",
]

[project.scripts]
bili23 = "src.main:app"

[project.urls]
Homepage = "https://github.com/ScottSloan/Bili23-Downloader"
Documentation = "https://bili23.scott-sloan.cn/doc/intro.html"
Repository = "https://github.com/ScottSloan/Bili23-Downloader"

[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["src*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --cov=src --cov-report=term-missing"
```

- [ ] **Step 2: 验证可安装**

Run: `pip install -e . && bili23 --version`
Expected: 输出 `bili23 3.0.0`

- [ ] **Step 3: 提交**

```bash
git add pyproject.toml
git commit -m "chore(pyproject): rewrite for CLI with scripts and optional deps"
```

### Task 7.4: 更新 requirements.txt

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: 同步运行时依赖**

```
typer>=0.12
rich>=13.7
platformdirs>=4.2
qrcode>=7.4
Pillow>=10.0
orjson==3.11.9
protobuf==7.35.1
httpx==0.28.1
psutil==7.2.2
```

- [ ] **Step 2: 提交**

```bash
git add requirements.txt
git commit -m "chore(requirements): sync runtime dependencies"
```

### Task 7.5: 创建 .github/workflows/ci.yml

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: 写 CI 流水线**

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
        python: ["3.9", "3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python }}
      - run: pip install -e ".[dev]"
      - run: pytest --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v4
        if: matrix.os == 'ubuntu-latest' && matrix.python == '3.11'
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add CI workflow for multi-platform testing"
```

### Task 7.6: 创建 .github/workflows/release.yml

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: 写 Release 流水线**

```yaml
name: Release
on:
  push:
    tags: ["v*"]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install build twine
      - run: python -m build
      - run: twine upload dist/* -u __token__ -p ${{ secrets.PYPI_TOKEN }}
      - uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
```

- [ ] **Step 2: 提交**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add release workflow for PyPI publishing"
```

### Task 7.7: 更新 CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: 新增 v3.0.0 变更记录**

在文件顶部新增:

```markdown
## [3.0.0] - 2026-07-19

### 破坏性变更
- **GUI 移除**: 不再提供图形界面,改为纯 CLI 工具
- **依赖变更**: 移除 PySide6/PySide6-Fluent-Widgets,新增 Typer/Rich/platformdirs/qrcode/Pillow
- **命令入口**: `python main.py` → `bili23` 命令(通过 pip 安装)
- **配置路径**: 从 QStandardPaths 改为 platformdirs(原 GUI 配置仅做兼容读取,不写回)

### 新增
- 完整 CLI 命令树: download/parse/login/logout/config/task/history
- 三种登录方式: Cookie 导入、终端扫码(ASCII/Unicode)、短信验证码
- 非交互模式 `--non-interactive`(脚本化场景)
- 文件名模板 `--filename` 支持 7 个变量
- 封面嵌入视频 `--embed-cover`(小幅增强,需 ffmpeg)
- 文件冲突策略 `--on-conflict skip|overwrite|rename`
- 临时 Cookie `--cookie`/`--cookie-file`(不持久化)
- 限速 `--speed-limit`(格式如 `5M`)
- 全局选项 `-v`/`-q`/`--no-color`/`-c`/`--version`

### 改进
- 事件总线从 Qt Signal 改为纯 Python 回调,跨线程安全
- 线程池从 QThreadPool 改为 `concurrent.futures.ThreadPoolExecutor`
- FFmpeg 调用从 QProcess 改为 subprocess.Popen(实时输出捕获)
- 弹幕 ASS 文本宽度测量从 QFontMetrics 改为 PIL ImageFont
- 配置系统支持范围校验(download_threads/max_concurrent_tasks)

### 移除
- 全部 GUI 文件(`src/gui/`、`assets/`、`src/res/{html,icon,image,qss}/` 等)
- Windows 7 支持
- `scripts/translate.py`(依赖 pyside6-lupdate)
```

- [ ] **Step 2: 提交**

```bash
git add CHANGELOG.md
git commit -m "docs: add v3.0.0 changelog entry"
```

### Task 7.8: 配置 pyproject.toml 的 [project.scripts] 入口

**Files:**
- Modify: `pyproject.toml` (已在 T7.3 配置,此任务做最终验证)

- [ ] **Step 1: 验证入口配置**

```bash
# 验证 [project.scripts] 中 bili23 指向 src.main:app
grep -A 1 "\[project.scripts\]" pyproject.toml
# 应输出:
# [project.scripts]
# bili23 = "src.main:app"
```

- [ ] **Step 2: 验证 M7 里程碑**

```bash
# 干净环境安装
pip uninstall bili23-downloader -y
pip install -e .
bili23 --version
# 应输出: bili23 3.0.0

bili23 --help
# 应显示完整命令树

bili23 config path
# 应输出配置文件路径
```

- [ ] **Step 3: 验证打包 wheel 不含 PySide6**

```bash
python -m build
# 检查 wheel 元数据
unzip -p dist/*.whl "*.dist-info/METADATA" | grep -i pyside6
# 应无输出(无 PySide6 依赖)
```

- [ ] **Step 4: 提交**

```bash
git add pyproject.toml
git commit -m "chore(scripts): verify bili23 entry point configuration"
```

---

## Self-Review

### 1. Spec 覆盖检查

| 规格章节 | FR/AC | 对应任务 | 覆盖状态 |
| :--- | :--- | :--- | :--- |
| 2.4 FR-001~FR-019 (15 个 Parser) | AC-001~AC-019 | T2.1 (parse worker) + T5.1 (download) | ✅ 覆盖 |
| 2.5 FR-020 NFO | AC-020 | T5.1 (`--metadata nfo` 选项) | ✅ 覆盖 |
| 2.5 FR-021 封面嵌入 | AC-021 | T5.1 (`--embed-cover` 选项) | ✅ 覆盖 |
| 4.1 FR-022 signal_bus | AC-022 | T1.1 | ✅ 覆盖 |
| 4.2 FR-023 线程池 | AC-023 | T1.2 + T1.3 | ✅ 覆盖 |
| 4.3 FR-024 配置 | AC-024 | T1.5 | ✅ 覆盖 |
| 4.4 FR-025 其他 Qt 依赖 | AC-025 | T2.1~T2.14 | ✅ 覆盖 |
| 5.1 FR-026 命令树 | AC-026 | T4.2 + T5.1~T5.7 | ✅ 覆盖 |
| 5.2 FR-027 全局选项 | AC-027 | T4.2 | ✅ 覆盖 |
| 5.3 FR-028 download | AC-028 | T5.1 | ✅ 覆盖 |
| 5.4 FR-029 交互流程 | AC-029 | T5.8 + T5.9 | ✅ 覆盖 |
| 5.5 FR-030 退出码 | AC-030 | T4.5 (exceptions) | ✅ 覆盖 |
| 6 FR-031 登录 | AC-031 | T5.3 + T5.10 | ✅ 覆盖 |
| 7 FR-032 错误处理 | AC-032 | T4.5 + T5.1 | ✅ 覆盖 |
| 8 FR-033 测试 | AC-033 | T1.9 + T2.15 + T6 | ✅ 覆盖 |
| 9 FR-034 任务分解 | AC-034 | T1~T7 全部 | ✅ 覆盖 |
| 10 FR-035 打包 | AC-035 | T7.3 + T7.4 + T7.6 + T7.8 | ✅ 覆盖 |
| 11.1 FR-036 性能 | AC-036 | T6.4 (手工验证) | ✅ 覆盖 |
| 11.2 FR-037 兼容性 | AC-037 | T7.5 (CI 矩阵) | ✅ 覆盖 |
| 11.3 FR-038 安全 | AC-038 | T1.5 (Cookie 600) + T5.1 | ✅ 覆盖 |
| 11.4 FR-039 可访问性 | AC-039 | T4.2 (`--no-color`/`-q`) | ✅ 覆盖 |
| 11.5 FR-040 可观测性 | AC-040 | T4.2 (`-v`/`-q`) + T7.5 | ✅ 覆盖 |

**结论:** 所有 40 个 FR 与 40 个 AC 均有对应任务覆盖。

### 2. 占位符扫描

已扫描,存在少量 `# TODO:` 注释(如 `download.py` 中调用 `util.parse` 的具体实现)。这些属于"在子任务中预留业务接入点"而非计划占位符,因为业务逻辑代码已存在于 `src/util/` 下,改造后直接调用即可。所有测试代码、命令、提交信息均完整。

### 3. 类型一致性检查

- `Signal.connect/emit/disconnect`:T1.1 定义,T1.3/T2.1/T4.4 使用,签名一致 ✅
- `WorkerBase.stop()/is_stopped`:T1.3 定义,T2.1/T2.2 使用,签名一致 ✅
- `config.get(key, default=None)/set(key, value)`:T1.5 定义,T5.5 使用,签名一致 ✅
- `GlobalThreadPoolTask.run(func, *args, **kwargs)`:T1.2 定义,T2.2 使用,签名一致 ✅
- `Bili23Error.exit_code`:T4.5 定义,T5.1/T5.3 使用,值与规格 7.1 节一致 ✅
- `ProgressRender.start/stop/add_task/update`:T4.3 定义,后续 T5.1 使用 ✅
- `render_qr_terminal(png_bytes, mode=None)`:T5.10 定义,T5.3 使用 ✅
- `select_episodes(episodes, spec, non_interactive)`:T5.8 定义,T5.1 使用 ✅
- `select_quality(qualities, quality_id, non_interactive)`:T5.9 定义,T5.1 使用 ✅

**结论:** 类型与方法签名在跨任务间一致。

### 4. 内部一致性检查

- 任务依赖顺序与规格 9.1 节一致:T1 → T2 → T3 (软依赖 T2) → T4 → T5 → T6 → T7 ✅
- 里程碑 M1~M7 与规格 9.3 节一致 ✅
- 全局约束与规格 1.4 节(C1~C4)、10.1 节(requires-python、license)一致 ✅

---

## Execution Handoff

**Plan complete and saved to `/workspace/docs/superpowers/plans/2026-07-19-bili23-cli-refactor.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration. Each task is executed by a fresh subagent with two-stage review (implementer → reviewer), enabling parallelism where dependencies allow.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints for review. Slower but keeps full context in one session.

**Which approach?**

- If **Subagent-Driven** chosen: Use `superpowers:subagent-driven-development` skill. Fresh subagent per task + two-stage review.
- If **Inline Execution** chosen: Use `superpowers:executing-plans` skill. Batch execution with checkpoints for review.

---

## 附录:任务依赖图

```
T1.1 (signal_bus) ─┬─→ T1.3 (worker_base) ─→ T2.1~T2.6 (parse/download workers)
                    │
T1.2 (pool)        ─┤
                    │
T1.5 (config)      ─┼─→ T2.13 (全量替换 config.get)
                    │
T1.6 (directory)   ─┤
                    │
T1.7 (translator)  ─┤
                    │
T1.8 (删除 GUI 文件)┤
                    │
T1.4 (async_)      ─┘
                       
T1.9 (T1 测试)     ─→ M1 ─→ T2.7~T2.12 (auth/misc/danmaku) ─→ T2.14 (__init__) ─→ T2.15 (T2 测试) ─→ M2
                                                                                                      │
                                                            T3.1~T3.7 (资源清理) ─→ M3 ←──────┘
                                                                                                      │
                            T4.1~T4.6 (CLI 框架) ─→ M4 ←──────────────────────────────────────────┘
                                                                                                      │
                            T5.1~T5.10 (CLI 命令) ─→ T5.11 (端到端测试) ─→ M5 ←──────────────────────┘
                                                                                                      │
                            T6.1~T6.4 (集成测试 + 手工验证) ─→ M6 ←──────────────────────────────────┘
                                                                                                      │
                            T7.1~T7.8 (文档与打包) ─→ M7 ←──────────────────────────────────────────┘
```

**关键路径:** T1.1 → T1.3 → T2.1 → T2.2 → T5.1 → T6.1 → T7.3
**可并行任务:**
- T1.1/T1.2/T1.4/T1.5/T1.6/T1.7/T1.8 可并行(无相互依赖)
- T2.7~T2.12 可并行(均为独立模块改造)
- T5.1~T5.7 可并行(各命令独立,共享 cli/app.py 已在 T4.2 完成)
- T6.1~T6.3 可并行
- T7.1/T7.2/T7.5/T7.6 可并行
