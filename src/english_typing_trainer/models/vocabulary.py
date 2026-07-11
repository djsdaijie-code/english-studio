from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(slots=True)
class VocabularyItem:
    normalized_word: str
    display_word: str
    meaning: str = ""
    note: str = ""
    source_article_id: int | None = None
    source_section_id: int | None = None
    source_character_index: int | None = None
    source_sentence: str = ""
    status: str = "new"
    mastery_level: int = 0
    review_count: int = 0
    correct_review_count: int = 0
    wrong_review_count: int = 0
    next_review_at: date | None = None
    last_reviewed_at: date | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_archived: bool = False
    id: int | None = None


@dataclass(slots=True)
class PracticeSet:
    title: str
    practice_mode: str
    source_type: str
    generated_text: str
    item_count: int
    configuration: dict[str, object]
    created_at: datetime | None = None
    last_practiced_at: datetime | None = None
    is_deleted: bool = False
    id: int | None = None


@dataclass(slots=True)
class PracticeSetItem:
    practice_set_id: int
    item_type: str
    item_value: str
    source_article_id: int | None = None
    source_section_id: int | None = None
    source_character_index: int | None = None
    source_sentence: str = ""
    error_count: int = 0
    sort_order: int = 0
    id: int | None = None
