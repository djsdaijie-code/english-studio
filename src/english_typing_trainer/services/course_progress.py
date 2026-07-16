from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import datetime, timezone

from english_typing_trainer.courses.models import (
    Course,
    CourseLesson,
    CourseLevel,
    CourseSentence,
    CourseUnit,
)
from english_typing_trainer.courses.repository import CourseRepository
from english_typing_trainer.database.course_progress_repository import CourseProgressRepository
from english_typing_trainer.models.course_progress import (
    CourseEnrollment,
    CourseItemProgress,
    CourseProgressSummary,
    EnrollmentStatus,
    ItemProgressStatus,
    ProgressScope,
)


ENROLLMENT_STATUSES: frozenset[EnrollmentStatus] = frozenset(
    {"active", "paused", "completed", "archived"}
)


class CourseProgressError(RuntimeError):
    pass


class CourseContentNotFoundError(CourseProgressError, LookupError):
    pass


class CourseEnrollmentNotFoundError(CourseProgressError, LookupError):
    pass


class InvalidEnrollmentStatusError(CourseProgressError, ValueError):
    pass


class CourseProgressService:
    """Coordinates immutable course content with sparse, stable-keyed user state."""

    def __init__(
        self,
        courses: CourseRepository,
        progress: CourseProgressRepository,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.courses = courses
        self.progress = progress
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def enroll(self, course_id: str) -> CourseEnrollment:
        course = self._require_course(course_id)
        next_lesson = self._next_lesson(course, None)
        return self.progress.enroll(
            course_stable_key=course.stable_key,
            course_version=course.version,
            content_version=course.content_version,
            current_lesson_stable_key=next_lesson.stable_key if next_lesson else None,
            now=self._now(),
        )

    def get_enrollment(self, course_id: str) -> CourseEnrollment | None:
        course = self._require_course(course_id)
        return self.progress.get_enrollment(course.stable_key)

    def set_enrollment_status(
        self,
        course_id: str,
        status: EnrollmentStatus,
    ) -> CourseEnrollment:
        if status not in ENROLLMENT_STATUSES:
            raise InvalidEnrollmentStatusError(f"Unsupported course enrollment status: {status!r}")
        course = self._require_course(course_id)
        enrollment = self.progress.set_enrollment_status(course.stable_key, status, self._now())
        if enrollment is None:
            raise CourseEnrollmentNotFoundError(
                f"Course {course_id!r} has no enrollment to update"
            )
        return enrollment

    def start_item(self, course_id: str, item_stable_key: str) -> CourseItemProgress:
        course = self._require_course(course_id)
        unit, lesson, item = self._require_item(course, item_stable_key)
        enrollment = self._ensure_enrollment(course)
        existing = self.progress.get_item_progress(course.stable_key, item.stable_key)
        now = self._now()
        saved = self.progress.save_item_progress(
            self._item_state(
                course,
                unit,
                lesson,
                item,
                status="completed" if existing and existing.status == "completed" else "in_progress",
                attempt_count=(existing.attempt_count if existing else 0) + 1,
                best_score=existing.best_score if existing else None,
                latest_score=existing.latest_score if existing else None,
                first_started_at=(
                    existing.first_started_at
                    if existing is not None and existing.first_started_at is not None
                    else now
                ),
                completed_at=existing.completed_at if existing else None,
                now=now,
                existing=existing,
            ),
            now,
        )
        self._record_course_activity(course, enrollment, now, reactivate_completed=True)
        return saved

    def complete_item(
        self,
        course_id: str,
        item_stable_key: str,
        score: float | None = None,
    ) -> CourseItemProgress:
        course = self._require_course(course_id)
        unit, lesson, item = self._require_item(course, item_stable_key)
        enrollment = self._ensure_enrollment(course)
        existing = self.progress.get_item_progress(course.stable_key, item.stable_key)
        now = self._now()
        previous_best = existing.best_score if existing else None
        best_score = previous_best
        if score is not None:
            best_score = score if previous_best is None else max(previous_best, score)
        saved = self.progress.save_item_progress(
            self._item_state(
                course,
                unit,
                lesson,
                item,
                status="completed",
                attempt_count=max(1, existing.attempt_count if existing else 0),
                best_score=best_score,
                latest_score=score if score is not None else (existing.latest_score if existing else None),
                first_started_at=(
                    existing.first_started_at
                    if existing is not None and existing.first_started_at is not None
                    else now
                ),
                completed_at=(
                    existing.completed_at
                    if existing is not None and existing.completed_at is not None
                    else now
                ),
                now=now,
                existing=existing,
            ),
            now,
        )
        self._record_course_activity(course, enrollment, now)
        return saved

    def skip_item(self, course_id: str, item_stable_key: str) -> CourseItemProgress:
        course = self._require_course(course_id)
        unit, lesson, item = self._require_item(course, item_stable_key)
        enrollment = self._ensure_enrollment(course)
        existing = self.progress.get_item_progress(course.stable_key, item.stable_key)
        now = self._now()
        saved = self.progress.save_item_progress(
            self._item_state(
                course,
                unit,
                lesson,
                item,
                status="completed" if existing and existing.status == "completed" else "skipped",
                attempt_count=existing.attempt_count if existing else 0,
                best_score=existing.best_score if existing else None,
                latest_score=existing.latest_score if existing else None,
                first_started_at=existing.first_started_at if existing else None,
                completed_at=existing.completed_at if existing else None,
                now=now,
                existing=existing,
            ),
            now,
        )
        self._record_course_activity(course, enrollment, now)
        return saved

    def get_item_progress(
        self,
        course_id: str,
        item_stable_key: str,
    ) -> CourseItemProgress:
        course = self._require_course(course_id)
        unit, lesson, item = self._require_item(course, item_stable_key)
        existing = self.progress.get_item_progress(course.stable_key, item.stable_key)
        if existing is not None:
            return existing
        return self._item_state(
            course,
            unit,
            lesson,
            item,
            status="not_started",
            attempt_count=0,
            best_score=None,
            latest_score=None,
            first_started_at=None,
            completed_at=None,
            now=None,
            existing=None,
        )

    def get_lesson_progress(self, course_id: str, lesson_id: str) -> CourseProgressSummary:
        course = self._require_course(course_id)
        unit, lesson = self._require_lesson(course, lesson_id)
        return self._summarize(
            "lesson",
            course,
            lesson.stable_key,
            self._required_items_for_lesson(unit, lesson),
        )

    def get_unit_progress(self, course_id: str, unit_id: str) -> CourseProgressSummary:
        course = self._require_course(course_id)
        unit = self._require_unit(course, unit_id)
        items = (
            item
            for lesson in unit.lessons
            for item in self._required_items_for_lesson(unit, lesson)
        )
        return self._summarize("unit", course, unit.stable_key, items)

    def get_course_progress(self, course_id: str) -> CourseProgressSummary:
        course = self._require_course(course_id)
        items = (
            item
            for _level, unit, lesson in self._ordered_lessons(course)
            for item in self._required_items_for_lesson(unit, lesson)
        )
        return self._summarize("course", course, course.stable_key, items)

    def get_next_lesson(self, course_id: str) -> CourseLesson | None:
        course = self._require_course(course_id)
        enrollment = self.progress.get_enrollment(course.stable_key)
        return self._next_lesson(course, enrollment)

    def get_next_required_item(self, course_id: str) -> CourseSentence | None:
        course = self._require_course(course_id)
        enrollment = self.progress.get_enrollment(course.stable_key)
        if enrollment is not None and enrollment.status in {"paused", "archived"}:
            return None
        states = self._state_by_item(course)
        for _level, unit, lesson in self._ordered_lessons(course):
            for item in self._required_items_for_lesson(unit, lesson):
                state = states.get(item.stable_key)
                if state is None or state.status not in {"completed", "skipped"}:
                    return item
        return None

    def _ensure_enrollment(self, course: Course) -> CourseEnrollment:
        existing = self.progress.get_enrollment(course.stable_key)
        if existing is not None:
            return existing
        next_lesson = self._next_lesson(course, None)
        return self.progress.enroll(
            course_stable_key=course.stable_key,
            course_version=course.version,
            content_version=course.content_version,
            current_lesson_stable_key=next_lesson.stable_key if next_lesson else None,
            now=self._now(),
        )

    def _record_course_activity(
        self,
        course: Course,
        enrollment: CourseEnrollment,
        now: datetime,
        *,
        reactivate_completed: bool = False,
    ) -> None:
        next_lesson = self._next_lesson(course, None)
        course_progress = self.get_course_progress(course.course_id)
        status: EnrollmentStatus | None = None
        if course_progress.is_completed and enrollment.status in {"active", "completed"}:
            status = "completed"
        elif reactivate_completed and enrollment.status == "completed":
            status = "active"
        self.progress.record_activity(
            course_stable_key=course.stable_key,
            course_version=course.version,
            content_version=course.content_version,
            current_lesson_stable_key=next_lesson.stable_key if next_lesson else None,
            now=now,
            status=status,
        )

    def _next_lesson(
        self,
        course: Course,
        enrollment: CourseEnrollment | None,
    ) -> CourseLesson | None:
        if enrollment is not None and enrollment.status in {"paused", "archived"}:
            return None
        states = self._state_by_item(course)
        for _level, unit, lesson in self._ordered_lessons(course):
            required = self._required_items_for_lesson(unit, lesson)
            if any(
                (state := states.get(item.stable_key)) is None
                or state.status not in {"completed", "skipped"}
                for item in required
            ):
                return lesson
        return None

    def _summarize(
        self,
        scope: ProgressScope,
        course: Course,
        stable_key: str,
        items: Iterable[CourseSentence],
    ) -> CourseProgressSummary:
        unique_items = {item.stable_key: item for item in items}
        states = self._state_by_item(course)
        total = len(unique_items)
        completed = sum(
            1
            for item_stable_key in unique_items
            if (state := states.get(item_stable_key)) is not None and state.status == "completed"
        )
        is_completed = total > 0 and completed == total
        percentage = round((completed / total) * 100, 2) if total else 0.0
        return CourseProgressSummary(
            scope=scope,
            course_stable_key=course.stable_key,
            stable_key=stable_key,
            completed_required_items=completed,
            total_required_items=total,
            completion_percentage=percentage,
            is_completed=is_completed,
        )

    def _state_by_item(self, course: Course) -> dict[str, CourseItemProgress]:
        return {
            item.item_stable_key: item
            for item in self.progress.list_item_progress(course.stable_key)
        }

    @staticmethod
    def _required_items_for_lesson(
        unit: CourseUnit,
        lesson: CourseLesson,
    ) -> tuple[CourseSentence, ...]:
        if unit.status == "deprecated" or lesson.status == "deprecated":
            return ()
        required_ids = {
            sentence_id
            for activity in lesson.activities
            if activity.required
            for sentence_id in activity.sentence_ids
        }
        return tuple(
            sentence
            for sentence in unit.sentences
            if sentence.sentence_id in required_ids and sentence.status != "deprecated"
        )

    @staticmethod
    def _ordered_lessons(
        course: Course,
    ) -> Iterator[tuple[CourseLevel, CourseUnit, CourseLesson]]:
        for level in course.levels:
            for unit in level.units:
                for lesson in unit.lessons:
                    yield level, unit, lesson

    def _require_course(self, course_id: str) -> Course:
        course = self.courses.get_course(course_id)
        if course is None:
            raise CourseContentNotFoundError(f"Course not found: {course_id!r}")
        return course

    @staticmethod
    def _require_unit(course: Course, unit_id: str) -> CourseUnit:
        for level in course.levels:
            for unit in level.units:
                if unit.unit_id == unit_id:
                    return unit
        raise CourseContentNotFoundError(
            f"Unit not found in course {course.course_id!r}: {unit_id!r}"
        )

    @staticmethod
    def _require_lesson(course: Course, lesson_id: str) -> tuple[CourseUnit, CourseLesson]:
        for level in course.levels:
            for unit in level.units:
                for lesson in unit.lessons:
                    if lesson.lesson_id == lesson_id:
                        return unit, lesson
        raise CourseContentNotFoundError(
            f"Lesson not found in course {course.course_id!r}: {lesson_id!r}"
        )

    @staticmethod
    def _require_item(
        course: Course,
        item_stable_key: str,
    ) -> tuple[CourseUnit, CourseLesson, CourseSentence]:
        for level in course.levels:
            for unit in level.units:
                lessons = {lesson.lesson_id: lesson for lesson in unit.lessons}
                for item in unit.sentences:
                    if item.stable_key == item_stable_key:
                        lesson = lessons.get(item.lesson_id)
                        if lesson is None:
                            break
                        return unit, lesson, item
        raise CourseContentNotFoundError(
            f"Learning item not found in course {course.course_id!r}: {item_stable_key!r}"
        )

    @staticmethod
    def _item_state(
        course: Course,
        unit: CourseUnit,
        lesson: CourseLesson,
        item: CourseSentence,
        *,
        status: ItemProgressStatus,
        attempt_count: int,
        best_score: float | None,
        latest_score: float | None,
        first_started_at: datetime | None,
        completed_at: datetime | None,
        now: datetime | None,
        existing: CourseItemProgress | None,
    ) -> CourseItemProgress:
        return CourseItemProgress(
            course_stable_key=course.stable_key,
            unit_stable_key=unit.stable_key,
            lesson_stable_key=lesson.stable_key,
            item_stable_key=item.stable_key,
            item_type="sentence",
            status=status,
            attempt_count=attempt_count,
            best_score=best_score,
            latest_score=latest_score,
            first_started_at=first_started_at,
            completed_at=completed_at,
            last_studied_at=now,
            content_version=item.content_version,
            created_at=existing.created_at if existing else now,
            updated_at=now,
        )

    def _now(self) -> datetime:
        return self._now_provider()


__all__ = [
    "CourseContentNotFoundError",
    "CourseEnrollmentNotFoundError",
    "CourseProgressError",
    "CourseProgressService",
    "InvalidEnrollmentStatusError",
]
