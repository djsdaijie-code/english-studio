# 项目状态

## 当前阶段

v0.2.0-dev：文章本地拆词与连续单词学习队列。开发分支 `feature/v0.2-sentence-learning`，不包含复杂记忆算法、听写、跟读评分或新安装包。

## 架构与目录

- `typing_engine`：逐字符输入判定与基础指标。
- `services/sentence_*`：拆句、懒生成和集中式计时状态机。
- `services/translation_*`：provider 抽象、DeepSeek 请求、缓存去重和重试。
- `database`：标准库 SQLite、事务、v1-v4 迁移和 repository。
- `ui`：连续练习、逐句学习、翻译面板及设置页面。
- `tests`：临时数据库、fake clock、mock provider 和 UI 烟测。

## 数据库

当前 schema version 为 7。v7 新增 `article_word_occurrences`，保存文章中每次词出现的原始词形、标准词、来源句和精确 offset；不在迁移阶段扫描旧文章。v6 数据和学习记录保持不变。

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

## 数据目录与隐私

- 正式目录：`%LOCALAPPDATA%\EnglishTypingTrainer\`。
- 开发/验收：`ENGLISH_TYPING_TRAINER_DATA_DIR` 指向独立目录。
- API Key：Windows Credential Manager；测试使用内存凭据存储。
- 翻译缓存：用户本地 SQLite；日志不记录 Key 或大段正文。

## 测试状态

2026-07-13，Python 3.14.6：当前全量 pytest `157 passed`。新增覆盖 v6→v7、文章词 offset/重复统计、URL/邮箱排除、懒生成、重建、输入稳定和队列自动切换。

## 尚未完成

- 阶段 B 已完成真实 Free Dictionary、DeepSeek 三语境讲解、词典音频、MiniMax 单词回退和来源句缓存联调；隔离数据目录中二次运行未重复调用 DeepSeek/MiniMax。
- v0.2 新安装包、无 Python 环境验证和发布签名。
- 真人逐句输入验收；mock provider 运行验收不能替代真人输入。
- 全局单词体系、ABCD 测试、段位和字符速度分析留待后续版本。
- 复杂间隔重复、AI 中文答案判分、听写、语音识别和跟读评分留待后续版本。
