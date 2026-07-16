# 只读课程加载器

Phase 2 在 `english_typing_trainer.courses` 中提供独立、只读的课程加载层。它只读取安装资源中的 JSON，不访问 SQLite，不创建用户进度，也不把课程正文映射到文章表。

## 公共入口

```python
from english_typing_trainer.courses import CourseRepository

repository = CourseRepository()
catalog = repository.load_catalog()
courses = repository.list_courses()
course = repository.get_course("ai-large-models")
sentence = repository.get_sentence("ai-large-models", "ai-s0001")
same_sentence = repository.get_sentence_by_stable_key(
    "ai-large-models-sentence-0001"
)
```

查询接口为：

- `load_catalog()`
- `list_courses()`
- `get_course(course_id)`
- `get_level(course_id, level_id)`
- `get_unit(course_id, unit_id)`
- `get_lesson(course_id, lesson_id)`
- `get_sentence(course_id, sentence_id)`
- `get_sentence_by_stable_key(stable_key)`
- `clear_cache()`
- `reload()`

所有 `get_*` 查询在目标不存在或所属课程已被隔离时返回 `None`。catalog 整体无法读取时，`load_catalog()` 抛出明确异常。

`AppContext.course_repository` 暴露同一仓库实例，未来 UI 和学习服务应从应用上下文取得它，不需要自行解析 JSON。

## 领域对象

公共层级对象为 `CourseCatalog`、`Course`、`CourseLevel`、`CourseUnit`、`CourseLesson` 和 `CourseSentence`。活动、测评、学习计划、易错点、替代表达与音频提示也会转换为类型明确的值对象。

所有模型使用 `@dataclass(frozen=True, slots=True)`，数组转换为 tuple。公共 API 不返回原始 dict，也不含 SQLite ID、用户进度或可写内容引用。尚未生成内容文件的 Unit 仍作为骨架对象返回，`is_materialized` 为 `False`，其 Lesson 和 Sentence 为空。

## 加载与校验流程

```text
定位 courses 根目录
→ 读取四份 Schema
→ 读取并检查 catalog.json
→ 分别加载每门 Course
→ 加载非空 content_path 对应的 Unit
→ 校验 Schema、路径、身份、引用、顺序和稳定键
→ 构建冻结领域对象与进程内查询索引
```

`english_typing_trainer.courses.validation.CourseValidator` 是运行时和离线脚本共享的校验实现。`python scripts/validate_courses.py` 只是薄入口，不再维护第二套规则。

校验包括 UTF-8、JSON 语法、JSON Schema Draft 2020-12 的项目所用子集、必需文件、安全相对路径、Course/Unit/Lesson/Sentence 引用、ID、`stable_key`、顺序和固定大小写。当前支持 `specification_version: 1.0`；其他版本产生 `UnsupportedCourseVersionError`。

## 错误隔离

- `CourseLoadError`：缺失文件或其他无法安全加载的资源问题。
- `CourseValidationError`：JSON、Schema、路径、引用、身份或唯一性不符合契约。
- `UnsupportedCourseVersionError`：课程规范版本不受当前加载器支持。
- `CourseLoadFailure`：提供给调用方的只读失败摘要。

错误包含课程 ID、文件路径、异常类型和简短原因，不包含课程全文。单门课程失败时，仓库记录 warning 日志，把摘要放入 `CourseCatalog.failures`，并继续加载其他课程。catalog 或 Schema 基础设施整体缺失时无法安全枚举课程，因此直接抛错，不静默返回空目录。

## 资源路径与打包

路径逻辑集中在 `courses.paths`：

- 开发环境：从模块文件位置反推项目根下的 `courses/`，不读取当前工作目录。
- PyInstaller：使用 `sys._MEIPASS / "courses"`，与现有样式和图标资源机制一致。
- 测试或替代课程源：`CourseRepository(courses_root=temporary_path)` 显式注入目录。

PyInstaller 不会自动收集仓库 JSON，因此 `EnglishStudio.spec` 只增加了一条 `courses → courses` 数据目录映射。这是让现有 `_MEIPASS` 路径在正式包中实际可用的最小必要打包修改；没有改变构建流程或安装器配置。

## 缓存与生命周期

首次查询时延迟加载整个 catalog 和已物化 Unit，并建立进程内索引。同一个仓库实例在运行周期内复用 `CourseCatalog` 和领域对象，不反复读取磁盘。

- `clear_cache()` 清除对象、索引和 Schema 缓存；下一次访问重新加载。
- `reload()` 清除后立即重新加载并返回新的 `CourseCatalog`。

加载器不监听文件变化，也不创建数据库缓存。内置课程随应用发布时，通常一个进程生命周期只需加载一次。

## 测试中的临时目录

```python
import shutil

temporary_courses = tmp_path / "courses"
shutil.copytree(project_root / "courses", temporary_courses)
repository = CourseRepository(temporary_courses)
```

测试可以修改临时副本来覆盖无效 JSON、缺失文件、断裂引用、重复 ID、重复稳定键、版本不支持、错误隔离和重新加载，不会触碰正式课程或用户数据。

## 与现有架构的关系

- Python 包继续按现有 `models/services/application` 风格组织；课程作为边界清楚的功能包，仓库对象由 `AppContext` 提供。
- 只读值对象沿用项目已有 frozen dataclass 模式。
- 日志使用标准 `logging.getLogger(__name__)`，进入现有旋转日志配置。
- 路径沿用 `ui.theme.resource_root` 的开发态与 `_MEIPASS` 思路，但课程路径不依赖 UI 模块。
- pytest 继续通过临时目录和标准 fixtures 隔离数据。

本阶段不写 SQLite，因为 JSON 是课程静态内容的权威源，而 schema 11 没有课程稳定键和进度结构。只有进入课程选课、Day 进度和内容升级状态阶段时，才应单独评审 schema 12。
