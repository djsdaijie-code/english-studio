from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from english_typing_trainer.models.course_progress import CourseActivityType


CourseCapabilityType = Literal["speaking"]
CourseCapabilityStatus = Literal[
    "completed", "failed", "cancelled", "not_configured"
]
CourseReviewCardType = Literal["sentence_listening", "sentence_review"]


@dataclass(frozen=True, slots=True)
class LearningContentRef:
    source_type: Literal["built_in_course"]
    content_stable_key: str
    course_stable_key: str
    unit_stable_key: str
    lesson_stable_key: str
    item_stable_key: str
    content_version: str


@dataclass(frozen=True, slots=True)
class CourseCapabilityItem:
    ref: LearningContentRef
    sentence_id: str
    text: str
    translation: str
    activity_types: tuple[CourseActivityType, ...]


@dataclass(frozen=True, slots=True)
class CourseCapabilityAttempt:
    course_stable_key: str
    item_stable_key: str
    capability_type: CourseCapabilityType
    status: CourseCapabilityStatus
    content_version: str
    attempted_at: datetime
    score: float | None = None
    accuracy_score: float | None = None
    fluency_score: float | None = None
    completeness_score: float | None = None
    prosody_score: float | None = None
    error_count: int = 0
    omitted_count: int = 0
    inserted_count: int = 0
    replay_count: int = 0
    duration_ms: int = 0
    provider: str = ""
    id: int | None = None


@dataclass(slots=True)
class CourseReviewCard:
    course_stable_key: str
    item_stable_key: str
    card_type: CourseReviewCardType
    fsrs_card_json: str
    due_at_utc: datetime
    content_version: str
    last_reviewed_at_utc: datetime | None = None
    state: str = "learning"
    is_suspended: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: int | None = None


@dataclass(frozen=True, slots=True)
class CourseReviewLog:
    course_review_card_id: int
    rating: str
    review_log_json: str
    previous_card_json: str
    reviewed_at_utc: datetime
    created_at: datetime | None = None
    id: int | None = None


@dataclass(frozen=True, slots=True)
class CourseReviewQueueItem:
    card: CourseReviewCard
    item: CourseCapabilityItem
    course_title: str
    lesson_title: str
    lesson_day: int
    sentence_order: int
