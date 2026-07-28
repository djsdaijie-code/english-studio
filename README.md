# English Studio

English Studio 是面向 Windows 的本地英语学习与打字应用，通过阅读、打字、AI 朗读和复习学习英语。它支持导入英文 TXT、逐字或逐句练习、保存进度和历史，并根据错误记录安排专项与间隔复习。

## 技术基线

- Python `>=3.14,<3.15`，当前验证环境 Python 3.14.6
- PySide6 6.11.1
- SQLite（标准库 `sqlite3`），schema version 13
- pytest 9.1.1；PyInstaller 6.21.0
- 当前开发版本 `2.0.0-dev.1`，最新正式发布版本为 `1.0.0`；Windows 安装器和便携版由 `scripts/package.ps1` 构建

## 功能

- 文章库：中文路径 TXT 导入、编码识别、内容去重、全文单段保存、搜索、重命名、软删除和手动重新分段；配置 DeepSeek 后，导入会异步检查格式、拼写和单词错误，已有文章也可重新检测并由用户确认是否应用。
- 练习：普通连续模式、逐句学习模式、可见错误输入、Backspace、暂停、进度恢复和实时指标；连续模式可按当前句显示已有中文翻译缓存，并可临时隐藏。
- 逐句学习：可靠拆句并移除句首、句尾空格/Tab/换行，首个有效输入开始计时、无输入自动暂停、句后学习暂停、Enter 下一句和每句成绩保存。
- 翻译：DeepSeek 异步按需翻译、前后句上下文、全局句子缓存、重点表达、人工编辑、重试及整篇后台翻译。
- 音频：单词优先使用 Free Dictionary 发音，缺失时由 MiniMax 生成；逐句、连续和课程练习支持小喇叭播放、预取、句末自动播放和 Space 重听，并复用本地缓存与 QtMultimedia 播放。
- 单词学习：在逐句或连续练习原文中双击/选中单词，通过右键“加入单词本”；Free Dictionary 提供音标、英文释义和词典音频，DeepSeek 只结合当前来源句生成简短中文语境讲解。
- 单词练习：支持 3/5/10 次重复打字、原句填空，以及“看英文回忆中文”后由用户自评；中文表达不做机械逐字判错。
- 文章导入不会自动加入或展示全文单词；用户可在文章预览、逐句或连续练习原文中主动选择单词并加入单词本。“当前文章已收藏”只显示用户亲自收藏的词，右下角小书本可随时打开单词本。
- 单词学习按当前筛选结果生成队列，默认排除已掌握词；完成目标次数后自动进入下一个，支持上一个、跳过、下一个和本轮结果。
- 学习管理：历史记录、单次详情、学习统计、错误分析、错词/错误字符/原句专项练习、生词本和间隔复习。
- 每日学习：首页显示有效学习时间、自动打卡、固定经验档位、连续天数、本周轨迹、长期等级和核心成就；90 秒无学习行为后自动停止计时，网络等待和非学习页面停留不计入。
- FSRS 智能复习：首页和单词本均可进入“今日复习”。每个词条分别维护严格词形拼写卡和词义自评卡；支持忘记了、困难、记得、很熟、稍后复习、跳过与暂停，复习数据按 UTC 持久化并以本地时间显示。
- AI 朗读：单词优先使用 Free Dictionary 音频，缺失时回退 MiniMax；逐句和课程练习支持小喇叭播放、Space 重听、输入期间预取及句末自动播放。
- 内置课程：浏览 Course、Level、Unit 和 Day，按 stable key 保存打字、AI 朗读与词汇状态；提供版本升级提示和跨会话继续，课程正文不写入文章表。
- 产品界面：简体中文、浅色/深色主题和专注练习布局。

## 安装与运行

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\main.py
```

也可运行 `powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1`。

## Windows 发布版

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package.ps1
```

当前开发版本构建会生成 `EnglishStudio-2.0.0-dev.1-Setup.exe` 与 `EnglishStudio-2.0.0-dev.1-win-x64-portable.zip`。安装器默认安装到当前用户目录，不需要管理员权限；卸载默认保留学习数据。未签名构建可能触发 SmartScreen，请先核对 `SHA256SUMS.txt`。

## 数据与隐私

正式数据目录为 `%LOCALAPPDATA%\EnglishStudio\`，包含数据库、日志和迁移备份。首次启用新目录时会复制旧 `%LOCALAPPDATA%\EnglishTypingTrainer\` 数据，验证后保留旧目录不删除。翻译缓存保存在 `typing_trainer.db` 的 `sentence_translations` 表；DeepSeek API Key 使用 Windows Credential Manager 保存，不进入数据库、配置文件或日志。

MiniMax API Key 在设置页“语音服务”中配置，独立保存到 Windows Credential Manager 的 `English Studio/MiniMax TTS` 凭据。音频文件保存在 `%LOCALAPPDATA%\EnglishStudio\audio_cache\`，索引位于 `tts_audio_cache`。相同文本、模型、音色和生成参数会直接复用缓存，不会再次请求或收费；设置页可查看数量/大小并清空缓存。

单词标准数据和中文讲解分开保存在 `vocabulary_entries` 与 `vocabulary_contexts`。Free Dictionary 请求只发送查询单词；DeepSeek 只接收单词、当前来源句和最多三条精简英文释义；MiniMax 只接收需要生成标准发音的单词或来源句。Key 不进入 SQLite、配置文件或日志。词典音频会下载到现有 `audio_cache/`，后续离线直接播放；词典无音频时回退到 MiniMax。

已缓存词条在离线时仍可查看音标、释义、中文讲解、来源句并完成三种练习；未缓存词条可先收藏，联网后再补充。FSRS 复习不依赖网络，默认期望保持率为 90%，可在设置中选择 85% / 90% / 93%；每日新词上限为 10 / 20 / 30。旧的 `next_review_at` 只作为首次 FSRS 建卡的到期参考，不会伪造复习历史。

MiniMax 语音生成可能按字符产生费用，具体以 [MiniMax 官方语音价格页面](https://platform.minimax.io/docs/guides/pricing-speech) 为准，程序不写死价格。单词优先使用 Free Dictionary 音频，缺失时回退 MiniMax；句子 AI 朗读由 MiniMax 生成；已缓存内容可离线复用。

按句翻译仅发送当前句及可选前后句。文章校对会在用户已配置 DeepSeek Key 时，将新导入或主动重新检测的文章按安全边界分块发送给 DeepSeek；建议只在用户确认后应用。使用这些在线能力即表示相关文本会发送给所选服务商；离线时仍可读取已有缓存，文章导入本身不会因校对不可用而失败。

开发与验收必须使用隔离目录：

```powershell
$env:ENGLISH_TYPING_TRAINER_DATA_DIR = "$env:TEMP\EnglishStudio-isolated"
.\.venv\Scripts\python.exe .\main.py
```

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .\tmp_pytest -v
```

测试使用临时数据库和 fake provider，不访问真实凭据或付费 API。测试数量以实际 pytest 输出为准，本次结果记录在 `PROJECT_STATUS.md`。

## 数据库迁移

迁移由 `src/english_typing_trainer/database/migrations.py` 管理，v1-v12 数据库可顺序升级到 v13。升级旧库前会通过 SQLite backup API 在数据目录的 `backups\` 中创建备份；迁移使用事务，失败回滚。v12 新增课程 enrollment 与稀疏 Item 状态，v13 新增按能力拆分的活动、数值尝试历史和课程 FSRS 卡/日志；两者都不复制课程正文，也不改变 WPM 计时或既有普通练习记录。真实用户库应先用 `scripts/verify_schema13_migration.py` 对仓库外副本验证，流程见 `docs/course-release-hardening.md`。

## 已知限制

- English Studio v1.0.0 已正式发布，GitHub Release 提供 Windows 安装包和便携版；当前仓库正在开发 `2.0.0-dev.1`，尚未作为正式安装包发布。安装器目前为英文，应用本体为中文；安装包未签名，Windows SmartScreen 可能提示。完整安装、覆盖安装、卸载和重装矩阵仍在真实使用中持续验证。
- 真实 DeepSeek 调用需要用户自己的 API Key；自动测试只使用 mock provider。
- 中途退出时保存 session 级字符进度；已完成句子保存 `sentence_attempts`，未完成句子暂不单独保存 attempt。
- 真人连续输入和真实 API 联调必须由用户按人工验收清单完成，自动化不能替代。

升级或迁移电脑前，请先退出程序并完整备份 `%LOCALAPPDATA%\EnglishStudio\`，避免遗漏 SQLite 的 WAL/SHM 文件。详细隐私说明见 [PRIVACY.md](PRIVACY.md)，开源与贡献说明见 [LICENSE](LICENSE) 和 [CONTRIBUTING.md](CONTRIBUTING.md)。
