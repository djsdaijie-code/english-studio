# 项目状态

## 当前阶段

v0.4.0：单词与句子听写。开发分支 `feature/v0.2-sentence-learning`，不包含排行榜、社交系统、复杂任务或新安装包。

## 架构与目录

- `typing_engine`：逐字符输入判定与基础指标。
- `services/sentence_*`：拆句、懒生成和集中式计时状态机。
- `services/translation_*`：provider 抽象、DeepSeek 请求、缓存去重和重试。
- `services/learning_*`：有效学习时间状态机、档位、等级和成就计算。
- `database`：标准库 SQLite、事务、v1-v10 迁移和 repository。
- `services/fsrs_review.py`：FSRS profile、UTC 调度、评分、今日队列和延后处理。
- `ui`：连续练习、逐句学习、翻译面板及设置页面。
- `tests`：临时数据库、fake clock、mock provider 和 UI 烟测。

## 数据库

当前 schema version 为 10。v8 新增 `daily_learning_stats`、`learning_events`、`achievements` 和 `profile_progress`；v9 新增 `fsrs_profiles`、`vocabulary_review_cards` 和 `vocabulary_review_logs`；v10 新增 `dictation_attempts`。FSRS 卡片与日志使用 UTC 保存；旧 `next_review_at` 只作为首次建卡的到期参考。迁移使用备份、事务和失败回滚，既有练习记录保持不变。

## 已完成

- 原有文章库、连续练习、历史统计、错误分析、专项练习、生词本和间隔复习保持兼容。
- 普通文章可默认进入逐句学习；老数据库升级默认保留连续模式，新安装默认启用逐句模式。
- 首次有效输入开始计时；默认 3 秒无输入自动暂停；句子完成后进入学习计时；Enter 进入下一句但不提前启动有效计时。
- DeepSeek provider、Windows Credential Manager、异步请求、全局缓存、人工编辑、显式重新生成和整篇翻译已接入。
- MiniMax 同步 T2A provider、独立凭据、异步生成、参数化缓存、并发去重、退避重试和 QtMultimedia 播放已接入逐句与连续练习。
- Free Dictionary 标准词典、DeepSeek 当前句中文讲解、文章选词收藏、多来源语境、单词/来源句发音、重复打字、原句填空、自评复习和离线缓存已完成第一版。
- 新文章导入后本地拆词，旧文章首次访问懒生成；单词本支持待学习、当前文章和全部范围，文章预览可查看或重新提取。
- 单词学习使用连续队列，异步词典/讲解只原位刷新右栏，不重载输入状态；完成后自动下一个并显示本轮结果。
- 已完成句子保存 `sentence_attempts`；中途未完成句子按 session 级进度恢复。
- 首页每日学习卡显示有效时间、自动打卡、固定经验档位、连续/累计天数、本周轨迹、长期等级和最近成就。
- 集中式 `LearningTimeTracker` 只接收真实学习行为，使用单调时钟并在 90 秒空闲后截止；网络等待、列表停留和非学习页面不计时，WPM 计时保持独立。
- 首页和单词本的“今日复习”使用 FSRS 6 默认参数与 fuzzing；每个词条独立维护拼写和词义卡，严格保留来源词形大小写。复习支持四级评分、稍后复习、跳过、暂停和每日新词上限。
- 单词本与今日复习可进入听写：优先复用词典音频，缺失时回退到 MiniMax TTS 缓存/生成；单词严格判定，句子提供严格与学习模式。听写记录和 listening 卡与拼写/词义卡相互独立。

## 数据目录与隐私

- 正式目录：`%LOCALAPPDATA%\EnglishTypingTrainer\`。
- 开发/验收：`ENGLISH_TYPING_TRAINER_DATA_DIR` 指向独立目录。
- API Key：Windows Credential Manager；测试使用内存凭据存储。
- 翻译缓存：用户本地 SQLite；日志不记录 Key 或大段正文。

## 测试状态

2026-07-13，Python 3.14.6：全量 pytest 216 passed。覆盖 v8→v10、事务回滚、FSRS 四级评分、卡片独立性、JSON 重启、旧复习日期兼容、延后/暂停/删除、保持率设置、严格拼写及单词/句子听写；测试数量仍以每次实际 pytest 输出为准。

## 尚未完成

- 阶段 B 已完成真实 Free Dictionary、DeepSeek 三语境讲解、词典音频、MiniMax 单词回退和来源句缓存联调；隔离数据目录中二次运行未重复调用 DeepSeek/MiniMax。
- v0.2 新安装包、无 Python 环境验证和发布签名。
- 真人逐句输入验收；mock provider 运行验收不能替代真人输入。
- 排行榜、社交分享、商店、虚拟货币、装扮和复杂任务不在当前范围。
- AI 中文答案判分、听写、语音识别和跟读评分留待后续版本。
