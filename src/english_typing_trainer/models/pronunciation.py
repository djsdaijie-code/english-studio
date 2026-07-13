from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class PronunciationRequest:
    reference_text: str
    locale: str
    audio_path: Path
    granularity: str = "Phoneme"
    enable_miscue: bool = True
    enable_prosody: bool = True


@dataclass(slots=True)
class WordFeedback:
    word: str
    accuracy_score: float | None = None
    error_type: str = "None"
    phonemes: list[dict[str, object]] = field(default_factory=list)


@dataclass(slots=True)
class PronunciationResult:
    status: str
    provider: str
    overall_score: float | None = None
    accuracy_score: float | None = None
    fluency_score: float | None = None
    completeness_score: float | None = None
    prosody_score: float | None = None
    words: list[WordFeedback] = field(default_factory=list)
    request_id: str = ""
    error_code: str = ""
    message: str = ""


@dataclass(slots=True)
class PronunciationAttempt:
    target_type: str
    reference_text_hash: str
    provider: str
    locale: str
    status: str
    vocabulary_entry_id: int | None = None
    vocabulary_context_id: int | None = None
    overall_score: float | None = None
    accuracy_score: float | None = None
    fluency_score: float | None = None
    completeness_score: float | None = None
    prosody_score: float | None = None
    word_feedback_json: str = "[]"
    error_code: str = ""
    recorded_at: datetime | None = None
    audio_path: str | None = None
    id: int | None = None
