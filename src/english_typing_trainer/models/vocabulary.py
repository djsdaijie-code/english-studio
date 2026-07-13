from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any


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


@dataclass(slots=True)
class VocabularyEntry:
    normalized_word: str
    display_word: str
    lemma: str = ""
    phonetic: str = ""
    primary_part_of_speech: str = ""
    dictionary_status: str = "pending"
    dictionary_payload: dict[str, Any] | list[Any] | None = None
    dictionary_fetched_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: int | None = None


@dataclass(slots=True)
class VocabularyContext:
    vocabulary_entry_id: int
    source_word: str
    source_sentence: str = ""
    article_id: int | None = None
    article_sentence_id: int | None = None
    start_offset: int = 0
    end_offset: int = 0
    contextual_part_of_speech: str = ""
    contextual_meaning_zh: str = ""
    explanation_zh: str = ""
    common_collocation: str = ""
    example_en: str = ""
    example_zh: str = ""
    ai_status: str = "pending"
    ai_prompt_version: str = "word-context-v1"
    ai_generated_at: datetime | None = None
    is_manual: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None
    id: int | None = None


@dataclass(slots=True)
class VocabularyLearningState:
    vocabulary_entry_id: int
    status: str = "new"
    typing_target_count: int = 5
    typing_completed_count: int = 0
    correct_attempts: int = 0
    incorrect_attempts: int = 0
    familiarity_level: int = 0
    last_practiced_at: datetime | None = None
    next_review_at: datetime | None = None
    mastered_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class VocabularyAttempt:
    vocabulary_entry_id: int
    practice_type: str
    expected_answer: str = ""
    user_input: str = ""
    is_correct: bool | None = None
    accuracy: float = 0.0
    duration_ms: int = 0
    self_rating: str | None = None
    vocabulary_context_id: int | None = None
    created_at: datetime | None = None
    id: int | None = None
