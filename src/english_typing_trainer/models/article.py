from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Article:
    title: str
    full_text: str
    original_filename: str = ""
    source_path: str = ""
    id: int | None = None
    content_hash: str = ""
    character_count: int = 0
    word_count: int = 0
    section_count: int = 0
    imported_at: datetime | None = None
    last_practiced_at: datetime | None = None
    is_deleted: bool = False
    current_section_index: int = 0
    current_character_index: int = 0
    completed_section_count: int = 0

    def __post_init__(self) -> None:
        if not self.character_count:
            self.character_count = len(self.full_text)
        if not self.word_count:
            self.word_count = len([part for part in self.full_text.split() if part])
        if self.imported_at is None:
            self.imported_at = datetime.now()

    @property
    def content(self) -> str:
        return self.full_text

    @property
    def paragraph_count(self) -> int:
        return len([part for part in self.full_text.split("\n\n") if part.strip()])
