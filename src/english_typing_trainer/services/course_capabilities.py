from __future__ import annotations

from datetime import datetime, timezone

from fsrs import Card, Scheduler

from english_typing_trainer.courses.models import Course, CourseLesson, CourseSentence, CourseUnit
from english_typing_trainer.courses.repository import CourseRepository
from english_typing_trainer.database.course_capability_repository import (
    CourseCapabilityRepository,
)
from english_typing_trainer.models.learning_content import (
    CourseCapabilityItem,
    CourseCapabilityStatus,
    CourseReviewCard,
    CourseReviewCardType,
    CourseReviewLog,
    CourseReviewQueueItem,
    LearningContentRef,
)
from english_typing_trainer.models.vocabulary import VocabularyContext
from english_typing_trainer.services.article_word_index import (
    ArticleWordIndexService,
    ArticleWordOccurrence,
)
from english_typing_trainer.services.course_progress import CourseProgressService
from english_typing_trainer.services.fsrs_review import RATINGS, FsrsReviewService
from english_typing_trainer.services.vocabulary_learning import (
    CollectionResult,
    VocabularyLearningService,
)


class CourseCapabilityError(RuntimeError):
    pass


class CourseCapabilityContentError(CourseCapabilityError, LookupError):
    pass


class CourseContentChangedError(CourseCapabilityError):
    pass


class CourseCapabilityService:
    """Adapts immutable course items to existing learning capabilities."""

    def __init__(
        self,
        courses: CourseRepository,
        progress: CourseProgressService,
        repository: CourseCapabilityRepository,
        vocabulary: VocabularyLearningService,
        word_index: ArticleWordIndexService,
        fsrs: FsrsReviewService,
        *,
        now_provider=None,
    ) -> None:
        self.courses = courses
        self.progress = progress
        self.repository = repository
        self.vocabulary = vocabulary
        self.word_index = word_index
        self.fsrs = fsrs
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def content_ref(
        self, course_id: str, item_stable_key: str
    ) -> LearningContentRef:
        course, unit, lesson, sentence = self._require_item(course_id, item_stable_key)
        return LearningContentRef(
            source_type="built_in_course",
            content_stable_key=sentence.stable_key,
            course_stable_key=course.stable_key,
            unit_stable_key=unit.stable_key,
            lesson_stable_key=lesson.stable_key,
            item_stable_key=sentence.stable_key,
            content_version=sentence.content_version,
        )

    def content_ref_by_stable_key(
        self, course_stable_key: str, item_stable_key: str
    ) -> LearningContentRef:
        return self.content_ref(
            self._course_id(course_stable_key), item_stable_key
        )

    def item(self, course_id: str, item_stable_key: str) -> CourseCapabilityItem:
        course, unit, lesson, sentence = self._require_item(course_id, item_stable_key)
        activity_types = self._activity_types_for_sentence(lesson, sentence.sentence_id)
        return CourseCapabilityItem(
            ref=self.content_ref(course_id, sentence.stable_key),
            sentence_id=sentence.sentence_id,
            text=sentence.english,
            translation=sentence.chinese,
            activity_types=activity_types,
        )

    def lesson_items(
        self,
        course_id: str,
        lesson_id: str,
        activity_type: str | None = None,
    ) -> tuple[CourseCapabilityItem, ...]:
        course = self._require_course(course_id)
        unit, lesson = self._require_lesson(course, lesson_id)
        sentence_by_id = {item.sentence_id: item for item in unit.sentences}
        ordered_ids: list[str] = []
        for activity in lesson.activities:
            mapped = self._progress_activity_type(activity.activity_type)
            if activity_type is not None and mapped != activity_type:
                continue
            for sentence_id in activity.sentence_ids:
                if sentence_id not in ordered_ids:
                    ordered_ids.append(sentence_id)
        if activity_type is None:
            for sentence_id in (*lesson.new_sentence_ids, *lesson.review_sentence_ids):
                if sentence_id not in ordered_ids:
                    ordered_ids.append(sentence_id)
        return tuple(
            self.item(course_id, sentence.stable_key)
            for sentence_id in ordered_ids
            if (sentence := sentence_by_id.get(sentence_id)) is not None
            and sentence.status != "deprecated"
        )

    def resolve_context(self, context: VocabularyContext) -> str:
        if context.source_type != "built_in_course" or not context.item_stable_key:
            return context.source_sentence
        sentence = self.courses.get_sentence_by_stable_key(context.item_stable_key)
        if sentence is None:
            return ""
        course = self._course_by_stable_key(context.course_stable_key)
        if course is None or not self._course_contains_item(course, sentence.stable_key):
            return ""
        return sentence.english

    def extract_words(
        self, content_ref: LearningContentRef
    ) -> tuple[ArticleWordOccurrence, ...]:
        item = self.resolve_item(content_ref)
        return tuple(self.word_index.extract(item.text))

    def lesson_words(
        self, course_id: str, lesson_id: str
    ) -> tuple[tuple[CourseCapabilityItem, ArticleWordOccurrence], ...]:
        result: list[tuple[CourseCapabilityItem, ArticleWordOccurrence]] = []
        for item in self.lesson_items(course_id, lesson_id):
            result.extend((item, occurrence) for occurrence in self.word_index.extract(item.text))
        return tuple(result)

    def collect_word(
        self,
        content_ref: LearningContentRef,
        raw_word: str,
        *,
        start_offset: int,
        end_offset: int,
        typing_target_count: int = 5,
    ) -> CollectionResult:
        item = self.resolve_item(content_ref)
        result = self.vocabulary.collect(
            raw_word,
            sentence=item.text,
            start_offset=start_offset,
            end_offset=end_offset,
            typing_target_count=typing_target_count,
            content_ref=content_ref,
        )
        self.progress.complete_activity(
            self._course_id(content_ref.course_stable_key),
            content_ref.item_stable_key,
            "vocabulary",
        )
        return result

    def start_listening(self, content_ref: LearningContentRef) -> None:
        self.resolve_item(content_ref)
        self.progress.start_activity(
            self._course_id(content_ref.course_stable_key),
            content_ref.item_stable_key,
            "review",
        )

    def complete_listening(self, content_ref: LearningContentRef) -> None:
        self.resolve_item(content_ref)
        self.progress.complete_activity(
            self._course_id(content_ref.course_stable_key),
            content_ref.item_stable_key,
            "review",
        )

    def fail_listening(self, content_ref: LearningContentRef) -> None:
        self.resolve_item(content_ref)
        self.progress.fail_activity(
            self._course_id(content_ref.course_stable_key),
            content_ref.item_stable_key,
            "review",
        )

    def ensure_vocabulary_review(
        self,
        content_ref: LearningContentRef,
        entry_id: int,
        context_id: int | None,
    ):
        self.resolve_item(content_ref)
        cards = self.fsrs.ensure_entry_cards(entry_id, context_id)
        self.progress.start_activity(
            self._course_id(content_ref.course_stable_key),
            content_ref.item_stable_key,
            "review",
        )
        return cards

    def ensure_sentence_review(
        self,
        content_ref: LearningContentRef,
        card_type: CourseReviewCardType = "sentence_review",
    ) -> CourseReviewCard:
        item = self.resolve_item(content_ref)
        if self._sentence_status(content_ref.item_stable_key) == "deprecated":
            raise CourseCapabilityContentError("Deprecated course items cannot create new review cards.")
        course_id = self._course_id(content_ref.course_stable_key)
        self.progress.start_activity(course_id, content_ref.item_stable_key, "review")
        existing = self.repository.get_review_card(
            content_ref.course_stable_key, content_ref.item_stable_key, card_type
        )
        if existing is not None:
            if existing.content_version != item.ref.content_version:
                existing.content_version = item.ref.content_version
                existing = self.repository.update_review_card(existing, self._now())
            return existing
        now = self._now()
        fsrs_card = Card()
        fsrs_card.due = now
        return self.repository.create_review_card(
            CourseReviewCard(
                course_stable_key=content_ref.course_stable_key,
                item_stable_key=content_ref.item_stable_key,
                card_type=card_type,
                fsrs_card_json=fsrs_card.to_json(),
                due_at_utc=fsrs_card.due,
                state=fsrs_card.state.name.lower(),
                content_version=item.ref.content_version,
            ),
            now,
        )

    def rate_sentence_review(
        self, card_id: int, rating: str
    ) -> CourseReviewCard:
        if rating not in RATINGS:
            raise ValueError("Unknown FSRS rating.")
        stored = self.repository.get_review_card_by_id(card_id)
        if stored is None:
            raise CourseCapabilityContentError("Course review card does not exist.")
        content_ref = self.content_ref(
            self._course_id(stored.course_stable_key), stored.item_stable_key
        )
        item = self.resolve_item(content_ref)
        if self._sentence_status(stored.item_stable_key) == "deprecated":
            raise CourseCapabilityContentError("Deprecated course review cards are paused.")
        now = self._now()
        scheduler = Scheduler.from_json(self.fsrs.profile().scheduler_json)
        previous_json = stored.fsrs_card_json
        card = Card.from_json(previous_json)
        updated, review_log = scheduler.review_card(
            card, RATINGS[rating], review_datetime=now
        )
        stored.fsrs_card_json = updated.to_json()
        stored.due_at_utc = updated.due.astimezone(timezone.utc)
        stored.last_reviewed_at_utc = now
        stored.state = updated.state.name.lower()
        stored.content_version = item.ref.content_version
        saved, _log = self.repository.save_review(
            stored,
            CourseReviewLog(
                course_review_card_id=stored.id or 0,
                rating=rating,
                review_log_json=review_log.to_json(),
                previous_card_json=previous_json,
                reviewed_at_utc=now,
            ),
            now,
        )
        self.progress.complete_activity(
            self._course_id(stored.course_stable_key),
            stored.item_stable_key,
            "review",
        )
        return saved

    def rate_existing_sentence_review(
        self,
        content_ref: LearningContentRef,
        rating: str,
        card_type: CourseReviewCardType = "sentence_listening",
    ) -> CourseReviewCard | None:
        """Rate an explicitly created course card without enrolling by side effect."""
        self.resolve_item(content_ref)
        card = self.repository.get_review_card(
            content_ref.course_stable_key,
            content_ref.item_stable_key,
            card_type,
        )
        if card is None or card.id is None:
            return None
        return self.rate_sentence_review(card.id, rating)

    def due_sentence_reviews(
        self, limit: int = 100
    ) -> tuple[CourseReviewQueueItem, ...]:
        result: list[CourseReviewQueueItem] = []
        for card in self.repository.list_due_review_cards(self._now(), limit):
            course = self._course_by_stable_key(card.course_stable_key)
            sentence = self.courses.get_sentence_by_stable_key(card.item_stable_key)
            if course is None or sentence is None or sentence.status == "deprecated":
                continue
            enrollment = self.progress.get_enrollment(course.course_id)
            if enrollment is not None and enrollment.status in {"paused", "archived"}:
                continue
            try:
                item = self.item(course.course_id, card.item_stable_key)
                _course, _unit, lesson, resolved_sentence = self._require_item(
                    course.course_id, card.item_stable_key
                )
            except CourseCapabilityError:
                continue
            result.append(
                CourseReviewQueueItem(
                    card=card,
                    item=item,
                    course_title=course.title,
                    lesson_title=lesson.title,
                    lesson_day=lesson.day,
                    sentence_order=resolved_sentence.order,
                )
            )
        return tuple(result)

    def resolve_item(self, content_ref: LearningContentRef) -> CourseCapabilityItem:
        item = self.item(
            self._course_id(content_ref.course_stable_key),
            content_ref.item_stable_key,
        )
        if item.ref.content_version != content_ref.content_version:
            raise CourseContentChangedError(
                f"Course item {content_ref.item_stable_key!r} changed from "
                f"{content_ref.content_version!r} to {item.ref.content_version!r}."
            )
        return item

    def _require_course(self, course_id: str) -> Course:
        course = self.courses.get_course(course_id)
        if course is None:
            raise CourseCapabilityContentError(f"Course not found: {course_id!r}")
        return course

    @staticmethod
    def _require_lesson(course: Course, lesson_id: str) -> tuple[CourseUnit, CourseLesson]:
        for level in course.levels:
            for unit in level.units:
                for lesson in unit.lessons:
                    if lesson.lesson_id == lesson_id:
                        return unit, lesson
        raise CourseCapabilityContentError(
            f"Lesson not found in course {course.course_id!r}: {lesson_id!r}"
        )

    def _require_item(
        self, course_id: str, item_stable_key: str
    ) -> tuple[Course, CourseUnit, CourseLesson, CourseSentence]:
        course = self._require_course(course_id)
        for level in course.levels:
            for unit in level.units:
                lessons = {lesson.lesson_id: lesson for lesson in unit.lessons}
                for sentence in unit.sentences:
                    if sentence.stable_key != item_stable_key:
                        continue
                    lesson = lessons.get(sentence.lesson_id)
                    if lesson is not None:
                        return course, unit, lesson, sentence
        raise CourseCapabilityContentError(
            f"Course item not found in {course_id!r}: {item_stable_key!r}"
        )

    def _course_by_stable_key(self, stable_key: str) -> Course | None:
        return next(
            (course for course in self.courses.list_courses() if course.stable_key == stable_key),
            None,
        )

    def _course_id(self, course_stable_key: str) -> str:
        course = self._course_by_stable_key(course_stable_key)
        if course is None:
            raise CourseCapabilityContentError(
                f"Course stable key not found: {course_stable_key!r}"
            )
        return course.course_id

    @staticmethod
    def _course_contains_item(course: Course, item_stable_key: str) -> bool:
        return any(
            sentence.stable_key == item_stable_key
            for level in course.levels
            for unit in level.units
            for sentence in unit.sentences
        )

    def _sentence_status(self, item_stable_key: str) -> str:
        sentence = self.courses.get_sentence_by_stable_key(item_stable_key)
        return sentence.status if sentence is not None else "missing"

    @staticmethod
    def _activity_types_for_sentence(
        lesson: CourseLesson, sentence_id: str
    ) -> tuple[str, ...]:
        values: list[str] = []
        for activity in lesson.activities:
            if sentence_id not in activity.sentence_ids:
                continue
            mapped = CourseCapabilityService._progress_activity_type(
                activity.activity_type
            )
            if mapped not in values:
                values.append(mapped)
        return tuple(values)  # type: ignore[return-value]

    @staticmethod
    def _progress_activity_type(activity_type: str) -> str:
        return {
            "fsrs": "review",
            "reading": "typing",
            "translation": "typing",
            "self_test": "typing",
        }.get(activity_type, activity_type)

    @staticmethod
    def _capability_status(status: str) -> CourseCapabilityStatus:
        if status == "completed":
            return "completed"
        if status == "not_configured":
            return "not_configured"
        if status == "cancelled":
            return "cancelled"
        return "failed"

    def _now(self) -> datetime:
        value = self._now_provider()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


__all__ = [
    "CourseCapabilityContentError",
    "CourseCapabilityError",
    "CourseCapabilityService",
    "CourseContentChangedError",
]
