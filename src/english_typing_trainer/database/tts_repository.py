from __future__ import annotations

import sqlite3
from datetime import datetime


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class TTSAudioCacheRepository:
    def get(self, connection: sqlite3.Connection, cache_key: str):
        return connection.execute(
            "SELECT * FROM tts_audio_cache WHERE cache_key = ? AND status = 'completed'", (cache_key,)
        ).fetchone()

    def complete(self, connection: sqlite3.Connection, *, cache_key: str, request, text_hash: str, file_path: str, duration_ms: int | None, size_bytes: int) -> None:
        connection.execute(
            """
            INSERT INTO tts_audio_cache(cache_key, provider, model, voice_id, speed, volume, pitch,
                text_hash, text_preview, file_path, audio_format, duration_ms, size_bytes, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed')
            ON CONFLICT(cache_key) DO UPDATE SET file_path=excluded.file_path, duration_ms=excluded.duration_ms,
                size_bytes=excluded.size_bytes, status='completed', error_message=''
            """,
            (cache_key, request.provider, request.model, request.voice_id, request.speed, request.volume,
             request.pitch, text_hash, request.text.strip()[:80], file_path, request.audio_format,
             duration_ms, size_bytes, _now()),
        )

    def complete_external(self, connection: sqlite3.Connection, *, cache_key: str, source_url_hash: str,
                          text_preview: str, file_path: str, audio_format: str, size_bytes: int) -> None:
        connection.execute(
            """INSERT INTO tts_audio_cache(cache_key, provider, model, voice_id, speed, volume, pitch,
               text_hash, text_preview, file_path, audio_format, size_bytes, created_at, status,
               source_type, source_url_hash, content_type)
               VALUES (?, 'free_dictionary', '', '', 1, 1, 0, ?, ?, ?, ?, ?, ?, 'completed',
                       'dictionary', ?, 'word')
               ON CONFLICT(cache_key) DO UPDATE SET file_path=excluded.file_path,
               size_bytes=excluded.size_bytes, status='completed', error_message=''""",
            (cache_key, source_url_hash, text_preview[:80], file_path, audio_format, size_bytes, _now(), source_url_hash),
        )

    def delete(self, connection: sqlite3.Connection, cache_key: str) -> None:
        connection.execute("DELETE FROM tts_audio_cache WHERE cache_key = ?", (cache_key,))

    def clear(self, connection: sqlite3.Connection) -> None:
        connection.execute("DELETE FROM tts_audio_cache")

    def rows(self, connection: sqlite3.Connection):
        return connection.execute("SELECT * FROM tts_audio_cache").fetchall()

    def mark_played(self, connection: sqlite3.Connection, cache_key: str) -> None:
        connection.execute("UPDATE tts_audio_cache SET last_played_at = ? WHERE cache_key = ?", (_now(), cache_key))
