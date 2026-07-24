from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from english_typing_trainer.models.article import Article
from english_typing_trainer.models.practice import PracticeSessionRecord, TypingErrorEventRecord
from english_typing_trainer.models.section import ArticleSection
from english_typing_trainer.models.vocabulary import PracticeSet, PracticeSetItem, VocabularyItem
from english_typing_trainer.statistics.metrics import MIN_EFFECTIVE_CHARACTERS, MIN_EFFECTIVE_SECONDS

ARTICLE_PRACTICE_TYPES = ("article", "article_section")
SPECIAL_PRACTICE_TYPES = (
    "error_words",
    "error_characters",
    "context_sentences",
    "vocabulary_review",
    "mixed_review",
)


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


@dataclass(slots=True)
class HistoryQuery:
    article_id: int | None = None
    practice_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    completed: bool | None = None
    order_by: str = "created_at"
    descending: bool = True
    limit: int = 500
    offset: int = 0
    valid_only: bool = False
    exclude_automated: bool = True


class ArticleRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def list_articles(self, search: str = "") -> list[Article]:
        query = """
            SELECT
                a.*,
                COALESCE(p.current_section_index, 0) AS current_section_index,
                COALESCE(p.current_character_index, 0) AS current_character_index,
                COALESCE(p.completed_section_count, 0) AS completed_section_count
            FROM articles a
            LEFT JOIN article_progress p ON p.article_id = a.id
            WHERE a.is_deleted = 0
        """
        params: list[object] = []
        if search.strip():
            query += " AND a.title LIKE ?"
            params.append(f"%{search.strip()}%")
        query += " ORDER BY a.imported_at DESC"
        rows = self._connection_provider().execute(query, params).fetchall()
        return [self._row_to_article(row) for row in rows]

    def get_article(self, article_id: int, include_deleted: bool = False) -> Article | None:
        query = """
            SELECT
                a.*,
                COALESCE(p.current_section_index, 0) AS current_section_index,
                COALESCE(p.current_character_index, 0) AS current_character_index,
                COALESCE(p.completed_section_count, 0) AS completed_section_count
            FROM articles a
            LEFT JOIN article_progress p ON p.article_id = a.id
            WHERE a.id = ?
        """
        params: list[object] = [article_id]
        if not include_deleted:
            query += " AND a.is_deleted = 0"
        row = self._connection_provider().execute(query, params).fetchone()
        return self._row_to_article(row) if row else None

    def get_article_by_hash(self, content_hash: str) -> Article | None:
        row = self._connection_provider().execute(
            """
            SELECT
                a.*,
                COALESCE(p.current_section_index, 0) AS current_section_index,
                COALESCE(p.current_character_index, 0) AS current_character_index,
                COALESCE(p.completed_section_count, 0) AS completed_section_count
            FROM articles a
            LEFT JOIN article_progress p ON p.article_id = a.id
            WHERE a.content_hash = ?
            """,
            (content_hash,),
        ).fetchone()
        return self._row_to_article(row) if row else None

    def insert_article(
        self,
        connection: sqlite3.Connection,
        article: Article,
        sections: list[ArticleSection],
    ) -> Article:
        cursor = connection.execute(
            """
            INSERT INTO articles(
                title, original_filename, source_path, content_hash, full_text,
                character_count, word_count, section_count, imported_at, last_practiced_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                article.title,
                article.original_filename,
                article.source_path,
                article.content_hash,
                article.full_text,
                article.character_count,
                article.word_count,
                len(sections),
                article.imported_at.isoformat(timespec="seconds") if article.imported_at else now_iso(),
                article.last_practiced_at.isoformat(timespec="seconds") if article.last_practiced_at else None,
            ),
        )
        article_id = int(cursor.lastrowid)
        self.insert_sections(connection, article_id, sections)
        connection.execute(
            """
            INSERT INTO article_progress(article_id, current_section_index, current_character_index, completed_section_count, updated_at)
            VALUES (?, 0, 0, 0, ?)
            """,
            (article_id, now_iso()),
        )
        return self.get_article(article_id, include_deleted=True)  # type: ignore[return-value]

    def insert_sections(
        self,
        connection: sqlite3.Connection,
        article_id: int,
        sections: list[ArticleSection],
    ) -> None:
        connection.executemany(
            """
            INSERT INTO article_sections(
                article_id, section_index, text, character_count, word_count,
                start_offset, end_offset, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            [
                (
                    article_id,
                    section.section_index,
                    section.text,
                    section.character_count,
                    section.word_count,
                    section.start_offset,
                    section.end_offset,
                )
                for section in sections
            ],
        )
        connection.execute(
            "UPDATE articles SET section_count = ? WHERE id = ?",
            (len(sections), article_id),
        )

    def get_active_sections(self, article_id: int) -> list[ArticleSection]:
        rows = self._connection_provider().execute(
            """
            SELECT *
            FROM article_sections
            WHERE article_id = ? AND is_active = 1
            ORDER BY section_index ASC
            """,
            (article_id,),
        ).fetchall()
        return [self._row_to_section(row) for row in rows]

    def get_active_section_by_index(self, article_id: int, section_index: int) -> ArticleSection | None:
        row = self._connection_provider().execute(
            """
            SELECT *
            FROM article_sections
            WHERE article_id = ? AND section_index = ? AND is_active = 1
            """,
            (article_id, section_index),
        ).fetchone()
        return self._row_to_section(row) if row else None

    def get_section(self, section_id: int) -> ArticleSection | None:
        row = self._connection_provider().execute(
            "SELECT * FROM article_sections WHERE id = ?",
            (section_id,),
        ).fetchone()
        return self._row_to_section(row) if row else None

    def deactivate_active_sections(self, connection: sqlite3.Connection, article_id: int) -> None:
        connection.execute(
            "UPDATE article_sections SET is_active = 0 WHERE article_id = ? AND is_active = 1",
            (article_id,),
        )

    def rename_article(self, connection: sqlite3.Connection, article_id: int, new_title: str) -> None:
        connection.execute("UPDATE articles SET title = ? WHERE id = ?", (new_title, article_id))

    def update_article_content(
        self,
        connection: sqlite3.Connection,
        article_id: int,
        *,
        content_hash: str,
        full_text: str,
        character_count: int,
        word_count: int,
    ) -> None:
        connection.execute(
            """
            UPDATE articles
            SET content_hash = ?, full_text = ?, character_count = ?, word_count = ?
            WHERE id = ?
            """,
            (content_hash, full_text, character_count, word_count, article_id),
        )

    def soft_delete_article(self, connection: sqlite3.Connection, article_id: int) -> None:
        connection.execute("UPDATE articles SET is_deleted = 1 WHERE id = ?", (article_id,))

    def restore_article(self, connection: sqlite3.Connection, article_id: int) -> None:
        connection.execute("UPDATE articles SET is_deleted = 0 WHERE id = ?", (article_id,))

    def update_last_practiced(self, connection: sqlite3.Connection, article_id: int) -> None:
        connection.execute(
            "UPDATE articles SET last_practiced_at = ? WHERE id = ?",
            (now_iso(), article_id),
        )

    def update_progress(
        self,
        connection: sqlite3.Connection,
        article_id: int,
        current_section_index: int,
        current_character_index: int,
        completed_section_count: int,
    ) -> None:
        connection.execute(
            """
            INSERT INTO article_progress(article_id, current_section_index, current_character_index, completed_section_count, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(article_id) DO UPDATE SET
                current_section_index = excluded.current_section_index,
                current_character_index = excluded.current_character_index,
                completed_section_count = excluded.completed_section_count,
                updated_at = excluded.updated_at
            """,
            (
                article_id,
                current_section_index,
                current_character_index,
                completed_section_count,
                now_iso(),
            ),
        )

    def reset_progress(self, connection: sqlite3.Connection, article_id: int) -> None:
        self.update_progress(connection, article_id, 0, 0, 0)

    def _row_to_article(self, row: sqlite3.Row) -> Article:
        return Article(
            id=row["id"],
            title=row["title"],
            original_filename=row["original_filename"],
            source_path=row["source_path"],
            content_hash=row["content_hash"],
            full_text=row["full_text"],
            character_count=row["character_count"],
            word_count=row["word_count"],
            section_count=row["section_count"],
            imported_at=parse_datetime(row["imported_at"]),
            last_practiced_at=parse_datetime(row["last_practiced_at"]),
            is_deleted=bool(row["is_deleted"]),
            current_section_index=int(row["current_section_index"]),
            current_character_index=int(row["current_character_index"]),
            completed_section_count=int(row["completed_section_count"]),
        )

    def _row_to_section(self, row: sqlite3.Row) -> ArticleSection:
        return ArticleSection(
            id=row["id"],
            article_id=row["article_id"],
            section_index=row["section_index"],
            text=row["text"],
            character_count=row["character_count"],
            word_count=row["word_count"],
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            is_active=bool(row["is_active"]),
        )


class PracticeRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def save_session(
        self,
        connection: sqlite3.Connection,
        record: PracticeSessionRecord,
        errors: list[TypingErrorEventRecord] | None = None,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO practice_sessions(
                article_id, section_id, started_at, finished_at, active_seconds, paused_seconds,
                total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters,
                wpm, cpm, accuracy, completion_rate, completed, practice_type,
                longest_correct_streak, average_wpm, app_version, practice_set_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.article_id,
                record.section_id,
                record.started_at.isoformat(timespec="seconds") if record.started_at else None,
                record.finished_at.isoformat(timespec="seconds") if record.finished_at else None,
                record.active_seconds,
                record.paused_seconds,
                record.total_keystrokes,
                record.correct_keystrokes,
                record.error_keystrokes,
                record.correct_characters,
                record.wpm,
                record.cpm,
                record.accuracy,
                record.completion_rate,
                int(record.completed),
                record.practice_type,
                record.longest_correct_streak,
                record.average_wpm,
                record.app_version,
                record.practice_set_id,
                now_iso(),
            ),
        )
        session_id = int(cursor.lastrowid)
        if errors:
            connection.executemany(
                """
                INSERT INTO typing_errors(
                    session_id, article_id, section_id, character_index,
                    expected_character, actual_character, target_word, error_type, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_id,
                        error.article_id,
                        error.section_id,
                        error.character_index,
                        error.expected_character,
                        error.actual_character,
                        error.target_word,
                        error.error_type,
                        error.occurred_at.isoformat(timespec="seconds"),
                    )
                    for error in errors
                ],
            )
        return session_id

    def list_sessions_for_article(self, article_id: int) -> list[sqlite3.Row]:
        return self._connection_provider().execute(
            "SELECT * FROM practice_sessions WHERE article_id = ? ORDER BY created_at DESC",
            (article_id,),
        ).fetchall()

    def list_history(self, query: HistoryQuery) -> list[sqlite3.Row]:
        order_map = {
            "created_at": "ps.created_at",
            "wpm": "ps.wpm",
            "accuracy": "ps.accuracy",
            "error_keystrokes": "ps.error_keystrokes",
            "active_seconds": "ps.active_seconds",
        }
        order_column = order_map.get(query.order_by, "ps.created_at")
        direction = "DESC" if query.descending else "ASC"
        sql = f"""
            SELECT
                ps.*,
                a.title AS article_title,
                s.section_index AS section_index,
                pset.title AS practice_set_title,
                COUNT(te.id) AS typing_error_count,
                CASE
                    WHEN ps.completed = 1
                     AND ps.correct_characters >= {MIN_EFFECTIVE_CHARACTERS}
                     AND ps.active_seconds >= {MIN_EFFECTIVE_SECONDS}
                    THEN 1 ELSE 0
                END AS is_effective_result,
                CASE
                    WHEN {self._automated_sql('ps')} THEN 1 ELSE 0
                END AS is_automated
            FROM practice_sessions ps
            LEFT JOIN articles a ON a.id = ps.article_id
            LEFT JOIN article_sections s ON s.id = ps.section_id
            LEFT JOIN practice_sets pset ON pset.id = ps.practice_set_id
            LEFT JOIN typing_errors te ON te.session_id = ps.id
            WHERE 1 = 1
        """
        params: list[object] = []
        if query.article_id is not None:
            sql += " AND ps.article_id = ?"
            params.append(query.article_id)
        if query.practice_type:
            if query.practice_type == "article":
                placeholders = ", ".join("?" for _ in ARTICLE_PRACTICE_TYPES)
                sql += f" AND ps.practice_type IN ({placeholders})"
                params.extend(ARTICLE_PRACTICE_TYPES)
            else:
                sql += " AND ps.practice_type = ?"
                params.append(query.practice_type)
        if query.date_from is not None:
            sql += " AND date(ps.created_at) >= date(?)"
            params.append(query.date_from.isoformat())
        if query.date_to is not None:
            sql += " AND date(ps.created_at) <= date(?)"
            params.append(query.date_to.isoformat())
        if query.completed is not None:
            sql += " AND ps.completed = ?"
            params.append(int(query.completed))
        if query.valid_only:
            sql += (
                f" AND ps.completed = 1 AND ps.correct_characters >= {MIN_EFFECTIVE_CHARACTERS}"
                f" AND ps.active_seconds >= {MIN_EFFECTIVE_SECONDS}"
            )
        if query.exclude_automated:
            sql += f" AND NOT ({self._automated_sql('ps')})"
        sql += f" GROUP BY ps.id ORDER BY {order_column} {direction} LIMIT ? OFFSET ?"
        params.extend([query.limit, query.offset])
        return self._connection_provider().execute(sql, params).fetchall()

    def get_session_detail(self, session_id: int) -> tuple[sqlite3.Row | None, list[sqlite3.Row]]:
        session = self._connection_provider().execute(
            f"""
            SELECT
                ps.*,
                a.title AS article_title,
                s.section_index AS section_index,
                pset.title AS practice_set_title,
                pset.practice_mode AS practice_set_mode,
                CASE
                    WHEN ps.completed = 1
                     AND ps.correct_characters >= {MIN_EFFECTIVE_CHARACTERS}
                     AND ps.active_seconds >= {MIN_EFFECTIVE_SECONDS}
                    THEN 1 ELSE 0
                END AS is_effective_result,
                CASE
                    WHEN {self._automated_sql('ps')} THEN 1 ELSE 0
                END AS is_automated
            FROM practice_sessions ps
            LEFT JOIN articles a ON a.id = ps.article_id
            LEFT JOIN article_sections s ON s.id = ps.section_id
            LEFT JOIN practice_sets pset ON pset.id = ps.practice_set_id
            WHERE ps.id = ?
            """,
            (session_id,),
        ).fetchone()
        errors = self._connection_provider().execute(
            """
            SELECT *
            FROM typing_errors
            WHERE session_id = ?
            ORDER BY character_index ASC, occurred_at ASC, id ASC
            """,
            (session_id,),
        ).fetchall()
        return session, errors

    def delete_session(self, connection: sqlite3.Connection, session_id: int) -> None:
        connection.execute("DELETE FROM practice_sessions WHERE id = ?", (session_id,))

    def aggregate_overview(self, today: date) -> dict[str, object]:
        connection = self._connection_provider()
        ranges = {
            "today": today.isoformat(),
            "last_7": (today - timedelta(days=6)).isoformat(),
            "last_30": (today - timedelta(days=29)).isoformat(),
        }
        formal_article_filter = self._effective_sql("practice_sessions")
        formal_any_filter = self._effective_sql("practice_sessions", article_only=False)
        non_automated_filter = f"NOT ({self._automated_sql('practice_sessions')})"
        totals = connection.execute(
            f"""
            SELECT
                COALESCE(SUM(active_seconds), 0) AS total_active_seconds,
                COALESCE(SUM(CASE WHEN date(created_at) = date(?) THEN active_seconds ELSE 0 END), 0) AS today_active_seconds,
                COALESCE(SUM(CASE WHEN date(created_at) >= date(?) THEN active_seconds ELSE 0 END), 0) AS last_7_active_seconds,
                COALESCE(SUM(CASE WHEN date(created_at) >= date(?) THEN active_seconds ELSE 0 END), 0) AS last_30_active_seconds,
                COUNT(CASE WHEN date(created_at) = date(?) THEN 1 END) AS today_sessions,
                COUNT(CASE WHEN completed = 1 THEN 1 END) AS completed_sessions,
                COALESCE(SUM(correct_characters), 0) AS total_correct_characters,
                COUNT(CASE WHEN practice_type IN ('error_words', 'error_characters', 'context_sentences', 'vocabulary_review', 'mixed_review') THEN 1 END) AS special_session_count,
                COUNT(CASE WHEN practice_type = 'vocabulary_review' THEN 1 END) AS vocabulary_review_sessions
            FROM practice_sessions
            WHERE {non_automated_filter}
            """,
            (ranges["today"], ranges["last_7"], ranges["last_30"], ranges["today"]),
        ).fetchone()
        averages = connection.execute(
            f"""
            SELECT
                AVG(CASE WHEN {formal_any_filter} THEN wpm END) AS average_wpm,
                AVG(CASE WHEN {formal_any_filter} THEN accuracy END) AS average_accuracy,
                AVG(CASE WHEN practice_type IN ('error_words', 'error_characters', 'context_sentences', 'vocabulary_review', 'mixed_review')
                         AND {formal_any_filter} THEN accuracy END) AS special_average_accuracy
            FROM practice_sessions
            WHERE {non_automated_filter}
            """
        ).fetchone()
        highest = connection.execute(
            f"""
            SELECT MAX(wpm) AS highest_effective_wpm
            FROM practice_sessions
            WHERE {formal_any_filter}
              AND {non_automated_filter}
            """
        ).fetchone()
        streak = self._compute_streaks(today)
        vocab = connection.execute(
            """
            SELECT
                COUNT(CASE WHEN is_archived = 0 AND status = 'mastered' THEN 1 END) AS mastered_words,
                COUNT(CASE WHEN is_archived = 0 AND next_review_at IS NOT NULL AND date(next_review_at) <= date(?) THEN 1 END) AS due_vocabulary_words
            FROM vocabulary_items
            """,
            (today.isoformat(),),
        ).fetchone()
        return {
            "today_practice_seconds": totals["today_active_seconds"],
            "today_practice_sessions": totals["today_sessions"],
            "last_7_practice_seconds": totals["last_7_active_seconds"],
            "last_30_practice_seconds": totals["last_30_active_seconds"],
            "total_practice_seconds": totals["total_active_seconds"],
            "completed_sessions": totals["completed_sessions"],
            "total_correct_characters": totals["total_correct_characters"],
            "average_wpm": averages["average_wpm"],
            "average_accuracy": averages["average_accuracy"],
            "highest_effective_wpm": highest["highest_effective_wpm"],
            "current_streak_days": streak["current"],
            "longest_streak_days": streak["longest"],
            "special_practice_sessions": totals["special_session_count"],
            "vocabulary_review_sessions": totals["vocabulary_review_sessions"],
            "special_average_accuracy": averages["special_average_accuracy"],
            "mastered_words": vocab["mastered_words"],
            "due_vocabulary_words": vocab["due_vocabulary_words"],
        }

    def trend_series(self, days: int | None = None, practice_group: str = "all") -> list[sqlite3.Row]:
        connection = self._connection_provider()
        practice_alias = "practice_sessions"
        formal_filter = self._effective_sql(practice_alias, article_only=False)
        non_automated_filter = self._automated_where(practice_alias)
        sql = f"""
            SELECT
                date(created_at) AS practice_date,
                AVG(CASE WHEN {formal_filter} THEN wpm END) AS average_wpm,
                AVG(CASE WHEN {formal_filter} THEN accuracy END) AS average_accuracy,
                COALESCE(SUM(CASE WHEN NOT ({self._automated_sql(practice_alias)}) THEN active_seconds ELSE 0 END), 0) / 60.0 AS active_minutes
            FROM practice_sessions
            WHERE {non_automated_filter}
        """
        params: list[object] = []
        if practice_group == "article":
            sql += " AND practice_type IN ('article', 'article_section')"
        elif practice_group == "special":
            sql += " AND practice_type IN ('error_words', 'error_characters', 'context_sentences', 'vocabulary_review', 'mixed_review')"
        if days is not None:
            start = (date.today() - timedelta(days=days - 1)).isoformat()
            sql += " AND date(created_at) >= date(?)"
            params.append(start)
        sql += " GROUP BY date(created_at) ORDER BY date(created_at) ASC"
        return connection.execute(sql, params).fetchall()

    def error_analysis(self, days: int | None = None, limit: int = 20) -> dict[str, list[sqlite3.Row]]:
        connection = self._connection_provider()
        where = f"WHERE NOT ({self._automated_sql('ps')})"
        params: list[object] = []
        if days is not None:
            start = (date.today() - timedelta(days=days - 1)).isoformat()
            where += " AND date(te.occurred_at) >= date(?)"
            params.append(start)
        chars = connection.execute(
            f"""
            SELECT expected_character, COUNT(*) AS error_count
            FROM typing_errors te
            JOIN practice_sessions ps ON ps.id = te.session_id
            {where}
            GROUP BY expected_character
            ORDER BY error_count DESC, expected_character ASC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        combos = connection.execute(
            f"""
            SELECT expected_character, actual_character, COUNT(*) AS error_count
            FROM typing_errors te
            JOIN practice_sessions ps ON ps.id = te.session_id
            {where}
            GROUP BY expected_character, actual_character
            ORDER BY error_count DESC, expected_character ASC, actual_character ASC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        words = connection.execute(
            f"""
            SELECT target_word, COUNT(*) AS error_count
            FROM typing_errors te
            JOIN practice_sessions ps ON ps.id = te.session_id
            {where} AND target_word != ''
            GROUP BY target_word
            ORDER BY error_count DESC, target_word ASC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()
        types = connection.execute(
            f"""
            SELECT error_type, COUNT(*) AS error_count
            FROM typing_errors te
            JOIN practice_sessions ps ON ps.id = te.session_id
            {where}
            GROUP BY error_type
            ORDER BY error_count DESC, error_type ASC
            """,
            params,
        ).fetchall()
        return {
            "characters": chars,
            "combinations": combos,
            "words": words,
            "types": types,
        }

    def list_error_events(self, days: int | None = None) -> list[sqlite3.Row]:
        sql = f"""
            SELECT
                te.*,
                sec.text AS section_text,
                a.title AS article_title
            FROM typing_errors te
            JOIN practice_sessions ps ON ps.id = te.session_id
            LEFT JOIN article_sections sec ON sec.id = te.section_id
            LEFT JOIN articles a ON a.id = te.article_id
            WHERE NOT ({self._automated_sql('ps')})
        """
        params: list[object] = []
        if days is not None:
            start = (date.today() - timedelta(days=days - 1)).isoformat()
            sql += " AND date(te.occurred_at) >= date(?)"
            params.append(start)
        sql += " ORDER BY te.occurred_at DESC, te.id DESC"
        return self._connection_provider().execute(sql, params).fetchall()

    def recent_wrong_word_series(self, days: int = 30) -> list[sqlite3.Row]:
        start = (date.today() - timedelta(days=days - 1)).isoformat()
        return self._connection_provider().execute(
            f"""
            SELECT date(occurred_at) AS error_date, COUNT(*) AS error_count
            FROM typing_errors te
            JOIN practice_sessions ps ON ps.id = te.session_id
            WHERE target_word != ''
              AND NOT ({self._automated_sql('ps')})
              AND date(occurred_at) >= date(?)
            GROUP BY date(occurred_at)
            ORDER BY date(occurred_at) ASC
            """,
            (start,),
        ).fetchall()

    def _compute_streaks(self, today: date) -> dict[str, int]:
        rows = self._connection_provider().execute(
            f"""
            SELECT DISTINCT date(created_at) AS practice_date
            FROM practice_sessions
            WHERE active_seconds > 0
              AND NOT ({self._automated_sql('practice_sessions')})
            ORDER BY practice_date ASC
            """
        ).fetchall()
        dates = [date.fromisoformat(row["practice_date"]) for row in rows]
        if not dates:
            return {"current": 0, "longest": 0}
        longest = 1
        current_run = 1
        for index in range(1, len(dates)):
            if dates[index] == dates[index - 1] + timedelta(days=1):
                current_run += 1
            else:
                longest = max(longest, current_run)
                current_run = 1
        longest = max(longest, current_run)

        current = 0
        expected = today
        for practice_day in reversed(dates):
            if practice_day == expected:
                current += 1
                expected -= timedelta(days=1)
            elif practice_day < expected:
                break
        return {"current": current, "longest": longest}

    def _effective_sql(self, alias: str, *, article_only: bool = True) -> str:
        practice_scope = (
            f"{alias}.practice_type IN ('article', 'article_section') AND "
            if article_only
            else ""
        )
        return (
            f"{practice_scope}{alias}.completed = 1"
            f" AND {alias}.correct_characters >= {MIN_EFFECTIVE_CHARACTERS}"
            f" AND {alias}.active_seconds >= {MIN_EFFECTIVE_SECONDS}"
        )

    def _automated_sql(self, alias: str) -> str:
        lowered = f"LOWER(COALESCE({alias}.app_version, ''))"
        return (
            f"{lowered} LIKE '%acceptance%' OR "
            f"{lowered} LIKE '%runtime%' OR "
            f"{lowered} LIKE '%phase%' OR "
            f"{lowered} LIKE '%qa%' OR "
            f"{lowered} LIKE '%test%' OR "
            f"{lowered} LIKE '%automation%'"
        )

    def _automated_where(self, alias: str) -> str:
        return f"NOT ({self._automated_sql(alias)})"


class PracticeSetRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def create_set(
        self,
        connection: sqlite3.Connection,
        practice_set: PracticeSet,
        items: list[PracticeSetItem],
    ) -> PracticeSet:
        cursor = connection.execute(
            """
            INSERT INTO practice_sets(
                title, practice_mode, source_type, generated_text, item_count,
                configuration_json, created_at, last_practiced_at, is_deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                practice_set.title,
                practice_set.practice_mode,
                practice_set.source_type,
                practice_set.generated_text,
                practice_set.item_count,
                json.dumps(practice_set.configuration, ensure_ascii=False, sort_keys=True),
                practice_set.created_at.isoformat(timespec="seconds") if practice_set.created_at else now_iso(),
                practice_set.last_practiced_at.isoformat(timespec="seconds") if practice_set.last_practiced_at else None,
                int(practice_set.is_deleted),
            ),
        )
        practice_set_id = int(cursor.lastrowid)
        if items:
            connection.executemany(
                """
                INSERT INTO practice_set_items(
                    practice_set_id, item_type, item_value, source_article_id, source_section_id,
                    source_character_index, source_sentence, error_count, sort_order
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        practice_set_id,
                        item.item_type,
                        item.item_value,
                        item.source_article_id,
                        item.source_section_id,
                        item.source_character_index,
                        item.source_sentence,
                        item.error_count,
                        item.sort_order,
                    )
                    for item in items
                ],
            )
        return self.get_set(practice_set_id)  # type: ignore[return-value]

    def get_set(self, practice_set_id: int) -> PracticeSet | None:
        row = self._connection_provider().execute(
            "SELECT * FROM practice_sets WHERE id = ?",
            (practice_set_id,),
        ).fetchone()
        return self._row_to_practice_set(row) if row else None

    def list_sets(self, practice_mode: str | None = None, include_deleted: bool = False) -> list[PracticeSet]:
        sql = "SELECT * FROM practice_sets WHERE 1 = 1"
        params: list[object] = []
        if not include_deleted:
            sql += " AND is_deleted = 0"
        if practice_mode:
            sql += " AND practice_mode = ?"
            params.append(practice_mode)
        sql += " ORDER BY created_at DESC"
        rows = self._connection_provider().execute(sql, params).fetchall()
        return [self._row_to_practice_set(row) for row in rows]

    def list_items(self, practice_set_id: int) -> list[PracticeSetItem]:
        rows = self._connection_provider().execute(
            """
            SELECT *
            FROM practice_set_items
            WHERE practice_set_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (practice_set_id,),
        ).fetchall()
        return [self._row_to_practice_set_item(row) for row in rows]

    def touch_last_practiced(self, connection: sqlite3.Connection, practice_set_id: int) -> None:
        connection.execute(
            "UPDATE practice_sets SET last_practiced_at = ? WHERE id = ?",
            (now_iso(), practice_set_id),
        )

    def soft_delete(self, connection: sqlite3.Connection, practice_set_id: int) -> None:
        connection.execute(
            "UPDATE practice_sets SET is_deleted = 1 WHERE id = ?",
            (practice_set_id,),
        )

    def _row_to_practice_set(self, row: sqlite3.Row) -> PracticeSet:
        return PracticeSet(
            id=row["id"],
            title=row["title"],
            practice_mode=row["practice_mode"],
            source_type=row["source_type"],
            generated_text=row["generated_text"],
            item_count=row["item_count"],
            configuration=json.loads(row["configuration_json"]) if row["configuration_json"] else {},
            created_at=parse_datetime(row["created_at"]),
            last_practiced_at=parse_datetime(row["last_practiced_at"]),
            is_deleted=bool(row["is_deleted"]),
        )

    def _row_to_practice_set_item(self, row: sqlite3.Row) -> PracticeSetItem:
        return PracticeSetItem(
            id=row["id"],
            practice_set_id=row["practice_set_id"],
            item_type=row["item_type"],
            item_value=row["item_value"],
            source_article_id=row["source_article_id"],
            source_section_id=row["source_section_id"],
            source_character_index=row["source_character_index"],
            source_sentence=row["source_sentence"],
            error_count=row["error_count"],
            sort_order=row["sort_order"],
        )


class VocabularyRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def add_or_restore(
        self,
        connection: sqlite3.Connection,
        item: VocabularyItem,
    ) -> VocabularyItem:
        existing = self.get_by_normalized_word(item.normalized_word)
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO vocabulary_items(
                    normalized_word, display_word, meaning, note, source_article_id, source_section_id,
                    source_character_index, source_sentence, status, mastery_level, review_count,
                    correct_review_count, wrong_review_count, next_review_at, last_reviewed_at,
                    created_at, updated_at, is_archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.normalized_word,
                    item.display_word,
                    item.meaning,
                    item.note,
                    item.source_article_id,
                    item.source_section_id,
                    item.source_character_index,
                    item.source_sentence,
                    item.status,
                    item.mastery_level,
                    item.review_count,
                    item.correct_review_count,
                    item.wrong_review_count,
                    item.next_review_at.isoformat() if item.next_review_at else None,
                    item.last_reviewed_at.isoformat() if item.last_reviewed_at else None,
                    item.created_at.isoformat(timespec="seconds") if item.created_at else now_iso(),
                    item.updated_at.isoformat(timespec="seconds") if item.updated_at else now_iso(),
                    int(item.is_archived),
                ),
            )
            return self.get_item(int(cursor.lastrowid))  # type: ignore[return-value]

        connection.execute(
            """
            UPDATE vocabulary_items
            SET
                display_word = CASE WHEN display_word = '' THEN ? ELSE display_word END,
                source_article_id = COALESCE(source_article_id, ?),
                source_section_id = COALESCE(source_section_id, ?),
                source_character_index = COALESCE(source_character_index, ?),
                source_sentence = CASE WHEN source_sentence = '' THEN ? ELSE source_sentence END,
                is_archived = 0,
                updated_at = ?
            WHERE id = ?
            """,
            (
                item.display_word,
                item.source_article_id,
                item.source_section_id,
                item.source_character_index,
                item.source_sentence,
                now_iso(),
                existing.id,
            ),
        )
        return self.get_item(existing.id)  # type: ignore[return-value]

    def get_item(self, item_id: int) -> VocabularyItem | None:
        row = self._connection_provider().execute(
            "SELECT * FROM vocabulary_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        return self._row_to_vocabulary_item(row) if row else None

    def get_by_normalized_word(self, normalized_word: str) -> VocabularyItem | None:
        row = self._connection_provider().execute(
            "SELECT * FROM vocabulary_items WHERE normalized_word = ?",
            (normalized_word,),
        ).fetchone()
        return self._row_to_vocabulary_item(row) if row else None

    def list_items(
        self,
        *,
        search: str = "",
        status: str | None = None,
        archived: bool = False,
        due_on: date | None = None,
        limit: int = 500,
    ) -> list[VocabularyItem]:
        sql = "SELECT * FROM vocabulary_items WHERE is_archived = ?"
        params: list[object] = [int(archived)]
        if search.strip():
            sql += " AND (normalized_word LIKE ? OR display_word LIKE ? OR meaning LIKE ? OR note LIKE ?)"
            needle = f"%{search.strip()}%"
            params.extend([needle, needle, needle, needle])
        if status and status != "all":
            sql += " AND status = ?"
            params.append(status)
        if due_on is not None:
            sql += " AND next_review_at IS NOT NULL AND date(next_review_at) <= date(?)"
            params.append(due_on.isoformat())
        sql += " ORDER BY COALESCE(next_review_at, created_at) ASC, normalized_word ASC LIMIT ?"
        params.append(limit)
        rows = self._connection_provider().execute(sql, params).fetchall()
        return [self._row_to_vocabulary_item(row) for row in rows]

    def update_details(self, connection: sqlite3.Connection, item_id: int, meaning: str, note: str) -> None:
        connection.execute(
            """
            UPDATE vocabulary_items
            SET meaning = ?, note = ?, updated_at = ?
            WHERE id = ?
            """,
            (meaning, note, now_iso(), item_id),
        )

    def set_archived(self, connection: sqlite3.Connection, item_id: int, archived: bool) -> None:
        connection.execute(
            """
            UPDATE vocabulary_items
            SET is_archived = ?, updated_at = ?
            WHERE id = ?
            """,
            (int(archived), now_iso(), item_id),
        )

    def update_learning_state(
        self,
        connection: sqlite3.Connection,
        item_id: int,
        *,
        status: str,
        mastery_level: int,
        next_review_at: date | None,
        last_reviewed_at: date | None = None,
        review_count_delta: int = 0,
        correct_review_delta: int = 0,
        wrong_review_delta: int = 0,
    ) -> None:
        connection.execute(
            """
            UPDATE vocabulary_items
            SET
                status = ?,
                mastery_level = ?,
                next_review_at = ?,
                last_reviewed_at = COALESCE(?, last_reviewed_at),
                review_count = review_count + ?,
                correct_review_count = correct_review_count + ?,
                wrong_review_count = wrong_review_count + ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                mastery_level,
                next_review_at.isoformat() if next_review_at else None,
                last_reviewed_at.isoformat() if last_reviewed_at else None,
                review_count_delta,
                correct_review_delta,
                wrong_review_delta,
                now_iso(),
                item_id,
            ),
        )

    def due_summary(self, today: date) -> dict[str, int]:
        row = self._connection_provider().execute(
            """
            SELECT
                COUNT(CASE WHEN is_archived = 0 AND next_review_at IS NOT NULL AND date(next_review_at) <= date(?) THEN 1 END) AS due_count,
                COUNT(CASE WHEN is_archived = 0 AND next_review_at IS NOT NULL AND date(next_review_at) < date(?) THEN 1 END) AS overdue_count,
                COUNT(CASE WHEN is_archived = 0 AND status = 'new' THEN 1 END) AS new_count,
                COUNT(CASE WHEN is_archived = 0 AND status IN ('learning', 'reviewing') THEN 1 END) AS learning_count,
                COUNT(CASE WHEN is_archived = 0 AND status = 'mastered' THEN 1 END) AS mastered_count
            FROM vocabulary_items
            """,
            (today.isoformat(), today.isoformat()),
        ).fetchone()
        return {
            "due_count": row["due_count"],
            "overdue_count": row["overdue_count"],
            "new_count": row["new_count"],
            "learning_count": row["learning_count"],
            "mastered_count": row["mastered_count"],
        }

    def count_error_occurrences(self, normalized_word: str) -> int:
        row = self._connection_provider().execute(
            """
            SELECT COUNT(*) AS error_count
            FROM typing_errors
            WHERE lower(target_word) = ?
            """,
            (normalized_word,),
        ).fetchone()
        return int(row["error_count"]) if row else 0

    def _row_to_vocabulary_item(self, row: sqlite3.Row) -> VocabularyItem:
        return VocabularyItem(
            id=row["id"],
            normalized_word=row["normalized_word"],
            display_word=row["display_word"],
            meaning=row["meaning"],
            note=row["note"],
            source_article_id=row["source_article_id"],
            source_section_id=row["source_section_id"],
            source_character_index=row["source_character_index"],
            source_sentence=row["source_sentence"],
            status=row["status"],
            mastery_level=row["mastery_level"],
            review_count=row["review_count"],
            correct_review_count=row["correct_review_count"],
            wrong_review_count=row["wrong_review_count"],
            next_review_at=date.fromisoformat(row["next_review_at"]) if row["next_review_at"] else None,
            last_reviewed_at=date.fromisoformat(row["last_reviewed_at"]) if row["last_reviewed_at"] else None,
            created_at=parse_datetime(row["created_at"]),
            updated_at=parse_datetime(row["updated_at"]),
            is_archived=bool(row["is_archived"]),
        )


class SettingsRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def get_all(self) -> dict[str, str]:
        rows = self._connection_provider().execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}

    def set_many(self, connection: sqlite3.Connection, values: dict[str, str]) -> None:
        connection.executemany(
            """
            INSERT INTO settings(key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            [(key, value, now_iso()) for key, value in values.items()],
        )
