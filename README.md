# Bili23-Downloader

[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue.svg?style=flat-square)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-3.0.0-green.svg?style=flat-square)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-1167%20passed-brightgreen.svg?style=flat-square)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg?style=flat-square)](tests/)

> 开源、免费、跨平台的 B 站视频**命令行下载工具**,支持全部 B 站 URL 类型。

[中文](README.md) | [English](README_en.md)

---

## 目录

- [功能特性](#功能特性)
- [安装](#安装)
- [快速开始](#快速开始)
- [命令参考](#命令参考)
- [配置](#配置)
- [退出码](#退出码)
- [FFmpeg 依赖](#ffmpeg-依赖)
- [开发](#开发)
- [贡献](#贡献)
- [协议](#协议)
- [致谢](#致谢)

---

## 功能特性

- **19 种 URL 类型**:投稿视频、番剧、课程、UP 主空间、收藏夹、每周必看、订阅合集、追番追剧、稍后再看、历史记录、互动视频、音频专辑、动态、节日视频、单条收藏、b23.tv 短链等
- **三种登录方式**:扫码登录(终端二维码)、短信验证码、Cookie 导入
- **多线程下载**:并发分片下载 + FFmpeg 合并/转封装
- **附加产物**:
  - 弹幕:`xml` / `ass` / `json`
  - 字幕:`srt` / `lrc` / `txt` / `ass` / `json`
  - 封面:`jpg` / `png` / `avif` / `webp`(原图无损)
  - NFO 元数据(兼容 Kodi / Jellyfin / Emby)
- **封面嵌入视频**:`--embed-cover` 选项(需 ffmpeg),将封面写入视频首帧
- **双模式运行**:交互式选择(默认)+ 脚本化非交互模式(`--non-interactive`)
- **跨平台**:Windows 10+、Ubuntu 20.04+、macOS 11+
- **配置持久化**:基于 `platformdirs` + JSON,自动定位用户配置目录
- **任务管理与历史记录**:支持暂停、恢复、取消、批量清空与历史回溯

---

## 安装

### 从 PyPI 安装(推荐)

```bash
pip install bili23-downloader
```

### 从源码安装

```bash
git clone https://github.com/ScottSloan/Bili23-Downloader.git
cd Bili23-Downloader
pip install -e .
```

### 验证安装

```bash
bili23 --version
bili23 --help
```

### 环境要求

- Python >= 3.9
- FFmpeg(可选,用于音视频合并、转封装、封面嵌入)
- 网络可访问 `bilibili.com` 及其子域

---

## 快速开始

### 查看帮助

```bash
# 顶层帮助
bili23 --help

# 子命令帮助
bili23 download --help
bili23 login --help
```

### 扫码登录

```bash
bili23 login qr
```

终端会渲染二维码,使用手机哔哩哔哩客户端扫码完成登录。Cookie 持久化到用户数据目录(POSIX 权限 600)。

### 下载视频(交互式)

```bash
bili23 download "https://www.bilibili.com/video/BVxxxxx"
```

进入交互式选择:分集勾选、画质/音质/编码选择、附加产物勾选,确认后开始下载。

### 非交互模式(脚本化 / CI/CD)

```bash
bili23 download "https://www.bilibili.com/video/BVxxxxx" \
    --non-interactive \
    --episodes all \
    --video-quality 80 \
    --video-codec AVC \
    --danmaku xml \
    --subtitle srt \
    --cover jpg \
    --metadata nfo
```

### 仅解析不下载

```bash
# 富文本表格输出
bili23 parse "https://www.bilibili.com/video/BVxxxxx"

# JSON 输出(便于脚本解析)
bili23 parse "https://www.bilibili.com/video/BVxxxxx" --json
```

### 模拟下载(Dry-run)

```bash
bili23 download "https://www.bilibili.com/video/BVxxxxx" --dry-run
```

打印下载计划(标题、分集、画质、输出目录),不实际下载。

---

## 命令参考

CLI 入口为 `bili23`,共 7 类子命令。所有命令均支持全局选项 `-c/--config`、`-v/--verbose`、`-q/--quiet`、`--no-color`、`--version`。

### `bili23 download <url>`

下载 B 站视频/番剧/课程等。

| 选项 | 类型 | 说明 |
| :--- | :--- | :--- |
| `url` | 参数 | B 站 URL(必填) |
| `-o, --output` | 路径 | 输出目录(默认当前目录) |
| `--filename` | 模板 | 文件名模板 |
| `--episodes` | 规范 | 分集规范,如 `1-3,5` 或 `all`(默认交互选择) |
| `--video-quality` | ID | 画质 ID(127=8K,120=4K,116=1080P60,80=1080P,64=720P,32=480P,16=360P 等) |
| `--audio-quality` | ID | 音质 ID(30280=Hi-Res,30232=132K,30255=杜比,30250=全景声,30240=64K) |
| `--video-codec` | 字符串 | 视频编码:`AVC` / `HEVC` / `AV1` |
| `--danmaku` | 格式 | 弹幕格式:`xml` / `ass` / `json` |
| `--subtitle` | 格式 | 字幕格式:`srt` / `lrc` / `txt` / `ass` / `json` |
| `--cover` | 格式 | 封面格式:`jpg` / `png` / `avif` / `webp` |
| `--metadata` | 格式 | 元数据:`nfo` |
| `--embed-cover` | 标志 | 封面嵌入视频(需 ffmpeg) |
| `--threads` | 整数 | 下载线程数(1-32) |
| `--concurrent` | 整数 | 最大并发任务数(1-10) |
| `--non-interactive` | 标志 | 非交互模式(参数即选择结果) |
| `--dry-run` | 标志 | 仅模拟,不实际下载 |
| `--overwrite` | 标志 | 覆盖已存在文件 |

### `bili23 parse <url>`

仅解析 URL,展示标题、UP 主、分集列表,不下载。

| 选项 | 类型 | 说明 |
| :--- | :--- | :--- |
| `url` | 参数 | B 站 URL(必填) |
| `--json` | 标志 | 以 JSON 格式输出解析结果 |
| `--no-color` | 标志 | 禁用彩色输出 |

### `bili23 login <subcommand>`

登录管理子命令组。

| 子命令 | 说明 | 关键选项 |
| :--- | :--- | :--- |
| `qr` | 扫码登录 | `--timeout`(默认 180 秒)、`--invert`(深色终端)、`--mode unicode\|ascii` |
| `sms` | 短信验证码登录 | `-p/--phone`(必填)、`-c/--country-code`(默认 86)、`--timeout` |
| `cookie` | Cookie 导入登录 | `-c/--cookie`(必填)、`--sessdata`、`--bili-jct`、`--dedeuserid` |
| `status` | 查询当前登录状态 | 无 |

### `bili23 logout`

清除 Cookie 文件,登出当前账号。

| 选项 | 类型 | 说明 |
| :--- | :--- | :--- |
| `-y, --yes` | 标志 | 跳过确认提示 |

### `bili23 config <subcommand>`

配置管理子命令组。

| 子命令 | 说明 |
| :--- | :--- |
| `get <key>` | 获取配置项值 |
| `set <key> <value>` | 设置配置项值并保存(自动转换类型) |
| `list` | 列出所有配置项 |
| `path` | 打印配置文件路径 |

### `bili23 task <subcommand>`

下载任务管理子命令组(仅操作进行中任务,不影响历史记录)。

| 子命令 | 说明 | 关键选项 |
| :--- | :--- | :--- |
| `list` | 列出现存任务 | `-n/--limit`(默认 50)、`--status downloading\|paused\|completed\|failed`、`--json` |
| `pause <task_id>` | 暂停任务(仅 downloading) | `task_id` |
| `resume <task_id>` | 恢复任务(仅 paused) | `task_id` |
| `cancel <task_id>` | 取消并删除任务 | `task_id`、`-y/--yes` |
| `clear` | 清空任务列表 | `-y/--yes`、`--status` |

### `bili23 history <subcommand>`

下载历史记录管理子命令组。

| 子命令 | 说明 | 关键选项 |
| :--- | :--- | :--- |
| `list` | 列出下载历史 | `-n/--limit`(默认 50)、`--offset`、`--json` |
| `clear` | 清空历史记录 | `-y/--yes`、`--older-than N`(仅清除 N 天前) |

---

## 配置

### 配置文件路径

配置文件由 `platformdirs` 跨平台定位,运行以下命令查看实际路径:

```bash
bili23 config path
```

典型路径:

| 平台 | 路径 |
| :--- | :--- |
| Linux | `~/.config/Bili23-Downloader/config.json` |
| macOS | `~/Library/Application Support/Bili23-Downloader/config.json` |
| Windows | `%APPDATA%\Bili23-Downloader\config.json` |

### 配置项

| key | 类型 | 默认值 | 说明 |
| :--- | :--- | :--- | :--- |
| `video_quality_id` | int | `80` | 默认画质 ID(1080P) |
| `audio_quality_id` | int | `30280` | 默认音质 ID(Hi-Res) |
| `video_codec` | int | `7` | 默认视频编码(7=AVC,12=HEVC,13=AV1) |
| `download_threads` | int | `8` | 下载线程数(1-32) |
| `max_concurrent_tasks` | int | `3` | 最大并发任务数(1-10) |
| `video_container` | str | `mp4` | 输出容器(`mp4` / `mkv`) |
| `retry_count` | int | `5` | 网络重试次数 |
| `video_quality_priority` | list | `[127, 126, ...]` | 画质优先级(降序) |
| `audio_quality_priority` | list | `[30251, 30250, ...]` | 音质优先级(降序) |
| `video_codec_priority` | list | `[7, 12, 13]` | 编码优先级(降序) |
| `download_danmaku` | bool | `false` | 默认是否下载弹幕 |
| `download_subtitle` | bool | `false` | 默认是否下载字幕 |
| `download_cover` | bool | `false` | 默认是否下载封面 |
| `download_metadata` | bool | `false` | 默认是否生成 NFO |
| `user_agent` | str | Edge UA | 默认 User-Agent |
| `ffmpeg_source` | str | `bundled` | FFmpeg 来源:`bundled` / `system` / `custom` |
| `custom_ffmpeg_path` | str | `""` | 自定义 FFmpeg 路径(`ffmpeg_source=custom` 时生效) |

### 配置优先级

```
命令行参数 > 配置文件 > 默认值
```

- **命令行参数**:优先级最高,仅作用于本次调用
- **配置文件**:通过 `bili23 config set` 修改,持久化到 JSON
- **默认值**:代码内置,见 `src/util/common/config.py`

### 配置示例

```bash
# 设置默认下载线程
bili23 config set download_threads 16

# 设置默认视频编码为 HEVC
bili23 config set video_codec 12

# 设置默认开启弹幕下载
bili23 config set download_danmaku true

# 设置自定义 FFmpeg 路径
bili23 config set ffmpeg_source custom
bili23 config set custom_ffmpeg_path /usr/local/bin/ffmpeg

# 查看全部配置
bili23 config list
```

> 说明:配置文件损坏时,会自动备份为 `config.json.bak` 并重置为默认值,详见 `src/util/common/config.py`。

---

## 退出码

CLI 遵循规范退出码,便于脚本与 CI/CD 判断执行结果:

| 退出码 | 含义 | 触发场景 |
| :--- | :--- | :--- |
| `0` | 成功 | 命令正常完成 |
| `3` | 用户取消 | Ctrl+C 或交互式取消 |
| `4` | 解析错误 | URL 不识别或无可用分集 |
| `5` | 需要登录 | Cookie 失效或未登录访问会员内容 |
| `6` | 网络错误 | 请求超时、DNS 失败等 |
| `7` | 磁盘满 | 磁盘空间不足 |
| `8` | FFmpeg 缺失 | 合并/嵌入需要但未找到 FFmpeg |
| `9` | 配置错误 | 配置项非法或类型不符 |
| `70` | 通用错误 | 未分类的 Bili23 内部错误 |

异常层次定义于 `src/cli/exceptions.py`,每个异常类对应一个 `exit_code`。

---

## FFmpeg 依赖

FFmpeg 为可选依赖,以下场景必需:

- **音视频合并**:B 站高画质视频流与音频流分离,需用 FFmpeg 合并
- **转封装**:输出 `mp4` / `mkv` 容器
- **封面嵌入**:`--embed-cover` 将封面写入视频首帧

### 安装方法

#### Windows

```powershell
# 方式一:winget(Windows 10 1809+)
winget install Gyan.FFmpeg

# 方式二:手动下载
# 从 https://www.gyan.dev/ffmpeg/builds/ 下载 release-full 版本,
# 解压后将 bin 目录加入 PATH
```

#### macOS

```bash
# Homebrew
brew install ffmpeg
```

#### Linux

```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y ffmpeg

# Fedora
sudo dnf install -y ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

### 配置 FFmpeg 来源

```bash
# 使用系统 PATH 中的 ffmpeg
bili23 config set ffmpeg_source system

# 使用自定义路径
bili23 config set ffmpeg_source custom
bili23 config set custom_ffmpeg_path /opt/homebrew/bin/ffmpeg
```

---

## 开发

### 环境准备

```bash
git clone https://github.com/ScottSloan/Bili23-Downloader.git
cd Bili23-Downloader
pip install -e ".[dev]"
```

### 运行测试

```bash
# 全量测试
pytest

# 带覆盖率
pytest --cov=src

# 仅运行 CLI 端到端测试
pytest tests/cli/
```

当前状态:**1167 个测试通过,总体覆盖率 85%**。

### 项目结构

```
src/
├── main.py                    # CLI 入口(Typer app)
├── cli/                       # CLI 层
│   ├── app.py                 # Typer 应用与全局选项
│   ├── exceptions.py          # 异常类与退出码定义
│   ├── callbacks.py           # signal_bus 回调转 Rich 输出
│   ├── commands/              # 子命令实现
│   │   ├── download.py        # bili23 download <url>
│   │   ├── parse.py           # bili23 parse <url>
│   │   ├── login.py           # bili23 login qr/sms/cookie/status
│   │   ├── logout.py          # bili23 logout
│   │   ├── config_cmd.py      # bili23 config get/set/list/path
│   │   ├── task.py            # bili23 task list/pause/resume/cancel/clear
│   │   └── history.py         # bili23 history list/clear
│   ├── interact/              # 交互组件(分集选择、画质选择、终端二维码)
│   └── render/                # Rich 渲染(进度条、表格、Toast)
├── util/                      # 业务逻辑层(纯 Python,无 Qt 依赖)
│   ├── auth/                  # 登录(扫码、短信、Cookie)
│   ├── common/                # 配置、目录、信号总线、枚举、序列化
│   ├── download/              # 下载器、任务管理、封面
│   ├── ffmpeg/                # FFmpeg 命令与运行器
│   ├── network/               # httpx 客户端、CDN、代理
│   ├── parse/                 # URL 解析器(15 个)+ 附加产物
│   └── thread/                # 线程池
└── res/i18n/                  # 翻译资源(.ts/.qm)
```

### 技术栈

- **CLI 框架**:Typer + Rich
- **HTTP 客户端**:httpx
- **配置**:platformdirs + JSON
- **二维码**:qrcode
- **Protobuf**:protobuf(protobuf 弹幕解析)
- **测试**:pytest + respx + freezegun

---

## 贡献

欢迎通过 Issue 与 Pull Request 参与贡献。

### 开发规范

- **代码注释**:中文(说明设计意图,非功能描述)
- **代码标识符**:英文(变量名、函数名、类名、提交信息)
- **提交信息**:遵循 Conventional Commits(`feat:` / `fix:` / `docs:` / `refactor:` 等)
- **测试**:新增功能须附带单元测试,确保总体覆盖率不低于 85%
- **Python 版本**:兼容 3.9+,不使用 3.10+ 专有语法

### 提交流程

1. Fork 仓库并创建特性分支(`feat/xxx` 或 `fix/xxx`)
2. 编写代码与测试,本地运行 `pytest` 确保通过
3. 提交 PR,描述变更内容与关联 Issue

---

## 协议

本项目基于 [GPL-3.0](LICENSE) 协议发布。

> wbi 签名、部分接口以及 buvid3 等参数生成参考 [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)。

### 使用条款

本项目仅供个人学习与研究用途,下载内容**仅限于个人非商业使用,严禁用于任何形式的商业目的、公开传播或分发**。

本软件仅基于用户账号的合法访问权限操作,**不会绕过任何付费墙或平台知识产权保护措施**。请勿将本软件用于批量抓取或任何违反目标平台服务条款的行为。

**免责声明**:用户需完全自行承担使用本项目可能带来的所有风险(包括但不限于账号封禁、版权纠纷等)。项目开发者不对任何人因使用或无法使用本软件所引发的任何直接或间接法律纠纷、损害承担责任。

---

## 致谢

- 原 [Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) 项目作者 [Scott Sloan](https://github.com/ScottSloan)
- 所有为本项目贡献代码、提交 Issue、翻译与测试的社区贡献者
- [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) 提供的 B 站 API 文档
