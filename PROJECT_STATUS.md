# 项目状态

## 当前阶段

English Studio v1.0.0 已正式发布。GitHub 仓库与正式 Release 已完成；`feature/course-system` 已完成内置课程 Phase 1–5、Phase 6A 发布加固和 Phase 6B 第一版候选内容。“AI 与大模型英语” `1.0.0` 当前为 `reviewed`；“全球汽车品牌与车标英语” `0.1.1` 与“币圈与区块链英语” `0.1.0` 当前为 `draft`，三门课程均未设为 `published`。

## 架构与目录

- `typing_engine`：逐字符输入判定与基础指标。
- `services/sentence_*`：拆句、懒生成和集中式计时状态机。
- `services/translation_*`、`services/article_proofreading.py`：句子翻译缓存，以及 DeepSeek 文章格式/拼写校对和安全分块请求。
- `services/learning_*`：有效学习时间状态机、档位、等级和成就计算。
- `database`：标准库 SQLite、事务、v1-v13 迁移和 repository。
- `courses`、`services/course_progress.py`、`services/course_learning.py` 与 `services/course_capabilities.py`：只读课程加载、stable key 状态关联、按能力动态进度、不持久化正文的课程会话，以及 AI 朗读/词汇适配；课程规范 `1.1` 另支持经过路径与 SVG 安全校验的可选视觉提示。
- `scripts/qa_course_content.py`：独立课程内容 QA，检查规模、状态、句长、重复、核心词与句型、Day 活动和原 stable key 保留；不参与运行时业务。
- `services/migration_verification.py` 与 `scripts/verify_schema13_migration.py`：只读源、SQLite Backup API、副本迁移、完整性与行数一致性验证。
- `services/fsrs_review.py`：FSRS profile、UTC 调度、评分、今日队列和延后处理。
- `ui`：连续练习、逐句学习、课程列表/层级/Day 浏览、课程打字会话、翻译面板、AI 朗读、设置及本地数据管理入口。
- `tests`：临时数据库、fake clock、mock provider 和 UI 烟测。

## 数据库

当前 schema version 为 13。v8 新增 `daily_learning_stats`、`learning_events`、`achievements` 和 `profile_progress`；v9 新增普通词汇 FSRS；v10 与 v11 的旧听写、跟读历史表仅为升级兼容保留，当前产品不再提供对应入口或写入新记录；v12 新增只保存 enrollment 与稀疏 Item 状态的 `course_enrollments` 和 `course_item_progress`。v13 新增 `course_activity_progress`、`course_capability_attempts`、`course_review_cards`、`course_review_logs`，并仅为 `vocabulary_contexts` 增加四个 stable-key 来源字段。迁移沿用迁移前备份、事务和失败回滚，不重写既有文章、词汇或卡片。

## 已完成

- 原有文章库、连续练习、历史统计、错误分析、专项练习、生词本和间隔复习保持兼容。
- 内置课程可从主窗口浏览 Course、Level、Unit 和 Day，显示动态进度，支持推荐继续、自由进入和已完成 Day 复习。
- “AI 与大模型英语”第一版候选课程已完成 5 个 Level、8 个 Unit、56 个 Day 和 176 条 reviewed 句子；Unit 1–4 与 Unit 5–8 各 88 句，每个 Unit 均具备四天新内容、综合场景、AI 朗读练习和复习自测。
- Unit 1 原 12 条样例保留英文核心语义和 stable key；全课程共有 176 个唯一句子 stable key，没有 deprecated 或 replacement 项。课程与内容版本为 `1.0.0`，状态保持 `reviewed`。
- “全球汽车品牌与车标英语”MVP 已建立 1 个 Level、2 个 Unit、14 个 Day、40 个品牌 stable key 和 40 份本地 SVG。`0.1.1` 将目标改为“品牌名 + 8–12 词简短事实介绍”，练习开始即显示完整英文，车标只作辅助记忆，完成后显示完整中文翻译。课程仍复用现有进度和 schema 13，不创建文章记录。catalog 已提升为 `1.2.1`。
- “币圈与区块链英语”MVP 已建立 1 个 Level、2 个 Unit、14 个 Day 和 40 个唯一 stable key，覆盖钱包、转账、交易、DeFi、TVL、市场指标、跨链和风险英语。`TVL` 明确定义为 `Total Value Locked`；课程活动只有必做打字和可选 FSRS，全部 `audio_hint` 为 `null`，不依赖已移除的朗读或听写能力，不创建文章记录。新增课程后 catalog 提升为 `1.3.0`。
- 课程 Sentence Item 复用现有逐句字符判定与计时；首次输入和完成事件写入 schema 12 兼容状态与 schema 13 typing 活动状态，但课程正文不写文章、文章句子、普通句子尝试或练习记录表。
- 课程 AI 朗读复用现有 MiniMax 音频缓存；用户录音和 Azure 跟读评分不再提供。
- 课程词汇复用共享词条与提取规则，课程来源语境只保存 stable key、版本和字符位置，显示或生成讲解时动态解析正文；一个词条可同时拥有多个文章和课程语境。
- 旧课程句子 FSRS 卡与日志仍按 stable key 保留用于数据兼容，但当前界面不再通过听写页面呈现该队列。共享词条的拼写/词义 FSRS 不受影响。
- enrollment 记录版本低于当前 JSON 语义版本时显示“课程有新内容”、历史版本和当前版本；历史状态不清除，新增 required Item 可按当前内容改变完成率。
- 真实 schema 11 用户库以只读方式通过 SQLite Backup API 生成仓库外副本，仅副本升级到 schema 13；源与目标 integrity 均为 `ok`，全部既有表计数一致，正式用户数据库未修改。
- 跨 AppContext 和 PyInstaller 双启动均验证 enrollment、推荐 Lesson、课程活动、课程 FSRS 和 `in_progress` Item 可恢复；Phase 6A 打包验收基于当时的 12 句内容骨架。Phase 6B 已将同一资源路径扩展为 176 句且未修改打包配置，下一次正式候选构建仍应复核完整内容资源。
- 本机音频设备验收检测到 1 个输入和 5 个输出，短提示音播放及临时录音成功且录音已清理。MiniMax/Azure 凭据均未配置，因此真实云请求明确保留为人工验收项。
- Lesson 完成率按当前 JSON 的 required `(item_stable_key, activity_type)` 动态聚合；typing、speaking、vocabulary 和 review 独立，可选活动不阻止完成，重复练习保留最早完成时间。
- 普通文章可默认进入逐句学习；老数据库升级默认保留连续模式，新安装默认启用逐句模式。
- 首次有效输入开始计时；默认 3 秒无输入自动暂停；句子完成后进入学习计时；Enter 进入下一句但不提前启动有效计时。
- DeepSeek provider、Windows Credential Manager、异步请求、全局缓存、人工编辑、显式重新生成和整篇翻译已接入。
- 文章导入后以完整单段保存，可异步调用 DeepSeek 检查格式、拼写和单词错误；已有文章支持重新检测，建议版本经用户确认后事务化更新并保留历史。逐句文本不再包含首尾空格、Tab 或换行。
- MiniMax 同步 T2A provider、独立凭据、异步生成、参数化缓存、并发去重、退避重试和 QtMultimedia 播放用于单词发音与句子 AI 朗读；连续、逐句和课程练习均保留朗读入口、自动播放与预取。
- Free Dictionary 标准词典、DeepSeek 当前句中文讲解、文章选词收藏、多来源语境、单词/来源句发音、重复打字、原句填空、自评复习和离线缓存已完成第一版。
- 文章导入不再自动拆词或填充候选列表；用户从文章预览、逐句或连续练习原文中主动选词收藏。单词本支持待学习、当前文章已收藏和全部单词范围，并提供右下角快捷入口与添加成功卡片。
- 单词学习使用连续队列，异步词典/讲解只原位刷新右栏，不重载输入状态；完成后自动下一个并显示本轮结果。
- 已完成句子保存 `sentence_attempts`；中途未完成句子按 session 级进度恢复。
- 首页每日学习卡显示有效时间、自动打卡、固定经验档位、连续/累计天数、本周轨迹、长期等级和最近成就。
- 集中式 `LearningTimeTracker` 只接收真实学习行为，使用单调时钟并在 90 秒空闲后截止；网络等待、列表停留和非学习页面不计时，WPM 计时保持独立。
- 首页和单词本的“今日复习”使用 FSRS 6 默认参数与 fuzzing；每个词条独立维护拼写和词义卡，严格保留来源词形大小写。复习支持四级评分、稍后复习、跳过、暂停和每日新词上限。
- 听写页面、首页/单词本入口、课程听写活动和 listening 复习队列已移除；旧数据库表、旧记录和旧 listening 卡只为数据兼容保留，不再展示或新增。
- AI 朗读：逐句、连续和课程练习共用 MiniMax 语音缓存，支持预取、自动播放、小喇叭播放和 Space 重听；用户录音与 Azure 跟读评分已从当前产品中移除。
- GitHub 源码已推送至 `main`；`v1.0.0-rc1` 和 `v1.0.0` tags 已发布。
- RC Pre-release 和正式 Release 已创建；安装包、便携版、`SHA256SUMS.txt` 和 Release Notes 已上传。
- 发布包已完成 API Key、数据库、日志、录音和个人配置审计。

## 数据目录与隐私

- 正式目录：`%LOCALAPPDATA%\EnglishStudio\`；首次运行会兼容复制旧 `EnglishTypingTrainer` 数据并保留旧目录。
- 开发/验收：`ENGLISH_TYPING_TRAINER_DATA_DIR` 指向独立目录。
- API Key：Windows Credential Manager；测试使用内存凭据存储。
- 翻译缓存：用户本地 SQLite；日志不记录 Key 或大段正文。

## 测试状态

2026-07-27，Python 3.14.6：共享课程校验与 Phase 6B 内容 QA 均通过；加入币圈课程后的全量 pytest 为 318 passed。课程专项继续覆盖原课程的 5 个 Level、8 个 Unit、56 个 Day、176 句与 stable key，车标课程的 2 个 Unit、14 个 Day、40 条品牌介绍和视觉素材，以及币圈课程的 2 个 Unit、14 个 Day、40 条短句、TVL 定义、无音频活动边界、Day 会话和文章表零写入。发布加固回归继续覆盖数据库副本迁移、跨 AppContext 恢复、课程 due 队列与 FSRS 日志、版本升级提示、Provider 降级和打包双启动。测试数量仍以每次实际 pytest 输出为准。

## 尚未完成

- 阶段 B 已完成真实 Free Dictionary、DeepSeek 三语境讲解、词典音频、MiniMax 单词回退和来源句缓存联调；隔离数据目录中二次运行未重复调用 DeepSeek/MiniMax。
- 真实 MiniMax 课程短句生成、缓存命中和内容版本换键受本机缺少凭据限制，仍需按发布加固清单完成 1–2 次短请求。
- 安装器中文向导资源仍待补充；当前安装向导为英文，应用本体为中文。
- 完整安装、覆盖安装、卸载和重装真人矩阵仍需在实际使用中持续验证。
- 实际使用中的 Bug 收集与 v1.0.1 准备工作仍在进行。
- 真人逐句输入验收；mock provider 运行验收不能替代真人输入。
- 排行榜、社交分享、商店、虚拟货币、装扮和复杂任务不在当前范围。
- Phase 6B 候选内容已完成；仍需目标用户逐日试学、英语内容审核者签核、Unit 6–8 技术复核，以及真实 Provider 的短音频人工验收。未完成这些门禁前不得把课程状态提升为 `published`。
- 车标课程仍需逐品牌核对简短介绍事实、当前官方视觉、商标/品牌指南与目标市场使用边界，并由真人试学确认内容长度、品牌读音和严格大小写是否合理；完成前保持 `draft`。
