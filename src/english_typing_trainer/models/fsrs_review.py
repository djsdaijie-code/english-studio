from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from english_typing_trainer.models.vocabulary import VocabularyContext, VocabularyEntry


@dataclass(slots=True)
class FsrsProfile:
    scheduler_json: str
    desired_retention: float = 0.90
    parameters_version: str = "fsrs-6"
    optimized_at: datetime | None = None


@dataclass(slots=True)
class VocabularyReviewCard:
    vocabulary_entry_id: int
    card_type: str
    fsrs_card_json: str
    due_at_utc: datetime
    vocabulary_context_id: int | None = None
    last_reviewed_at_utc: datetime | None = None
    state: str = "learning"
    is_suspended: bool = False
    id: int | None = None


@dataclass(slots=True)
class VocabularyReviewLog:
    vocabulary_review_card_id: int
    rating: str
    review_log_json: str
    previous_card_json: str
    reviewed_at_utc: datetime
    id: int | None = None


@dataclass(slots=True)
class ReviewQueueItem:
    card: VocabularyReviewCard
    entry: VocabularyEntry
    context: VocabularyContext | None

    @property
    def target_word(self) -> str:
        if self.context and self.context.source_word:
            return self.context.source_word
        return self.entry.display_word or self.entry.normalized_word


@dataclass(slots=True)
class ReviewQueue:
    items: list[ReviewQueueItem]
    overdue_count: int
    due_count: int
    learning_count: int
    new_count: int
