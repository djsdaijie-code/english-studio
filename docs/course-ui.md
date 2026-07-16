# 课程浏览 UI 与基础打字学习

Phase 4 在只读 `CourseRepository` 和 schema 12 `CourseProgressService` 之上提供第一版课程浏览与 Sentence Item 打字流程。课程 JSON 仍是正文和层级的唯一来源；UI 只读取领域对象，SQLite 只保存 enrollment、稀疏 Item 状态和不含正文的学习事件。

本文保留 Phase 4 的基础 UI 设计记录。Phase 5 已接入课程朗读、听写、跟读、词汇和 FSRS；当前能力边界与 schema 13 设计见 `docs/course-capabilities.md`。

## 页面与入口

主窗口侧栏的“课程”进入 `CoursePage`。页面内部保留浏览位置，并提供三层视图：

1. 课程列表：课程名称、简介、Level/Unit 数量、预计天数、状态、完成率，以及开始或继续入口。catalog 中单门课程失败时显示隔离摘要，其他课程仍可用；catalog 整体不可读时显示重新加载入口。
2. 课程详情：课程介绍、目标、总进度、推荐 Day 和 Level → Unit → Day 树。尚未物化的 Unit 显示“内容待补充”。
3. Day 详情：标题、目标、新句/复习句数量、活动类型、Item 状态和开始/继续按钮。空 Day、断裂引用和状态读取失败都会禁用或降级对应操作，不使主窗口退出。

推荐入口使用 `CourseProgressService.get_next_lesson()`。用户也可双击或选中任意 Day；前置 Day 未完成只显示提示，不强制锁定，也不会因跳学而自动完成。暂停和归档课程不提供自动下一课，但 Day 仍可查看和手动进入。已完成 Day 的按钮切换为“重新复习”。

## 课程学习会话

`AppContext.course_learning_service` 提供 `CourseLearningService`。它通过课程和 Day ID 构造内存中的 `CourseLearningSession`，主要字段包括：

```text
course_id / course_stable_key
unit_id
lesson_id / lesson_stable_key
sentence_ids / item_stable_keys
current_index
session_mode: recommended | manual | review
```

服务按 Lesson 的新句、复习句和 activity 引用顺序去重，忽略 deprecated Item，并把 `CourseSentence` 适配为现有逐句组件需要的内存 `ArticleSentence`。适配对象没有文章句子 ID，使用连续内存 offset；课程对象本身保持冻结且不被修改。

推荐和继续模式跳过已经完成的 Item；如果 Day 已全部完成，则自动进入 review 模式并重新提供全部有效句子。review 模式不会清除原完成时间或降低历史状态。课程内容在学习过程中刷新并导致 stable key 或引用失效时，会在当前练习状态区提示，并记录课程 ID、稳定键和原因。

## 复用现有打字能力

课程学习直接调用 `SentencePracticeView`、`SentenceLearningSession` 和 `TypingSession`，因此字符级正确性、大小写设置、退格、暂停、有效输入计时和统计继续使用现有实现，没有第二套字符判定逻辑。

课程模式只增加薄适配：

- 中文区显示课程 JSON 已提供的译文，不调用 AI 翻译，也不写翻译缓存；
- 课程模式关闭文章级翻译、人工编辑和单词收藏入口；
- 当前 TTS 缓存表会保存文本预览，因此课程模式暂时隐藏并阻止 TTS，避免把课程正文写入 SQLite；后续需先把缓存身份改为只保存不可逆哈希，才可安全接入；
- 学习事件使用 `course_` 前缀，且不附带文章或文章句子 ID，以区分课程来源；
- 不生成临时文章，不调用文章编辑、删除或分段服务。

## 状态写入时机

- 第一次有效字符输入：`start_item()`，状态变为 `in_progress`，同一会话对同一 Item 只调用一次。
- 一次完整输入句子：`complete_item()`，状态变为 `completed`。
- 退出未完成句子：已经写入的 `in_progress` 保留；下次继续仍从这个未完成 Item 开始。
- 重练已完成句子：保留最早完成时间和完成状态，仅按状态服务既有规则更新实际练习信息。
- Day、Unit 和 Course 完成率：每次展示时由当前 JSON 的有效必做 Item 动态聚合，不另建进度行。

`skipped` 在 UI 中显示“暂时跳过”，不显示为完成。schema 12 已能发现 enrollment 的课程版本与当前版本不同，UI 会提示“课程内容版本已更新”；它没有保存旧版本必做 Item 集合，因此 Phase 4 不伪造精确的“有新内容”状态。后续若需要区分“已完成旧版本”和“新增必做内容”，应增加显式的版本快照或升级差异服务。

## 错误与重新加载

课程页分别处理 catalog 整体异常、单门课程隔离失败、缺失 Day、断裂引用、空 Day 和进度数据库异常。日志只记录课程 ID、stable key、资源路径或异常原因，不记录课程全文和用户输入全文。课程页的“重新加载”调用 `CourseRepository.reload()`；测试可通过：

```python
context = build_app_context(
    data_dir=temp_data,
    courses_root=temp_courses,
)
```

注入临时课程目录，覆盖损坏课程、缺失 catalog 与内容刷新场景。

## 为什么不写文章表

内置课程是版本化、只读的发布资源，文章则是用户可编辑、可删除的持久内容。把课程句子伪装成文章会引入两套身份、升级同步、删除语义和全文复制问题。因此课程学习只把正文放入当前进程的打字会话，持久化只使用 stable key 关联 schema 12 状态；`articles`、`article_sections`、`article_sentences`、`sentence_attempts` 和普通 `practice_sessions` 都不会收到课程正文或课程学习记录。

## 当前边界与 Phase 5 接入点

Phase 4 不创建 FSRS 卡，不进入听写、跟读评分或课程词汇映射，也不升级数据库 schema。Phase 5 建议从 `CourseLearningSession.item_stable_keys` 和完成事件建立显式的能力适配层：先定义课程 Item 与 FSRS/词汇/听写目标的稳定关联及生命周期，再分别接入既有服务；不要反向依赖文章 ID，也不要把课程对象改成可写模型。
