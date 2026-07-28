# 课程系统真实环境验收与发布加固

Phase 6A 在 schema 13 和 Phase 5 课程能力层之上完成发布前验证。它不增加 schema 14，不制作完整课程内容，也不发布安装包或 Git Tag。

## 安全数据库副本迁移

可复用入口为：

```powershell
.\.venv\Scripts\python.exe scripts\verify_schema13_migration.py `
  --source <schema-11-source.db> `
  --output <outside-repository-copy.db>
```

脚本遵守以下约束：

- `--output` 必填，源与目标解析为同一路径时立即拒绝；已经存在的目标也不会覆盖。
- 在确认应用退出后，源数据库使用 SQLite URI `mode=ro&immutable=1` 和 `query_only` 打开，再通过 SQLite Backup API 生成一致性 staging 副本。
- 仅 staging 副本交给 `DatabaseManager` 执行 11 → 12 → 13；验证成功后原子改名为指定输出。
- 迁移前后执行 `PRAGMA integrity_check`，比较全部既有表的行数，并输出有限的关键表统计和新增表名。
- 主库、`-wal` 和 `-shm` 在备份前后共同计算大小、修改时间和 SHA-256 指纹；发生迁移、完整性或计数错误时返回非零并清理专用 staging 目录及其内部迁移备份。
- 输出不包含文章、句子、单词、用户输入、数据库路径或其他正文。

`immutable=1` 的选择依据 [SQLite URI](https://sqlite.org/uri.html) 与 [WAL read-only](https://sqlite.org/wal.html#readonly) 官方说明：它会以只读方式打开并跳过锁和变更检测；WAL 模式只读数据库也可以依靠该参数避免要求创建旁文件。该参数只在已经确认应用退出、源库不会并发变化时使用。

2026-07-16 的真实用户数据库验收在确认 English Studio 未运行后执行。源库为 schema 11，源与迁移副本的完整性检查均为 `ok`，副本到达 schema 13，源文件哈希保持不变。全部既有表行数保持一致；新增表为 `course_enrollments`、`course_item_progress`、`course_activity_progress`、`course_capability_attempts`、`course_review_cards` 和 `course_review_logs`。

关键数据计数如下：

| 数据 | 迁移前 | 迁移后 |
|---|---:|---:|
| articles | 4 | 4 |
| article_sections | 35 | 35 |
| article_sentences | 304 | 304 |
| article_progress | 4 | 4 |
| sentence_attempts | 137 | 137 |
| practice_sessions | 38 | 38 |
| typing_errors | 383 | 383 |
| article_word_occurrences | 1063 | 1063 |
| vocabulary_entries | 411 | 411 |
| vocabulary_contexts | 412 | 412 |
| vocabulary_learning_state | 411 | 411 |
| vocabulary_attempts | 339 | 339 |
| fsrs_profiles | 1 | 1 |
| vocabulary_review_cards | 109 | 109 |
| vocabulary_review_logs | 6 | 6 |
| dictation_attempts | 2 | 2 |
| pronunciation_attempts | 0 | 0 |
| daily_learning_stats | 2 | 2 |
| learning_events | 972 | 972 |
| achievements | 10 | 10 |
| profile_progress | 1 | 1 |

正式用户主数据库没有被应用启动、迁移或写入。初版 `mode=ro` 验证暴露出 SQLite 在 WAL 模式下会刷新临时 `-wal/-shm` 旁文件元数据；主库哈希、schema 和逻辑数据未变化，也没有不可逆数据变化。工具随即改为 `immutable=1`，最终复验确认主库、WAL 和 SHM 内容指纹全程不变。仓库外验收副本在记录非敏感统计后清理，不进入 Git。

## 跨会话状态

自动化测试关闭并重新创建完整 `AppContext`，验证以下状态使用同一临时数据库恢复：

- enrollment、状态和当前推荐 Lesson；
- typing、dictation、speaking 的状态、次数和分数；
- 课程能力逐次历史、FSRS card、due、state 与 review log；
- 重复完成和重复建卡的幂等性；
- paused、archived 和恢复 active 后的推荐行为；
- 课程句子调整顺序或文案后，原 stable key 状态仍可读取；
- 所有流程均不创建文章或普通课程正文副本。

不恢复句内字符位置；未完成 Item 只恢复为 `in_progress` 并从该 Item 重新开始。

## 课程到期复习入口

课程列表提供“课程到期复习”入口和当前数量。UI 通过 `CourseCapabilityService.due_sentence_reviews()` 获取队列，不直接查询数据库。队列按 `due_at_utc`、卡片 ID 排序，并显示课程标题、Day、Lesson、句子位置、卡片类型和本地到期时间。

课程复习复用句子听写页面的文本比较和播放能力，但评分使用具体 `course_review_card_id` 调用 `rate_sentence_review()`，因此可以准确更新 FSRS card、due、state 和 `course_review_logs`。课程听写数值仍进入课程能力历史；普通 `dictation_attempts` 和普通词汇 FSRS 队列不受影响。

deprecated Item 被保留为历史卡但不进入队列；paused 或 archived enrollment 不主动推荐。空队列显示明确提示，退出后返回课程页。

## 课程版本升级规则

`CourseProgressService.get_version_status()` 比较 enrollment 最后学习时记录的 course/content 语义版本与当前只读 JSON：

- 当前版本不高于记录版本时不提示；
- course version 或 content version 提高时显示“课程有新内容”；
- 提示同时显示记录版本、当前版本，以及用户是否曾完成记录版本；
- 历史 Item 和活动状态不清除；完成率始终按当前 JSON 的 required `(item_stable_key, activity_type)` 重算，所以新增必做 Item 可降低当前完成率；
- “查看新内容”定位当前推荐 Day，“继续”仍使用既有推荐入口；
- 排序和文案小修只要 stable key 不变，就不会破坏历史状态。

schema 13 没有单独的版本历史表，因此 enrollment 开始学习新版本后会记录当前版本；本阶段展示的是升级前最后学习版本，不提供长期版本时间线。

## Provider 与音频设备验收

验收程序只读取凭据是否存在，不输出 Key。当前 AI 朗读使用 MiniMax；用户录音与 Azure 跟读评分已经移除。

自动化降级覆盖：

- MiniMax Key 缺失、网络/超时/provider 错误；
- 播放设备缺失；
- 音频缓存文件缺失、空文件或大小不一致；
- 课程资源或 stable key 失效；
- 数据库迁移失败和 partial 副本清理。

跟读标准音频播放失败时会显示错误；失败的 speaking 活动不会停在虚假的进行中或完成状态。日志记录稳定键、provider、模型、字符数和错误分类，不记录 Key、课程正文或录音内容。

### MiniMax 人工验收

1. 在设置中配置有效 MiniMax Key，使用隔离数据目录启动测试构建。
2. 打开课程 Day 1 的跟读页，播放一条短句的标准音频；再次播放确认不发起新请求。
3. 检查 `tts_audio_cache.text_preview` 对该课程缓存为空；提高测试课程 `content_version` 后最多再请求一次，确认生成不同缓存键。
4. 删除测试 Key 或断网，确认提示可返回课程页。不要打印 Key。

### Azure 人工验收

1. 在隔离环境配置 Azure Key 与区域，确认系统麦克风权限。
2. 对一条短课程句录音并评分一次，确认数值结果、活动状态和课程尝试历史。
3. 确认普通 `pronunciation_attempts` 没有新增课程行，临时录音按设置清理。
4. 断网或撤销麦克风权限再试一次，确认清晰降级。不要保存或提交录音。

## PyInstaller 验收

本阶段使用现有 spec 和测试构建命令，不生成 ZIP 或安装器：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\package.ps1 -DebugBuild -SkipTests -AllowDirty
```

构建使用 Python 3.14.6、PyInstaller 6.21.0，生成 243 个文件、约 162 MB 的 one-folder 调试构建。`scripts/package.ps1` 仅增加课程资源存在性检查；spec、安装器和打包架构未改变。

打包程序从与源码无关的临时工作目录连续启动两次，并使用隔离数据目录。两次均成功读取 1 门课程、5 个 Level、8 个 Unit 和 12 句，catalog 无失败，课程列表与 Day 页面可打开，新数据库为 schema 13。第一次写入一个 `in_progress` 课程 Item，第二次恢复相同 enrollment、推荐 Lesson 和 Item 状态；文章表行数保持 0。缺少凭据不会阻止启动。

自动退出冒烟仅在显式设置 `ENGLISH_STUDIO_ACCEPTANCE_REPORT` 时启用；`ENGLISH_STUDIO_ACCEPTANCE_ACTION=seed|verify` 分别创建最小课程状态或只读验证恢复。报告只含 schema、资源数量、稳定 ID、状态和文章行数，不含课程正文、用户正文或路径；普通启动不受影响。

构建日志出现 PyInstaller 的可选 `tzdata` hidden import 警告，但本次启动、SQLite、FSRS UTC 状态和课程页面验收均正常。正式发布前仍应在目标 Windows 机器复查本地时区展示。

## 正式启用 schema 13 前检查清单

- [ ] 确认 English Studio 已退出，任务管理器中没有残留进程。
- [ ] 对正式数据库先做独立 SQLite backup，并验证 `integrity_check`。
- [ ] 使用本脚本和仓库外输出副本复核 11 → 13；不要对正式文件运行迁移测试。
- [ ] 对比关键表计数并抽查原文章、词汇、普通 FSRS、听写、跟读和学习统计可读取。
- [ ] 在隔离目录完成一次 schema 13 新库启动和两次跨会话课程继续。
- [ ] 用实际发布构建检查课程列表、Day、到期课程复习和版本提示。
- [ ] 按需完成 MiniMax/Azure 各 1–2 次短请求；记录结果，不记录 Key 或正文。
- [ ] 检查麦克风、播放设备、断网、无凭据和损坏缓存降级。
- [ ] 运行课程校验、全量 pytest 和 `git diff --check`。
- [ ] 确认没有数据库、日志、音频、凭据、临时报告、调试构建或用户路径进入提交。

## 已验证与未验证

已验证：真实 schema 11 只读源到 schema 13 副本迁移、关键计数一致、跨 AppContext 恢复、课程到期复习与评分、版本升级提示、本地播放和录音、PyInstaller 课程资源与双启动、主要异常降级。

受环境限制未验证：真实 MiniMax 请求/缓存命中、真实 Azure 云评分、云端超时/配额错误、不同 Windows 主机和真实安装器下的音频设备矩阵。Phase 6B 不应顺带实现这些基础设施；应先完成上述短人工验收，再独立开展课程内容开发。
