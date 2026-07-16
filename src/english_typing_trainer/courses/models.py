from __future__ import annotations

from dataclasses import dataclass

from english_typing_trainer.courses.errors import CourseLoadFailure


@dataclass(frozen=True, slots=True)
class CourseLearningPlan:
    new_sentences_per_day: int | None = None
    unit_days: int | None = None
    review_day: int | None = None
    dictation_day: int | None = None
    assessment_day: int | None = None


@dataclass(frozen=True, slots=True)
class CourseActivity:
    activity_type: str
    sentence_ids: tuple[str, ...]
    required: bool


@dataclass(frozen=True, slots=True)
class CourseAssessment:
    assessment_type: str
    sentence_ids: tuple[str, ...]
    passing_score: int


@dataclass(frozen=True, slots=True)
class CourseMistake:
    incorrect: str
    explanation_zh: str


@dataclass(frozen=True, slots=True)
class CourseAlternative:
    english: str
    chinese: str


@dataclass(frozen=True, slots=True)
class CourseAudioHint:
    stress_words: tuple[str, ...] = ()
    pause_after: tuple[str, ...] = ()
    note_zh: str = ""


@dataclass(frozen=True, slots=True)
class CourseSentence:
    sentence_id: str
    stable_key: str
    unit_id: str
    lesson_id: str
    day: int
    order: int
    english: str
    chinese: str
    scene: str
    difficulty: str
    core_words: tuple[str, ...]
    core_patterns: tuple[str, ...]
    common_mistakes: tuple[CourseMistake, ...]
    alternative_expressions: tuple[CourseAlternative, ...]
    skill_tags: tuple[str, ...]
    source_type: str
    audio_hint: CourseAudioHint | None
    review_group: str
    content_version: str
    status: str
    replacement_stable_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CourseLesson:
    lesson_id: str
    stable_key: str
    unit_id: str
    day: int
    order: int
    title: str
    lesson_type: str
    description: str
    learning_goals: tuple[str, ...]
    new_sentence_ids: tuple[str, ...]
    review_sentence_ids: tuple[str, ...]
    activities: tuple[CourseActivity, ...]
    assessment: CourseAssessment | None
    content_version: str
    status: str


@dataclass(frozen=True, slots=True)
class CourseUnit:
    unit_id: str
    stable_key: str
    order: int
    title: str
    status: str
    content_path: str | None
    specification_version: str | None = None
    content_version: str | None = None
    course_id: str | None = None
    level_id: str | None = None
    description: str = ""
    difficulty: str | None = None
    estimated_days: int | None = None
    learning_goals: tuple[str, ...] = ()
    core_vocabulary: tuple[str, ...] = ()
    core_patterns: tuple[str, ...] = ()
    learning_plan_override: CourseLearningPlan | None = None
    lessons: tuple[CourseLesson, ...] = ()
    sentences: tuple[CourseSentence, ...] = ()

    @property
    def is_materialized(self) -> bool:
        return self.content_path is not None


@dataclass(frozen=True, slots=True)
class CourseLevel:
    level_id: str
    stable_key: str
    order: int
    title: str
    description: str
    difficulty: str
    learning_goals: tuple[str, ...]
    units: tuple[CourseUnit, ...]


@dataclass(frozen=True, slots=True)
class Course:
    specification_version: str
    course_id: str
    stable_key: str
    version: str
    content_version: str
    title: str
    subtitle: str
    description: str
    language: str
    target_level: str
    topics: tuple[str, ...]
    estimated_days: int
    estimated_sentences: int
    prerequisites: tuple[str, ...]
    learning_goals: tuple[str, ...]
    default_learning_plan: CourseLearningPlan
    levels: tuple[CourseLevel, ...]
    status: str
    built_in: bool
    read_only: bool
    default_order: int
    source_path: str


@dataclass(frozen=True, slots=True)
class CourseCatalog:
    catalog_version: str
    courses: tuple[Course, ...]
    failures: tuple[CourseLoadFailure, ...] = ()
