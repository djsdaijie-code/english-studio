# English Studio 内置课程内容

本目录保存随版本管理的只读课程静态内容。用户进度、收藏、笔记、FSRS、听写和跟读状态不进入这些 JSON；未来由 SQLite 按 `stable_key` 关联。

## 文件关系

```text
catalog.json
└── ai-large-models/course.json
    └── levels[].units[].content_path
        └── units/unit-01-foundations.json
            ├── lessons[]
            └── sentences[]
```

- `AGENTS.md`：课程内容开发的最高规范。
- `schema/`：JSON Schema Draft 2020-12 契约。
- `templates/`：可复制填写的 JSON 模板。
- `catalog.json`：应用可发现的课程目录；只登记真实存在的课程入口。
- `ai-large-models/COURSE_PLAN.md`：第一套课程的内容路线图。

`course.json` 只保存 Course、Level 和 Unit 清单。尚未编写的 Unit 使用 `content_path: null`，不得指向不存在的占位文件。每个实际 Unit 文件保存 Day/Lesson 与 Learning Item；当前第一轮样例只使用句子。

## ID 与版本

机器 ID 和 `stable_key` 一经发布不可复用。移动内容、调整翻译或轻微修改英文时保留稳定键；核心语义改变时创建新键并弃用旧项。详细规则见 `AGENTS.md`。

课程契约版本为 `specification_version`，课程包版本为 `version`，具体内容修订为 `content_version`。所有版本使用语义化版本。

## 新增或修改内容

1. 完整阅读 `AGENTS.md`。
2. 从 `templates/` 复制相应模板。
3. 分配未使用的稳定 ID，填写内容并更新版本。
4. 更新课程的 Unit 清单；仅当目标文件已经存在时填写 `content_path`。
5. 运行课程校验和相关项目测试。
6. 完成英语、中文、技术事实、听写、跟读和 FSRS 人工审核后再提升状态。

运行时入口为 `english_typing_trainer.courses.CourseRepository`。它把课程解析为冻结的 Python 对象，隔离损坏课程，并支持 ID、`stable_key`、缓存刷新和测试目录注入。`scripts/validate_courses.py` 与运行时加载器复用同一套标准库校验模块，不会修改课程或用户数据。开发说明见 `docs/course-loader.md`。
