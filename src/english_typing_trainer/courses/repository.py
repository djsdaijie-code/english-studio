from __future__ import annotations

import logging
from pathlib import Path

from english_typing_trainer.courses.errors import CourseLoadError, CourseLoadFailure, CourseValidationError
from english_typing_trainer.courses.loader import build_course
from english_typing_trainer.courses.models import (
    Course,
    CourseCatalog,
    CourseLesson,
    CourseLevel,
    CourseSentence,
    CourseUnit,
)
from english_typing_trainer.courses.paths import resolve_courses_root
from english_typing_trainer.courses.validation import CourseValidator


class CourseRepository:
    """Lazy, read-only access to validated built-in course resources."""

    def __init__(self, courses_root: Path | None = None) -> None:
        self.courses_root = resolve_courses_root(courses_root)
        self._logger = logging.getLogger(__name__)
        self._validator = CourseValidator(self.courses_root)
        self._catalog: CourseCatalog | None = None
        self._courses: dict[str, Course] = {}
        self._levels: dict[tuple[str, str], CourseLevel] = {}
        self._units: dict[tuple[str, str], CourseUnit] = {}
        self._lessons: dict[tuple[str, str], CourseLesson] = {}
        self._sentences: dict[tuple[str, str], CourseSentence] = {}
        self._sentences_by_stable_key: dict[str, CourseSentence] = {}

    def load_catalog(self) -> CourseCatalog:
        if self._catalog is not None:
            return self._catalog

        self._validator.load_schema_registry()
        raw_catalog = self._validator.load_catalog_document()
        courses: list[Course] = []
        failures: list[CourseLoadFailure] = []
        known_stable_keys: set[str] = set()

        for entry in sorted(raw_catalog["courses"], key=lambda item: item["default_order"]):
            try:
                data = self._validator.load_course_data(entry)
                course = build_course(data)
                stable_keys = self._stable_keys(course)
                duplicate = sorted(known_stable_keys.intersection(stable_keys))
                if duplicate:
                    raise CourseValidationError(
                        f"stable_key conflicts with another course: {duplicate!r}",
                        path=data.course_path,
                        course_id=course.course_id,
                    )
            except CourseLoadError as exc:
                failure = CourseLoadFailure.from_error(exc)
                failures.append(failure)
                self._logger.warning(
                    "course isolated course_id=%s path=%s error_type=%s reason=%s",
                    failure.course_id,
                    failure.path,
                    failure.error_type,
                    failure.reason,
                )
                continue
            courses.append(course)
            known_stable_keys.update(stable_keys)

        self._catalog = CourseCatalog(raw_catalog["catalog_version"], tuple(courses), tuple(failures))
        self._rebuild_indexes(self._catalog.courses)
        return self._catalog

    def list_courses(self) -> tuple[Course, ...]:
        return self.load_catalog().courses

    def get_course(self, course_id: str) -> Course | None:
        self.load_catalog()
        return self._courses.get(course_id)

    def get_level(self, course_id: str, level_id: str) -> CourseLevel | None:
        self.load_catalog()
        return self._levels.get((course_id, level_id))

    def get_unit(self, course_id: str, unit_id: str) -> CourseUnit | None:
        self.load_catalog()
        return self._units.get((course_id, unit_id))

    def get_lesson(self, course_id: str, lesson_id: str) -> CourseLesson | None:
        self.load_catalog()
        return self._lessons.get((course_id, lesson_id))

    def get_sentence(self, course_id: str, sentence_id: str) -> CourseSentence | None:
        self.load_catalog()
        return self._sentences.get((course_id, sentence_id))

    def get_sentence_by_stable_key(self, stable_key: str) -> CourseSentence | None:
        self.load_catalog()
        return self._sentences_by_stable_key.get(stable_key)

    @property
    def failures(self) -> tuple[CourseLoadFailure, ...]:
        return self.load_catalog().failures

    def clear_cache(self) -> None:
        self._catalog = None
        self._courses.clear()
        self._levels.clear()
        self._units.clear()
        self._lessons.clear()
        self._sentences.clear()
        self._sentences_by_stable_key.clear()
        self._validator = CourseValidator(self.courses_root)

    def reload(self) -> CourseCatalog:
        self.clear_cache()
        return self.load_catalog()

    def _rebuild_indexes(self, courses: tuple[Course, ...]) -> None:
        for course in courses:
            self._courses[course.course_id] = course
            for level in course.levels:
                self._levels[(course.course_id, level.level_id)] = level
                for unit in level.units:
                    self._units[(course.course_id, unit.unit_id)] = unit
                    for lesson in unit.lessons:
                        self._lessons[(course.course_id, lesson.lesson_id)] = lesson
                    for sentence in unit.sentences:
                        self._sentences[(course.course_id, sentence.sentence_id)] = sentence
                        self._sentences_by_stable_key[sentence.stable_key] = sentence

    @staticmethod
    def _stable_keys(course: Course) -> set[str]:
        keys = {course.stable_key}
        for level in course.levels:
            keys.add(level.stable_key)
            for unit in level.units:
                keys.add(unit.stable_key)
                keys.update(lesson.stable_key for lesson in unit.lessons)
                keys.update(sentence.stable_key for sentence in unit.sentences)
        return keys
