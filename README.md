# English Studio

English Studio 是面向 Windows 的本地英语学习与打字应用，通过阅读、打字、听写和复习学习英语。它支持导入英文 TXT、逐字或逐句练习、保存进度和历史，并根据错误记录安排专项与间隔复习。可选的跟读评分 Beta 支持本地录音、回放和 Azure Speech Provider 架构；未配置 Azure 时不会显示模拟评分。

## 技术基线

- Python `>=3.14,<3.15`，当前验证环境 Python 3.14.6
- PySide6 6.11.1
- SQLite（标准库 `sqlite3`），schema version 11
- pytest 9.1.1；PyInstaller 6.21.0
- 当前本地交付版本 `1.0.0`；Windows 安装器和便携版由 `scripts/package.ps1` 构建

## 功能

- 文章库：中文路径 TXT 导入、编码识别、内容去重、自动分段、搜索、重命名、软删除和重新分段。
- 练习：普通连续模式、逐句学习模式、可见错误输入、Backspace、暂停、进度恢复和实时指标；连续模式可按当前句显示已有中文翻译缓存，并可临时隐藏。
- 逐句学习：可靠拆句、首个有效输入开始计时、无输入自动暂停、句后学习暂停、Enter 下一句和每句成绩保存。
- 翻译：DeepSeek 异步按需翻译、前后句上下文、全局句子缓存、重点表达、人工编辑、重试及整篇后台翻译。
- 语音：MiniMax `speech-2.8-hd`/`speech-2.8-turbo` 句子与单词朗读、三档语速、英语系统音色、本地音频缓存和 QtMultimedia 播放。
- 单词学习：在逐句或连续练习原文中双击/选中单词，通过右键“加入单词本”；Free Dictionary 提供音标、英文释义和词典音频，DeepSeek 只结合当前来源句生成简短中文语境讲解。
- 单词练习：支持 3/5/10 次重复打字、原句填空，以及“看英文回忆中文”后由用户自评；中文表达不做机械逐字判错。
- 文章导入后由本地程序自动提取英文词和精确位置，不调用外部 API。单词本提供“待学习 / 当前文章 / 全部”范围；自动索引不会把全部词加入长期收藏，用户开始学习或主动收藏后才建立学习词条。
- 单词学习按当前筛选结果生成队列，默认排除已掌握词；完成目标次数后自动进入下一个，支持上一个、跳过、下一个和本轮结果。
- 学习管理：历史记录、单次详情、学习统计、错误分析、错词/错误字符/原句专项练习、生词本和间隔复习。
- 每日学习：首页显示有效学习时间、自动打卡、固定经验档位、连续天数、本周轨迹、长期等级和核心成就；90 秒无学习行为后自动停止计时，网络等待和非学习页面停留不计入。
- FSRS 智能复习：首页和单词本均可进入“今日复习”。每个词条分别维护严格词形拼写卡和词义自评卡；支持忘记了、困难、记得、很熟、稍后复习、跳过与暂停，复习数据按 UTC 持久化并以本地时间显示。
- 听写：单词听写严格保留大小写、撇号和连字符；句子听写支持严格模式与学习模式，后者仅忽略句首大小写、句末标点并规范空白。结果保存错误、遗漏、多余、重播、语速、时长和 FSRS listening 评分；比对完全离线。
- 跟读评分 Beta：单词与来源句可播放标准发音、录音和回放；Azure Speech 区域与 Key 均由用户在设置中配置并仅保存到 Windows Credential Manager。未配置、无网络或 SDK 不可用时仅显示清晰状态，不显示 fake 或随机分数；临时录音默认在取消或评分完成后清理。
- 产品界面：简体中文、浅色/深色主题和专注练习布局。

## 安装与运行

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\main.py
```

也可运行 `powershell -ExecutionPolicy Bypass -File .\scripts\run.ps1`。

## Windows RC 构建

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\package.ps1
```

构建会生成 `EnglishStudio-1.0.0-Setup.exe` 与 `EnglishStudio-1.0.0-win-x64-portable.zip`。安装器默认安装到当前用户目录，不需要管理员权限；卸载默认保留学习数据。未签名构建可能触发 SmartScreen，请先核对 `SHA256SUMS.txt`。

## 数据与隐私

正式数据目录为 `%LOCALAPPDATA%\EnglishStudio\`，包含数据库、日志和迁移备份。首次启用新目录时会复制旧 `%LOCALAPPDATA%\EnglishTypingTrainer\` 数据，验证后保留旧目录不删除。翻译缓存保存在 `typing_trainer.db` 的 `sentence_translations` 表；DeepSeek API Key 使用 Windows Credential Manager 保存，不进入数据库、配置文件或日志。

MiniMax API Key 在设置页“语音服务”中配置，独立保存到 Windows Credential Manager 的 `English Studio/MiniMax TTS` 凭据。音频文件保存在 `%LOCALAPPDATA%\EnglishStudio\audio_cache\`，索引位于 `tts_audio_cache`。相同文本、模型、音色和生成参数会直接复用缓存，不会再次请求或收费；设置页可查看数量/大小并清空缓存。

单词标准数据和中文讲解分开保存在 `vocabulary_entries` 与 `vocabulary_contexts`。Free Dictionary 请求只发送查询单词；DeepSeek 只接收单词、当前来源句和最多三条精简英文释义；MiniMax 只接收待朗读单词或来源句。Key 不进入 SQLite、配置文件或日志。词典音频会下载到现有 `audio_cache/`，后续离线直接播放；词典无音频时回退到 MiniMax。

已缓存词条在离线时仍可查看音标、释义、中文讲解、来源句并完成三种练习；未缓存词条可先收藏，联网后再补充。FSRS 复习不依赖网络，默认期望保持率为 90%，可在设置中选择 85% / 90% / 93%；每日新词上限为 10 / 20 / 30。旧的 `next_review_at` 只作为首次 FSRS 建卡的到期参考，不会伪造复习历史。

MiniMax 语音生成可能按字符产生费用，具体以 [MiniMax 官方语音价格页面](https://platform.minimax.io/docs/guides/pricing-speech) 为准，程序不写死价格。当前仅提供句子朗读，未接入词典真人音频或完整单词功能。

按句翻译仅发送当前句及可选前后句，不发送整篇文章。使用在线翻译即表示相关文本会发送给所选服务商；离线时仍可读取已有缓存。

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

迁移由 `src/english_typing_trainer/database/migrations.py` 管理，v1-v10 数据库可顺序升级到 v11。升级旧库前会通过 SQLite backup API 在数据目录的 `backups\` 中创建备份；迁移使用事务，失败回滚。v11 新增 `pronunciation_attempts`，不改变 WPM 计时或既有练习记录。

## 已知限制

- v1.0.0 安装包仍在发布候选准备阶段；现有 v0.1.0 发布包不会被覆盖。
- 真实 DeepSeek 调用需要用户自己的 API Key；自动测试只使用 mock provider。
- 中途退出时保存 session 级字符进度；已完成句子保存 `sentence_attempts`，未完成句子暂不单独保存 attempt。
- 真人连续输入和真实 API 联调必须由用户按人工验收清单完成，自动化不能替代。

升级或迁移电脑前，请先退出程序并完整备份 `%LOCALAPPDATA%\EnglishStudio\`，避免遗漏 SQLite 的 WAL/SHM 文件。详细隐私说明见 [PRIVACY.md](PRIVACY.md)，开源与贡献说明见 [LICENSE](LICENSE) 和 [CONTRIBUTING.md](CONTRIBUTING.md)。
