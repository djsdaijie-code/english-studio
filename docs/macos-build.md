# 拾句 macOS Apple Silicon 测试版

目标设备：MacBook Air M2、8GB 内存；目标使用系统为用户提供的 macOS 27.2。
应用基线：Python 3.14、PySide6 6.11.1、SQLite schema 13。

## 数据与凭据

- macOS 数据目录：`~/Library/Application Support/EnglishStudio/`。
- 数据库、日志、备份和音频缓存集中保存在该目录，删除 `.app` 不会删除学习数据。
- `ENGLISH_TYPING_TRAINER_DATA_DIR` 可覆盖数据目录，测试和验收使用独立目录。
- macOS Key 使用系统钥匙串，仅调用 keyring 的原生 macOS 后端，不使用明文文件或内存作为生产存储替代。
- Windows 的 `%LOCALAPPDATA%\EnglishStudio`、旧数据迁移及 Windows 凭据标识不改变。
- 两个平台数据库结构一致，本轮没有新增迁移；Windows 的 API Key 不随数据库备份转移，需在 Mac 中重新配置。

## 源码运行和构建

在原生 Apple Silicon Python 3.14 环境执行：

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
# 生成 Mac 包（含完整测试）：
.venv/bin/python scripts/package_macos.py
```

也可执行 `zsh scripts/run_macos.command` 启动源码。构建只能在原生 arm64 macOS 上进行。
脚本使用 `Shiju-macOS.spec` 生成 `dist-macos/拾句.app`，打包本地 SVG、ICNS、主题、课程、QtCharts、QtSvg、QtMultimedia 和 macOS Qt 平台插件。
随后校验架构、代码完整性、无个人运行数据，并用独立目录执行两次启动验收。

产物：

- `release/Shiju-<版本>-macOS-arm64.dmg`：拖入 Applications 安装。
- `release/Shiju-<版本>-macOS-arm64.zip`：保留 `.app` 权限和符号链接的压缩包。
- `release/SHA256SUMS-macOS.txt`：SHA-256 校验文件。
- `artifacts/macos-build/report.json`：构建与资源审计报告。

GitHub Actions 使用 `.github/workflows/macos-build.yml`，在 `codex/macos-arm64` 分支推送时构建；也支持手动触发。
产物通过 Actions Artifact 提供，不自动发布到正式 GitHub Release。

## 测试版安装

1. 打开 DMG，把“拾句.app”拖入 Applications，退出磁盘映像。
2. 从 Applications 打开拾句。
3. 本版只有 ad-hoc 代码完整性签名，没有 Apple Developer ID 签名与公证；如 macOS 阻止启动，在“系统设置 → 隐私与安全性”中确认打开自己信任的测试包。
4. 无 Key 时基础练习、课程和已有缓存可使用；DeepSeek 翻译与 MiniMax 朗读需要用户自己的 Key。
5. 删除应用后，用户数据和钥匙串项目默认保留。

## 实机待验收

- macOS 27.2 中从 Finder 和 Dock 启动，深浅主题、Retina 图标和实际屏幕布局。
- 中文路径粘贴/导入、中文和五笔输入法组合与提交。
- Command+C / Command+V 在普通编辑框可用，练习输入区仍禁止粘贴。
- Enter 下一句、Space 重听、Esc 暂停与恢复。
- 声音实际输出、缓存复用和语速切换。
- Keychain 首次授权、Key 保存、读取和删除。
- 文章、英文精读、中文打字、单词本、FSRS 和课程的保存/重启恢复。
- 覆盖安装和移除应用后数据保留。

构建机自动测试不能代替上述用户实机验收。
