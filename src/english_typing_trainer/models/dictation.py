from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DictationComparison:
    expected: str
    actual: str
    normalized_expected: str
    normalized_actual: str
    correct: bool
    error_count: int
    omitted_count: int
    inserted_count: int
    operations: list[tuple[str, str]]


@dataclass(slots=True)
class DictationAttempt:
    dictation_type: str
    comparison_mode: str
    expected_text: str
    user_input: str
    normalized_comparison: str
    error_count: int
    omitted_count: int
    inserted_count: int
    replay_count: int = 0
    speed: float = 1.0
    duration_ms: int = 0
    rating: str | None = None
    vocabulary_entry_id: int | None = None
    vocabulary_context_id: int | None = None
    reviewed_at_utc: datetime | None = None
    id: int | None = None
