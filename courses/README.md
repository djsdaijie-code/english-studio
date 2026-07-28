# English Studio 内置课程内容

本目录保存随版本管理的只读课程静态内容。用户进度、收藏、笔记、FSRS 和 AI 朗读状态不进入这些 JSON；由 SQLite 按 `stable_key` 关联。

## 文件关系

```text
catalog.json
├── ai-large-models/course.json
│   └── levels[].units[].content_path → units/unit-*.json
├── global-car-logos/course.json
│   ├── levels[].units[].content_path → units/unit-*.json
│   ├── assets/logos/*.svg
│   └── ASSET_SOURCES.json
└── crypto-blockchain-english/course.json
    └── levels[].units[].content_path → units/unit-*.json
```

- `AGENTS.md`：课程内容开发的最高规范。
- `schema/`：JSON Schema Draft 2020-12 契约。
- `templates/`：可复制填写的 JSON 模板。
- `catalog.json`：应用可发现的课程目录；只登记真实存在的课程入口。
- `ai-large-models/COURSE_PLAN.md`：第一套课程的内容路线图。
- `global-car-logos/COURSE_PLAN.md`：40 品牌车标 MVP 的教学路线。
- `crypto-blockchain-english/COURSE_PLAN.md`：40 条币圈与区块链英语 MVP 的教学路线。

`course.json` 只保存 Course、Level 和 Unit 清单。尚未编写的 Unit 使用 `content_path: null`，不得指向不存在的占位文件。每个实际 Unit 文件保存 Day/Lesson 与 Learning Item。

“AI 与大模型英语”第一版候选内容为 `1.0.0`：5 个 Level、8 个已实体化 Unit、56 个 Day 和 176 条 reviewed 句子。每个 Unit 含 7 个 Day 和 22 条核心句子，Day 5 复用所学内容形成综合场景，Day 6 通过重复打字巩固重点句，Day 7 复习、自测并提供可选 FSRS 活动。AI 朗读只作为练习页辅助能力，不再设置专门朗读 Day。课程当前状态为 `reviewed`，尚未发布。

“全球汽车品牌与车标英语”MVP 为 `0.1.1`：1 个 Level、2 个 Unit、14 个 Day、40 个品牌项和 40 份 SVG 素材。它使用 `specification_version: 1.1` 的可选 `visual_prompt`，从练习开始显示“品牌名 + 简短事实介绍”，车标用于辅助记忆；用户跟打完整英文后查看中文翻译。课程当前为 `draft`；内容事实、读音、商标、素材时效和真人试学尚未签核，不能标为 `reviewed` 或 `published`。

“币圈与区块链英语”MVP 为 `0.1.0`：1 个 Level、2 个 Unit、14 个 Day 和 40 条中级短句，覆盖钱包、转账、交易、DeFi、TVL、链上指标和风险。课程只配置打字与可选 FSRS，不配置 AI 朗读，全部 `audio_hint` 为 `null`；内容不包含价格预测、收益承诺或投资建议。课程当前为 `draft`，技术复核与真人试学完成前不能标为 `reviewed` 或 `published`。

## ID 与版本

机器 ID 和 `stable_key` 一经发布不可复用。移动内容、调整翻译或轻微修改英文时保留稳定键；核心语义改变时创建新键并弃用旧项。详细规则见 `AGENTS.md`。

课程契约版本为 `specification_version`，课程包版本为 `version`，具体内容修订为 `content_version`。加载器同时兼容 `1.0` 和 `1.1`；`1.1` 仅增加可选视觉提示，不改变原有句子课程。所有版本使用语义化版本。

## 新增或修改内容

1. 完整阅读 `AGENTS.md`。
2. 从 `templates/` 复制相应模板。
3. 分配未使用的稳定 ID，填写内容并更新版本。
4. 更新课程的 Unit 清单；仅当目标文件已经存在时填写 `content_path`。
5. 运行课程校验和相关项目测试。
6. 完成英语、中文、技术事实、AI 朗读和 FSRS 人工审核后再提升状态。

第一版课程内容还应运行：

```powershell
.\.venv\Scripts\python.exe scripts\qa_course_content.py
```

该检查覆盖候选课程规模、状态、句长、重复、核心词和句型、每日活动及原样例 stable key 保留情况；它不能替代真人试学和内容审核。

运行时入口为 `english_typing_trainer.courses.CourseRepository`。它把课程解析为冻结的 Python 对象，隔离损坏课程，并支持 ID、`stable_key`、缓存刷新和测试目录注入。`scripts/validate_courses.py` 与运行时加载器复用同一套标准库校验模块，不会修改课程或用户数据。开发说明见 `docs/course-loader.md`。
