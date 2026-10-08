from __future__ import annotations

import json
import re
from dataclasses import dataclass

from english_typing_trainer.database.repositories import SettingsRepository
from english_typing_trainer.models.article import Article
from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.services.text_importer import normalize_text


def clean_reading_text(text: str) -> str:
    text = normalize_text(text.replace("\u00a0", " ").replace("\u200b", ""))
    paragraphs = re.split(r"\n\s*\n", text)
    return "\n\n".join(
        cleaned
        for paragraph in paragraphs
        if (cleaned := re.sub(r"\s+", " ", paragraph).strip())
    )


@dataclass(slots=True)
class ReadingMaterial:
    article: Article
    sentences: list[ArticleSentence]
    index: int = 0
    completed: bool = False


class ReadingService:
    """Keeps reading bookmarks separate from typing progress using existing settings."""

    def __init__(self, context) -> None:
        self.context = context
        self._settings = SettingsRepository(context.database.connect)

    @staticmethod
    def _key(article_id: int) -> str:
        return f"reading.article.{article_id}"

    def import_article(self, title: str, text: str, source_url: str = "") -> Article:
        title = title.strip()
        content = clean_reading_text(text)
        if not title or not content:
            raise ValueError("请填写标题并粘贴英文正文。")
        if not re.search(r"[A-Za-z]", content):
            raise ValueError("正文中没有检测到英文，请粘贴英文文章或帖子。")
        result = self.context.article_library.import_pasted_english(title, content, source_url.strip())
        if result.article is None:
            raise ValueError(result.message)
        article = result.article
        saved = self._bookmark(article.id)
        if not saved:
            self._save(article, 0, False, source_url=source_url.strip())
        return article

    def _bookmark(self, article_id: int) -> dict:
        raw = self._settings.get_all().get(self._key(article_id), "{}")
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}

    def list_articles(self) -> list[tuple[Article, dict]]:
        settings = self._settings.get_all()
        return [
            (article, self._bookmark(article.id))
            for article in self.context.article_library.list_articles()
            if self._key(article.id) in settings
        ]

    def load(self, article_id: int, *, restart: bool = False) -> ReadingMaterial:
        article = self.context.article_library.get_article(article_id)
        if article is None:
            raise ValueError("文章已删除或不存在，请重新选择。")
        sentences = [
            sentence
            for section in self.context.article_library.get_sections(article_id)
            for sentence in self.context.sentence_service.ensure_for_section(section.id)
        ]
        if not sentences:
            raise ValueError("文章没有可精读的句子。")
        saved = self._bookmark(article_id)
        same_content = saved.get("content_hash") == article.content_hash
        try:
            index = int(saved.get("index", 0)) if same_content and not restart else 0
        except (TypeError, ValueError):
            index = 0
        material = ReadingMaterial(
            article, sentences, max(0, min(index, len(sentences) - 1)),
            bool(saved.get("completed")) if same_content and not restart else False,
        )
        self.save_position(material)
        return material

    def save_position(self, material: ReadingMaterial) -> None:
        self._save(material.article, material.index, material.completed, total=len(material.sentences))

    def _save(self, article: Article, index: int, completed: bool, *, total: int = 0, source_url: str | None = None) -> None:
        saved = self._bookmark(article.id)
        saved.update(content_hash=article.content_hash, index=index, completed=completed, total=total)
        if source_url is not None:
            saved["source_url"] = source_url
        with self.context.database.transaction() as connection:
            self._settings.set_many(connection, {self._key(article.id): json.dumps(saved, ensure_ascii=False)})
