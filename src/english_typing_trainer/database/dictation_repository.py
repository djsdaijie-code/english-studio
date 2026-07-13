from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from english_typing_trainer.models.dictation import DictationAttempt


class DictationRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def add_attempt(self, connection: sqlite3.Connection, attempt: DictationAttempt, now: datetime) -> DictationAttempt:
        stamp = now.astimezone(timezone.utc).isoformat(timespec="seconds")
        cursor = connection.execute(
            """INSERT INTO dictation_attempts(vocabulary_entry_id,vocabulary_context_id,dictation_type,comparison_mode,
                expected_text,user_input,normalized_comparison,error_count,omitted_count,inserted_count,replay_count,
                speed,duration_ms,rating,reviewed_at_utc,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (attempt.vocabulary_entry_id, attempt.vocabulary_context_id, attempt.dictation_type, attempt.comparison_mode,
             attempt.expected_text, attempt.user_input, attempt.normalized_comparison, attempt.error_count,
             attempt.omitted_count, attempt.inserted_count, attempt.replay_count, attempt.speed, attempt.duration_ms,
             attempt.rating, stamp, stamp),
        )
        attempt.id = int(cursor.lastrowid)
        attempt.reviewed_at_utc = now
        return attempt
