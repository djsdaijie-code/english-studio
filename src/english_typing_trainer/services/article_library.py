from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import ArticleRepository
from english_typing_trainer.models.article import Article
from english_typing_trainer.services.sectioning import SectioningService
from english_typing_trainer.services.text_importer import normalize_text, read_text_file


@dataclass(slots=True)
class ArticleImportResult:
    status: str
    article: Article | None
    message: str


class ArticleLibraryService:
    def __init__(self, database: DatabaseManager, sectioning: SectioningService, word_index=None) -> None:
        self._database = database
        self._repository = ArticleRepository(database.connect)
        self._sectioning = sectioning
        self._word_index = word_index

    def list_articles(self, search: str = "") -> list[Article]:
        return self._repository.list_articles(search=search)

    def import_txt_file(self, file_path: str | Path, target_characters: int) -> ArticleImportResult:
        imported = read_text_file(file_path)
        if not imported.content.strip():
            return ArticleImportResult("error", None, "所选 TXT 在规范化后为空，无法导入。")

        content_hash = sha256(imported.content.encode("utf-8")).hexdigest()
        existing = self._repository.get_article_by_hash(content_hash)
        if existing and not existing.is_deleted:
            return ArticleImportResult("duplicate", existing, "这篇文章已经导入过了。")

        if existing and existing.is_deleted:
            with self._database.transaction() as connection:
                self._repository.restore_article(connection, existing.id)
            restored = self._repository.get_article(existing.id, include_deleted=False)
            return ArticleImportResult("restored", restored, "这篇文章已从已删除列表中恢复。")

        sections = self._sectioning.split_into_sections(imported.content, target_characters)
        article = Article(
            title=imported.title,
            original_filename=imported.original_filename,
            source_path=imported.source_path,
            content_hash=content_hash,
            full_text=imported.content,
            character_count=len(imported.content),
            word_count=len([part for part in imported.content.split() if part]),
            section_count=len(sections),
        )

        with self._database.transaction() as connection:
            created = self._repository.insert_article(connection, article, sections)
        if self._word_index and created.id is not None:
            self._word_index.rebuild(created.id)

        return ArticleImportResult("imported", created, "文章导入成功。")

    def rename_article(self, article_id: int, new_title: str) -> None:
        with self._database.transaction() as connection:
            self._repository.rename_article(connection, article_id, new_title.strip())

    def soft_delete_article(self, article_id: int) -> None:
        with self._database.transaction() as connection:
            self._repository.soft_delete_article(connection, article_id)

    def resegment_article(self, article_id: int, target_characters: int) -> Article:
        article = self._repository.get_article(article_id, include_deleted=True)
        if article is None:
            raise ValueError("未找到文章。")

        sections = self._sectioning.split_into_sections(article.full_text, target_characters)
        with self._database.transaction() as connection:
            self._repository.deactivate_active_sections(connection, article_id)
            self._repository.insert_sections(connection, article_id, sections)
            self._repository.reset_progress(connection, article_id)
        updated = self._repository.get_article(article_id, include_deleted=True)
        if updated is None:
            raise ValueError("重新分段后无法重新载入文章。")
        return updated

    def replace_article_content(
        self,
        article_id: int,
        corrected_text: str,
        target_characters: int,
    ) -> Article:
        article = self._repository.get_article(article_id, include_deleted=True)
        if article is None:
            raise ValueError("未找到文章。")
        content = normalize_text(corrected_text)
        if not content:
            raise ValueError("建议文本为空，已保留原文。")
        content_hash = sha256(content.encode("utf-8")).hexdigest()
        duplicate = self._repository.get_article_by_hash(content_hash)
        if duplicate is not None and duplicate.id != article_id:
            raise ValueError(f"建议版本与已存在文章《{duplicate.title}》内容相同，无法重复保存。")
        if content == article.full_text:
            return article

        sections = self._sectioning.split_into_sections(content, target_characters)
        occurrences = self._word_index.extract(content) if self._word_index else []
        with self._database.transaction() as connection:
            self._repository.update_article_content(
                connection,
                article_id,
                content_hash=content_hash,
                full_text=content,
                character_count=len(content),
                word_count=len([part for part in content.split() if part]),
            )
            self._repository.deactivate_active_sections(connection, article_id)
            self._repository.insert_sections(connection, article_id, sections)
            self._repository.reset_progress(connection, article_id)
            if self._word_index:
                self._word_index.replace_in_transaction(connection, article_id, occurrences)
        updated = self._repository.get_article(article_id, include_deleted=True)
        if updated is None:
            raise ValueError("应用建议后无法重新载入文章。")
        return updated

    def get_article(self, article_id: int, include_deleted: bool = False) -> Article | None:
        return self._repository.get_article(article_id, include_deleted=include_deleted)

    def get_sections(self, article_id: int):
        return self._repository.get_active_sections(article_id)
