# 英语打字练习器

英语打字练习器是一款面向 Windows 的本地桌面应用，用于导入英文 TXT 文章、逐字练习、保存进度，并根据历史错误安排专项与间隔复习。界面为简体中文，业务数据默认只保存在本机。

## 技术基线

- Python `>=3.14,<3.15`，当前验证环境为 Python 3.14.6
- PySide6 6.11.1
- SQLite（Python 标准库 `sqlite3`），schema version 3
- pytest 9.1.1
- PyInstaller 6.21.0 已列为开发依赖，但尚未开始正式打包

## 已完成功能

- 文章库：TXT 编码识别、中文路径导入、内容哈希去重、自动分段、搜索、重命名、软删除和重新分段。
- 普通练习：大小写、空格、标点和换行校验，实时 WPM/CPM/正确率/错误数，暂停、继续、专注模式及段落完成结果。
- 持久化：练习结果、文章进度、基础设置和中途退出状态保存；重新启动后可继续上次位置。
- 历史与统计：历史记录、单次详情、有效成绩筛选、趋势、学习总览和错误分析。
- 专项与复习：错词、错误字符、原句练习、生词本和间隔复习计划。
- 产品界面：简体中文界面、浅色/深色主题、练习专注模式。
- 数据质量：正式速度统计仅纳入 `completed = 1`、`correct_characters >= 100`、`active_seconds >= 30` 的非自动化记录；不足记录保留但显示“数据不足”。

## 项目结构

```text
src/english_typing_trainer/
  application/     应用启动与依赖组装
  database/        SQLite 管理、迁移和 repository
  models/          数据模型
  services/        文章、练习、统计和复习业务服务
  statistics/      指标计算规则
  typing_engine/   输入判定与单调计时
  ui/              PySide6 中文界面
tests/             自动化测试
resources/         示例文章与 QSS 主题
scripts/           运行、清理和未来打包入口
```

## 安装与启动

```powershell
if (Test-Path .\.venv) { Remove-Item -Recurse -Force .\.venv }
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\main.py
```

也可以运行 `powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1`。

## 数据目录

正式 Windows 数据目录为 `%LOCALAPPDATA%\EnglishTypingTrainer\`，其中包含 `typing_trainer.db`、`logs\` 和 `backups\`。应用通过统一路径服务解析目录，不依赖当前工作目录。

开发、测试和验收必须设置独立目录：

```powershell
$env:ENGLISH_TYPING_TRAINER_DATA_DIR = "$env:TEMP\EnglishTypingTrainer-Test"
.\.venv\Scripts\python.exe .\main.py
```

pytest 使用自身的临时目录 fixture，不得接触正式用户数据库。

## 测试

```powershell
$env:ENGLISH_TYPING_TRAINER_DATA_DIR = "$env:TEMP\EnglishTypingTrainer-Pytest"
.\.venv\Scripts\python.exe -m pytest -v
```

完整测试数量以实际 pytest 输出为准。本次发布基线结果记录在 `PROJECT_STATUS.md`。

## 数据库迁移

数据库由 `src/english_typing_trainer/database/migrations.py` 管理。首次启动按顺序创建 schema；旧数据库依次执行 v1、v2、v3 迁移。不要手工修改 `schema_version`，升级前应备份整个数据目录。

## 已知限制

- 尚未完成正式 PyInstaller 打包，也未验证无 Python 环境的 Windows 启动。
- 真人连续打字至少 60 秒仍须按 `MANUAL_TEST_CHECKLIST.md` 完成，自动化输入不能替代。
- 在线词典、翻译、TTS、用户账户和云同步不在当前范围内。
- 卸载时用户数据保留或清理策略仍需在正式发布前明确。

## 数据备份

升级、清理记录或迁移电脑前，请先正常退出应用，再完整复制 `%LOCALAPPDATA%\EnglishTypingTrainer\`。复制整个目录可避免遗漏 SQLite 的 `-wal` / `-shm` 文件。