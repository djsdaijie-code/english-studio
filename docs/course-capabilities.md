# 课程学习能力接入（schema 13）

Phase 5 在只读 `CourseRepository`、schema 12 课程状态和 Phase 4 课程打字 UI 之上接入朗读、听写、跟读、词汇与 FSRS。静态课程 JSON 仍是正文、层级、顺序和活动配置的唯一来源；SQLite 只保存用户状态、数值结果和 stable key，不保存课程英文或中文副本。

## 统一入口与身份

应用入口是 `AppContext.course_capability_service`，类型为 `CourseCapabilityService`。UI 只向该服务传递课程 ID、Lesson ID 或 `LearningContentRef`，不解析 JSON，也不直接写数据库。

`LearningContentRef` 在运行时包含：

```text
source_type = built_in_course
course_stable_key
unit_stable_key
lesson_stable_key
item_stable_key
content_version
```

其中只有 `enrollment_id`、`item_stable_key`、能力类型和版本等最小状态进入课程能力表。Unit 与 Lesson stable key 由 `CourseRepository` 根据 Item 动态解析，不在 schema 13 的多张表中重复保存。正文、JSON 路径、数组下标和排序值均不作为身份。

主要接口包括：

```python
service.item(course_id, item_stable_key)
service.lesson_items(course_id, lesson_id, activity_type=None)
service.extract_words(content_ref)
service.collect_word(content_ref, word, start_offset=..., end_offset=...)
service.record_dictation(content_ref, ...)
service.record_speaking(content_ref, result, ...)
service.ensure_vocabulary_review(content_ref, entry_id, context_id)
service.ensure_sentence_review(content_ref, card_type="sentence_review")
service.rate_sentence_review(card_id, rating)
service.due_sentence_reviews()
```

课程内容在能力执行前会重新按 stable key 和 `content_version` 解析。会话期间内容版本变化时抛出 `CourseContentChangedError`，避免把旧运行时正文的结果关联到新版本。

## schema 13

schema 13 只新增四张课程表，并对 `vocabulary_contexts` 增加四个来源字段。

### `course_activity_progress`

同一 Item 的 `typing`、`dictation`、`speaking`、`vocabulary` 和 `review` 独立保存。字段包括 enrollment 外键、Item stable key、活动类型、状态、尝试次数、最好/最近分数、内容版本，以及完成、最近学习、创建和更新时间。

唯一约束为：

```text
(enrollment_id, item_stable_key, activity_type)
```

状态为 `not_started`、`in_progress`、`completed`、`skipped` 或 `failed`。重复完成会增加尝试次数并更新数值结果，但保留第一次 `completed_at`。

### `course_capability_attempts`

保存每次课程听写或跟读的数值历史：能力类型、状态、总分和必要分项、错误/遗漏/多余数、重播次数、provider、时长、内容版本和尝试时间。该表没有标准答案、用户输入、参考正文或课程正文列。

### `vocabulary_contexts`

仅新增：

```text
source_type
course_stable_key
item_stable_key
content_version
```

普通文章继续使用原有文章 ID、文章句子 ID 和 `source_sentence`。课程语境将文章外键置空、`source_sentence` 保存为空字符串，并通过 stable key 在显示或生成中文讲解时动态读取当前课程句子。课程来源使用局部唯一索引，保证同一共享词条、Item 和字符位置幂等，同时允许一个词条拥有多个文章或课程语境。

### `course_review_cards` 与 `course_review_logs`

课程句子使用独立 FSRS 卡，不伪造 `vocabulary_entry`。卡片以 `(enrollment_id, item_stable_key, card_type)` 唯一，保存 FSRS card JSON、到期时间、状态、暂停标记、内容版本和时间字段；日志保存评分、前一状态和 FSRS review log。

课程句子卡与共享词条卡是两个概念：课程句子的听力/综合复习写入课程卡；课程语境中收藏的共享单词仍复用普通词条的拼写与词义卡。普通文章 FSRS 的身份和生命周期没有改变。

schema 13 没有 `learning_content_links`，没有修改 `tts_audio_cache` 或普通 `pronunciation_attempts` 的表结构，也没有新增 Level、Unit 或 Lesson 状态表。

## 迁移与备份

新数据库顺序初始化到 schema 13；旧数据库支持 11 → 12 → 13 和 12 → 13。`DatabaseManager` 在迁移前沿用现有 SQLite backup API，在数据目录的 `backups/` 生成 `typing_trainer-v{旧版本}-before-v13-*.db`。

全部 DDL 和版本更新位于同一 savepoint。任何一步失败都会回滚新增列、新表、索引和版本号；重复初始化不会重复建表、复制数据或创建用户状态。迁移不会重写文章、普通词汇、普通 FSRS、听写或跟读历史。

## TTS

课程朗读复用现有 `TTSService`、provider、异步任务、音频文件缓存和 QtMultimedia 播放。课程缓存键由以下值组成：

```text
item_stable_key + content_version
+ provider/model/voice/speed/volume/pitch/format
```

正文不参与逻辑身份；生成请求的正文在调用时从 `CourseRepository` 读取。课程缓存仍使用原 `tts_audio_cache` 表，但 `text_preview` 强制写空，且没有新增课程列。内容版本变化会产生新缓存键；普通文章缓存继续使用正文哈希和原有正文预览行为。

课程配置了 listening 活动时，音频准备阶段写 `review/in_progress`，播放器实际进入播放状态后写 `review/completed`。生成或播放失败保留明确失败状态与 UI 提示。课程单词发音走共享词条的既有音频/TTS 流程，不使用整句 Item 缓存键，避免单词与整句音频键碰撞。

## 听写与跟读

课程听写复用 `DictationService.compare()` 的严格/学习模式比较，但目标句只存在于当前 `CourseCapabilityItem`。提交后只把数值指标写入 `course_capability_attempts`，把聚合状态写入 `course_activity_progress`；不会创建普通 `dictation_attempts`、文章、文章句子或普通词汇语境。

课程跟读复用现有录音服务、Azure provider、异步评分和 Beta 降级提示。参考正文只随当前请求进入 provider，结果写入课程能力表，不写普通 `pronunciation_attempts`。一次成功完成即可完成 speaking 活动，没有最低分门槛；未配置、失败或取消会保留独立失败历史，不伪造分数。

## 词汇与收藏

课程词汇复用 `ArticleWordIndexService.extract()` 的英文词形规则和现有 `VocabularyLearningService`：

```text
共享 vocabulary entry
+ 课程来源 context（stable key + 字符位置）
+ 用户学习状态与普通词条 FSRS
```

词义、收藏和共享词条学习状态仍由原服务维护。课程语境在返回给单词详情、FSRS 队列或中文讲解 provider 前动态补回当前课程句子；数据库中的课程 `source_sentence` 始终为空。

## 活动完成规则

Lesson、Unit 和 Course 的完成率仍由当前课程 JSON 动态聚合，但 schema 13 的计数单位是唯一的 `(item_stable_key, activity_type)`：

- required activity 进入分母，可选 activity 不阻止完成；
- typing、dictation、speaking、vocabulary、review 状态互不覆盖；
- listening 与 fsrs 映射为 `review`，reading、translation 和 self-test 映射为 `typing`；
- 听写和跟读只要求完成，不设置固定分数；
- `skipped` 不算完成，`deprecated` Item 不进入当前分母或到期课程队列；
- 同一活动重复练习保留最早完成时间和全部逐次历史。

schema 12 已完成的打字状态继续作为 typing 的兼容来源；下一次实际练习会同步写入新的 activity 行。

## UI 与错误处理

课程 Day 页按 Lesson activity 显示朗读、听写和跟读入口，并根据课程词汇与 FSRS 标签显示收藏和课程复习入口。逐句课程练习继续复用 `SentencePracticeView`，只增加薄的课程能力按钮；听写和跟读复用原页面的课程运行时模式。

内容刷新、stable key 丢失、数据库失败、provider 不可用和空活动都会显示可理解的提示并记录课程 ID/stable key 与原因，不记录课程全文或用户输入全文。单门课程加载失败仍由课程仓储隔离，不影响其他课程或主窗口。

测试中应使用：

```python
context = build_app_context(
    data_dir=temp_data,
    courses_root=temp_courses,
)
```

迁移和能力测试不得连接真实用户数据库。

## 边界

本阶段不把课程正文写入文章表，不创建临时文章，不改变普通文章编辑/删除语义，不实现 schema 14、在线课程、课程包、自定义课程或强制 Level 解锁。Phase 6 应在现有 `CourseCapabilityService`、独立课程 FSRS 队列和动态课程版本解析之上继续，而不是引入第二套正文存储。
