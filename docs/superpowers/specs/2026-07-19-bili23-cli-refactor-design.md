# Bili23-Downloader GUI 转 CLI 改造规格文档

| 字段 | 值 |
| :--- | :--- |
| 文档版本 | v1.0 |
| 创建日期 | 2026-07-19 |
| 作者 | DocReview 协作流程 |
| 状态 | 待审核 |
| 关联项目 | Bili23-Downloader (当前版本 2.11.0,目标版本 3.0.0) |

---

## 1. 项目背景与目标

### 1.1 背景

Bili23-Downloader 当前是一个基于 PySide6/Qt 的跨平台 B 站视频下载器(GUI 版本 2.11.0),主要特性包括多线程下载、多类型解析(投稿视频/番剧/课程/UP主空间/收藏夹等)、弹幕字幕封面 NFO 等附加产物、自定义命名规则等。

为适配服务器、脚本化、CI/CD 等无图形界面场景,需将仓库改造为纯 CLI 工具,同时移除所有 GUI 相关代码与资源。

### 1.2 目标

- **G1**:将基于 PySide6 的 GUI 应用改造为基于 Typer + Rich 的 CLI 应用
- **G2**:彻底移除 PySide6/PySide6-Fluent-Widgets 依赖,业务逻辑层(`src/util/`)与 Qt 完全解耦
- **G3**:保留原 GUI 全部下载能力(功能对等),包括所有解析类型与附加产物
- **G4**:删除所有 GUI 专属文件(控件、样式、图标、打包配置等)
- **G5**:支持三种登录方式(Cookie 导入、终端扫码、短信验证码)
- **G6**:支持交互式选择(分集/画质/附加产物)与脚本化非交互模式
- **G7**:提供完整测试覆盖(≥80%)与 CI 流水线
- **G8**:通过 PyPI 发布,`pip install bili23-downloader` 后 `bili23` 命令可用

### 1.3 非目标

- **N1**:不保留任何 GUI 入口或 GUI/CLI 双模式
- **N2**:不保留 PySide6 作为依赖(即使仅使用其非 GUI 部分)
- **N3**:不实现新的下载能力(如其他视频平台);但允许小幅后处理增强(如封面嵌入,见 FR-021)
- **N4**:不实现 GUI 配置文件到 CLI 配置文件的自动迁移工具(但会做兼容读取)
- **N5**:不支持 Windows 7(原 GUI 版本通过特殊 PySide6 兼容 Win7,CLI 版本不再支持)

### 1.4 假设与约束

- **A1**:用户已安装 Python 3.9+
- **A2**:用户在需要合并/转封装时已安装 FFmpeg(或通过配置指定路径)
- **A3**:原 `src/util/` 下的业务逻辑(解析、下载、登录)在去除 Qt 依赖后能保持功能等价
- **A4**:原 `src/res/i18n/` 下的翻译文件(.ts)可被解析为 Python dict 复用
- **C1**:必须保持跨平台(Windows/Linux/macOS)
- **C2**:必须保持 GPL-3.0 协议
- **C3**:CLI 命令名固定为 `bili23`(短名,便于输入)
- **C4**:PyPI 包名固定为 `bili23-downloader`(若被占用则用 `bili23-downloader-cli`,需在发布前查询)

---

## 2. 范围

### 2.1 移除清单

以下文件/目录将在改造中删除:

| 路径 | 类型 | 删除原因 |
| :--- | :--- | :--- |
| `src/gui/` | 目录 | GUI 控件层,全部移除 |
| `src/res/html/` | 目录 | captcha.html 验证码页面,GUI 专用 |
| `src/res/icon/` | 目录 | dark/light SVG 图标,GUI 专用 |
| `src/res/image/` | 目录 | noface.jpg、placeholder.png,GUI 专用 |
| `src/res/qss/` | 目录 | dark/light QSS 样式表,GUI 专用 |
| `src/res/resources.qrc` | 文件 | Qt 资源描述文件 |
| `src/res/resources_rc.py` | 文件 | Qt 资源编译产物 |
| `assets/app.icns` | 文件 | macOS 应用图标 |
| `assets/setup.iss` | 文件 | Inno Setup Windows 安装包脚本 |
| `.github/workflows/publish.yml` | 文件 | GUI 版打包发布流水线 |
| `.github/ISSUE_TEMPLATE/` | 目录 | GUI 版 Issue 模板(后续按需重建) |
| `scripts/translate.py` | 文件 | 依赖 `pyside6-lupdate` 且 sources 全为 GUI 文件(经核查) |

### 2.2 保留清单

以下文件/目录保留(部分需改造):

| 路径 | 处理方式 |
| :--- | :--- |
| `src/util/` | 保留目录结构,逐文件去除 Qt 依赖 |
| `src/res/i18n/` | 保留 .ts 翻译源文件,运行时改为 Python dict 加载 |
| `LICENSE` | 原样保留 |
| `CHANGELOG.md` | 更新,记录 CLI 改造变更 |
| `README.md` | 重写为 CLI 说明 |
| `README_en.md` | 重写为 CLI 英文说明 |
| `pyproject.toml` | 更新依赖与入口点 |
| `requirements.txt` | 同步更新 |
| `.gitignore` | 移除 GUI 专用条目 |
| `.gitattributes` | 原样保留 |

### 2.3 新增清单

| 路径 | 用途 |
| :--- | :--- |
| `src/cli/` | CLI 层(命令、交互、渲染、回调) |
| `src/main.py` | 重写为 Typer 入口(原 Qt 入口替换) |
| `tests/` | 测试目录(单元/集成/CLI 端到端) |
| `docs/superpowers/specs/` | 本规格文档所在目录 |
| `.github/workflows/ci.yml` | CI 流水线 |
| `.github/workflows/release.yml` | 发布流水线 |

### 2.4 功能对等矩阵(FR-001 ~ FR-019)

以下功能需求(FR)必须与原 GUI 版本对等。FR 编号、对应原 Parser 类、CLI 实现方式与 AC 验收标准一一对应:

| FR 编号 | 功能 | 原 Parser 类 | CLI 实现方式 | AC 编号 |
| :--- | :--- | :--- | :--- | :--- |
| FR-001 | 投稿视频下载 | `VideoParser` | `bili23 download <url>` + 交互式/参数 | AC-001 |
| FR-002 | 番剧下载 | `BangumiParser` | 同 FR-001 | AC-002 |
| FR-003 | 课程下载 | `CheeseParser` | 同 FR-001 | AC-003 |
| FR-004 | UP主空间下载 | `SpaceParser` | 同 FR-001 | AC-004 |
| FR-005 | 收藏夹下载 | `FavlistParser` | 同 FR-001 | AC-005 |
| FR-006 | 每周必看下载 | `PopularParser` | 同 FR-001 | AC-006 |
| FR-007 | 订阅合集(列表)下载 | `ListParser` | 同 FR-001 | AC-007 |
| FR-008 | 追番追剧下载 | `BangumiParser`(追番 tab) | 同 FR-001 | AC-008 |
| FR-009 | 稍后再看下载 | `WatchLaterParser` | 同 FR-001 | AC-009 |
| FR-010 | 历史记录下载 | `HistoryParser` | 同 FR-001 | AC-010 |
| FR-011 | 互动视频下载 | `InteractiveVideoParser`(在 `video.py` 内) | 同 FR-001 | AC-011 |
| FR-012 | 音频专辑下载 | `AudioParser` | 同 FR-001 | AC-012 |
| FR-013 | 动态下载 | `DynamicParser` | 同 FR-001 | AC-013 |
| FR-014 | 节日视频下载 | `FestivalParser` | 同 FR-001 | AC-014 |
| FR-015 | 单条收藏下载 | `FavoriteParser` | 同 FR-001 | AC-015 |
| FR-016 | b23.tv 短链解析 | `B23Parser` | 同 FR-001(自动跟随重定向) | AC-016 |
| FR-017 | 弹幕下载(xml/ass/json) | (附加产物) | `--danmaku [xml\|ass\|json]` | AC-017 |
| FR-018 | 字幕下载(srt/lrc/txt/ass/json) | (附加产物) | `--subtitle [srt\|lrc\|txt\|ass\|json]` | AC-018 |
| FR-019 | 封面下载(jpg/png/avif/webp) | (附加产物) | `--cover [jpg\|png\|avif\|webp]` | AC-019 |

> **说明**:
> - 原 `src/util/parse/parser/` 共 15 个 Parser 文件,本矩阵全部覆盖
> - `base.py` 为基类,不单独对应 FR
> - NFO 元数据生成归入 FR-020(附加产物,见下)
> - 封面嵌入视频(`--embed-cover`)为 CLI 版本小幅增强,见 FR-021

### 2.5 附加功能(FR-020 ~ FR-021)

| FR 编号 | 功能 | 原 GUI | CLI 实现 | AC 编号 |
| :--- | :--- | :--- | :--- | :--- |
| FR-020 | NFO 元数据生成 | GUI 选项 | `--metadata [nfo]` | AC-020 |
| FR-021 | 封面嵌入视频 | **新增**(原 GUI 无) | `--embed-cover`(需 ffmpeg) | AC-021 |

> **关于 FR-021**: 封面嵌入是 CLI 版本新增的小幅增强。虽然 N3 声明"不实现新的下载能力",但封面嵌入不属于"下载能力"(下载的是流本身,嵌入是后处理),属于合理增强。在 N3 中显式排除"封面嵌入"作为允许的小幅增强。

### 2.6 FR-001 ~ FR-021 验收标准(AC-001 ~ AC-021)

> 本节为 2.4/2.5 节 FR 矩阵的一一对应 AC,确保功能对等可机械化验证。

- **AC-001** (FR-001 投稿视频):
  - AC-001-1: `bili23 download <投稿视频单P URL> --non-interactive` 成功下载视频文件
  - AC-001-2: `bili23 download <投稿视频多P URL> --non-interactive --episodes 1-3` 下载指定分 P
  - AC-001-3: 交互式模式下分 P 列表正确展示,可勾选
- **AC-002** (FR-002 番剧):
  - AC-002-1: `bili23 download <番剧URL> --non-interactive --episodes all` 下载整季
  - AC-002-2: 番剧分集列表正确展示(含集号、标题、时长)
- **AC-003** (FR-003 课程): `bili23 download <课程URL> --non-interactive --episodes 1` 成功下载
- **AC-004** (FR-004 UP主空间):
  - AC-004-1: `bili23 download <UP主空间URL> --non-interactive` 列出全部投稿
  - AC-004-2: 大列表(>1000 条)翻页正常
- **AC-005** (FR-005 收藏夹): `bili23 download <收藏夹URL> --non-interactive --episodes 1-10` 下载前 10 条
- **AC-006** (FR-006 每周必看): `bili23 download <每周必看URL> --non-interactive` 列出本期全部视频
- **AC-007** (FR-007 订阅合集): `bili23 download <合集URL> --non-interactive --episodes all` 下载整个合集
- **AC-008** (FR-008 追番追剧): `bili23 download <追番页URL> --non-interactive` 列出追番列表
- **AC-009** (FR-009 稍后再看): `bili23 download <稍后再看URL> --non-interactive` 列出稍后再看列表
- **AC-010** (FR-010 历史记录): `bili23 download <历史记录URL> --non-interactive` 列出历史记录
- **AC-011** (FR-011 互动视频): `bili23 download <互动视频URL> --non-interactive` 成功下载(注:互动视频下载主线,不下载分支)
- **AC-012** (FR-012 音频专辑): `bili23 download <音频专辑URL> --non-interactive` 成功下载音频
- **AC-013** (FR-013 动态): `bili23 download <动态URL> --non-interactive` 成功下载动态中的视频
- **AC-014** (FR-014 节日视频): `bili23 download <节日视频URL> --non-interactive` 成功下载
- **AC-015** (FR-015 单条收藏): `bili23 download <单条收藏URL> --non-interactive` 成功下载
- **AC-016** (FR-016 b23 短链): `bili23 download <b23.tv短链> --non-interactive` 自动跟随重定向并下载
- **AC-017** (FR-017 弹幕):
  - AC-017-1: `--danmaku xml` 生成 xml 格式弹幕
  - AC-017-2: `--danmaku ass` 生成 ass 格式弹幕(含样式)
  - AC-017-3: `--danmaku json` 生成 json 格式弹幕
- **AC-018** (FR-018 字幕):
  - AC-018-1: `--subtitle srt/lrc/txt/ass/json` 五种格式均可生成
- **AC-019** (FR-019 封面):
  - AC-019-1: `--cover jpg/png/avif/webp` 四种格式均可下载原图
- **AC-020** (FR-020 NFO): `--metadata nfo` 生成 Kodi/Jellyfin/Emby 兼容的 NFO 文件
- **AC-021** (FR-021 封面嵌入): `--embed-cover` 生成的视频文件首帧为封面(需 ffmpeg)

---

## 3. 架构设计

### 3.1 改造后目录结构

```
src/
├── main.py                    # CLI 入口(Typer app)
├── cli/                       # CLI 层(新增)
│   ├── __init__.py
│   ├── app.py                 # Typer 应用与子命令注册、全局异常处理
│   ├── exceptions.py          # 异常类与退出码定义
│   ├── callbacks.py           # signal_bus 回调转 rich 输出
│   ├── commands/              # 子命令实现
│   │   ├── __init__.py
│   │   ├── download.py        # bili23 download <url>
│   │   ├── parse.py           # bili23 parse <url>
│   │   ├── login.py           # bili23 login qr/sms/cookie/status
│   │   ├── logout.py          # bili23 logout
│   │   ├── config_cmd.py      # bili23 config get/set/list/path
│   │   ├── task.py            # bili23 task list/pause/resume/cancel/clear
│   │   └── history.py         # bili23 history list/clear
│   ├── interact/              # 交互式选择
│   │   ├── __init__.py
│   │   ├── episode_selector.py    # 分集勾选(rich Live 表格)
│   │   ├── quality_selector.py    # 画质/音质/编码选择
│   │   └── qr_terminal.py         # 终端二维码渲染
│   └── render/                # 输出渲染
│       ├── __init__.py
│       ├── progress.py        # 下载/解析进度条(rich.Progress)
│       ├── table.py           # 表格输出
│       └── toast.py           # Toast 通知转终端提示
├── util/                      # 业务逻辑(保留结构,去 Qt)
│   ├── common/
│   │   ├── signal_bus.py      # 重写:事件总线(回调)
│   │   ├── config.py          # 重写:JSON + platformdirs
│   │   ├── translator.py      # 重写:Python dict 翻译
│   │   ├── io/directory.py    # 重写:platformdirs
│   │   └── (其余文件仅去 Qt)
│   ├── thread/
│   │   ├── pool.py            # 重写:ThreadPoolExecutor
│   │   ├── worker_base.py     # 重写:纯 Python 基类
│   │   └── async_.py          # 重写:threading 包装
│   ├── auth/                  # 登录(去 Qt)
│   ├── download/              # 下载(去 Qt)
│   ├── parse/                 # 解析(去 Qt)
│   ├── network/               # 网络(基本无 Qt)
│   ├── ffmpeg/                # FFmpeg 调用(QProcess → subprocess)
│   ├── format/                # 格式化(无 Qt)
│   └── misc/                  # 杂项(去 Qt)
└── res/
    └── i18n/                  # 仅保留翻译文件(.ts/.qm)
```

### 3.2 数据流

```
用户输入 URL
    │
    ▼
cli/commands/download.py        # Typer 命令入口,解析参数
    │
    ▼
util/parse/parser/*             # URL 识别 + 解析(保持原逻辑)
    │
    ▼
cli/interact/episode_selector   # 交互式选择(分集/画质/附加产物)
    │
    ▼
util/download/task/manager      # 创建任务(保持原逻辑)
    │
    ▼
cli/callbacks.py                # signal_bus 回调注册 → rich 输出
    │
    ▼
util/download/downloader        # 实际下载(多线程 + 合并)
util/ffmpeg/runner              # FFmpeg 合并/转封装
    │
    ▼
cli/render/progress.py          # rich.Progress 实时显示
```

### 3.3 配置优先级

从高到低:
1. **命令行参数**(`--video-quality` 等)
2. **配置文件**(`config.json`,由 platformdirs 定位)
3. **内置默认值**(`DefaultValue` 类)

> 注:环境变量支持作为开放问题 O4,首期不实现。

---

## 4. Qt 解耦策略

### 4.1 事件总线重写(FR-022)

**原设计**: 基于 `PySide6.QtCore.Signal` + `QObject`,通过 `signal.emit()` 触发,`signal.connect()` 注册回调,跨线程安全依靠 Qt 事件循环。

**新设计**: 基于 `dict` + 回调列表的纯 Python 事件总线。

**关键 API**:
- `Signal.connect(callback)`: 注册回调
- `Signal.disconnect(callback)`: 注销回调
- `Signal.emit(*args, **kwargs)`: 同步触发所有回调(在调用线程)
- `SignalBus.emit_signal(signal, *args, **kwargs)`: 保留 `pending_signals` 机制(原代码依赖)
- `SignalBus.emit_pending_signals()`: 标记 `main_window_ready=True` 并 flush 待发送信号

**约束**:
- `Signal.emit()` 在调用线程同步执行所有回调(不再支持 Qt 的 `QueuedConnection`)
- 跨线程场景由 `concurrent.futures.Future.add_done_callback` 或显式队列处理
- 原 `connect()` 调用代码无需改动(签名一致)
- 保留 `main_window_ready` 标志和 `pending_signals` 机制,CLI 启动时立即调用 `emit_pending_signals()`

**验收标准(AC-022)**:
- AC-022-1: `import util.common.signal_bus` 不触发 PySide6 导入
- AC-022-2: `connect` 后 `emit` 触发回调,`disconnect` 后不再触发
- AC-022-3: 跨线程 `emit` 安全(无竞态);测试方法: 启动 1000 个 `threading.Thread` 并发 `emit`,断言所有回调被调用且无异常,执行时间 < 5 秒
- AC-022-4: `pending_signals` 在 `main_window_ready=False` 时缓存,`True` 后 flush
- AC-022-5: 原 `signal_bus` 所有信号名称(ToastNotification/Parse/Download/Login/Update/Interface)保留

### 4.2 线程池重写(FR-023)

**原设计**: `QThreadPool.globalInstance()` + `QRunnable`。

**新设计**: `concurrent.futures.ThreadPoolExecutor` 全局单例。

**关键 API**:
- `GlobalThreadPoolTask.run(func, *args, **kwargs)`: 提交后台任务
- `GlobalThreadPoolTask.run_func(func, *args, **kwargs)`: 兼容原 API 别名
- 线程池大小: `min(32, (cpu_count or 4) * 4)`
- `atexit` 注册 `shutdown(wait=False)`

**WorkerBase 重写**:
- 继承 `object`(不再继承 `QObject`)
- 保留 `success/error/finished` 三个 `Signal`(纯 Python 版本)
- 新增 `_stop_event: threading.Event` 和 `stop()` / `is_stopped` 属性
- 移除 `@Slot()` 装饰器
- `run()` 方法签名不变

**QRunnable 替换**:
- 原 `class ChunkWorker(WorkerBase, QRunnable)` 改为 `class ChunkWorker(WorkerBase)`
- 提交方式: `GlobalThreadPoolTask.run(worker.run)` 替代 `pool.start(worker)`

**验收标准(AC-023)**:
- AC-023-1: `import util.thread` 不触发 PySide6 导入
- AC-023-2: `GlobalThreadPoolTask.run(func)` 能在后台执行 func
- AC-023-3: `WorkerBase.stop()` 后 `is_stopped` 返回 True
- AC-023-4: 线程池在程序退出时正确关闭(无挂起线程)

### 4.3 配置系统重写(FR-024)

**原设计**: 继承 `qfluentwidgets.QConfig`,使用 `ConfigItem`/`OptionsConfigItem`,通过 `qconfig.load()` 自动持久化,路径由 `QStandardPaths` 决定。

**新设计**: 纯 Python `Config` 类 + JSON 文件 + platformdirs。

**关键 API**:
- `Config.get(key, default=None)`: 读取配置项
- `Config.set(key, value)`: 设置并立即持久化
- `Config.save()`: 显式保存(通常由 `set` 自动调用)
- `Config.load()`: 加载配置文件

**路径规范**:
- 配置目录: `platformdirs.user_config_dir("Bili23-Downloader")`
- 数据目录: `platformdirs.user_data_dir("Bili23-Downloader")`
- 配置文件: `<config_dir>/config.json`
- Cookie 文件: `<data_dir>/cookie.json`(权限 600)
- 日志目录: `<data_dir>/logs/`
- 任务数据库: `<data_dir>/tasks.db`

**API 变更**:
- 原 `config.get(config.video_quality_id).value` → `config.get("video_quality_id")`
- 原 `config.video_quality_id` 属性访问 → 保留为属性(内部读写 `_data`)
- 全量替换: 通过 grep 找出所有 `config.get(config.xxx).value` 调用并改为 `config.get("xxx")`

**校验迁移**:
- 原 `RangeConfigItem` / `OptionsConfigItem` 的校验逻辑迁移到 `Config.set()` 中
- 校验失败抛出 `ConfigError`

**删除的配置项**:
- 主题(`theme`)
- 显示缩放(`display_scaling`)
- Mica 效果(`mica_effect`)
- 窗口几何信息等 GUI 专属项

**新增的配置项**(原 GUI 无,CLI 版本新增):
- `download_threads`(int,默认 8,范围 1-32): 下载单任务的多线程数
- `max_concurrent_tasks`(int,默认 3,范围 1-10): 同时进行的下载任务数上限
- 校验规则: `RangeConfigItem` 范围校验,超出范围抛出 `ConfigError`

**验收标准(AC-024)**:
- AC-024-1: `import util.common.config` 不触发 PySide6 导入
- AC-024-2: 配置文件不存在时使用默认值,不报错
- AC-024-3: 配置文件损坏(非法 JSON)时备份并重置为默认,输出警告
- AC-024-4: `set` 后立即持久化,重启后可读取
- AC-024-5: 并发 `set` 线程安全;测试方法: 启动 100 个 `threading.Thread` 并发 `set` 不同 key,断言所有写入持久化且无数据损坏,执行时间 < 3 秒
- AC-024-6: 配置目录跨平台正确(Windows/Linux/macOS)
- AC-024-7: `download_threads` 和 `max_concurrent_tasks` 范围校验生效

### 4.4 其他 Qt 依赖点处理(FR-025)

| 文件 | 原用法 | 替换方案 |
| :--- | :--- | :--- |
| `common/icon.py` | `QIcon`、`QPixmap` | 删除整个文件 |
| `common/style_sheet.py` | QSS 主题 | 删除整个文件 |
| `common/color.py` | `QColor` | 删除(CLI 用 rich.color 替代) |
| `common/translator.py` | `QTranslator` 加载 .qm | 重写为 Python dict,从 .ts 解析 |
| `common/io/directory.py` | `QStandardPaths` | 改用 platformdirs |
| `network/request.py` | `Signal`/`QObject`/`Slot` + 18 处 `config.get(config.` | 去除 Signal/QObject/Slot,改用回调或 logging;config 调用按 4.3 节 API 变更同步替换 |
| `auth/qrcode.py` | `QPixmap` 显示二维码 | 返回 PNG 字节流 + 终端渲染 |
| `auth/sms.py` | `QTimer` 轮询 | `threading.Timer` |
| `auth/cookie_login.py` | `QWebEngine`(若有) | 移除浏览器登录,仅保留 Cookie 导入 |
| `auth/server.py` | 无直接 PySide6 导入(仅通过 `signal_bus` 间接依赖 Qt) | 去除对 `signal_bus` 的引用(改为回调或 logging) |
| `auth/captcha.py` | `QPixmap` 验证码显示 | 终端 ASCII 渲染或保存 PNG |
| `download/downloader/downloader.py` | `QRunnable`/`QTimer`/`Slot`/`QMetaObject` | 见 4.2 |
| `download/downloader/merger.py` | `QProcess` | `subprocess.Popen` |
| `download/cover/manager.py` | `QPixmap` | 字节流保存,不预览 |
| `parse/worker.py` | `Signal`/`WorkerBase` | 见 4.1、4.2 |
| `parse/additional/file/danmaku_ass.py` | `QApplication.font()` + `QFontMetrics` 用于弹幕文本宽度计算(第 1-2、85、94 行) | 改用 PIL `ImageFont.textlength()` 或 `tkinter.font.Font.measure()` 测量文本宽度,移除 Qt 导入(详见 T2.12) |
| `misc/update.py` | `QNetworkAccessManager` | `httpx.get` |
| `misc/web.py` | `QDesktopServices.openUrl` | `webbrowser.open` |
| `ffmpeg/runner.py` | `QProcess` | `subprocess.Popen` |
| 各级 `__init__.py` | 可能含 Qt import | 检查并改造所有 `util/**/__init__.py`,确保无 Qt 导入 |

**验收标准(AC-025)**:
- AC-025-1: `import util` 整个包不触发 PySide6 导入
- AC-025-2: `pyproject.toml` 移除 PySide6 依赖后 `import util` 成功
- AC-025-3: FFmpeg 合并/转封装通过 subprocess 正常工作
- AC-025-4: `webbrowser.open` 能打开浏览器
- AC-025-5: `auth/server.py` 在去除 signal_bus 引用后仍能正常启动本地 HTTP 服务

---

## 5. CLI 命令设计

### 5.1 命令树(FR-026)

```
bili23
├── download <url>              # 解析并下载(主命令)
├── parse <url>                 # 仅解析,展示分集列表(不下载)
├── login                       # 登录管理(子命令组)
│   ├── qr                      # 终端扫码登录
│   ├── sms                     # 短信验证码登录
│   ├── cookie                  # Cookie 导入
│   └── status                  # 查看当前登录状态
├── logout                      # 退出登录
├── config                      # 配置管理(子命令组)
│   ├── get <key>               # 查询单项
│   ├── set <key> <value>       # 设置单项
│   ├── list                    # 列出全部配置
│   └── path                    # 显示配置文件路径
├── task                        # 下载任务管理(子命令组)
│   ├── list                    # 列出所有任务
│   ├── pause <task_id>         # 暂停任务
│   ├── resume <task_id>        # 恢复任务
│   ├── cancel <task_id>        # 取消任务
│   └── clear                   # 清空已完成任务记录
└── history                     # 解析历史
    ├── list                    # 列出解析历史
    └── clear                   # 清空解析历史
```

**验收标准(AC-026)**:
- AC-026-1: 所有子命令 `--help` 输出完整说明
- AC-026-2: 未知子命令退出码 64
- AC-026-3: `bili23`(无参数)显示主帮助
- AC-026-4: 子命令组(`login`/`config`/`task`/`history`)无子参数时显示子帮助

### 5.2 全局选项(FR-027)

```
bili23 [OPTIONS] COMMAND

Options:
  -c, --config PATH          指定配置文件路径(覆盖默认)
  -v, --verbose              详细日志输出(DEBUG 级别)
  -q, --quiet                静默模式(仅输出错误)
  --no-color                 禁用彩色输出
  --version                  显示版本
  --help                     显示帮助
```

**验收标准(AC-027)**:
- AC-027-1: `-c <path>` 指定配置文件可加载,路径不存在时报错退出码 9
- AC-027-2: `-v` 输出 DEBUG 级别日志,`-q` 仅输出 ERROR
- AC-027-3: `--no-color` 禁用所有 ANSI 颜色码
- AC-027-4: `--version` 输出 `bili23 3.0.0`
- AC-027-5: `--help` 输出主帮助

### 5.3 download 命令(FR-028)

```
bili23 download [OPTIONS] URL

Arguments:
  URL                        B 站视频/番剧/课程/收藏夹/UP主空间等链接

Options:
  # 输出控制
  -o, --output-dir PATH              输出目录(覆盖 config)
  -n, --filename TEMPLATE             文件名模板(覆盖 config,见 5.3.1 模板规范)
  --yes / -y                          跳过交互确认,使用默认/全部
  --non-interactive                   完全非交互(脚本模式,等价于 --yes)
  --dry-run                           仅模拟,不实际下载

  # 分集选择(覆盖交互)
  -e, --episodes SPEC                 分集选择,如 "1-5,10" 或 "all"
  -p, --page SPEC                     `-e` 的别名(全类型通用,非仅限投稿视频)

  # 画质/音质/编码(覆盖 config)
  --video-quality ID                  画质 ID(如 80=1080P,127=8K)
  --audio-quality ID                  音质 ID(如 30280=高码率)
  --video-codec ID                    视频编码(7=AVC,12=HEVC,13=AV1)

  # 附加产物(覆盖 config)
  --danmaku [xml|ass|json]            下载弹幕(可指定格式)
  --no-danmaku                        不下载弹幕
  --subtitle [srt|lrc|txt|ass|json]   下载字幕
  --no-subtitle                       不下载字幕
  --cover [jpg|png|avif|webp]         下载封面
  --no-cover                          不下载封面
  --metadata [nfo]                    生成 NFO 元数据
  --no-metadata                       不生成 NFO
  --embed-cover                       将封面嵌入视频(需 ffmpeg)

  # 输出格式
  --container [mp4|mkv]               输出封装格式(默认取 config.video_container,原默认 MP4)

  # 下载控制
  --threads N                         多线程数(默认取 config.download_threads,默认 8)
  --speed-limit RATE                  限速,格式 `<数字>[K|M|G]`(不区分大小写),如 `5M`、`1.5m`、`100K`
  --retry N                           重试次数(默认 5)

  # 网络
  --proxy URL                         代理地址(覆盖 config)
  --user-agent STRING                 User-Agent(覆盖 config)

  # 冲突处理
  --on-conflict [skip|overwrite|rename]  文件冲突处理策略

  # 登录态(临时覆盖)
  --cookie STRING                     临时 Cookie(SESSDATA=xxx;bili_jct=yyy)
  --cookie-file PATH                  从文件读取 Cookie
```

> **参数优先级说明**:
> - `--cookie` 与 `--cookie-file` 同时指定时,`--cookie` 优先(直接使用参数值,不读文件)
> - 临时 Cookie 优先级高于已登录 Cookie,且不持久化(仅本次命令有效)
> - `--video-quality` / `--audio-quality` / `--video-codec` 未指定时,使用 config 中配置的优先级列表(`video_quality_priority` 等)
> - `--threads` 未指定时,使用 config 中的 `download_threads`(默认 8)
> - `--container` 未指定时,使用 config 中的 `video_container`(原默认 MP4)

### 5.3.1 文件名模板规范(FR-028 子项)

`-n, --filename TEMPLATE` 支持以下模板变量(与原 `FileNameFormatter` 一致):

| 变量 | 含义 | 示例 |
| :--- | :--- | :--- |
| `{leaf_title}` | 叶子节点标题(分集标题) | `第1集` |
| `{parent_title}` | 父级标题(合集名) | `某番剧第一季` |
| `{episode_title}` | 完整分集标题 | `某番剧第一季-第1集` |
| `{number}` | 集号(按 `--starting-number` 起始) | `01` |
| `{cover_id}` | 封面 ID(aid/bid/season_id 等) | `av123456` |
| `{uploader}` | UP 主名 | `某UP主` |
| `{upload_date}` | 发布日期 | `2026-07-19` |

**优先级**:
1. 命令行 `--filename` 参数(本次命令有效,不持久化)
2. config 中对应类型(`video`/`bangumi`/`cheese` 等)的命名规则模板
3. 内置 `DefaultValue.naming_rule_list` 默认模板

**适用类型**: 投稿视频、番剧、课程、收藏夹、UP主空间等全部 15 种解析器类型,每种类型有独立模板(config 中可分别设置)。

**验收标准(AC-028)**:
- AC-028-1: `bili23 download --help` 输出完整选项说明
- AC-028-2: 无效 URL 退出码 4
- AC-028-3: `--dry-run` 不实际下载,仅输出解析结果
- AC-028-4: `--non-interactive --episodes 1-3` 全参数模式可执行
- AC-028-5: 交互式分集选择可用(方向键/空格/回车)
- AC-028-6: `--on-conflict skip` 文件已存在时跳过
- AC-028-7: `--cookie` 临时 Cookie 不持久化
- AC-028-8: `--threads 16` 多线程下载正常
- AC-028-9: `--speed-limit 5M` 限速生效(实际下载速度 ≤ 5MB/s ±10%)
- AC-028-10: `--speed-limit abc` 格式错误退出码 64
- AC-028-11: `-n "{number}-{leaf_title}"` 模板正确渲染文件名
- AC-028-12: `--container mkv` 输出 mkv 封装

### 5.4 交互式流程(FR-029)

`download` 命令默认交互式流程:

1. **解析 URL**: 显示解析进度条(rich.Progress),完成后展示表格(`| # | 标题 | 时长 | 清晰度 | 发布时间 |`)
2. **分集选择**(若未指定 `--episodes`): rich Live 表格 + 复选框,提示"方向键选择/空格勾选/a 全选/q 确认",默认全选
3. **画质/音质/编码选择**(若未指定 `--video-quality` 等): 单选列表(rich 表格),默认 config 优先级
4. **附加产物确认**(若未指定 `--danmaku` 等): 多选列表
5. **确认下载**: 显示摘要表格 + "确认下载? [Y/n]"
6. **下载过程**: 每个任务一个进度条(rich.Progress 多任务),实时显示已下载/总大小/速度/剩余时间/线程数;完成后显示 `✓ 任务名 1.2GB 5m32s`;全部完成后显示"下载完成: 5/5 成功,0 失败"

**验收标准(AC-029)**:
- AC-029-1: 解析进度条正确显示与消失
- AC-029-2: 分集表格正确渲染,支持键盘交互
- AC-029-3: 默认全选,按 `q` 确认
- AC-029-4: 下载进度条实时更新
- AC-029-5: 完成后摘要正确

### 5.5 退出码规范(FR-030)

| 码 | 含义 |
| :--- | :--- |
| 0 | 成功 |
| 1 | 部分失败(至少一个任务失败) |
| 2 | 全部失败 |
| 3 | 用户取消(Ctrl+C / ESC) |
| 4 | 解析失败(URL 无效、未找到资源) |
| 5 | 需要登录(内容需登录访问,但未登录或 Cookie 失效) |
| 6 | 网络错误(无法连接) |
| 7 | 磁盘空间不足 |
| 8 | FFmpeg 缺失(需要合并/转封装但未找到 ffmpeg) |
| 9 | 配置错误 |
| 64 | 命令行参数错误(参考 sysexits.h) |
| 70 | 内部错误(未捕获异常) |

**验收标准(AC-030)**:
- AC-030-1: 各场景退出码符合上表
- AC-030-2: Ctrl+C 退出码 3,且优雅停止所有 worker
- AC-030-3: 未登录访问需登录内容退出码 5

---

## 6. 登录流程(FR-031)

### 6.1 Cookie 导入(`bili23 login cookie`)

**命令**:
```
bili23 login cookie                          # 交互式输入
bili23 login cookie --file cookies.txt       # 从文件读取
bili23 login cookie --data "SESSDATA=xxx;bili_jct=yyy"
```

**流程**:
1. 读取 Cookie 字符串(交互输入 / 文件 / 参数)
2. 调用 `util/auth/cookie.py` 的 `cookie_manager.set_cookie_info()` 保存
3. 调用 `util/auth/user.py` 的 `user_manager.init_user_info()` 拉取用户信息验证
4. 成功输出: `✓ 登录成功: 用户名 [UID]`
5. 失败输出: `✗ Cookie 无效或已过期`,退出码 5

**存储**: `<data_dir>/cookie.json`,文件权限 600

### 6.2 终端扫码(`bili23 login qr`)

**命令**: `bili23 login qr`

**流程**:
1. 调用 `util/auth/qrcode.py` 获取二维码 URL 和 qrcode_key
2. 用 `qrcode` 库生成二维码矩阵
3. **终端渲染**(自动选择,检测逻辑见下):
   - ASCII 模式(默认,所有终端兼容): 用 `██` 和 `  ` 渲染
   - Unicode half-block 模式(支持 UTF-8 终端): 用 `▀▄█` 渲染,密度更高

**模式检测逻辑**:
- 检测 `sys.stdout.encoding`,若为 `utf-8` 或 `utf-16` 则使用 Unicode 模式
- Windows 平台额外检测 `chcp` 输出,65001 (UTF-8) 才用 Unicode 模式
- 用户可通过 `--no-color` 强制 ASCII 模式(复用全局选项)
- 非 TTY 环境(管道重定向)强制 ASCII 模式
4. 同时保存二维码 PNG 到 `<data_dir>/login_qr.png`
5. 启动轮询线程(`threading.Timer` 每 2 秒),调用状态查询
6. 终端显示倒计时(180 秒)和扫描状态:
   - `等待扫描...`
   - `已扫描,等待确认...`
   - `✓ 登录成功`
7. 成功后清除二维码显示,拉取用户信息

**渲染示例**:
```
█████████████████████████████
██ ▄▄▄▄▄ █ ▀▄▄▀█ ▄▄▄▄▄ ██
██ █   █ █▀▄▀ ▀ █   █ ██
...
█████████████████████████████

请使用 B 站手机客户端扫描上方二维码
或扫描此文件: /home/user/.local/share/Bili23-Downloader/login_qr.png

剩余时间: 178s | 状态: 等待扫描
```

### 6.3 短信登录(`bili23 login sms`)

**命令**:
```
bili23 login sms                      # 交互式
bili23 login sms --phone 13800138000  # 直接指定手机号
```

**流程**:
1. 输入手机号(若未指定)
2. 调用 `util/auth/sms.py` 发送验证码
3. 终端提示: `验证码已发送至 138****8000,请输入 6 位验证码:`
4. 用户输入验证码(masked 输入)
5. 调用 `util/auth/sms.py` 验证
6. 成功后保存 Cookie,拉取用户信息

### 6.4 登录状态查询(`bili23 login status`)

**命令**: `bili23 login status`

**已登录输出**:
```
登录状态: 已登录
用户名:   张三
UID:      12345678
登录方式: 扫码登录
登录时间: 2026-07-19 10:30:00
Cookie 有效期: 23h 45min
```

**未登录输出**:
```
登录状态: 未登录
请运行 `bili23 login qr` 扫码登录
```

**验收标准(AC-031)**:
- AC-031-1: Cookie 导入有效 → 登录成功
- AC-031-2: Cookie 导入无效 → 报错,退出码 5
- AC-031-3: 扫码登录二维码在终端正确渲染
- AC-031-4: 扫码登录 PNG 文件正确生成
- AC-031-5: 扫码超时(180s)后提示并退出
- AC-031-6: 短信登录验证码发送与验证流程完整
- AC-031-7: `login status` 正确显示登录态

---

## 7. 错误处理与边界场景(FR-032)

### 7.1 异常类层次

```
Bili23Error (基类, exit_code=70)
├── ParseError (exit_code=4)
├── AuthRequiredError (exit_code=5)
├── NetworkError (exit_code=6)
├── DiskFullError (exit_code=7)
├── FFmpegMissingError (exit_code=8)
├── ConfigError (exit_code=9)
└── UserCancelledError (exit_code=3)
```

### 7.2 全局异常处理

`cli/app.py` 注册 Typer 异常回调:
- `KeyboardInterrupt` → 输出"用户取消",退出码 3
- `Bili23Error` → 输出错误信息,退出码取自异常
- 其他异常 → 输出完整 traceback,退出码 70

### 7.3 重试与恢复

- **网络请求**: `httpx` 重试机制保留(`util/network/request.py`)
- **下载分块**: `ChunkWorker.max_retries = 5` 保留,失败后标记任务为 `FAILED`
- **解析失败**: 不重试,直接报错(原 GUI 行为)
- **断点续传**: 保留原 `TaskDatabase` 机制,任务状态持久化到 SQLite
- **Ctrl+C**: 捕获 `KeyboardInterrupt`,优雅停止所有 worker,保存当前进度,下次 `bili23 download <同URL>` 自动续传

### 7.4 边界场景

| 场景 | 处理 | 退出码 |
| :--- | :--- | :--- |
| URL 无效 | 解析阶段报错 | 4 |
| 资源不存在(404) | 解析阶段报错 | 4 |
| 需要大会员但未开通 | 提示并降级到可访问的最高画质 | 0 |
| 需要登录但未登录 | 提示运行 `bili23 login` | 5 |
| Cookie 过期 | 提示重新登录 | 5 |
| 网络中断 | 自动重试 5 次,仍失败则报错 | 6 |
| 磁盘空间不足 | 下载前检查,不足则报错 | 7 |
| FFmpeg 缺失(需合并) | 检查 `config.ffmpeg_path`,缺失则提示安装 | 8 |
| 文件已存在 | 按 `--on-conflict` 处理(skip/overwrite/rename) | 0 |
| 输出目录无写权限 | 报错 | 9 |
| 配置文件损坏 | 备份后重置为默认,警告提示 | 0 |
| 并发任务过多 | 按 `config.max_concurrent_tasks` 排队 | 0 |
| 空 URL | 提示用法 | 64 |
| 未知命令 | 提示用法 | 64 |

**验收标准(AC-032)**:
- AC-032-1: 所有边界场景退出码符合上表
- AC-032-2: Ctrl+C 后任务状态正确保存,可续传
- AC-032-3: 网络重试机制工作(5 次后报错)
- AC-032-4: 配置文件损坏时自动备份并重置,退出码 0(带警告输出)
- AC-032-5: 需要大会员但未开通时降级到可访问最高画质,退出码 0

---

## 8. 测试策略(FR-033)

### 8.1 测试分层

```
tests/
├── unit/                    # 单元测试
│   ├── test_signal_bus.py
│   ├── test_config.py
│   ├── test_thread_pool.py
│   ├── test_parser/         # 各 URL 解析器
│   ├── test_downloader.py   # 下载器(用 httpx mock)
│   └── test_formatters.py   # 文件名/时间/单位格式化
├── integration/             # 集成测试
│   ├── test_parse_download.py  # 解析→下载流程(本地 mock 服务器)
│   └── test_login_flow.py      # 登录流程(mock API)
├── cli/                     # CLI 端到端测试
│   ├── test_commands.py     # 用 CliRunner 调用
│   └── test_interact.py     # 交互式选择(用 pty)
└── fixtures/                # 测试数据
    ├── urls.txt
    ├── mock_responses/
    └── expected_outputs/
```

### 8.2 测试工具

- **pytest**: 测试框架
- **pytest-mock**: mock 工具
- **pytest-asyncio**: 异步测试
- **pytest-cov**: 覆盖率
- **respx**: mock httpx 请求
- **typer.testing.CliRunner**: CLI 端到端测试
- **freezegun**: 时间冻结

### 8.3 覆盖率目标

| 模块 | 覆盖率目标 |
| :--- | :--- |
| `util/common/` | ≥ 90% |
| `util/parse/` | ≥ 80% |
| `util/download/` | ≥ 75% |
| `cli/` | ≥ 70% |
| **总体** | **≥ 80%** |

### 8.4 关键测试用例

- **事件总线**: connect 后 emit 触发;disconnect 后不触发;跨线程 emit 安全;pending_signals 缓存与 flush
- **配置系统**: 不存在文件用默认;损坏 JSON 备份重置;set 后持久化;并发 set 线程安全
- **CLI 命令**: `--version` 输出版本;无效 URL 退出码 4;`--dry-run` 不下载;`--non-interactive --episodes 1-3` 全参数;`config get/set` 持久化
- **登录流程**: Cookie 有效 → 成功;Cookie 无效 → 报错;扫码 mock 生成与渲染;短信 mock 发送与验证

### 8.5 CI 集成

`.github/workflows/ci.yml`:
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
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
```

### 8.6 手工验证清单

改造完成后,人工执行以下场景验证(三平台:Windows 10/11、Ubuntu 22.04、macOS 14):

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

**验收标准(AC-033)**:
- AC-033-1: 单元测试全部通过
- AC-033-2: 集成测试全部通过
- AC-033-3: CLI 端到端测试全部通过
- AC-033-4: 覆盖率达到 8.3 节目标
- AC-033-5: 8.6 节手工验证清单全部通过
- AC-033-6: CI 在三平台 × 四 Python 版本全部通过

---

## 9. 任务分解与里程碑(FR-034)

### 9.1 任务依赖

```
T1(基础设施解耦) ──┬─→ T2(业务层去 Qt) ──→ T4(CLI 框架) ──┐
                   │                                       │
                   └─→ T3(资源清理,软依赖 T2)             ├─→ T6(集成测试)
                                                           │
                              T5(CLI 命令实现) ────────────┤
                                                           ▼
                                                    T7(文档与打包)
```

> **T2 与 T3 的软依赖说明**: T2 改造时若发现 util 代码引用 GUI 资源(如 `icon.py`、`resources_rc.py`),需同步删除被引用的资源;T3 负责 GUI 目录剩余文件的批量清理。建议 T2 完成后再执行 T3,避免并行导致 import 失败。

### 9.2 任务清单

#### T1: 基础设施解耦(阻塞项)
- T1.1 重写 `util/common/signal_bus.py`
- T1.2 重写 `util/thread/pool.py`
- T1.3 重写 `util/thread/worker_base.py`
- T1.4 重写 `util/thread/async_.py`
- T1.5 重写 `util/common/config.py`
- T1.6 重写 `util/common/io/directory.py`
- T1.7 重写 `util/common/translator.py`
- T1.8 删除 `util/common/icon.py`、`style_sheet.py`、`color.py`
- T1.9 编写 T1 单元测试(覆盖率门禁: `util/common/` ≥ 90%、`util/thread/` ≥ 90%)

**T1 验收**: `import util.common`、`import util.thread` 不触发 PySide6;T1 单测通过且覆盖率达门禁

#### T2: 业务层去 Qt
- T2.1 改造 `util/parse/worker.py`、`preview/worker.py`、`additional/worker.py`
- T2.2 改造 `util/download/downloader/downloader.py`(QRunnable → WorkerBase)
- T2.3 改造 `util/download/downloader/merger.py`、`ffmpeg/runner.py`(QProcess → subprocess)
- T2.4 改造 `util/download/downloader/parse_worker.py`
- T2.5 改造 `util/download/cover/manager.py`、`cache.py`、`query_worker.py`
- T2.6 改造 `util/download/task/manager.py`、`query_worker.py`、`reparse_worker.py`
- T2.7 改造 `util/auth/qrcode.py`(QPixmap + QTimer → 纯 Python)
- T2.8 改造 `util/auth/sms.py`(QTimer → threading.Timer)
- T2.9 改造 `util/auth/cookie_login.py`、`server.py`、`captcha.py`
- T2.10 改造 `util/network/request.py`(若有 Qt 依赖)
- T2.11 改造 `util/misc/update.py`、`web.py`
- T2.12 改造 `util/parse/additional/file/danmaku_ass.py`: 移除 `QApplication`/`QFontMetrics` 导入,改用 PIL `ImageFont.truetype(font_path, size).getlength(text)` 测量弹幕文本宽度(需新增 PIL/Pillow 依赖,或在无 Pillow 时回退到 `tkinter.font.Font.measure()`);保留原 `DanmakuLayoutEngine` 的轨道算法不变
- T2.13 全量替换 `config.get(config.xxx).value` → `config.get("xxx")`(经 grep 验证共 53 个文件、162 处调用)
- T2.14 改造所有 `util/**/__init__.py`,确保无 Qt 导入
- T2.15 编写 T2 单元测试(覆盖率门禁: `util/parse/` ≥ 80%、`util/download/` ≥ 75%、`util/auth/` ≥ 80%)

**T2 验收**: `import util` 整个包不触发 PySide6;`pyproject.toml` 移除 PySide6 后 import 成功;关键业务逻辑单测通过且覆盖率达门禁

#### T3: 资源清理
- T3.1 删除 `src/gui/` 整个目录
- T3.2 删除 `src/res/html/`、`icon/`、`image/`、`qss/`
- T3.3 删除 `src/res/resources.qrc`、`resources_rc.py`
- T3.4 删除 `assets/`
- T3.5 删除 `.github/workflows/publish.yml`、`ISSUE_TEMPLATE/`
- T3.6 删除 `scripts/translate.py`(经核查依赖 `pyside6-lupdate` 且 sources 全为 GUI 文件,必须删除)
- T3.7 更新 `.gitignore`

**T3 验收**: 仓库中无 GUI 文件;`git status` 干净;`src/res/` 仅剩 `i18n/`

#### T4: CLI 框架搭建
- T4.1 创建 `src/cli/` 目录结构
- T4.2 实现 `cli/app.py`(Typer 应用 + 全局选项 + 异常处理)
- T4.3 实现 `cli/render/`(console、progress、table、toast)
- T4.4 实现 `cli/callbacks.py`(signal_bus 回调注册)
- T4.5 实现 `cli/exceptions.py`(异常类与退出码)
- T4.6 编写 CLI 框架单元测试

**T4 验收**: `bili23 --version`、`bili23 --help` 正常;信号回调转 rich 输出工作

#### T5: CLI 命令实现
- T5.1 实现 `cli/commands/download.py`(主命令,含交互式)
- T5.2 实现 `cli/commands/parse.py`
- T5.3 实现 `cli/commands/login.py`(qr/sms/cookie/status)
- T5.4 实现 `cli/commands/logout.py`
- T5.5 实现 `cli/commands/config_cmd.py`
- T5.6 实现 `cli/commands/task.py`
- T5.7 实现 `cli/commands/history.py`
- T5.8 实现 `cli/interact/episode_selector.py`
- T5.9 实现 `cli/interact/quality_selector.py`
- T5.10 实现 `cli/interact/qr_terminal.py`(终端二维码渲染)
- T5.11 端到端测试(CliRunner + pty)

**T5 验收**: 所有命令 `--help` 完整;`bili23 download <url> --dry-run` 跑通;三种登录方式可用;交互式选择可用

#### T6: 集成测试
- T6.1 编写 `tests/integration/test_parse_download.py`
- T6.2 编写 `tests/integration/test_login_flow.py`
- T6.3 编写 `tests/cli/test_commands.py`
- T6.4 执行 8.6 节手工验证清单

**T6 验收**: 覆盖率 ≥ 80%;手工验证清单全部通过

#### T7: 文档与打包
- T7.1 重写 `README.md`(CLI 用法、安装、示例)
- T7.2 更新 `README_en.md`
- T7.3 更新 `pyproject.toml`(依赖、入口点 `bili23 = "src.main:app"`)
- T7.4 更新 `requirements.txt`
- T7.5 创建 `.github/workflows/ci.yml`
- T7.6 创建 `.github/workflows/release.yml`(PyPI 发布 + GitHub Release)
- T7.7 更新 `CHANGELOG.md`
- T7.8 配置 `pyproject.toml` 的 `[project.scripts]` 入口

**T7 验收**: `pip install -e .` 后 `bili23` 命令可用;CI 通过

### 9.3 里程碑

| 里程碑 | 任务 | 标志 |
| :--- | :--- | :--- |
| M1 | T1 完成 | `import util.common` 无 Qt |
| M2 | T2 完成 | `import util` 无 Qt |
| M3 | T3 完成 | 仓库无 GUI 文件 |
| M4 | T4 完成 | `bili23 --help` 正常 |
| M5 | T5 完成 | 所有命令可执行 |
| M6 | T6 完成 | 覆盖率 ≥ 80% |
| M7 | T7 完成 | PyPI 可发布 |

**验收标准(AC-034)**:
- AC-034-1: 每个任务(T1.x ~ T7.x)有明确的验收标准且全部满足
- AC-034-2: 里程碑 M1 ~ M7 按序达成,每个里程碑可独立验证

---

## 10. 打包与发布(FR-035)

### 10.1 pyproject.toml 更新

> **说明**: 本节为 `pyproject.toml` 的**完整重写版本**(原文件仅 20 行,无 `[project.scripts]`、`[tool.setuptools.packages.find]`、`[project.optional-dependencies]`、`[tool.pytest.ini_options]`),T7.3 任务执行时直接覆盖原文件。

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

### 10.2 发布流程

`.github/workflows/release.yml`:
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

### 10.3 版本策略

- 主版本号 `2.x → 3.0`:CLI 重构是破坏性变更
- README 和 CHANGELOG 明确说明:GUI 版本在 `v2-gui` 分支维护,CLI 版本进入 `v3.x`

**验收标准(AC-035)**:
- AC-035-1: `pip install -e .` 后 `bili23` 命令可用
- AC-035-2: `pip install bili23-downloader` 从 PyPI 安装可用(发布后)
- AC-035-3: `bili23 --version` 输出 `3.0.0`
- AC-035-4: CI 通过
- AC-035-5: 打包的 wheel 不包含 PySide6 依赖

---

## 11. 非功能性需求

### 11.1 性能(FR-036)

- **启动时间**: CLI 冷启动 < 500ms(Typer + rich + 加载配置)
- **下载速度**: 与原 GUI 版本一致(多线程 + 限速机制保留)
- **内存占用**: 单任务下载 < 200MB
- **大列表渲染**: UP 主空间/收藏夹可能有数千条目,rich 表格限制单次渲染 100 行,提示翻页

**验收标准(AC-036)**:
- AC-036-1: 冷启动时间 < 500ms;测试方法: 使用 `hyperfine --runs 10 bili23 --version` 测量,取三平台中位数
- AC-036-2: 下载速度不低于原 GUI 版本 90%;测试方法: 同一 URL、同一网络环境、同一时间段,分别用 GUI 版与 CLI 版下载 3 次取平均
- AC-036-3: 单任务下载内存 < 200MB;测试方法: 用 `psutil.Process().memory_info().rss` 在下载中采样峰值
- AC-036-4: 1000 条目列表渲染不卡顿(翻页机制工作);测试方法: mock 1000 条 UP 主投稿数据,渲染时间 < 1 秒

### 11.2 兼容性(FR-037)

- **Python**: 3.9 / 3.10 / 3.11 / 3.12
- **OS**: Windows 10+、Ubuntu 20.04+、macOS 11+
- **终端**: 兼容 ASCII 终端(自动降级)、支持 UTF-8 终端、Windows Terminal、iTerm2、GNOME Terminal
- **FFmpeg**: 可选(无 ffmpeg 时仅支持单流下载,不合并)
- **配置文件**: 兼容原 GUI 配置(自动读取,丢弃 GUI 专属项)

**验收标准(AC-037)**:
- AC-037-1: Python 3.9/3.10/3.11/3.12 全部通过 CI
- AC-037-2: Windows 10/Ubuntu 22.04/macOS 14 手工验证通过
- AC-037-3: ASCII 终端下二维码降级为 ASCII 模式
- AC-037-4: 无 FFmpeg 时单流下载正常,合并场景报错退出码 8
- AC-037-5: 原 GUI 配置文件能被读取(GUI 专属项被忽略并警告,不写回新路径,仅本次会话生效)

### 11.3 安全(FR-038)

- **Cookie 存储**: `<data_dir>/cookie.json`,文件权限 600(`chmod 600`)
- **日志脱敏**: 日志中不输出完整 Cookie、SESSDATA,只输出前 8 位
- **代理密码**: 代理 URL 中的密码在日志中脱敏
- **路径遍历**: 用户输入的 URL 标题作为文件名时,过滤 `..`、`/`、`\` 等危险字符(原 `FileNameFormatter` 已有,保留)
- **临时文件**: 下载临时文件在 `tempfile.mkdtemp()` 中,异常退出时清理

**验收标准(AC-038)**:
- AC-038-1: cookie.json 文件权限为 600(POSIX 系统)
- AC-038-2: 日志中 SESSDATA 显示为 `xxxxxxxx` 前 8 位 + `***`
- AC-038-3: 代理 URL `http://user:pass@host` 在日志中显示为 `http://user:***@host`
- AC-038-4: 包含 `../` 的标题被过滤为安全文件名
- AC-038-5: 异常退出后临时目录被清理(下次启动时扫描清理)

### 11.4 可访问性(FR-039)

- **彩色输出**: 支持 `--no-color` 禁用
- **非交互模式**: `--non-interactive` 完全无需用户输入
- **进度条**: 在非 TTY 环境自动降级为无进度条输出
- **帮助信息**: 所有命令和选项有中文帮助文本

**验收标准(AC-039)**:
- AC-039-1: `--no-color` 禁用所有 ANSI 颜色码
- AC-039-2: `--non-interactive` 模式下无任何交互提示
- AC-039-3: 非 TTY 环境(管道重定向)无进度条,仅输出文本结果
- AC-039-4: 所有命令 `--help` 输出中文说明

### 11.5 可观测性(FR-040)

- **日志级别**: DEBUG/INFO/WARNING/ERROR,通过 `-v` / `-q` 控制
- **日志文件**: `<data_dir>/logs/app.log`(保留原 TimedRotatingFileHandler 机制,去掉 Qt 部分)
- **进度文件**: 下载任务状态持久化到 SQLite,可恢复
- **退出码**: 严格遵循 5.5 节规范

**验收标准(AC-040)**:
- AC-040-1: `-v` 输出 DEBUG 级别日志,`-q` 仅输出 ERROR
- AC-040-2: 日志文件按天滚动,保留 15 天
- AC-040-3: 任务状态持久化到 SQLite,重启后可查询
- AC-040-4: 退出码严格遵循 5.5 节

---

## 12. 风险与缓解

| 风险 | 严重程度 | 概率 | 缓解措施 |
| :--- | :--- | :--- | :--- |
| `signal_bus` 重写后跨线程行为不一致 | 高 | 中 | 单元测试覆盖跨线程场景;保留 `pending_signals` 机制;关键路径 review |
| `config` API 变更导致全量调用方修改遗漏 | 高 | 高 | grep 全量替换 + 类型检查(mypy/pyright)+ 单元测试 |
| `QThreadPool` → `ThreadPoolExecutor` 行为差异(如取消) | 中 | 中 | `WorkerBase` 保留 `stop_event` 机制;中断测试 |
| `QProcess` → `subprocess` 行为差异(如实时输出) | 中 | 中 | ffmpeg 输出实时捕获 + 进度解析;集成测试 |
| 终端二维码在某些终端显示异常 | 中 | 中 | 提供备用 PNG 文件路径;ASCII 模式降级 |
| `i18n` 翻译系统重写后键值丢失 | 中 | 低 | 从 .ts 文件解析键值;对照原翻译逐项验证 |
| 原 GUI 配置文件迁移失败 | 中 | 低 | 迁移时备份原文件;无法识别的键忽略并警告 |
| Windows 终端 Unicode 显示问题 | 中 | 中 | 检测 `chcp`,UTF-8 模式才用 Unicode 渲染;否则 ASCII |
| 测试覆盖率不足导致回归 | 高 | 中 | 强制 80% 覆盖率门禁;关键路径 100% |
| 工作量超出预期 | 高 | 高 | 严格按里程碑推进;M1-M3 完成后即可独立验证 |

---

## 13. 开放问题

以下问题需在实施前确认或可在实施中决策:

- **O1**: ~~`scripts/translate.py` 是否保留?~~ **已决定**: 删除(经核查依赖 `pyside6-lupdate` 且 sources 全为 GUI 文件,见 2.1 移除清单与 T3.6)。如需 i18n 工具链另在 v3.1 重新设计。
- **O2**: `src/util/common/data/exclimbwuzhi.py` 文件名特殊,需确认其作用和是否依赖 Qt。决策时机:T2 阶段。
- **O3**: `src/util/misc/dm_pb2.py` 是 protobuf 生成文件,应保留但确认生成脚本是否存在(注:路径在 `util/misc/` 而非 `util/common/data/`)。决策时机:T2 阶段。
- **O4**: 环境变量支持(`BILI23_VIDEO_QUALITY` 等)是否实现?首期不实现,作为 v3.1 增强。
- **O5**: 原 GUI 配置文件路径与 CLI 的 `platformdirs` 路径不一致。**已决定**: 仅做兼容读取(读取旧路径 config.json,丢弃 GUI 专属项,不写回新路径,仅本次会话生效)。与 N4 一致,不实现迁移工具。
- **O6**: i18n 翻译复用方式:本规格确定为 Python dict(从 .ts 解析),实施时需编写 .ts → dict 的转换脚本或直接硬编码。
- **O7**: 原 GUI 版本维护:建议新建 `v2-gui` 分支保留 GUI 版本,主分支进入 `v3.x` CLI。决策时机:T7 阶段。
- **O8**: PyPI 包名 `bili23-downloader` 当前由本项目自己占用(版本 2.11.0)。由于本项目拥有该包名,3.0.0 作为破坏性版本号可直接覆盖发布(无需改名为 `bili23-downloader-cli`)。需在发布前再次确认 PyPI 上未被他人抢注。决策时机:T7 阶段。
- **O9**: FFmpeg 自动下载:本规格确定为不自动下载,只提示安装方法。可在 v3.1 增强。
- **O10**: Windows 7 支持:本规格确定不支持(去掉 Qt 后无兼容需求)。

---

## 14. 术语表

| 术语 | 含义 |
| :--- | :--- |
| FR | Functional Requirement,功能需求 |
| AC | Acceptance Criteria,验收标准 |
| Qt 解耦 | 移除 PySide6/PySide6-Fluent-Widgets 依赖,业务逻辑层不依赖 Qt |
| 事件总线 | `signal_bus.py` 重写后的纯 Python 信号/回调机制 |
| WorkerBase | 纯 Python 的 worker 基类,替代原 `QObject` 版本 |
| 分集 | 番剧/课程的每一集,或投稿视频的每一个分 P |
| 附加产物 | 弹幕、字幕、封面、NFO 等非视频本体文件 |
| 终端扫码 | 在终端用 ASCII/Unicode 字符渲染二维码供手机扫描 |
| 非交互模式 | `--non-interactive`,完全通过命令行参数执行,无任何用户输入提示 |
| TTY | Teletypewriter,指交互式终端(相对于管道重定向) |
| platformdirs | Python 库,提供跨平台的配置/数据目录路径 |

---

## 15. 变更记录

| 版本 | 日期 | 变更 |
| :--- | :--- | :--- |
| v1.0 | 2026-07-19 | 初始版本,基于 brainstorming 设计章节整理 |
| v1.1 | 2026-07-19 | DocReview 第 1 轮审核后修订:补全 FR-001~FR-021 与 AC 一一对应;补全遗漏的 5 个 Parser(互动视频/音频/动态/节日/单条收藏/b23);新增 `download_threads`/`max_concurrent_tasks` 配置项声明;修正 T2.4 路径错误;修正 O3 路径错误;决定 O1(translate.py)删除;统一 O5 表述与 N4 一致;补充 AC-022-3/AC-024-5 并发测试方法;补充 AC-036 性能测量方法;补充文件名模板规范 5.3.1;补充 `--container`/`--speed-limit` 格式说明;补充各级 `__init__.py` 改造任务 T2.14;补充 T1.9/T2.15 覆盖率门禁;补充 9.1 软依赖说明;补充 pyproject.toml 重写说明与 authors 字段;补充 AC-026/AC-027 命令树与全局选项验收 |
| v1.2 | 2026-07-19 | DocReview 第 2 轮审核后修订:修正 4.4 节 `danmaku_ass.py` 错误声明(实际使用 `QApplication`/`QFontMetrics`,非"无 Qt 依赖");T2.12 明确改造方案为 PIL `ImageFont.textlength()` 并新增 Pillow 依赖;修正 `auth/server.py` 表述为"无直接 PySide6 导入";FR-028a 改为 FR-028 子项以符合命名规范 |
