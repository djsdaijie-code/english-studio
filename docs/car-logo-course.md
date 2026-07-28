# 全球汽车品牌与车标英语 MVP

## 可交付范围

`global-car-logos` 是第一门视觉辅助品牌英语课程：40 个常见乘用车品牌、2 个 Unit、14 个 Day。每项内容先给出品牌名，再给出一条简短、稳定的事实介绍，例如 `Toyota. This Japanese brand makes cars, SUVs, and hybrid vehicles.`。用户查看完整英文并跟打，完成后显示整条中文翻译。车标是记忆线索，不是要求用户在学习前猜答案的测试题。

本版本不做全球品牌穷举、车型知识、在线素材更新、用户导入、自定义题库或新的数据库表。

## 数据与运行流程

```text
CourseSentence stable key
→ optional CourseVisualPrompt
→ validated course-relative SVG
→ CourseLearningSession
→ existing SentencePracticeView
→ schema 13 course progress
```

`specification_version: 1.1` 只给句子增加可选 `visual_prompt`：

- `prompt_type`：`illustrated_word` 表示图片辅助词汇学习；契约也保留 `image_recognition`，供未来明确的识图练习使用。
- `asset_path`：相对课程根目录的 `assets/...svg`。
- `alt_text`、`instruction_zh`：包含品牌名称的可访问性说明与跟打指令。
- `source_url`、`rights_note`：来源和权利提示。
- `hide_answer`：控制目标文本是否延迟显示；本课程统一为 `false`。

加载器把 `asset_path` 安全解析为绝对路径。普通 `1.0` 课程不带该字段，行为完全不变。

## UI 复用

逐句练习页新增一块白底视觉提示区域，使用 Qt SVG 渲染器等比绘制。品牌介绍练习开始时：

- 车标和“先读品牌名，再跟打一条简短介绍；车标用于辅助记忆”可见；
- 原文框以“品牌名与介绍”为标题显示完整目标；
- 右侧“英文原句”同步显示完整的品牌名与介绍句；
- 喇叭将完整英文与 Item stable key、`content_version: 0.1.1` 交给既有课程 TTS，完成后不自动生成付费音频，但可按 Space 主动重听；
- 现有字符判定、计时、暂停和进度逻辑不变。

句子正确完成后显示品牌名和介绍的完整中文翻译。Day 详情列表直接列出当日英文内容；Day 7 明确标为综合复习，不把可见答案的跟打包装成识别测试。无 `core_words` 的品牌项不显示课程词汇按钮。

## 路径与安全

视觉素材随 `courses/` 一起进入既有 PyInstaller data 映射，不增加打包配置。开发态从项目课程根加载，打包态从 `_MEIPASS/courses` 加载，测试可注入临时课程目录。

运行时拒绝：

- 绝对路径或逃逸课程目录的路径；
- 缺失、不可读或超过 256 KiB 的素材；
- 非 UTF-8 或缺少 SVG 根元素的文件；
- `script`、外部图片、`foreignObject`、事件处理器、`href`/`xlink:href` 和外部 `url(...)`。

单门视觉课程失败时仍按现有错误隔离策略处理，其他课程继续可用。

## 素材追溯与状态

`courses/global-car-logos/ASSET_SOURCES.json` 为每个 SVG 保存课程路径、品牌、来源提供方、上游版本、来源页、原始文件位置、权利说明和 SHA-256。课程标记为 `draft`，因为版权状态不等同于商标使用许可；正式发布前必须重新检查各品牌指南和目标市场边界。

## 数据库边界

本功能不升级 schema 13。品牌名与介绍句继续作为只读课程正文从 `CourseRepository` 解析；SQLite 只保存 enrollment、Item stable key、活动状态和 FSRS 状态。不会创建 `articles`、`article_sentences` 或普通文章练习记录。

## 验证

```powershell
.\.venv\Scripts\python.exe scripts\validate_courses.py
.\.venv\Scripts\python.exe -m pytest -q tests\test_car_logo_course.py
```

专项测试覆盖课程规模、8–12 词介绍长度、官方大小写、素材来源与哈希、stable key 查询、学习会话顺序、车标与完整英文同步显示、完成后中文翻译、跟读入口、Day 预览、综合复习语义、文章表零写入、素材缺失/恶意 SVG 隔离，以及规范 `1.0` 向后兼容。
