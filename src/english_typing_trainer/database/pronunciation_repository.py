from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from english_typing_trainer.models.pronunciation import PronunciationAttempt


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


class PronunciationRepository:
    def __init__(self, connection_provider) -> None: self._connection_provider = connection_provider

    def add(self, connection: sqlite3.Connection, attempt: PronunciationAttempt, now: datetime) -> PronunciationAttempt:
        cursor = connection.execute(
            """INSERT INTO pronunciation_attempts(target_type,vocabulary_entry_id,vocabulary_context_id,reference_text_hash,provider,locale,
                overall_score,accuracy_score,fluency_score,completeness_score,prosody_score,word_feedback_json,status,error_code,recorded_at,audio_path,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (attempt.target_type,attempt.vocabulary_entry_id,attempt.vocabulary_context_id,attempt.reference_text_hash,attempt.provider,attempt.locale,
             attempt.overall_score,attempt.accuracy_score,attempt.fluency_score,attempt.completeness_score,attempt.prosody_score,attempt.word_feedback_json,
             attempt.status,attempt.error_code,_iso(attempt.recorded_at or now),attempt.audio_path,_iso(now)),
        )
        attempt.id = int(cursor.lastrowid); return attempt

    def delete(self, connection: sqlite3.Connection, attempt_id: int) -> str | None:
        row=connection.execute("SELECT audio_path FROM pronunciation_attempts WHERE id=?",(attempt_id,)).fetchone()
        connection.execute("DELETE FROM pronunciation_attempts WHERE id=?",(attempt_id,))
        return str(row[0]) if row and row[0] else None
