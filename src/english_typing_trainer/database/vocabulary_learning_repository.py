from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from english_typing_trainer.models.vocabulary import (
    VocabularyAttempt,
    VocabularyContext,
    VocabularyEntry,
    VocabularyLearningState,
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class VocabularyLearningRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def get_entry(self, entry_id: int) -> VocabularyEntry | None:
        row = self._connection_provider().execute("SELECT * FROM vocabulary_entries WHERE id = ?", (entry_id,)).fetchone()
        return self._entry(row) if row else None

    def get_by_word(self, normalized_word: str) -> VocabularyEntry | None:
        row = self._connection_provider().execute(
            "SELECT * FROM vocabulary_entries WHERE normalized_word = ?", (normalized_word,)
        ).fetchone()
        return self._entry(row) if row else None

    def create_entry(self, connection: sqlite3.Connection, entry: VocabularyEntry) -> VocabularyEntry:
        stamp = now_iso()
        cursor = connection.execute(
            """
            INSERT INTO vocabulary_entries(
                normalized_word, display_word, lemma, phonetic, primary_part_of_speech,
                dictionary_status, dictionary_payload_json, dictionary_fetched_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (entry.normalized_word, entry.display_word, entry.lemma, entry.phonetic,
             entry.primary_part_of_speech, entry.dictionary_status,
             json.dumps(entry.dictionary_payload or {}, ensure_ascii=False), None, stamp, stamp),
        )
        entry.id = int(cursor.lastrowid)
        return entry

    def update_dictionary(self, connection: sqlite3.Connection, entry_id: int, *, lemma: str, phonetic: str,
                          part_of_speech: str, status: str, payload: object) -> None:
        connection.execute(
            """UPDATE vocabulary_entries SET lemma=?, phonetic=?, primary_part_of_speech=?,
               dictionary_status=?, dictionary_payload_json=?, dictionary_fetched_at=?, updated_at=? WHERE id=?""",
            (lemma, phonetic, part_of_speech, status, json.dumps(payload, ensure_ascii=False), now_iso(), now_iso(), entry_id),
        )

    def add_context(self, connection: sqlite3.Connection, context: VocabularyContext) -> tuple[VocabularyContext, bool]:
        existing = connection.execute(
            """SELECT * FROM vocabulary_contexts WHERE vocabulary_entry_id=? AND article_id IS ?
               AND article_sentence_id IS ? AND start_offset=? AND end_offset=?""",
            (context.vocabulary_entry_id, context.article_id, context.article_sentence_id,
             context.start_offset, context.end_offset),
        ).fetchone()
        if existing:
            return self._context(existing), False
        stamp = now_iso()
        cursor = connection.execute(
            """INSERT INTO vocabulary_contexts(
               vocabulary_entry_id, article_id, article_sentence_id, source_word, source_sentence,
               start_offset, end_offset, contextual_part_of_speech, contextual_meaning_zh,
               explanation_zh, common_collocation, example_en, example_zh, ai_status,
               ai_prompt_version, ai_generated_at, is_manual, created_at, updated_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (context.vocabulary_entry_id, context.article_id, context.article_sentence_id,
             context.source_word, context.source_sentence, context.start_offset, context.end_offset,
             context.contextual_part_of_speech, context.contextual_meaning_zh, context.explanation_zh,
             context.common_collocation, context.example_en, context.example_zh, context.ai_status,
             context.ai_prompt_version, None, int(context.is_manual), stamp, stamp),
        )
        context.id = int(cursor.lastrowid)
        return context, True

    def ensure_state(self, connection: sqlite3.Connection, entry_id: int, target_count: int = 5) -> None:
        stamp = now_iso()
        connection.execute(
            """INSERT OR IGNORE INTO vocabulary_learning_state(
               vocabulary_entry_id, typing_target_count, created_at, updated_at
               ) VALUES (?, ?, ?, ?)""", (entry_id, target_count, stamp, stamp)
        )

    def get_state(self, entry_id: int) -> VocabularyLearningState | None:
        row = self._connection_provider().execute(
            "SELECT * FROM vocabulary_learning_state WHERE vocabulary_entry_id=?", (entry_id,)
        ).fetchone()
        return self._state(row) if row else None

    def list_contexts(self, entry_id: int) -> list[VocabularyContext]:
        rows = self._connection_provider().execute(
            "SELECT * FROM vocabulary_contexts WHERE vocabulary_entry_id=? ORDER BY created_at, id", (entry_id,)
        ).fetchall()
        return [self._context(row) for row in rows]

    def get_context(self, context_id: int) -> VocabularyContext | None:
        row = self._connection_provider().execute("SELECT * FROM vocabulary_contexts WHERE id=?", (context_id,)).fetchone()
        return self._context(row) if row else None

    def update_explanation(self, connection: sqlite3.Connection, context_id: int, result, *, manual: bool = False) -> None:
        current = connection.execute("SELECT is_manual FROM vocabulary_contexts WHERE id=?", (context_id,)).fetchone()
        if current and current[0] and not manual:
            return
        connection.execute(
            """UPDATE vocabulary_contexts SET contextual_part_of_speech=?, contextual_meaning_zh=?,
               explanation_zh=?, common_collocation=?, example_en=?, example_zh=?, ai_status='ready',
               ai_generated_at=?, is_manual=?, updated_at=? WHERE id=?""",
            (result.part_of_speech, result.meaning_in_context_zh, result.simple_explanation_zh,
             result.collocation, result.example_en, result.example_zh, now_iso(), int(manual), now_iso(), context_id),
        )

    def mark_ai_failed(self, connection: sqlite3.Connection, context_id: int) -> None:
        connection.execute("UPDATE vocabulary_contexts SET ai_status='failed', updated_at=? WHERE id=?", (now_iso(), context_id))

    def list_entries(self, *, search: str = "", status: str = "all") -> list[sqlite3.Row]:
        sql = """SELECT e.*, s.status, s.typing_target_count, s.typing_completed_count,
                 s.last_practiced_at, s.next_review_at,
                 COALESCE((SELECT contextual_meaning_zh FROM vocabulary_contexts c
                           WHERE c.vocabulary_entry_id=e.id AND contextual_meaning_zh!=''
                           ORDER BY c.updated_at DESC LIMIT 1), '') AS meaning_zh,
                 COALESCE((SELECT a.title FROM vocabulary_contexts c LEFT JOIN articles a ON a.id=c.article_id
                           WHERE c.vocabulary_entry_id=e.id ORDER BY c.created_at DESC LIMIT 1), '') AS article_title
                 FROM vocabulary_entries e JOIN vocabulary_learning_state s ON s.vocabulary_entry_id=e.id WHERE 1=1"""
        params: list[object] = []
        if search.strip():
            sql += " AND (e.normalized_word LIKE ? OR e.display_word LIKE ?)"
            params += [f"%{search.strip()}%", f"%{search.strip()}%"]
        if status != "all":
            sql += " AND s.status=?"; params.append(status)
        sql += " ORDER BY s.next_review_at IS NULL, s.next_review_at, e.updated_at DESC"
        return self._connection_provider().execute(sql, params).fetchall()

    def save_attempt(self, connection: sqlite3.Connection, attempt: VocabularyAttempt) -> int:
        cursor = connection.execute(
            """INSERT INTO vocabulary_attempts(vocabulary_entry_id, vocabulary_context_id, practice_type,
               expected_answer, user_input, is_correct, accuracy, duration_ms, self_rating, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (attempt.vocabulary_entry_id, attempt.vocabulary_context_id, attempt.practice_type,
             attempt.expected_answer, attempt.user_input,
             None if attempt.is_correct is None else int(attempt.is_correct), attempt.accuracy,
             attempt.duration_ms, attempt.self_rating, now_iso()),
        )
        return int(cursor.lastrowid)

    def update_state(self, connection: sqlite3.Connection, state: VocabularyLearningState) -> None:
        connection.execute(
            """UPDATE vocabulary_learning_state SET status=?, typing_target_count=?, typing_completed_count=?,
               correct_attempts=?, incorrect_attempts=?, familiarity_level=?, last_practiced_at=?,
               next_review_at=?, mastered_at=?, updated_at=? WHERE vocabulary_entry_id=?""",
            (state.status, state.typing_target_count, state.typing_completed_count, state.correct_attempts,
             state.incorrect_attempts, state.familiarity_level,
             state.last_practiced_at.isoformat(timespec="seconds") if state.last_practiced_at else None,
             state.next_review_at.isoformat(timespec="seconds") if state.next_review_at else None,
             state.mastered_at.isoformat(timespec="seconds") if state.mastered_at else None,
             now_iso(), state.vocabulary_entry_id),
        )

    def delete_entry(self, connection: sqlite3.Connection, entry_id: int) -> None:
        connection.execute("DELETE FROM vocabulary_entries WHERE id=?", (entry_id,))

    @staticmethod
    def _dt(value): return datetime.fromisoformat(value) if value else None

    def _entry(self, row) -> VocabularyEntry:
        return VocabularyEntry(id=row["id"], normalized_word=row["normalized_word"], display_word=row["display_word"],
            lemma=row["lemma"], phonetic=row["phonetic"], primary_part_of_speech=row["primary_part_of_speech"],
            dictionary_status=row["dictionary_status"], dictionary_payload=json.loads(row["dictionary_payload_json"] or "{}"),
            dictionary_fetched_at=self._dt(row["dictionary_fetched_at"]), created_at=self._dt(row["created_at"]), updated_at=self._dt(row["updated_at"]))

    def _context(self, row) -> VocabularyContext:
        return VocabularyContext(id=row["id"], vocabulary_entry_id=row["vocabulary_entry_id"], article_id=row["article_id"],
            article_sentence_id=row["article_sentence_id"], source_word=row["source_word"], source_sentence=row["source_sentence"],
            start_offset=row["start_offset"], end_offset=row["end_offset"], contextual_part_of_speech=row["contextual_part_of_speech"],
            contextual_meaning_zh=row["contextual_meaning_zh"], explanation_zh=row["explanation_zh"],
            common_collocation=row["common_collocation"], example_en=row["example_en"], example_zh=row["example_zh"],
            ai_status=row["ai_status"], ai_prompt_version=row["ai_prompt_version"], ai_generated_at=self._dt(row["ai_generated_at"]),
            is_manual=bool(row["is_manual"]), created_at=self._dt(row["created_at"]), updated_at=self._dt(row["updated_at"]))

    def _state(self, row) -> VocabularyLearningState:
        return VocabularyLearningState(vocabulary_entry_id=row["vocabulary_entry_id"], status=row["status"],
            typing_target_count=row["typing_target_count"], typing_completed_count=row["typing_completed_count"],
            correct_attempts=row["correct_attempts"], incorrect_attempts=row["incorrect_attempts"],
            familiarity_level=row["familiarity_level"], last_practiced_at=self._dt(row["last_practiced_at"]),
            next_review_at=self._dt(row["next_review_at"]), mastered_at=self._dt(row["mastered_at"]),
            created_at=self._dt(row["created_at"]), updated_at=self._dt(row["updated_at"]))
