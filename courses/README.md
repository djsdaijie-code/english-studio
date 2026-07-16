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

本轮只建立数据与架构，不包含运行时加载器。`scripts/validate_courses.py` 使用 Python 标准库完成离线结构、引用、唯一性和大小写检查；它验证本仓库使用的 JSON Schema 子集，不会修改课程或用户数据。
