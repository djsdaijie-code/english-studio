from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


EnrollmentStatus = Literal["active", "paused", "completed", "archived"]
ItemProgressStatus = Literal["not_started", "in_progress", "completed", "skipped"]
CourseActivityType = Literal["typing", "speaking", "vocabulary", "review"]
CourseActivityStatus = Literal[
    "not_started", "in_progress", "completed", "skipped", "failed"
]
ProgressScope = Literal["course", "unit", "lesson"]


@dataclass(frozen=True, slots=True)
class CourseEnrollment:
    course_stable_key: str
    status: EnrollmentStatus
    current_lesson_stable_key: str | None
    course_version: str
    content_version: str
    enrolled_at: datetime
    last_studied_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class CourseItemProgress:
    course_stable_key: str
    unit_stable_key: str
    lesson_stable_key: str
    item_stable_key: str
    item_type: str
    status: ItemProgressStatus
    attempt_count: int
    best_score: float | None
    latest_score: float | None
    first_started_at: datetime | None
    completed_at: datetime | None
    last_studied_at: datetime | None
    content_version: str
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class CourseActivityProgress:
    course_stable_key: str
    item_stable_key: str
    activity_type: CourseActivityType
    status: CourseActivityStatus
    attempt_count: int
    best_score: float | None
    latest_score: float | None
    content_version: str
    completed_at: datetime | None
    last_studied_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class CourseProgressSummary:
    scope: ProgressScope
    course_stable_key: str
    stable_key: str
    completed_required_items: int
    total_required_items: int
    completion_percentage: float
    is_completed: bool


@dataclass(frozen=True, slots=True)
class CourseVersionStatus:
    course_stable_key: str
    recorded_course_version: str
    recorded_content_version: str
    current_course_version: str
    current_content_version: str
    has_new_content: bool
    completed_recorded_version: bool
