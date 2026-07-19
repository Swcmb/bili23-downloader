## [3.0.0] - 2026-07-19

### 重磅变更

**v3.0.0 是一次重大重构,将 Bili23-Downloader 从基于 PySide6 的 GUI 应用改造为基于 Typer + Rich 的纯 CLI 工具。**

- 完全移除 PySide6/PySide6-Fluent-Widgets 依赖
- 移除所有 GUI 控件、样式表、图标、打包配置
- 新增完整的 CLI 命令行接口
- 保留全部下载能力(功能对等)

### Added(新增)

#### CLI 子命令(7 类)

- `bili23 download <url>`:主下载命令,支持 19 种 URL 类型
- `bili23 parse <url>`:仅解析不下载,支持 JSON 输出
- `bili23 login qr/sms/cookie/status`:三种登录方式
- `bili23 logout`:登出
- `bili23 config get/set/list/path`:配置管理
- `bili23 task list/pause/resume/cancel/clear`:任务管理
- `bili23 history list/clear`:历史记录

#### 交互组件(3 个)

- 分集勾选(`--episodes 1-3,5` 或交互式)
- 画质/音质/编码选择(交互式或参数指定)
- 终端二维码渲染(Unicode 半块字符 + ASCII 后备)

#### 附加产物选项

- `--danmaku xml/ass/json`:弹幕
- `--subtitle srt/lrc/txt/ass/json`:字幕
- `--cover jpg/png/avif/webp`:封面
- `--metadata nfo`:NFO 元数据
- `--embed-cover`:封面嵌入视频(新增,需 ffmpeg)

#### 全局选项与运行模式

- 全局选项:`-c/--config`、`-v/--verbose`、`-q/--quiet`、`--no-color`、`--version`
- 非交互模式:`--non-interactive`(脚本化、CI/CD)
- Dry-run 模式:`--dry-run`(仅模拟,不实际下载)
- 退出码规范化:0/3/4/5/6/7/8/9/70

#### 基础设施

- 配置系统基于 platformdirs + JSON
- 完整测试套件:1167 个测试,覆盖率 85%
- CI/CD 流水线(GitHub Actions)
- 中英文 README

### Changed(变更)

- 事件总线:Qt Signal → 纯 Python 回调列表 + threading.Lock
- 线程池:QThreadPool → concurrent.futures.ThreadPoolExecutor
- Worker 基类:QObject → object + threading.Event
- 配置系统:QConfig/ConfigItem → JSON + platformdirs
- 子进程调用:QProcess → subprocess.Popen
- 网络请求:QNetworkAccessManager → httpx
- 字体度量:QApplication.font()/QFontMetrics → PIL ImageFont
- 二维码:QPixmap → PNG bytes(qrcode + Pillow)
- 定时器:QTimer → threading.Timer/Thread
- 文件路径:QStandardPaths → platformdirs
- 打开 URL:QDesktopServices → webbrowser.open
- 翻译系统:QTranslator → Python dict

### Removed(移除)

- 完全移除 PySide6 依赖
- 完全移除 PySide6-Fluent-Widgets 依赖
- 移除 `src/gui/` 目录(全部 GUI 控件)
- 移除 `src/res/{html,icon,image,qss}/` 资源
- 移除 `src/res/resources.qrc` 和 `resources_rc.py`
- 移除 `src/util/common/icon.py`、`style_sheet.py`、`color.py`
- 移除 `assets/` 目录(macOS 图标 + Windows Inno Setup 脚本)
- 移除 `.github/workflows/publish.yml`(GUI 版打包流水线)
- 移除 `.github/ISSUE_TEMPLATE/`
- 移除 `scripts/translate.py`(依赖 pyside6-lupdate)
- 移除浏览器登录方式(QWebEngine)
- 不再支持 Windows 7(原 GUI 版本通过特殊 PySide6 兼容)

### Fixed(修复)

- 跨线程事件总线竞态问题(纯 Python Lock 实现)
- 配置文件并发写入冲突(threading.Lock + 原子 rename)
- 模块循环导入(延迟导入模式)

### Deprecated(废弃)

- 无

### Security(安全)

- Cookie 文件权限改为 600(POSIX)
- 配置文件原子写入(tmp + rename)

### 文档

- README.md 完全重写为 CLI 说明
- README_en.md 完全重写
- 本 CHANGELOG 更新

## 2.11.0 (2026-07-16)
### 新增
- 支持使用 Cookie 登录
- 支持记忆下载列表的筛选设置，无需每次重新设置

### 优化
- 优化部分提示信息显示效果
- 提升下载时的界面响应速度
- 优化嵌入视频封面时的图片质量

### 修复
- 修复下载个人空间和收藏夹中的视频时，解析列表中的序号格式化结果异常的问题
- 修复从旧版本升级到 2.10.x 版本后，数据库文件未正确升级的问题
- 修复部分情况下，下载完成时找不到下载文件的问题
- 修复查看日志窗口显示异常的问题
- 修复部分气泡提示重复弹出的问题
- 修复部分电影解析失败的问题