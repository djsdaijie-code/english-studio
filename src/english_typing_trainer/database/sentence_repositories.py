from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from english_typing_trainer.models.sentence import ArticleSentence, SentenceTranslation


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SentenceRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def list_for_section(self, section_id: int) -> list[ArticleSentence]:
        rows = self._connection_provider().execute(
            "SELECT * FROM article_sentences WHERE section_id = ? ORDER BY sentence_index",
            (section_id,),
        ).fetchall()
        return [self._row(row) for row in rows]

    def insert_many(self, connection: sqlite3.Connection, sentences: list[ArticleSentence]) -> None:
        connection.executemany(
            """
            INSERT INTO article_sentences(
                article_id, section_id, sentence_index, text, normalized_text,
                sentence_hash, start_offset, end_offset, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [(item.article_id, item.section_id, item.sentence_index, item.text, item.normalized_text, item.sentence_hash, item.start_offset, item.end_offset, _now()) for item in sentences],
        )

    def find_for_character(self, section_id: int, absolute_offset: int) -> ArticleSentence | None:
        row = self._connection_provider().execute(
            """
            SELECT * FROM article_sentences
            WHERE section_id = ? AND start_offset <= ? AND end_offset > ?
            ORDER BY sentence_index LIMIT 1
            """,
            (section_id, absolute_offset, absolute_offset),
        ).fetchone()
        return self._row(row) if row else None

    def _row(self, row) -> ArticleSentence:
        return ArticleSentence(
            id=row["id"], article_id=row["article_id"], section_id=row["section_id"],
            sentence_index=row["sentence_index"], text=row["text"], normalized_text=row["normalized_text"],
            sentence_hash=row["sentence_hash"], start_offset=row["start_offset"], end_offset=row["end_offset"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class TranslationCacheRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def get(self, sentence_hash: str) -> SentenceTranslation | None:
        row = self._connection_provider().execute(
            "SELECT * FROM sentence_translations WHERE sentence_hash = ?", (sentence_hash,)
        ).fetchone()
        return self._row(row) if row else None

    def claim_pending(self, connection: sqlite3.Connection, *, sentence_hash: str, source_text: str, provider: str, model: str, prompt_version: str) -> bool:
        now = _now()
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO sentence_translations(
                sentence_hash, source_text, provider, model, prompt_version, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (sentence_hash, source_text, provider, model, prompt_version, now, now),
        )
        return cursor.rowcount == 1

    def mark_pending_for_retry(self, connection: sqlite3.Connection, sentence_hash: str) -> bool:
        cursor = connection.execute(
            """
            UPDATE sentence_translations
            SET status = 'pending', error_message = '', is_user_edited = 0, updated_at = ?
            WHERE sentence_hash = ? AND status IN ('failed', 'completed')
            """,
            (_now(), sentence_hash),
        )
        return cursor.rowcount == 1

    def complete(self, connection: sqlite3.Connection, sentence_hash: str, translation: str, expressions: list[dict[str, str]], provider: str, model: str, prompt_version: str) -> None:
        connection.execute(
            """
            UPDATE sentence_translations SET chinese_translation = ?, key_expressions_json = ?,
                provider = ?, model = ?, prompt_version = ?, status = 'completed', error_message = '', updated_at = ?
            WHERE sentence_hash = ? AND is_user_edited = 0
            """,
            (translation, json.dumps(expressions, ensure_ascii=False), provider, model, prompt_version, _now(), sentence_hash),
        )

    def fail(self, connection: sqlite3.Connection, sentence_hash: str, error_message: str) -> None:
        connection.execute(
            "UPDATE sentence_translations SET status = 'failed', error_message = ?, updated_at = ? WHERE sentence_hash = ? AND is_user_edited = 0",
            (error_message, _now(), sentence_hash),
        )

    def edit(self, connection: sqlite3.Connection, sentence_hash: str, translation: str, expressions: list[dict[str, str]]) -> None:
        connection.execute(
            "UPDATE sentence_translations SET chinese_translation = ?, key_expressions_json = ?, status = 'completed', is_user_edited = 1, updated_at = ? WHERE sentence_hash = ?",
            (translation, json.dumps(expressions, ensure_ascii=False), _now(), sentence_hash),
        )

    def _row(self, row) -> SentenceTranslation:
        try:
            expressions = json.loads(row["key_expressions_json"] or "[]")
        except json.JSONDecodeError:
            expressions = []
        return SentenceTranslation(
            id=row["id"], sentence_hash=row["sentence_hash"], source_text=row["source_text"],
            chinese_translation=row["chinese_translation"], key_expressions=expressions,
            provider=row["provider"], model=row["model"], prompt_version=row["prompt_version"],
            status=row["status"], error_message=row["error_message"], is_user_edited=bool(row["is_user_edited"]),
            created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]),
        )

class SentenceAttemptRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def insert(self, connection: sqlite3.Connection, attempt, *, practice_type: str = "article_sentence") -> int:
        cursor = connection.execute(
            """
            INSERT INTO sentence_attempts(
                session_id, article_sentence_id, sentence_hash, practice_type,
                started_at, completed_at, active_seconds, total_elapsed_seconds,
                correct_characters, total_characters, error_count, cpm, wpm,
                accuracy, completed, created_at
            ) VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt.article_sentence_id, attempt.sentence_hash, practice_type,
                attempt.started_at.isoformat(timespec="seconds") if attempt.started_at else None,
                attempt.completed_at.isoformat(timespec="seconds") if attempt.completed_at else None,
                attempt.active_seconds, attempt.total_elapsed_seconds, attempt.correct_characters,
                attempt.total_characters, attempt.error_count, attempt.cpm, attempt.wpm,
                attempt.accuracy, int(attempt.completed), _now(),
            ),
        )
        return int(cursor.lastrowid)

    def attach_to_session(self, connection: sqlite3.Connection, attempt_ids: list[int], session_id: int) -> None:
        if attempt_ids:
            placeholders = ",".join("?" for _ in attempt_ids)
            connection.execute(
                f"UPDATE sentence_attempts SET session_id = ? WHERE id IN ({placeholders})",
                (session_id, *attempt_ids),
            )

    def list_for_hash(self, sentence_hash: str, limit: int = 20):
        return self._connection_provider().execute(
            "SELECT * FROM sentence_attempts WHERE sentence_hash = ? ORDER BY created_at DESC LIMIT ?",
            (sentence_hash, limit),
        ).fetchall()
