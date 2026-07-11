from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from english_typing_trainer.models.vocabulary import VocabularyItem

REVIEW_INTERVAL_DAYS = {
    0: 0,
    1: 1,
    2: 3,
    3: 7,
    4: 14,
    5: 30,
}


@dataclass(slots=True)
class ReviewOutcome:
    status: str
    mastery_level: int
    next_review_at: date
    review_count_delta: int
    correct_review_delta: int
    wrong_review_delta: int
    last_reviewed_at: date


class ReviewPlanningService:
    def next_review_date_for_level(self, mastery_level: int, *, today: date | None = None) -> date:
        today = today or date.today()
        level = max(0, min(5, mastery_level))
        return today + timedelta(days=REVIEW_INTERVAL_DAYS[level])

    def mark_correct(self, item: VocabularyItem, *, today: date | None = None) -> ReviewOutcome:
        today = today or date.today()
        next_level = min(5, item.mastery_level + 1)
        status = "mastered" if next_level >= 5 else "reviewing"
        return ReviewOutcome(
            status=status,
            mastery_level=next_level,
            next_review_at=self.next_review_date_for_level(next_level, today=today),
            review_count_delta=1,
            correct_review_delta=1,
            wrong_review_delta=0,
            last_reviewed_at=today,
        )

    def mark_wrong(self, item: VocabularyItem, *, today: date | None = None) -> ReviewOutcome:
        today = today or date.today()
        next_level = max(0, item.mastery_level - 1)
        status = "reviewing" if next_level > 0 else "learning"
        next_review_at = today if item.status != "mastered" else today + timedelta(days=1)
        return ReviewOutcome(
            status=status,
            mastery_level=next_level,
            next_review_at=next_review_at,
            review_count_delta=1,
            correct_review_delta=0,
            wrong_review_delta=1,
            last_reviewed_at=today,
        )
