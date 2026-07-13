# 项目状态

## 当前阶段

v0.2.0-dev：每日学习打卡、长期等级与核心成就。开发分支 `feature/v0.2-sentence-learning`，不包含排行榜、社交系统、复杂任务或新安装包。

## 架构与目录

- `typing_engine`：逐字符输入判定与基础指标。
- `services/sentence_*`：拆句、懒生成和集中式计时状态机。
- `services/translation_*`：provider 抽象、DeepSeek 请求、缓存去重和重试。
- `services/learning_*`：有效学习时间状态机、档位、等级和成就计算。
- `database`：标准库 SQLite、事务、v1-v8 迁移和 repository。
- `ui`：连续练习、逐句学习、翻译面板及设置页面。
- `tests`：临时数据库、fake clock、mock provider 和 UI 烟测。

## 数据库

当前 schema version 为 8。v8 新增 `daily_learning_stats`、`learning_events`、`achievements` 和 `profile_progress`。有效时间按内存累计、定期或关键状态批量保存，支持跨午夜拆分和迁移失败回滚；v7 数据与既有练习记录保持不变。

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

## 数据目录与隐私

- 正式目录：`%LOCALAPPDATA%\EnglishTypingTrainer\`。
- 开发/验收：`ENGLISH_TYPING_TRAINER_DATA_DIR` 指向独立目录。
- API Key：Windows Credential Manager；测试使用内存凭据存储。
- 翻译缓存：用户本地 SQLite；日志不记录 Key 或大段正文。

## 测试状态

2026-07-13，Python 3.14.6：全量 pytest `200 passed`。新增覆盖 v7→v8、事务回滚、假时钟、90 秒空闲、网络等待、跨午夜、经验封顶、连续天数、等级阈值、成就幂等、设置持久化及三种窗口尺寸；测试数量仍以每次实际 pytest 输出为准。

## 尚未完成

- 阶段 B 已完成真实 Free Dictionary、DeepSeek 三语境讲解、词典音频、MiniMax 单词回退和来源句缓存联调；隔离数据目录中二次运行未重复调用 DeepSeek/MiniMax。
- v0.2 新安装包、无 Python 环境验证和发布签名。
- 真人逐句输入验收；mock provider 运行验收不能替代真人输入。
- 排行榜、社交分享、商店、虚拟货币、装扮和复杂任务不在当前范围。
- 复杂间隔重复、AI 中文答案判分、听写、语音识别和跟读评分留待后续版本。
