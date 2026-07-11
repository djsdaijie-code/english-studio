from __future__ import annotations

import os

from english_typing_trainer import __version__
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import ArticleRepository, PracticeRepository
from english_typing_trainer.models.practice import (
    PracticeMaterial,
    PracticeSessionRecord,
    TypingErrorEventRecord,
)
from english_typing_trainer.statistics.metrics import is_effective_result
from english_typing_trainer.typing_engine.session import SessionSnapshot, TypingSession


class PracticeService:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database
        self._articles = ArticleRepository(database.connect)
        self._practice = PracticeRepository(database.connect)

    def load_practice_material(self, article_id: int, mode: str = "resume") -> PracticeMaterial:
        article = self._articles.get_article(article_id, include_deleted=False)
        if article is None:
            raise ValueError("未找到文章。")

        section_index = article.current_section_index if mode == "resume" else 0
        character_index = article.current_character_index if mode == "resume" else 0
        completed_section_count = article.completed_section_count if mode == "resume" else 0

        section = self._articles.get_active_section_by_index(article_id, section_index)
        if section is None:
            section = self._articles.get_active_section_by_index(article_id, 0)
            if section is None:
                raise ValueError("当前文章没有可练习的有效段落。")
            section_index = 0
            character_index = 0
            completed_section_count = 0

        resume_character_index = min(character_index, len(section.text))
        return PracticeMaterial(
            article_id=article.id,
            article_title=article.title,
            section_id=section.id,
            section_index=section.section_index,
            section_count=article.section_count,
            section_text=section.text,
            resume_character_index=resume_character_index,
            completed_section_count=completed_section_count,
        )

    def save_interrupted_session(
        self,
        material: PracticeMaterial,
        session: TypingSession,
        snapshot: SessionSnapshot,
    ) -> None:
        if session.is_persisted or not self._should_persist_attempt(material, snapshot):
            return

        record = self._build_record(material, session, snapshot, completed=False)
        errors = self._build_errors(material, session)
        with self._database.transaction() as connection:
            session_id = self._practice.save_session(connection, record, errors)
            if material.article_id is not None and material.practice_type in {"article", "article_section"}:
                self._articles.update_progress(
                    connection,
                    article_id=material.article_id,
                    current_section_index=material.section_index,
                    current_character_index=snapshot.position,
                    completed_section_count=material.completed_section_count,
                )
                self._articles.update_last_practiced(connection, material.article_id)
        session.mark_persisted(session_id)

    def save_completed_session(
        self,
        material: PracticeMaterial,
        session: TypingSession,
        snapshot: SessionSnapshot,
    ) -> PracticeMaterial | None:
        if session.is_persisted:
            return None
        record = self._build_record(material, session, snapshot, completed=True)
        errors = self._build_errors(material, session)
        next_material: PracticeMaterial | None = None

        with self._database.transaction() as connection:
            session_id = self._practice.save_session(connection, record, errors)
            if material.article_id is not None and material.practice_type in {"article", "article_section"}:
                next_index = material.section_index + 1
                if next_index < material.section_count:
                    self._articles.update_progress(
                        connection,
                        article_id=material.article_id,
                        current_section_index=next_index,
                        current_character_index=0,
                        completed_section_count=material.section_index + 1,
                    )
                    self._articles.update_last_practiced(connection, material.article_id)
                else:
                    self._articles.update_progress(
                        connection,
                        article_id=material.article_id,
                        current_section_index=material.section_index,
                        current_character_index=len(material.section_text),
                        completed_section_count=material.section_count,
                    )
                    self._articles.update_last_practiced(connection, material.article_id)
        session.mark_persisted(session_id)

        if material.article_id is not None and material.section_index + 1 < material.section_count:
            next_material = self.load_practice_material(material.article_id, mode="resume")
        return next_material

    def _should_persist_attempt(self, material: PracticeMaterial, snapshot: SessionSnapshot) -> bool:
        return (
            snapshot.total_keystrokes > 0
            or snapshot.position != material.resume_character_index
        )

    def _build_record(
        self,
        material: PracticeMaterial,
        session: TypingSession,
        snapshot: SessionSnapshot,
        *,
        completed: bool,
    ) -> PracticeSessionRecord:
        completion_rate = 0.0
        if material.section_text:
            completion_rate = snapshot.position / len(material.section_text)
        effective_result = is_effective_result(
            completed=completed,
            correct_characters=snapshot.correct_characters,
            active_seconds=snapshot.elapsed_active_seconds,
        )
        return PracticeSessionRecord(
            article_id=material.article_id,
            section_id=material.section_id,
            started_at=session.started_at,
            finished_at=session.completed_at,
            active_seconds=snapshot.elapsed_active_seconds,
            paused_seconds=snapshot.paused_seconds,
            total_keystrokes=snapshot.total_keystrokes,
            correct_keystrokes=snapshot.correct_keystrokes,
            error_keystrokes=snapshot.error_keystrokes,
            correct_characters=snapshot.correct_characters,
            wpm=snapshot.wpm,
            cpm=snapshot.cpm,
            accuracy=snapshot.accuracy,
            completion_rate=1.0 if completed else completion_rate,
            completed=completed,
            practice_type=material.practice_type,
            longest_correct_streak=snapshot.best_streak,
            average_wpm=snapshot.wpm if effective_result else None,
            app_version=self._resolved_app_version(),
            practice_set_id=material.practice_set_id,
        )

    def _resolved_app_version(self) -> str:
        tag = os.environ.get("ENGLISH_TYPING_TRAINER_APP_TAG", "").strip()
        if tag:
            return f"{__version__}+{tag}"
        return __version__

    def _build_errors(
        self,
        material: PracticeMaterial,
        session: TypingSession,
    ) -> list[TypingErrorEventRecord]:
        return [
            TypingErrorEventRecord(
                session_id=session.persisted_session_id,
                article_id=material.article_id,
                section_id=material.section_id,
                character_index=error.position,
                expected_character=error.target_char,
                actual_character=error.actual_char,
                target_word=error.word,
                error_type=error.error_type,
                occurred_at=error.timestamp,
            )
            for error in session.errors
        ]
