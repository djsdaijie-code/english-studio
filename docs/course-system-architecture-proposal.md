# English Studio 内置课程系统架构提案（第一轮）

状态：Draft

设计基线：English Studio v1.0.0 / database schema 11；当前实现版本：v2.0.0 / schema 13

本轮边界：只设计静态课程内容与后续接入方案，不修改数据库、加载器或 UI。

## 1. 当前系统调查结果

### 1.1 文章、分段与句子

- `src/english_typing_trainer/database/migrations.py` 的 `MigrationRunner._apply_version_1` 建立 `articles`、`article_sections`、`article_progress` 和 `practice_sessions`。文章主键是自增 `articles.id`；正文以 `full_text` 保存，`content_hash` 用于导入去重。分段通过 `article_sections.article_id` 关联文章，以 `section_index` 排序。
- `src/english_typing_trainer/services/text_importer.py` 的 `read_text_file` 读取用户 TXT，`ArticleLibraryService.import_txt_file` 计算全文 SHA-256、去重、调用 `SectioningService.split_into_sections` 并写入文章和分段。来源只保存在 `original_filename` 与 `source_path`，没有 `source_type` 或内置课程标识。
- `ArticleLibraryService.soft_delete_article` 只设置 `articles.is_deleted`，不会立即删除练习历史。`resegment_article` 将旧分段设为非活动、插入新分段并重置文章进度；旧句子仍依附旧分段，但新分段会得到新的数据库 ID。
- schema 4 的 `article_sentences` 通过 `article_id`、`section_id` 和 `sentence_index` 关联。`SentenceService.ensure_for_section` 按需调用 `SentenceSegmentationService.split`；后者将规范化句子全文做 SHA-256，写入 `sentence_hash`。`article_sentences.id` 是数据库自增 ID，`sentence_hash` 会在英文小改后变化，二者都不是课程稳定键。
- `sentence_translations` 不直接外键关联句子，而以唯一 `sentence_hash` 缓存中文翻译；`TranslationCacheRepository` 允许用户编辑。优点是同文复用，限制是英文小改会成为新缓存项，无法自然继承课程翻译或用户编辑。
- `sentence_attempts` 同时保存可空的 `article_sentence_id` 与不可空的 `sentence_hash`。文章分段重建或内容变化后，已有 attempt 可保留，但没有课程项目的长期身份。

可复用能力包括 TXT 规范化、分段、拆句、逐句打字、翻译缓存、TTS 和文章练习统计。不能直接复用的部分是课程层级、只读来源、稳定键、课程版本与升级语义。

### 1.2 单词与 occurrence

- schema 6 将词条与语境分开：`vocabulary_entries` 以 `normalized_word` 唯一，`vocabulary_contexts` 通过 `vocabulary_entry_id` 关联词条，并可通过 `article_id`、`article_sentence_id` 关联来源语境。
- `VocabularyLearningRepository` 与 `VocabularyLearningService.collect` 负责词条、语境和学习状态。语境同时保存 `source_word`、`source_sentence` 和精确字符区间，因此原文章删除后仍有一定可读性；外键删除策略为 `SET NULL`。
- schema 7 的 `article_word_occurrences` 保存文章内每次出现的位置、来源词、来源句、`occurrence_index` 和 `extraction_version`。`ArticleWordIndexService.rebuild` 基于整篇文章重新生成 occurrence；其唯一键是文章 ID 与字符区间，不适合作为课程升级身份。

课程句子可以复用现有词条规范化和语境练习能力，但不能把 occurrence ID 当作课程词汇 ID。未来投影课程句子时，应创建 `stable_key → vocabulary_context_id/article_sentence_id` 的显式链接，或让课程运行时直接提供语境，再把用户收藏映射到稳定键。

### 1.3 FSRS

- schema 9 的 `vocabulary_review_cards` 以 `vocabulary_entry_id` 关联词条，以可空 `vocabulary_context_id` 关联语境，卡片类型固定为 `spelling`、`meaning`、`listening`，唯一约束为 `(vocabulary_entry_id, card_type)`。
- `FsrsReviewService._create_initial_cards` 为词条创建拼写卡和词义卡；`ensure_listening_card` 在开始听写时创建听力卡。`FsrsReviewRepository` 的查询、日志和队列全部围绕数据库自增词条 ID 与卡片 ID。
- 当前没有外部稳定键，也没有句子级 FSRS 卡。相同规范化单词跨课程共享一组卡，语境只是卡片上的可替换引用。

最大风险不是 FSRS 算法本身，而是“课程内容升级后如何保持卡片所代表的语义”。若直接重建文章、句子或语境，可能丢失当前语境链接；若为同一课程词再次建词条，则可能重复卡片。后续必须用课程 `stable_key` 建立内容链接，升级时更新链接而不是重建卡片和日志。

### 1.4 听写与跟读

- schema 10 的 `dictation_attempts` 保存 `expected_text`、用户输入、比较结果和可空的词条/语境 ID。句子听写可以没有词条关联，因此文本历史能保留，但没有 `article_sentence_id` 或课程稳定键。
- schema 11 的 `pronunciation_attempts` 保存 `target_type`、`reference_text_hash`、评分、可空词条/语境 ID 和录音路径。`PronunciationService.save_result` 对参考文本做 SHA-256；英文小改会产生新哈希，无法表示“同一课程句子的修订”。
- 文章软删除不会直接清除这些尝试；词条或语境删除时外键为 `SET NULL`，记录仍在。跟读录音是否保留由用户设置控制，删除单条跟读记录会同时尝试删除对应音频文件。

现有听写比较、录音、评分与持久化服务可复用，但课程接入时需要额外记录课程项目稳定键。不能用参考文本哈希替代它。

### 1.5 学习进度与内置内容

- `article_progress` 只记录文章当前分段和字符位置，没有 Unit、Day 或 Level 进度。
- schema 8 的 `daily_learning_stats` 是按日期汇总的有效学习时间与打卡；`learning_events` 可关联文章、句子和词条自增 ID。它可继续用于全局学习统计，但不能表达课程 Day 的完成状态。
- 仓库目前没有课程 seed data、bundled course data、课程 JSON 初始化器或课程内容迁移器。`resources/sample_article.txt` 是示例文章资源，不是版本化课程目录。
- `EnglishStudio.spec` 目前只打包样式、图标和 `sample_article.txt`。`src/english_typing_trainer/ui/theme.py` 的 `resource_root` 处理开发目录与 PyInstaller `_MEIPASS`；课程加载器可复用这一模式，但当前 spec 尚未包含 `courses/`。
- 用户数据由 `AppPathService` 定位到 `%LOCALAPPDATA%/EnglishStudio`，与安装目录资源天然分离；这为“只读内置 JSON + 可写 SQLite”提供了合适基础。

## 2. 推荐总体架构

采用“版本化 JSON 课程内容 + SQLite 用户状态”的混合架构。

```text
安装资源 courses/（只读、版本化、权威内容）
        ↓ 校验与加载
CourseCatalog / CourseRepository（内存对象与可选索引）
        ↓ stable_key
SQLite（选课、进度、FSRS、听写、跟读、收藏、笔记）
```

### JSON 加载与定位

1. 运行时从资源根定位 `courses/catalog.json`；开发环境使用项目根，打包环境使用 `_MEIPASS`/应用资源根。不要从当前工作目录推断。
2. 先校验 catalog，再按课程 `path` 加载 `course.json`，最后只加载非空 `content_path` 的 Unit。
3. 加载器应拒绝越出 `courses/` 的相对路径、重复 ID/稳定键、课程与 Unit 身份不一致、Schema 不兼容和损坏 JSON。
4. 第一版内容量很小，可在进入课程页时一次加载课程元数据，在打开 Unit 时加载 Unit；无需数据库镜像。可按文件修改时间、课程版本或内容版本做进程内缓存。
5. 搜索需求出现前不建立持久索引。若后续需要全课程搜索，可建立可重建缓存；缓存永远不是权威源。

### 对象映射与隔离

课程对象不应直接伪装成用户文章。UI 和计划器使用 Course/Level/Unit/Lesson/Sentence 领域对象；打字、TTS、听写和跟读入口通过适配器接收统一的“练习文本 + `stable_key` + 来源元数据”。

若现有练习服务暂时必须接收 `article_id/article_sentence_id`，可建立可重建的投影和 `course_content_links`。静态 JSON 永远不保存数据库 ID，SQLite 永远不复制为内容权威源。用户笔记、收藏和学习结果只能写 SQLite，不能回写安装目录 JSON。

## 3. schema 12 是否必要

结论：本轮暂时不必要；进入“SQLite 课程学习状态”阶段时分阶段必要。

schema 11 能运行文章、词汇、FSRS、听写和跟读，但不能可靠承载选课、Level/Unit/Day 进度或 `stable_key` 映射。第一轮只有静态规范与样例，不写用户状态，因此保持 schema 11 正确。真正开放课程学习前应设计 schema 12，最小候选表为：

- `course_enrollments`：课程稳定键、已加入状态、首次/最近学习时间、所见课程版本。
- `course_progress`：课程、当前 Level/Unit/Day、解锁与完成摘要。
- `course_item_progress`：Learning Item 稳定键、完成、熟练度、最近学习和复习状态引用。
- `course_content_links`：课程稳定键到现有文章句子、词条、语境或其他运行时对象的映射；仅在采用投影方案时需要。

不建议仅为形式完整就新增 `courses`、`course_units`、`course_lessons` 镜像表。JSON 已是权威源，除非性能或离线查询证明确有需要。FSRS 卡片若要原生支持课程句子，应另行评估是在 `vocabulary_review_cards` 增加外部内容身份，还是建立通用 review item；不能在本轮预先决定并迁移。

## 4. 现有文章表是否复用

### 方案 A：直接映射到现有文章和句子表

做法：每个 Unit 或 Day 生成一篇 `articles`，课程句子写入 `article_sentences`。

- 优点：最快复用逐句打字、翻译、TTS 和部分统计。
- 缺点：Course/Level/Unit/Day 语义缺失；内置内容与用户文章混在同一列表；只读约束、来源类型和升级规则都需额外补丁。
- 一致性：JSON 与 SQLite 容易双写漂移；数组或措辞变化可能生成新自增 ID 和哈希。
- 升级风险：高。重建文章会影响进度、语境、尝试关联和翻译缓存。
- FSRS：只能间接复用词条卡；课程句子的稳定身份仍缺失。
- 复杂度：短期低、长期高。

### 方案 B：内容保持 JSON，只写新的学习状态表

做法：Course/Level/Unit/Day/Sentence 直接从 JSON 加载，SQLite 只按稳定键保存用户状态；练习能力通过文本适配器调用。

- 优点：内容与状态边界最清晰；课程升级可按稳定键合并；不污染文章库；权威源唯一。
- 缺点：现有练习服务有些接口依赖文章或句子自增 ID，需要适配；全局文章统计不能自动覆盖课程。
- 一致性：最好。JSON 是内容事实，SQLite 是用户事实。
- 升级风险：最低，只需处理稳定键弃用/替代。
- FSRS：需要增加稳定键链接或通用 review item，但规则清晰。
- 复杂度：中等，领域边界明确后可逐步实施。

### 方案 C：JSON 为权威源，运行时建立索引或镜像表

做法：安装或启动时将课程内容投影到本地索引/镜像，并保留版本和稳定键。

- 优点：可复用 SQL 查询、现有句子/词汇服务和全文搜索；大课程规模下加载快。
- 缺点：必须实现幂等同步、事务、损坏恢复、弃用和映射迁移；镜像若混入用户状态会再次形成双写。
- 一致性：可做到较好，但前提是镜像可整表重建且不拥有用户事实。
- 升级风险：中等；稳定键映射正确时可控，失败时需要回退到旧索引。
- FSRS：通过 `course_content_links` 可保持卡片不重建，但设计和测试成本较高。
- 复杂度：三者最高。

推荐方案 B。只有当搜索或现有服务适配成本经过测量确实过高时，再在 B 上增加 C 的可重建索引；不采用 A 作为长期数据模型。

## 5. 内置课程与用户文章隔离

来源模型建议明确分为：

- 内置课程：安装资源中的签入 JSON，`built_in=true`、`read_only=true`，只允许更新课程包。
- 用户导入文章：继续使用 `articles`，来源为本地 TXT，不属于课程目录。
- 用户复制的课程：未来“复制为我的课程”生成新的用户课程身份，保存可编辑副本；副本记录 `copied_from_stable_key`，但之后独立版本化。
- 用户自定义课程：完全由用户创建，没有内置课程来源；不得占用官方稳定键命名空间。

导航和存储层都应区分来源，不能只靠标题或路径猜测。内置课程的收藏、笔记和学习状态只是用户覆盖层，不改变原 JSON。

## 6. 稳定标识策略

SQLite 状态表以 `(course_stable_key, item_stable_key)` 或全局唯一 `stable_key` 建唯一约束，并记录最近见到的 `content_version`。加载新课程包时：

1. 相同稳定键直接关联旧进度，不受文件路径、顺序、翻译或小幅文本修订影响。
2. 新稳定键创建无状态项目，不影响旧项目。
3. `deprecated` 项保留历史状态，默认不再安排新学习。
4. 替换项读取 `replacement_stable_keys` 或课程包迁移清单；迁移必须幂等并记录来源/目标版本。
5. 拆分时仅主语义继承项可保留旧键；其他项新建。合并时新项使用新键，旧项弃用。

需要 deprecated 状态。是否需要独立内容迁移映射表取决于课程开始发布后的变更复杂度：第一批未发布内容可只使用 JSON 中的替代键；一旦存在跨多版本升级、拆分/合并或独立课程包导入，应增加迁移映射及已应用版本记录。

## 7. 课程升级策略

### 阶段一：随软件版本或本地课程包更新

- 课程随应用打包，启动时只读加载；旧应用继续读取旧包。
- 更新前校验整个课程包；损坏时拒绝新包并保留现有用户 SQLite。
- 软件回滚只回滚静态内容，不回滚用户数据库；状态表必须容忍“用户见过的内容版本高于当前包”。

### 阶段二：独立课程包导入

- 使用带 manifest 的本地包，声明规范版本、课程版本、文件哈希、兼容应用版本和迁移映射。
- 导入到用户数据目录中的隔离课程区，先写临时目录、完整校验后原子切换。
- 同一课程命名空间只允许可信升级路径；第三方课程必须使用自己的命名空间。

在线课程目录属于更后期阶段，本提案不设计服务端、账户、下载、签名分发或自动更新协议。

## 8. UI 入口建议

- 主导航增加与“文章库”并列的“课程”，避免让内置课程伪装成用户文章。
- 课程首页显示课程标题、定位、总进度、当前 Day、预计天数、Level 列表和“继续学习”。Draft 内容不面向普通用户显示为已完成课程。
- 导航链为课程 → Level → Unit → Day；Day 内按活动顺序进入句子、听写、跟读、复习和测评。
- 内置课程使用“内置・只读”标识；用户文章显示文件来源；复制课程和自定义课程使用“我的课程”标识。
- Unit 卡显示完成天数与测评状态，Level 显示解锁条件，课程首页显示整体进度但不以句子数冒充掌握度。
- “复制为我的课程”未来放在课程详情的更多操作中，并在复制前说明副本将独立更新；不放在主学习按钮旁，避免误操作。

本轮不修改 UI。

## 9. 数据迁移影响

- 本轮新增文件不访问或修改用户数据库，不影响现有文章、卡片、听写、跟读和学习历史。
- 后续 schema 12 应只新增课程状态与链接结构，不迁移或重写现有文章/卡片；用户文章无需转换成课程。
- 数据库迁移继续使用 `DatabaseManager` 的迁移前备份和事务。失败时回滚 schema 变化并继续使用旧课程功能集。
- 课程文件缺失时隐藏对应入口、记录可诊断错误，文章学习和其他功能继续可用；不得删除孤立的课程状态。
- 课程 JSON 损坏或 Schema 不兼容时整门课程隔离，不尝试部分写入 SQLite。若新包更新失败，继续使用最后通过校验的本地包或随应用提供的旧包。

## 10. 后续实施拆分

### Phase 1：课程规范与样例（本轮）

- 目标：冻结第一版层级、Schema、模板、稳定键规则、课程骨架与小样例。
- 主要改动：仅 `courses/` 与架构文档。
- 风险：字段过多、ID 语义不清或样例掩盖真实需求。
- 验收：JSON/Schema/引用/唯一性校验通过，数据库仍为 schema 11。

### Phase 2：课程加载器

- 目标：安全定位、校验和加载 catalog、课程及 Unit，不写数据库。
- 主要改动：领域模型、资源路径、加载错误模型、缓存和打包资源。
- 风险：开发与打包路径差异、部分损坏课程被错误加载。
- 验收：开发版和 PyInstaller 包均能离线加载；路径越界和损坏包被拒绝；现有功能无回归。

### Phase 3：SQLite 学习状态

- 目标：按稳定键保存选课、Day、Unit 和项目进度，并设计 FSRS/听写/跟读链接。
- 主要改动：经评审后的 schema 12 最小表、仓库、迁移备份与升级合并逻辑。
- 风险：课程升级造成状态丢失或重复卡片。
- 验收：从 schema 11 无损升级；稳定键小改、移动、弃用和替换测试通过；旧文章与卡片不变。

### Phase 4：课程 UI

- 目标：提供课程入口、层级导航、继续学习和进度展示。
- 主要改动：课程首页、Level/Unit/Day 页面和练习适配器。
- 风险：课程状态与全局学习统计口径不一致。
- 验收：只读边界明确；键盘操作、空状态、损坏课程降级和恢复流程可用。

### Phase 5：AI 课程第一版内容

- 目标：按 20–30 句的小批次完成并审核约 192 句与复习/测评安排。
- 主要改动：八个 Unit 内容、版本和人工审核记录。
- 风险：英语机械化、技术过时、难度跳跃和无价值重复。
- 验收：逐批内容审核、Schema、固定大小写、重复、听写、跟读和 FSRS 适配全部通过。

### Phase 6：课程包导入与升级

- 目标：支持本地独立课程包的安全导入与幂等升级。
- 主要改动：manifest、哈希、兼容检查、原子安装和迁移映射。
- 风险：不可信内容、包损坏、降级和跨版本状态映射失败。
- 验收：安装、覆盖升级、失败回滚、缺失文件、损坏文件和跨版本映射矩阵通过；仍不要求在线服务。
