from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class TypingErrorEventRecord:
    session_id: int | None
    article_id: int | None
    section_id: int | None
    character_index: int
    expected_character: str
    actual_character: str
    target_word: str
    error_type: str
    occurred_at: datetime


@dataclass(slots=True)
class PracticeMaterial:
    article_id: int | None
    article_title: str
    section_id: int | None
    section_index: int
    section_count: int
    section_text: str
    resume_character_index: int = 0
    completed_section_count: int = 0
    practice_type: str = "article"
    practice_set_id: int | None = None
    source_items: list[str] | None = None


@dataclass(slots=True)
class PracticeSessionRecord:
    article_id: int | None
    section_id: int | None
    started_at: datetime | None
    finished_at: datetime | None
    active_seconds: float
    paused_seconds: float
    total_keystrokes: int
    correct_keystrokes: int
    error_keystrokes: int
    correct_characters: int
    wpm: float
    cpm: float
    accuracy: float
    completion_rate: float
    completed: bool
    practice_type: str = "article_section"
    longest_correct_streak: int = 0
    average_wpm: float | None = None
    app_version: str = "0.1.0"
    practice_set_id: int | None = None
