# 项目状态

## 当前阶段

English Studio v1.0.0 已正式发布。GitHub 仓库与正式 Release 已完成；`feature/course-system` 已完成内置课程 Phase 1–5，当前进入最终验收与后续 Phase 6 规划阶段。

## 架构与目录

- `typing_engine`：逐字符输入判定与基础指标。
- `services/sentence_*`：拆句、懒生成和集中式计时状态机。
- `services/translation_*`：provider 抽象、DeepSeek 请求、缓存去重和重试。
- `services/learning_*`：有效学习时间状态机、档位、等级和成就计算。
- `database`：标准库 SQLite、事务、v1-v13 迁移和 repository。
- `courses`、`services/course_progress.py`、`services/course_learning.py` 与 `services/course_capabilities.py`：只读课程加载、stable key 状态关联、按能力动态进度、不持久化正文的课程会话，以及 TTS/听写/跟读/词汇/FSRS 适配。
- `services/fsrs_review.py`：FSRS profile、UTC 调度、评分、今日队列和延后处理。
- `ui`：连续练习、逐句学习、课程列表/层级/Day 浏览、课程打字会话、翻译面板、跟读 Beta、设置及本地数据管理入口。
- `tests`：临时数据库、fake clock、mock provider 和 UI 烟测。

## 数据库

当前 schema version 为 13。v8 新增 `daily_learning_stats`、`learning_events`、`achievements` 和 `profile_progress`；v9 新增普通词汇 FSRS；v10 新增普通听写历史；v11 新增普通跟读历史；v12 新增只保存 enrollment 与稀疏 Item 状态的 `course_enrollments` 和 `course_item_progress`。v13 新增 `course_activity_progress`、`course_capability_attempts`、`course_review_cards`、`course_review_logs`，并仅为 `vocabulary_contexts` 增加四个 stable-key 来源字段。迁移支持 11 → 12 → 13 与 12 → 13，沿用迁移前备份、事务和失败回滚，不重写既有文章、词汇、卡片、听写或跟读数据。

## 已完成

- 原有文章库、连续练习、历史统计、错误分析、专项练习、生词本和间隔复习保持兼容。
- 内置课程可从主窗口浏览 Course、Level、Unit 和 Day，显示动态进度，支持推荐继续、自由进入和已完成 Day 复习。
- 课程 Sentence Item 复用现有逐句字符判定与计时；首次输入和完成事件写入 schema 12 状态，但课程正文不写文章、文章句子、普通句子尝试或练习记录表。
- 课程朗读复用现有 MiniMax/QtMultimedia 流程；缓存以 Item stable key、内容版本和音频参数为身份，课程缓存的 `text_preview` 保持为空，普通文章 TTS 行为不变。
- 课程听写复用纯文本比较，课程跟读复用现有录音与 Azure provider；聚合状态和数值历史写入课程专用表，不写普通 `dictation_attempts` 或 `pronunciation_attempts`。
- 课程词汇复用共享词条与提取规则，课程来源语境只保存 stable key、版本和字符位置，显示或生成讲解时动态解析正文；一个词条可同时拥有多个文章和课程语境。
- 课程句子使用独立 FSRS 卡与日志，stable key 幂等建卡；排序、翻译和小幅文字修订不重复建卡，deprecated Item 保留历史但不进入新的到期队列。共享词条的拼写/词义 FSRS 与课程句子卡保持概念分离。
- Lesson 完成率按当前 JSON 的 required `(item_stable_key, activity_type)` 动态聚合；typing、dictation、speaking、vocabulary 和 review 独立，可选活动不阻止完成，重复练习保留最早完成时间。
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
- 可选跟读评分 Beta：QtMultimedia 负责本地录音、回放和取消清理；Azure Provider 仅在用户配置 Key 与区域后调用。未配置时保存明确状态而非虚假评分；真实 Azure 评分、延迟、计费、Prosody 与区域兼容性将在 v1.0.1 使用真实资源验证。
- GitHub 源码已推送至 `main`；`v1.0.0-rc1` 和 `v1.0.0` tags 已发布。
- RC Pre-release 和正式 Release 已创建；安装包、便携版、`SHA256SUMS.txt` 和 Release Notes 已上传。
- 发布包已完成 API Key、数据库、日志、录音和个人配置审计。

## 数据目录与隐私

- 正式目录：`%LOCALAPPDATA%\EnglishStudio\`；首次运行会兼容复制旧 `EnglishTypingTrainer` 数据并保留旧目录。
- 开发/验收：`ENGLISH_TYPING_TRAINER_DATA_DIR` 指向独立目录。
- API Key：Windows Credential Manager；测试使用内存凭据存储。
- 翻译缓存：用户本地 SQLite；日志不记录 Key 或大段正文。

## 测试状态

2026-07-16，Python 3.14.6：全量 pytest 279 passed。覆盖新库 schema 13、11 → 13、12 → 13、备份、幂等和事务回滚；课程 TTS 无正文预览、独立听写/跟读历史、动态词汇语境、课程 FSRS、required/optional 活动、内容版本和排序变化；以及既有文章、普通 FSRS、听写、跟读 Beta 与无 Azure 配置降级。测试数量仍以每次实际 pytest 输出为准。

## 尚未完成

- 阶段 B 已完成真实 Free Dictionary、DeepSeek 三语境讲解、词典音频、MiniMax 单词回退和来源句缓存联调；隔离数据目录中二次运行未重复调用 DeepSeek/MiniMax。
- 真实 Azure Speech 资源联调、实际评分准确性、Prosody 与多区域验证，计划 v1.0.1。
- 安装器中文向导资源仍待补充；当前安装向导为英文，应用本体为中文。
- 完整安装、覆盖安装、卸载和重装真人矩阵仍需在实际使用中持续验证。
- 实际使用中的 Bug 收集与 v1.0.1 准备工作仍在进行。
- 真人逐句输入验收；mock provider 运行验收不能替代真人输入。
- 排行榜、社交分享、商店、虚拟货币、装扮和复杂任务不在当前范围。
- Azure Speech 真实资源联调、实际评分准确性、Prosody 与多区域验证留待 v1.0.1；其余跟读 Beta 的本地录音和安全降级已完成。
- Phase 6 尚未执行；建议聚焦课程专用到期复习入口、跨会话能力队列体验、课程版本升级提示和真实 provider 人工验收，不扩展 schema 14 或复制课程正文。
