# Bili23-Downloader

[![License](https://img.shields.io/badge/license-GPL--3.0-blue.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-%3E%3D3.9-blue.svg?style=flat-square)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-3.0.0-green.svg?style=flat-square)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-1167%20passed-brightgreen.svg?style=flat-square)](tests/)
[![Coverage](https://img.shields.io/badge/coverage-85%25-brightgreen.svg?style=flat-square)](tests/)

> Open source, free, cross-platform **command-line downloader** for Bilibili videos. Supports all Bilibili URL types.

[中文](README.md) | [English](README_en.md)

---

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Command Reference](#command-reference)
- [Configuration](#configuration)
- [Exit Codes](#exit-codes)
- [FFmpeg Dependency](#ffmpeg-dependency)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgements](#acknowledgements)

---

## Features

- **19 URL types**: user videos, bangumi, courses, user space, favorites, weekly must-watch, subscriptions, watch later, history, interactive videos, audio albums, dynamics, festival videos, single favorite, b23.tv short links, etc.
- **Three login methods**: QR code (rendered in terminal), SMS verification code, Cookie import
- **Multi-threaded download**: concurrent chunked download + FFmpeg muxing/remuxing
- **Side products**:
  - Danmaku: `xml` / `ass` / `json`
  - Subtitles: `srt` / `lrc` / `txt` / `ass` / `json`
  - Cover: `jpg` / `png` / `avif` / `webp` (lossless original)
  - NFO metadata (Kodi / Jellyfin / Emby compatible)
- **Cover embedding**: `--embed-cover` option (requires ffmpeg) writes the cover into the first video frame
- **Dual mode**: interactive selection (default) + scripted non-interactive mode (`--non-interactive`)
- **Cross-platform**: Windows 10+, Ubuntu 20.04+, macOS 11+
- **Persistent config**: based on `platformdirs` + JSON, auto-locates the user config directory
- **Task management & history**: pause, resume, cancel, bulk clear, and history review

---

## Installation

### From PyPI (recommended)

```bash
pip install bili23-downloader
```

### From source

```bash
git clone https://github.com/ScottSloan/Bili23-Downloader.git
cd Bili23-Downloader
pip install -e .
```

### Verify installation

```bash
bili23 --version
bili23 --help
```

### Requirements

- Python >= 3.9
- FFmpeg (optional; required for A/V muxing, remuxing, and cover embedding)
- Network access to `bilibili.com` and its subdomains

---

## Quick Start

### Show help

```bash
# Top-level help
bili23 --help

# Subcommand help
bili23 download --help
bili23 login --help
```

### QR code login

```bash
bili23 login qr
```

A QR code is rendered in the terminal. Scan it with the Bilibili mobile app to complete login. Cookies are persisted to the user data directory (POSIX permission 600).

### Download a video (interactive)

```bash
bili23 download "https://www.bilibili.com/video/BVxxxxx"
```

You will be prompted to select episodes, video quality / audio quality / codec, and side products, then the download starts.

### Non-interactive mode (scripting / CI/CD)

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

### Parse only (no download)

```bash
# Rich-text table output
bili23 parse "https://www.bilibili.com/video/BVxxxxx"

# JSON output (for scripting)
bili23 parse "https://www.bilibili.com/video/BVxxxxx" --json
```

### Dry-run

```bash
bili23 download "https://www.bilibili.com/video/BVxxxxx" --dry-run
```

Prints the download plan (title, episodes, quality, output directory) without actually downloading.

---

## Command Reference

The CLI entry point is `bili23`, with 7 subcommand groups. All commands support the global options `-c/--config`, `-v/--verbose`, `-q/--quiet`, `--no-color`, `--version`.

### `bili23 download <url>`

Download a Bilibili video / bangumi / course, etc.

| Option | Type | Description |
| :--- | :--- | :--- |
| `url` | argument | Bilibili URL (required) |
| `-o, --output` | path | Output directory (default: current directory) |
| `--filename` | template | Filename template |
| `--episodes` | spec | Episode spec, e.g. `1-3,5` or `all` (interactive by default) |
| `--video-quality` | ID | Video quality ID (127=8K, 120=4K, 116=1080P60, 80=1080P, 64=720P, 32=480P, 16=360P, etc.) |
| `--audio-quality` | ID | Audio quality ID (30280=Hi-Res, 30232=132K, 30255=Dolby, 30250=Atmos, 30240=64K) |
| `--video-codec` | string | Video codec: `AVC` / `HEVC` / `AV1` |
| `--danmaku` | format | Danmaku format: `xml` / `ass` / `json` |
| `--subtitle` | format | Subtitle format: `srt` / `lrc` / `txt` / `ass` / `json` |
| `--cover` | format | Cover format: `jpg` / `png` / `avif` / `webp` |
| `--metadata` | format | Metadata: `nfo` |
| `--embed-cover` | flag | Embed cover into video (requires ffmpeg) |
| `--threads` | int | Download threads (1-32) |
| `--concurrent` | int | Max concurrent tasks (1-10) |
| `--non-interactive` | flag | Non-interactive mode (options are the selection result) |
| `--dry-run` | flag | Simulate only, do not actually download |
| `--overwrite` | flag | Overwrite existing files |

### `bili23 parse <url>`

Parse a URL only; show title, uploader, and episode list without downloading.

| Option | Type | Description |
| :--- | :--- | :--- |
| `url` | argument | Bilibili URL (required) |
| `--json` | flag | Output the parse result as JSON |
| `--no-color` | flag | Disable colored output |

### `bili23 login <subcommand>`

Login management subcommand group.

| Subcommand | Description | Key options |
| :--- | :--- | :--- |
| `qr` | QR code login | `--timeout` (default 180s), `--invert` (dark terminal), `--mode unicode\|ascii` |
| `sms` | SMS verification login | `-p/--phone` (required), `-c/--country-code` (default 86), `--timeout` |
| `cookie` | Cookie import login | `-c/--cookie` (required), `--sessdata`, `--bili-jct`, `--dedeuserid` |
| `status` | Query current login status | none |

### `bili23 logout`

Clear the cookie file and log out of the current account.

| Option | Type | Description |
| :--- | :--- | :--- |
| `-y, --yes` | flag | Skip confirmation prompt |

### `bili23 config <subcommand>`

Configuration management subcommand group.

| Subcommand | Description |
| :--- | :--- |
| `get <key>` | Get a config value |
| `set <key> <value>` | Set a config value and persist (auto type-coerced) |
| `list` | List all config entries |
| `path` | Print the config file path |

### `bili23 task <subcommand>`

Download task management subcommand group (operates only on in-progress tasks; does not affect history).

| Subcommand | Description | Key options |
| :--- | :--- | :--- |
| `list` | List current tasks | `-n/--limit` (default 50), `--status downloading\|paused\|completed\|failed`, `--json` |
| `pause <task_id>` | Pause a task (downloading only) | `task_id` |
| `resume <task_id>` | Resume a task (paused only) | `task_id` |
| `cancel <task_id>` | Cancel and delete a task | `task_id`, `-y/--yes` |
| `clear` | Clear the task list | `-y/--yes`, `--status` |

### `bili23 history <subcommand>`

Download history subcommand group.

| Subcommand | Description | Key options |
| :--- | :--- | :--- |
| `list` | List download history | `-n/--limit` (default 50), `--offset`, `--json` |
| `clear` | Clear history records | `-y/--yes`, `--older-than N` (only records older than N days) |

---

## Configuration

### Config file path

The config file is located cross-platform via `platformdirs`. Run the following command to see the actual path:

```bash
bili23 config path
```

Typical paths:

| Platform | Path |
| :--- | :--- |
| Linux | `~/.config/Bili23-Downloader/config.json` |
| macOS | `~/Library/Application Support/Bili23-Downloader/config.json` |
| Windows | `%APPDATA%\Bili23-Downloader\config.json` |

### Config entries

| key | type | default | description |
| :--- | :--- | :--- | :--- |
| `video_quality_id` | int | `80` | Default video quality ID (1080P) |
| `audio_quality_id` | int | `30280` | Default audio quality ID (Hi-Res) |
| `video_codec` | int | `7` | Default video codec (7=AVC, 12=HEVC, 13=AV1) |
| `download_threads` | int | `8` | Download threads (1-32) |
| `max_concurrent_tasks` | int | `3` | Max concurrent tasks (1-10) |
| `video_container` | str | `mp4` | Output container (`mp4` / `mkv`) |
| `retry_count` | int | `5` | Network retry count |
| `video_quality_priority` | list | `[127, 126, ...]` | Quality priority (descending) |
| `audio_quality_priority` | list | `[30251, 30250, ...]` | Audio priority (descending) |
| `video_codec_priority` | list | `[7, 12, 13]` | Codec priority (descending) |
| `download_danmaku` | bool | `false` | Whether to download danmaku by default |
| `download_subtitle` | bool | `false` | Whether to download subtitles by default |
| `download_cover` | bool | `false` | Whether to download covers by default |
| `download_metadata` | bool | `false` | Whether to generate NFO by default |
| `user_agent` | str | Edge UA | Default User-Agent |
| `ffmpeg_source` | str | `bundled` | FFmpeg source: `bundled` / `system` / `custom` |
| `custom_ffmpeg_path` | str | `""` | Custom FFmpeg path (used when `ffmpeg_source=custom`) |

### Priority

```
CLI options > config file > default values
```

- **CLI options**: highest priority; only affects the current invocation
- **Config file**: modified via `bili23 config set`, persisted to JSON
- **Default values**: built into the code, see `src/util/common/config.py`

### Examples

```bash
# Set default download threads
bili23 config set download_threads 16

# Set default video codec to HEVC
bili23 config set video_codec 12

# Enable danmaku download by default
bili23 config set download_danmaku true

# Set a custom FFmpeg path
bili23 config set ffmpeg_source custom
bili23 config set custom_ffmpeg_path /usr/local/bin/ffmpeg

# List all config entries
bili23 config list
```

> Note: if the config file is corrupted, it is automatically backed up to `config.json.bak` and reset to defaults. See `src/util/common/config.py`.

---

## Exit Codes

The CLI follows conventional exit codes for scripting and CI/CD:

| Code | Meaning | Trigger |
| :--- | :--- | :--- |
| `0` | Success | Command completed normally |
| `3` | User cancelled | Ctrl+C or interactive cancellation |
| `4` | Parse error | URL not recognized or no episodes available |
| `5` | Login required | Cookie expired or accessing members-only content without login |
| `6` | Network error | Request timeout, DNS failure, etc. |
| `7` | Disk full | Insufficient disk space |
| `8` | FFmpeg missing | FFmpeg required for muxing/embedding but not found |
| `9` | Config error | Invalid config entry or type mismatch |
| `70` | Generic error | Unclassified Bili23 internal error |

The exception hierarchy is defined in `src/cli/exceptions.py`; each exception class maps to one `exit_code`.

---

## FFmpeg Dependency

FFmpeg is an optional dependency, required for the following scenarios:

- **A/V muxing**: high-quality Bilibili streams separate video and audio; FFmpeg merges them
- **Remuxing**: output `mp4` / `mkv` containers
- **Cover embedding**: `--embed-cover` writes the cover into the first frame

### Installation

#### Windows

```powershell
# Option 1: winget (Windows 10 1809+)
winget install Gyan.FFmpeg

# Option 2: manual download
# Download a release-full build from https://www.gyan.dev/ffmpeg/builds/,
# extract, and add the bin directory to PATH
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

### Configure FFmpeg source

```bash
# Use the ffmpeg found in system PATH
bili23 config set ffmpeg_source system

# Use a custom path
bili23 config set ffmpeg_source custom
bili23 config set custom_ffmpeg_path /opt/homebrew/bin/ffmpeg
```

---

## Development

### Setup

```bash
git clone https://github.com/ScottSloan/Bili23-Downloader.git
cd Bili23-Downloader
pip install -e ".[dev]"
```

### Running tests

```bash
# Full test suite
pytest

# With coverage
pytest --cov=src

# CLI end-to-end tests only
pytest tests/cli/
```

Current status: **1167 tests passing, 85% overall coverage**.

### Project structure

```
src/
├── main.py                    # CLI entry (Typer app)
├── cli/                       # CLI layer
│   ├── app.py                 # Typer app and global options
│   ├── exceptions.py          # Exception classes and exit codes
│   ├── callbacks.py           # signal_bus callbacks -> Rich output
│   ├── commands/              # Subcommand implementations
│   │   ├── download.py        # bili23 download <url>
│   │   ├── parse.py           # bili23 parse <url>
│   │   ├── login.py           # bili23 login qr/sms/cookie/status
│   │   ├── logout.py          # bili23 logout
│   │   ├── config_cmd.py      # bili23 config get/set/list/path
│   │   ├── task.py            # bili23 task list/pause/resume/cancel/clear
│   │   └── history.py         # bili23 history list/clear
│   ├── interact/              # Interactive components (episode/quality selectors, terminal QR)
│   └── render/                # Rich rendering (progress, tables, toasts)
├── util/                      # Business logic (pure Python, no Qt)
│   ├── auth/                  # Login (QR, SMS, Cookie)
│   ├── common/                # Config, directory, signal bus, enums, serialization
│   ├── download/              # Downloader, task manager, covers
│   ├── ffmpeg/                # FFmpeg command and runner
│   ├── network/               # httpx client, CDN, proxy
│   ├── parse/                 # URL parsers (15) + side products
│   └── thread/                # Thread pool
└── res/i18n/                  # Translation resources (.ts/.qm)
```

### Tech stack

- **CLI framework**: Typer + Rich
- **HTTP client**: httpx
- **Config**: platformdirs + JSON
- **QR code**: qrcode
- **Protobuf**: protobuf (protobuf danmaku parsing)
- **Testing**: pytest + respx + freezegun

---

## Contributing

Issues and Pull Requests are welcome.

### Development conventions

- **Code comments**: in Chinese (explain design intent, not behavior)
- **Code identifiers**: in English (variable/function/class names, commit messages)
- **Commit messages**: follow Conventional Commits (`feat:` / `fix:` / `docs:` / `refactor:`, etc.)
- **Tests**: new features must ship with unit tests; keep overall coverage at 85%+
- **Python version**: support 3.9+, avoid 3.10+-only syntax

### Submission flow

1. Fork the repository and create a feature branch (`feat/xxx` or `fix/xxx`)
2. Implement code and tests; run `pytest` locally to ensure it passes
3. Open a PR describing the change and referencing related issues

---

## License

This project is released under the [GPL-3.0](LICENSE) license.

> Wbi signature, specific APIs, and buvid3 generation are inspired by [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect).

### Terms of use

This project is for personal learning and research purposes only. Downloaded content **must be for personal, non-commercial use only; any commercial use, public dissemination, or distribution is strictly prohibited.**

This software operates solely on the user's legal account access permissions and **does not bypass any paywall or platform intellectual property protection.** Do not use this software for batch scraping or any action that violates the target platform's terms of service.

**Disclaimer**: Users must independently bear all risks associated with using this project (including but not limited to account bans, copyright disputes, etc.). The project developer assumes no responsibility for any direct or indirect legal disputes or damages caused by the use or inability to use this software.

---

## Acknowledgements

- The original [Bili23-Downloader](https://github.com/ScottSloan/Bili23-Downloader) author [Scott Sloan](https://github.com/ScottSloan)
- All community contributors who submitted code, issues, translations, and tests
- [SocialSisterYi/bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect) for the Bilibili API documentation
