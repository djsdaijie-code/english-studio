from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SentenceSegment:
    sentence_index: int
    text: str
    normalized_text: str
    sentence_hash: str
    start_offset: int
    end_offset: int


@dataclass(slots=True)
class ArticleSentence:
    id: int | None
    article_id: int
    section_id: int
    sentence_index: int
    text: str
    normalized_text: str
    sentence_hash: str
    start_offset: int
    end_offset: int
    created_at: datetime | None = None


@dataclass(slots=True)
class SentenceTranslation:
    id: int | None
    sentence_hash: str
    source_text: str
    chinese_translation: str
    key_expressions: list[dict[str, str]]
    provider: str
    model: str
    prompt_version: str
    status: str
    error_message: str = ""
    is_user_edited: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None