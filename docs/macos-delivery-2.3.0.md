# 拾句 2.3.0 · Apple Silicon 测试版交付

日期：2026-11-02。目标为用户 MacBook Air M2（8GB / 256GB）的首个测试版，不是正式发布或 macOS 27.2 的兼容性认证。

## 基线与范围

- 分支：`codex/macos-arm64`，未合并 `main`，未创建新 tag 或 GitHub Release。
- 实际构建提交：`adb5cf3a5fb36134884f5367993ef45f836f74db`。
- 源码版本 2.3.0，schema 13 不变；Python 3.14.6、PySide6 6.11.1、PyInstaller 6.21.0。
- 原生构建机：macOS 15.8.2 arm64；不是用户的 Mac 27.2 实机。
- 使用已确认的“展开书页 + 金色引号”图标，包内含 SVG / PNG / ICO / ICNS，应用名“拾句.app”。
- 原 Windows 数据、凭据标识、安装包和已发布 Release 不变。

## 产物

[构建运行及日志](https://github.com/djsdaijie-code/english-studio/actions/runs/41391233552) · [下载测试产物](https://github.com/djsdaijie-code/english-studio/actions/runs/41391233552/artifacts/13117921353)

Actions Artifact 名为 `Shiju-macOS-arm64`，需登录 GitHub；到期时间 2027-01-31。包含 `release/` 及脱敏构建报告，不包含测试数据库。

| 文件 | 字节数 | SHA-256 |
| --- | ---: | --- |
| Shiju-2.3.0-macOS-arm64.dmg | 64572913 | `f683129cf84c20648ebf32878c7b6fc53a836818f8952ebcf71c61133bba68f1` |
| Shiju-2.3.0-macOS-arm64.zip | 56236013 | `4d61af31b7f0dcded09480e9f9b63a6420ea19ccb75f64195635f6dfe4e77174` |

另含 `SHA256SUMS-macOS.txt`。包内应用文件逻辑大小 397754915 字节，审计计数 495（含符号链接指向文件），不是磁盘实际占用量。DMG 内带 Applications 快捷入口和安装说明。ZIP 通过 macOS ditto 生成以保留权限与符号链接。

以上三份文件已下载并保存到本机项目 `release/`。GitHub 外层 Artifact 摘要 `9817f46af07b1984fb9f2b10e4e22e8e524349192a91fb743aa27e753b54fd66` 与本地一致；内层 DMG、ZIP 的 SHA-256、ZIP 全部条目 CRC、应用版本、Mach-O arm64 标识、自带 CA 和 DMG UDIF 文件头均复核通过。本地复核记录为 `artifacts/macos-local-verification.json`，原始报告保存在 `artifacts/macos-download-41391233552/`。

## 已验证

- Windows：356 passed、1 skipped，115.47 秒；唯一跳过项为 Mac 原生钥匙串。
- Mac 原生：357 passed，36.14 秒，保留原 342 项并新增 15 项，包含真实钥匙串的随机测试项读写与清理。
- 原生 arm64 架构校验及 `codesign --verify --deep --strict` 通过。
- `.app` 打包版在非项目工作目录中两次启动；课程目录、Day 页面、enrollment 与进行中状态跨进程保留。启动测试使用 Qt offscreen，不代替 Finder/Dock 可见交互测试。
- 打包版 HTTPS 证书验证通过；使用自带 certifi CA，不关闭 TLS 校验，不覆盖显式 `SSL_CERT_FILE`。
- 包内包含深浅主题、图标、课程、QtCharts / SVG / Multimedia 及 macOS Cocoa 平台插件。
- 包审计未发现 `.db` / `.sqlite`、日志、录音、Key 配置文件、tests、Git 或运行数据目录；构建机没有用户生产凭据，不会把 Windows 凭据复制到包中。
- Windows 隔离可见窗口烟测通过；英文精读、主题、导入和重启书签验证记录位于 `artifacts/macos-windows-regression-20261102/`。
- 正式用户数据库前后 SHA-256 均为 `13b87a591ef5f92d9eeadf927f13add78be33afc9b2d3594ce3712e93b6f8428`，未用于测试。

## 数据和安装

1. 在 Mac 下载 Artifact，解压后打开 `release/Shiju-2.3.0-macOS-arm64.dmg`。
2. 把“拾句.app”拖入 Applications，退出 DMG，从 Applications 启动；无需安装 Python。
3. 这是 ad-hoc 完整性签名测试包，**没有 Apple Developer ID 签名或公证**。如被系统阻止，仅在确认来源和校验值后，通过“系统设置 → 隐私与安全性”确认打开；不要全局关闭 Gatekeeper。
4. Mac 数据保存在 `~/Library/Application Support/EnglishStudio/`，删除应用不会自动删除数据。
5. DeepSeek / MiniMax Key 需在 Mac 重新配置，保存至 macOS 钥匙串；不会随 Windows 数据备份转移。无 Key 时基础练习可用。

## 尚需用户实机验收

- Mac 27.2 上 Finder / Dock 启动、Retina 图标、真实布局和深浅主题。
- 中文路径、五笔及其他中文输入法组合与提交；Command 快捷键与键盘焦点。
- 真实音频输出、MiniMax / DeepSeek 联调、缓存复用、Space 重听、Enter 下一句和 Esc 暂停。
- 钥匙串首次授权体验、覆盖安装、删除应用后重装和学习数据保留。
- 用户真实输入、阅读、单词学习和长期运行体验；未声称完成真人手动验收。

构建工作流提示旧 Action 大版本依赖的 Node 20 已由平台转为 Node 24，本轮运行成功，属于后续维护事项而非应用阻塞问题。
