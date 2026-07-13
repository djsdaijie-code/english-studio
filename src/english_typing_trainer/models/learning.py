from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class LearningEvent:
    event_type: str
    active_seconds: float
    occurred_at: datetime
    related_article_id: int | None = None
    related_sentence_id: int | None = None
    related_vocabulary_id: int | None = None
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class LearningDashboard:
    date: str
    effective_seconds: float = 0.0
    checked_in: bool = False
    current_tier_minutes: int = 0
    next_tier_minutes: int | None = 15
    awarded_xp: int = 0
    total_xp: int = 0
    total_checkin_days: int = 0
    current_streak: int = 0
    longest_streak: int = 0
    current_rank: str = "启程 III"
    next_rank: str | None = "启程 II"
    rank_days_current: int = 0
    rank_days_required: int = 1
    week_completed: int = 0
    month_completed: int = 0
    week_track: list[bool] = field(default_factory=list)
    latest_achievement: str = "尚未解锁成就"


@dataclass(slots=True)
class LearningUpdate:
    milestones: list[int] = field(default_factory=list)
    reminders: list[int] = field(default_factory=list)
    achievements: list[str] = field(default_factory=list)
