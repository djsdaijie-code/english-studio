from __future__ import annotations

from dataclasses import replace

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import ArticleRepository
from english_typing_trainer.database.sentence_repositories import SentenceRepository
from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.services.sentence_segmentation import SentenceSegmentationService


class SentenceService:
    def __init__(self, database: DatabaseManager, segmentation: SentenceSegmentationService | None = None) -> None:
        self._database = database
        self._articles = ArticleRepository(database.connect)
        self._repository = SentenceRepository(database.connect)
        self._segmentation = segmentation or SentenceSegmentationService()

    def ensure_for_section(self, section_id: int) -> list[ArticleSentence]:
        existing = self._repository.list_for_section(section_id)
        if existing:
            return [self._without_boundary_whitespace(item) for item in existing]
        section = self._articles.get_section(section_id)
        if section is None or section.id is None or section.article_id is None:
            raise ValueError("未找到文章段落。")
        segments = self._segmentation.split(section.text)
        sentences = [
            ArticleSentence(
                id=None,
                article_id=section.article_id,
                section_id=section.id,
                sentence_index=item.sentence_index,
                text=item.text,
                normalized_text=item.normalized_text,
                sentence_hash=item.sentence_hash,
                start_offset=section.start_offset + item.start_offset,
                end_offset=section.start_offset + item.end_offset,
            )
            for item in segments
        ]
        with self._database.transaction() as connection:
            if not self._repository.list_for_section(section_id):
                self._repository.insert_many(connection, sentences)
        return [self._without_boundary_whitespace(item) for item in self._repository.list_for_section(section_id)]

    @staticmethod
    def _without_boundary_whitespace(sentence: ArticleSentence) -> ArticleSentence:
        left = len(sentence.text) - len(sentence.text.lstrip())
        right = len(sentence.text.rstrip())
        if left == 0 and right == len(sentence.text):
            return sentence
        return replace(
            sentence,
            text=sentence.text[left:right],
            start_offset=sentence.start_offset + left,
            end_offset=sentence.start_offset + right,
        )
