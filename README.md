# 英语打字练习器

英语打字练习器是面向 Windows 的本地桌面应用。它支持导入英文 TXT、逐字或逐句练习、保存进度和历史，并根据错误记录安排专项与间隔复习。v0.2 开发版新增逐句学习、DeepSeek 翻译、全局句子缓存和分离式学习计时。

## 技术基线

- Python `>=3.14,<3.15`，当前验证环境 Python 3.14.6
- PySide6 6.11.1
- SQLite（标准库 `sqlite3`），schema version 4
- pytest 9.1.1；PyInstaller 6.21.0
- 当前开发版本 `0.2.0-dev`；现有 v0.1.0 可移植包保持不变

## 功能

- 文章库：中文路径 TXT 导入、编码识别、内容去重、自动分段、搜索、重命名、软删除和重新分段。
- 练习：普通连续模式、逐句学习模式、可见错误输入、Backspace、暂停、进度恢复和实时指标。
- 逐句学习：可靠拆句、首个有效输入开始计时、无输入自动暂停、句后学习暂停、Enter 下一句和每句成绩保存。
- 翻译：DeepSeek 异步按需翻译、前后句上下文、全局句子缓存、重点表达、人工编辑、重试及整篇后台翻译。
- 学习管理：历史记录、单次详情、学习统计、错误分析、错词/错误字符/原句专项练习、生词本和间隔复习。
- 产品界面：简体中文、浅色/深色主题和专注练习布局。

## 安装与运行

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\main.py
```

也可运行 `powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1`。

## 数据与隐私

正式数据目录为 `%LOCALAPPDATA%\EnglishTypingTrainer\`，包含数据库、日志和迁移备份。翻译缓存保存在 `typing_trainer.db` 的 `sentence_translations` 表；DeepSeek API Key 使用 Windows Credential Manager 保存，不进入数据库、配置文件或日志。

按句翻译仅发送当前句及可选前后句，不发送整篇文章。使用在线翻译即表示相关文本会发送给所选服务商；离线时仍可读取已有缓存。

开发与验收必须使用隔离目录：

```powershell
$env:ENGLISH_TYPING_TRAINER_DATA_DIR = "$env:TEMP\EnglishTypingTrainer-v02"
.\.venv\Scripts\python.exe .\main.py
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\tmp_pytest -v
```

测试使用临时数据库和 fake provider，不访问真实凭据或付费 API。测试数量以实际 pytest 输出为准，本次结果记录在 `PROJECT_STATUS.md`。

## 数据库迁移

迁移由 `src/english_typing_trainer/database/migrations.py` 管理，v1、v2、v3 数据库可顺序升级到 v4。升级旧库前会通过 SQLite backup API 在数据目录的 `backups\` 中创建备份；迁移使用事务，失败回滚。旧文章的句子在首次进入对应段落时懒生成，避免升级时全量重算。

## 已知限制

- v0.2 尚未制作新安装包，现有 v0.1.0 发布包不会被覆盖。
- 真实 DeepSeek 调用需要用户自己的 API Key；自动测试只使用 mock provider。
- 中途退出时保存 session 级字符进度；已完成句子保存 `sentence_attempts`，未完成句子暂不单独保存 attempt。
- 真人连续输入和真实 API 联调必须由用户按人工验收清单完成，自动化不能替代。

升级或迁移电脑前，请先退出程序并完整备份 `%LOCALAPPDATA%\EnglishTypingTrainer\`，避免遗漏 SQLite 的 WAL/SHM 文件。
