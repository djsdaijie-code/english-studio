from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from english_typing_trainer.courses.models import (
    Course,
    CourseLesson,
    CourseSentence,
    CourseUnit,
    CourseVisualPrompt,
)
from english_typing_trainer.courses.repository import CourseRepository
from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.services.course_progress import CourseProgressService


CourseSessionMode = Literal["recommended", "manual", "review"]


class CourseLearningError(RuntimeError):
    """Base error raised while adapting immutable course content for typing."""


class CourseLessonNotFoundError(CourseLearningError, LookupError):
    pass


class EmptyCourseLessonError(CourseLearningError):
    pass


@dataclass(slots=True)
class CourseLearningSession:
    """Mutable cursor over an immutable snapshot of a course lesson."""

    course_id: str
    course_stable_key: str
    unit_id: str
    lesson_id: str
    lesson_stable_key: str
    sentence_ids: tuple[str, ...]
    item_stable_keys: tuple[str, ...]
    current_index: int
    session_mode: CourseSessionMode
    course_title: str
    lesson_title: str
    typing_sentences: tuple[ArticleSentence, ...]
    chinese_translations: tuple[str, ...]
    activity_types_by_item: tuple[tuple[str, ...], ...]
    has_vocabulary_by_item: tuple[bool, ...]
    core_words_by_item: tuple[tuple[str, ...], ...]
    core_patterns_by_item: tuple[tuple[str, ...], ...]
    visual_prompts: tuple[CourseVisualPrompt | None, ...]
    section_text: str
    _started_item_keys: set[str] = field(default_factory=set, repr=False)

    @property
    def current_item_stable_key(self) -> str | None:
        if 0 <= self.current_index < len(self.item_stable_keys):
            return self.item_stable_keys[self.current_index]
        return None

    def sync_index(self, index: int) -> None:
        if self.item_stable_keys:
            self.current_index = max(0, min(index, len(self.item_stable_keys) - 1))

    def mark_item_started(self, item_stable_key: str) -> bool:
        """Return True once per item and session, so input events are idempotent."""
        if item_stable_key in self._started_item_keys:
            return False
        self._started_item_keys.add(item_stable_key)
        return True


class CourseLearningService:
    """Builds non-persistent typing sessions from validated course objects."""

    def __init__(
        self,
        courses: CourseRepository,
        progress: CourseProgressService,
    ) -> None:
        self.courses = courses
        self.progress = progress

    def build_session(
        self,
        course_id: str,
        lesson_id: str,
        session_mode: CourseSessionMode = "manual",
    ) -> CourseLearningSession:
        if session_mode not in {"recommended", "manual", "review"}:
            raise ValueError(f"Unsupported course session mode: {session_mode!r}")

        course = self.courses.get_course(course_id)
        if course is None:
            raise CourseLessonNotFoundError(
                f"Course not found while building a learning session: {course_id!r}"
            )
        unit, lesson = self._find_lesson(course, lesson_id)
        referenced_ids = self._ordered_sentence_ids(lesson)
        sentences_by_id = {sentence.sentence_id: sentence for sentence in unit.sentences}
        missing = [sentence_id for sentence_id in referenced_ids if sentence_id not in sentences_by_id]
        if missing:
            raise CourseLessonNotFoundError(
                f"Lesson {lesson_id!r} in course {course_id!r} references missing sentence IDs: {missing!r}"
            )

        content = tuple(
            sentences_by_id[sentence_id]
            for sentence_id in referenced_ids
            if sentences_by_id[sentence_id].status != "deprecated"
        )
        if not content:
            raise EmptyCourseLessonError(
                f"Lesson {lesson_id!r} in course {course_id!r} has no active sentence items"
            )

        selected = content
        effective_mode = session_mode
        if session_mode != "review":
            selected = tuple(
                sentence
                for sentence in content
                if self.progress.get_item_progress(course_id, sentence.stable_key).status
                != "completed"
            )
            if not selected:
                selected = content
                effective_mode = "review"

        typing_sentences, section_text = self._adapt_sentences(selected)
        return CourseLearningSession(
            course_id=course.course_id,
            course_stable_key=course.stable_key,
            unit_id=unit.unit_id,
            lesson_id=lesson.lesson_id,
            lesson_stable_key=lesson.stable_key,
            sentence_ids=tuple(sentence.sentence_id for sentence in selected),
            item_stable_keys=tuple(sentence.stable_key for sentence in selected),
            current_index=0,
            session_mode=effective_mode,
            course_title=course.title,
            lesson_title=lesson.title,
            typing_sentences=typing_sentences,
            chinese_translations=tuple(sentence.chinese for sentence in selected),
            activity_types_by_item=tuple(
                self._activity_types(lesson, sentence.sentence_id)
                for sentence in selected
            ),
            has_vocabulary_by_item=tuple(bool(sentence.core_words) for sentence in selected),
            core_words_by_item=tuple(sentence.core_words for sentence in selected),
            core_patterns_by_item=tuple(sentence.core_patterns for sentence in selected),
            visual_prompts=tuple(sentence.visual_prompt for sentence in selected),
            section_text=section_text,
        )

    @staticmethod
    def _find_lesson(course: Course, lesson_id: str) -> tuple[CourseUnit, CourseLesson]:
        for level in course.levels:
            for unit in level.units:
                for lesson in unit.lessons:
                    if lesson.lesson_id == lesson_id:
                        return unit, lesson
        raise CourseLessonNotFoundError(
            f"Lesson not found in course {course.course_id!r}: {lesson_id!r}"
        )

    @staticmethod
    def _ordered_sentence_ids(lesson: CourseLesson) -> tuple[str, ...]:
        ordered: list[str] = []
        seen: set[str] = set()
        candidates = [*lesson.new_sentence_ids, *lesson.review_sentence_ids]
        candidates.extend(
            sentence_id
            for activity in lesson.activities
            for sentence_id in activity.sentence_ids
        )
        for sentence_id in candidates:
            if sentence_id not in seen:
                ordered.append(sentence_id)
                seen.add(sentence_id)
        return tuple(ordered)

    @staticmethod
    def _adapt_sentences(
        content: tuple[CourseSentence, ...],
    ) -> tuple[tuple[ArticleSentence, ...], str]:
        adapted: list[ArticleSentence] = []
        offset = 0
        for index, sentence in enumerate(content):
            end = offset + len(sentence.english)
            adapted.append(
                ArticleSentence(
                    id=None,
                    article_id=None,
                    section_id=None,
                    sentence_index=index,
                    text=sentence.english,
                    normalized_text=sentence.english,
                    sentence_hash=sentence.stable_key,
                    start_offset=offset,
                    end_offset=end,
                )
            )
            offset = end
        return tuple(adapted), "".join(sentence.english for sentence in content)

    @staticmethod
    def _activity_types(
        lesson: CourseLesson, sentence_id: str
    ) -> tuple[str, ...]:
        result: list[str] = []
        mapping = {
            "fsrs": "review",
            "reading": "typing",
            "translation": "typing",
            "self_test": "typing",
        }
        for activity in lesson.activities:
            if sentence_id not in activity.sentence_ids:
                continue
            value = mapping.get(activity.activity_type, activity.activity_type)
            if value not in result:
                result.append(value)
        return tuple(result)


__all__ = [
    "CourseLearningError",
    "CourseLearningService",
    "CourseLearningSession",
    "CourseLessonNotFoundError",
    "CourseSessionMode",
    "EmptyCourseLessonError",
]
