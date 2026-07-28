# 课程状态层（schema 12 与 schema 13）

Phase 3 在 Phase 2 只读课程加载器之上增加 schema 12 的最小用户状态层；Phase 5 的 schema 13 在此基础上增加按能力拆分的活动状态。课程正文、层级、顺序和必做规则仍以 `courses/` 下经过校验的 JSON 为权威源；SQLite 只保存 enrollment、实际发生过的 Item/活动状态与数值历史，不复制英文、中文或活动列表。

## 入口与对象

应用入口是 `AppContext.course_progress_service`，类型为 `CourseProgressService`。它组合：

- `CourseRepository`：读取不可变的 `Course`、`CourseUnit`、`CourseLesson` 和 `CourseSentence`。
- `CourseProgressRepository`：读写 schema 12/13 的稀疏用户状态。
- `CourseEnrollment`、`CourseItemProgress`、`CourseActivityProgress`、`CourseProgressSummary`：对外返回的冻结 dataclass，不暴露可变字典或 SQLite 内部 ID。

公共接口：

```python
service.enroll(course_id)
service.get_enrollment(course_id)
service.set_enrollment_status(course_id, status)

service.start_item(course_id, item_stable_key)
service.complete_item(course_id, item_stable_key, score=None)
service.skip_item(course_id, item_stable_key)
service.get_item_progress(course_id, item_stable_key)

service.start_activity(course_id, item_stable_key, activity_type)
service.complete_activity(course_id, item_stable_key, activity_type, score=None)
service.fail_activity(course_id, item_stable_key, activity_type, score=None)
service.skip_activity(course_id, item_stable_key, activity_type)
service.get_activity_progress(course_id, item_stable_key, activity_type)

service.get_lesson_progress(course_id, lesson_id)
service.get_unit_progress(course_id, unit_id)
service.get_course_progress(course_id)
service.get_next_lesson(course_id)
service.get_next_required_item(course_id)
```

课程、Unit、Lesson 或 Item 不存在时抛出 `CourseContentNotFoundError`。修改尚未建立的 enrollment 会抛出 `CourseEnrollmentNotFoundError`；非法 enrollment 状态会抛出 `InvalidEnrollmentStatusError`。未开始但有效的 Item 返回内存中的 `not_started` 对象，不写数据库。

## schema 12

迁移只新增两张表，不改变现有表语义。

### `course_enrollments`

每个 `course_stable_key` 最多一行，保存：

- `status`：`active`、`paused`、`completed` 或 `archived`；
- `current_lesson_stable_key`：当前推荐 Lesson；
- 最近看到的 `course_version` 与 `content_version`；
- `enrolled_at`、`last_studied_at`、`created_at`、`updated_at`。

### `course_item_progress`

仅在用户 start、complete 或 skip 一个 Item 时按需创建。它通过内部 `enrollment_id` 维护外键，同时明确保存 `course_stable_key`、`unit_stable_key`、`lesson_stable_key`、`item_stable_key`。其余字段包括：

- `item_type` 与 `status`；
- `attempt_count`、`best_score`、`latest_score`；
- `first_started_at`、`completed_at`、`last_studied_at`；
- Item 的 `content_version` 以及行创建、更新时间。

`enrollment_id` 和表自增 ID 只是 SQLite 内部键，业务身份与查询不依赖它们。两表都不保存课程正文，也没有为 Course、Unit、Lesson 建冗余进度表。

## schema 13 活动状态

schema 13 新增 `course_activity_progress`，把同一个 Item 的能力状态拆为：

```text
typing / speaking / vocabulary / review
```

每行只保存 enrollment 外键、Item stable key、活动类型、状态、尝试次数、最好/最近分数、内容版本和时间字段，唯一约束为 `(enrollment_id, item_stable_key, activity_type)`。该表不重复保存 Course、Level、Unit 或 Lesson stable key；需要层级时从当前 `CourseRepository` 解析。

状态为 `not_started`、`in_progress`、`completed`、`skipped` 或 `failed`。重复完成保持最早 `completed_at`，同时更新尝试次数、分数、内容版本和最近学习时间。schema 12 已存在的 `course_item_progress` 继续保存打字会话兼容状态；若尚未生成 typing activity 行，服务会把旧 `completed`/`skipped` 状态作为 typing 的读取来源。

schema 13 同时增加不含正文的课程能力历史和课程 FSRS 表，详见 `docs/course-capabilities.md`。这些表与完成率聚合共享 `enrollment_id + item_stable_key` 身份，但不改变 schema 12 enrollment 生命周期。

## stable key 规则与升级

状态关联只使用 `course_stable_key`、`unit_stable_key`、`lesson_stable_key`、`item_stable_key`，不使用 JSON 数组位置、文件路径、全文哈希、排序值或运行时对象 ID。

- 相同 Item `stable_key` 的文字修订、排序变化或层级调整保留原状态。
- 新增必做 Item 或新增必做 activity 不预写状态，并会进入当前分母，所以完成率可以下降。
- `deprecated` Item 的历史行保留，但不再进入当前完成率或下一项推荐。
- 语义变化必须使用新 `stable_key`；已经删除或弃用的 key 不得复用。
- enrollment 和 Item 的内容版本在下一次实际学习写入时更新，课程正文始终从当前 JSON 读取。

Phase 6A 增加只读 `get_version_status(course_id)`：它按语义版本比较 enrollment 最后学习时记录的 course/content version 与当前 JSON。当前版本提高时返回 `has_new_content=True`，同时指出用户是否曾完成记录版本。该查询不更新 enrollment；历史状态继续按 stable key 保留，完成率按当前 required 活动重算。用户实际开始新版本活动后，enrollment 才记录当前版本。

迁移从 schema 11 顺序执行到 12 再到 13，也支持从 12 直接升级到 13。迁移前沿用现有备份机制，全部 DDL 和版本更新运行在同一 savepoint 内，失败会回滚列、表、索引和版本号；新数据库可直接初始化到 13，重复启动不会重复建表或写 enrollment。

## enrollment 生命周期

显式 `enroll()` 是幂等的。第一次 start、complete 或 skip Item 时也会自动 enrollment。纯查询不会 enrollment，也不会预生成所有 Item 行。

暂停和归档只改变状态，不删除历史。`active` enrollment 完成当前全部有效必做活动后自动变为 `completed`。后续内容版本新增必做 Item 或 activity 时，动态进度会重新变为未完成；用户开始新活动时，已完成 enrollment 会重新激活。暂停或归档状态不会被学习写入自动覆盖。

## 完成率

完成率集中由 `CourseProgressService` 计算：

```text
完成率 = 当前已 completed 的有效必做活动 / 当前有效必做活动
```

- 只有 required activity 引用的 `(item_stable_key, activity_type)` 进入分母；可选 activity 不进入。
- 同一句可以分别要求 typing 或 speaking；各能力必须独立完成，且不设置固定分数门槛。
- `deprecated` Unit、Lesson 和 Item 不进入。
- `skipped` 保留为历史选择，但不视为完成。
- 同一 `(item_stable_key, activity_type)` 在一个聚合范围内只计一次。
- Lesson、Unit、Course 的百分比都实时聚合，不落库。
- 空 Lesson 明确定义为 `0 / 0`、`0%` 且未完成；它不会阻挡下一条可学习必做活动的推荐。
- 分数只记录，不构成课程活动的完成门槛。

## 下一课与下一必做项

推荐顺序来自当前只读课程对象的 Level、Unit、Lesson、activity 和 Sentence 顺序。服务选择第一个既未 `completed`、也未 `skipped` 的有效必做活动；`get_next_required_item()` 返回该活动对应的 Item，`get_next_lesson()` 返回包含它的 Lesson。同一句的 typing 与 speaking 可按课程配置独立推进。跳过前置活动不会把它标记完成，但推荐可继续向后移动。

新用户可查询首个推荐，而不会因此写 enrollment。课程当前必做活动全部完成时返回 `None`。`paused` 或 `archived` enrollment 也返回 `None`；恢复为 `active` 后重新按当前 JSON 和历史活动状态计算。当前仍不实现 Level 强制解锁，调用方可以进入任意 Lesson。

## UI 与测试调用

未来 UI 和学习服务应只调用 `context.course_progress_service`，不能直接写表。例如：

```python
context = build_app_context()
lesson = context.course_progress_service.get_next_lesson("ai-large-models")
item = context.course_progress_service.get_next_required_item("ai-large-models")
```

测试可同时注入临时数据目录和课程目录：

```python
context = build_app_context(data_dir=temp_data, courses_root=temp_courses)
```

也可以直接组合 `DatabaseManager`、`CourseRepository(temp_courses)`、`CourseProgressRepository` 和 `CourseProgressService`，并注入可控时钟验证时间字段。这样可以模拟新增、移动、排序变化和弃用，而不修改正式课程资源。

## 当前边界

Phase 5 已在 schema 13 中增加独立课程活动状态、数值尝试历史和课程句子 FSRS，但仍不把课程句子插入文章表，也不建立泛型课程内容映射表。当前课程跟读不写普通历史表；课程词汇只复用共享词条，并以 stable key 保存来源语境。旧听写活动行只为历史兼容保留。完整能力边界见 `docs/course-capabilities.md`，真实副本迁移和跨会话验收见 `docs/course-release-hardening.md`。
