from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ArticleSection:
    section_index: int
    text: str
    start_offset: int
    end_offset: int
    article_id: int | None = None
    id: int | None = None
    character_count: int = 0
    word_count: int = 0
    is_active: bool = True

    def __post_init__(self) -> None:
        if not self.character_count:
            self.character_count = len(self.text)
        if not self.word_count:
            self.word_count = len([part for part in self.text.split() if part])
