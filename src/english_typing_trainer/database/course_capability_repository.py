from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
from typing import cast

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.models.learning_content import (
    CourseCapabilityAttempt,
    CourseCapabilityStatus,
    CourseCapabilityType,
    CourseReviewCard,
    CourseReviewCardType,
    CourseReviewLog,
)


class CourseCapabilityRepository:
    """Persist course capability state without storing built-in course body text."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def add_attempt(self, attempt: CourseCapabilityAttempt) -> CourseCapabilityAttempt:
        with self.database.transaction() as connection:
            enrollment_id = self._require_enrollment_id(
                connection, attempt.course_stable_key
            )
            cursor = connection.execute(
                """
                INSERT INTO course_capability_attempts(
                    enrollment_id, item_stable_key, capability_type, status,
                    score, accuracy_score, fluency_score, completeness_score,
                    prosody_score, error_count, omitted_count, inserted_count,
                    replay_count, duration_ms, provider, content_version,
                    attempted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    enrollment_id,
                    attempt.item_stable_key,
                    attempt.capability_type,
                    attempt.status,
                    attempt.score,
                    attempt.accuracy_score,
                    attempt.fluency_score,
                    attempt.completeness_score,
                    attempt.prosody_score,
                    attempt.error_count,
                    attempt.omitted_count,
                    attempt.inserted_count,
                    attempt.replay_count,
                    attempt.duration_ms,
                    attempt.provider,
                    attempt.content_version,
                    self._iso(attempt.attempted_at),
                ),
            )
            row = connection.execute(
                """
                SELECT a.*, e.course_stable_key
                FROM course_capability_attempts a
                JOIN course_enrollments e ON e.id = a.enrollment_id
                WHERE a.id = ?
                """,
                (int(cursor.lastrowid),),
            ).fetchone()
        assert row is not None
        return self._map_attempt(row)

    def list_attempts(
        self,
        course_stable_key: str,
        item_stable_key: str,
        capability_type: CourseCapabilityType | None = None,
    ) -> tuple[CourseCapabilityAttempt, ...]:
        sql = """
            SELECT a.*, e.course_stable_key
            FROM course_capability_attempts a
            JOIN course_enrollments e ON e.id = a.enrollment_id
            WHERE e.course_stable_key = ? AND a.item_stable_key = ?
        """
        parameters: list[object] = [course_stable_key, item_stable_key]
        if capability_type is not None:
            sql += " AND a.capability_type = ?"
            parameters.append(capability_type)
        sql += " ORDER BY a.attempted_at, a.id"
        rows = self.database.connect().execute(sql, parameters).fetchall()
        return tuple(self._map_attempt(row) for row in rows)

    def get_review_card(
        self,
        course_stable_key: str,
        item_stable_key: str,
        card_type: CourseReviewCardType,
    ) -> CourseReviewCard | None:
        row = self.database.connect().execute(
            """
            SELECT c.*, e.course_stable_key
            FROM course_review_cards c
            JOIN course_enrollments e ON e.id = c.enrollment_id
            WHERE e.course_stable_key = ?
              AND c.item_stable_key = ?
              AND c.card_type = ?
            """,
            (course_stable_key, item_stable_key, card_type),
        ).fetchone()
        return self._map_review_card(row) if row is not None else None

    def get_review_card_by_id(self, card_id: int) -> CourseReviewCard | None:
        row = self.database.connect().execute(
            """
            SELECT c.*, e.course_stable_key
            FROM course_review_cards c
            JOIN course_enrollments e ON e.id = c.enrollment_id
            WHERE c.id = ?
            """,
            (card_id,),
        ).fetchone()
        return self._map_review_card(row) if row is not None else None

    def create_review_card(
        self, card: CourseReviewCard, now: datetime
    ) -> CourseReviewCard:
        stamp = self._iso(now)
        with self.database.transaction() as connection:
            enrollment_id = self._require_enrollment_id(
                connection, card.course_stable_key
            )
            connection.execute(
                """
                INSERT OR IGNORE INTO course_review_cards(
                    enrollment_id, item_stable_key, card_type, fsrs_card_json,
                    due_at_utc, last_reviewed_at_utc, state, is_suspended,
                    content_version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    enrollment_id,
                    card.item_stable_key,
                    card.card_type,
                    card.fsrs_card_json,
                    self._iso(card.due_at_utc),
                    self._optional_iso(card.last_reviewed_at_utc),
                    card.state,
                    int(card.is_suspended),
                    card.content_version,
                    stamp,
                    stamp,
                ),
            )
            row = connection.execute(
                """
                SELECT c.*, e.course_stable_key
                FROM course_review_cards c
                JOIN course_enrollments e ON e.id = c.enrollment_id
                WHERE c.enrollment_id = ?
                  AND c.item_stable_key = ?
                  AND c.card_type = ?
                """,
                (enrollment_id, card.item_stable_key, card.card_type),
            ).fetchone()
        assert row is not None
        return self._map_review_card(row)

    def update_review_card(
        self, card: CourseReviewCard, now: datetime
    ) -> CourseReviewCard:
        if card.id is None:
            raise ValueError("Course review card must be persisted before update.")
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE course_review_cards SET
                    fsrs_card_json = ?, due_at_utc = ?,
                    last_reviewed_at_utc = ?, state = ?, is_suspended = ?,
                    content_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    card.fsrs_card_json,
                    self._iso(card.due_at_utc),
                    self._optional_iso(card.last_reviewed_at_utc),
                    card.state,
                    int(card.is_suspended),
                    card.content_version,
                    self._iso(now),
                    card.id,
                ),
            )
            row = connection.execute(
                """
                SELECT c.*, e.course_stable_key
                FROM course_review_cards c
                JOIN course_enrollments e ON e.id = c.enrollment_id
                WHERE c.id = ?
                """,
                (card.id,),
            ).fetchone()
        if row is None:
            raise ValueError("Course review card does not exist.")
        return self._map_review_card(row)

    def list_due_review_cards(
        self, now: datetime, limit: int = 100
    ) -> tuple[CourseReviewCard, ...]:
        rows = self.database.connect().execute(
            """
            SELECT c.*, e.course_stable_key
            FROM course_review_cards c
            JOIN course_enrollments e ON e.id = c.enrollment_id
            WHERE c.is_suspended = 0 AND c.due_at_utc <= ?
            ORDER BY c.due_at_utc, c.id
            LIMIT ?
            """,
            (self._iso(now), max(0, limit)),
        ).fetchall()
        return tuple(self._map_review_card(row) for row in rows)

    def add_review_log(
        self, log: CourseReviewLog, now: datetime
    ) -> CourseReviewLog:
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                INSERT INTO course_review_logs(
                    course_review_card_id, rating, review_log_json,
                    previous_card_json, reviewed_at_utc, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    log.course_review_card_id,
                    log.rating,
                    log.review_log_json,
                    log.previous_card_json,
                    self._iso(log.reviewed_at_utc),
                    self._iso(now),
                ),
            )
            row = connection.execute(
                "SELECT * FROM course_review_logs WHERE id = ?",
                (int(cursor.lastrowid),),
            ).fetchone()
        assert row is not None
        return self._map_review_log(row)

    def save_review(
        self,
        card: CourseReviewCard,
        log: CourseReviewLog,
        now: datetime,
    ) -> tuple[CourseReviewCard, CourseReviewLog]:
        if card.id is None:
            raise ValueError("Course review card must be persisted before review.")
        with self.database.transaction() as connection:
            connection.execute(
                """
                UPDATE course_review_cards SET
                    fsrs_card_json = ?, due_at_utc = ?,
                    last_reviewed_at_utc = ?, state = ?, is_suspended = ?,
                    content_version = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    card.fsrs_card_json,
                    self._iso(card.due_at_utc),
                    self._optional_iso(card.last_reviewed_at_utc),
                    card.state,
                    int(card.is_suspended),
                    card.content_version,
                    self._iso(now),
                    card.id,
                ),
            )
            cursor = connection.execute(
                """
                INSERT INTO course_review_logs(
                    course_review_card_id, rating, review_log_json,
                    previous_card_json, reviewed_at_utc, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    log.course_review_card_id,
                    log.rating,
                    log.review_log_json,
                    log.previous_card_json,
                    self._iso(log.reviewed_at_utc),
                    self._iso(now),
                ),
            )
            card_row = connection.execute(
                """
                SELECT c.*, e.course_stable_key
                FROM course_review_cards c
                JOIN course_enrollments e ON e.id = c.enrollment_id
                WHERE c.id = ?
                """,
                (card.id,),
            ).fetchone()
            log_row = connection.execute(
                "SELECT * FROM course_review_logs WHERE id = ?",
                (int(cursor.lastrowid),),
            ).fetchone()
        if card_row is None or log_row is None:
            raise RuntimeError("Course review transaction did not persist its result.")
        return self._map_review_card(card_row), self._map_review_log(log_row)

    def list_review_logs(self, card_id: int) -> tuple[CourseReviewLog, ...]:
        rows = self.database.connect().execute(
            """
            SELECT * FROM course_review_logs
            WHERE course_review_card_id = ?
            ORDER BY reviewed_at_utc, id
            """,
            (card_id,),
        ).fetchall()
        return tuple(self._map_review_log(row) for row in rows)

    @staticmethod
    def _require_enrollment_id(
        connection: sqlite3.Connection, course_stable_key: str
    ) -> int:
        row = connection.execute(
            "SELECT id FROM course_enrollments WHERE course_stable_key = ?",
            (course_stable_key,),
        ).fetchone()
        if row is None:
            raise RuntimeError(f"Missing enrollment for {course_stable_key!r}")
        return int(row["id"])

    @classmethod
    def _map_attempt(cls, row: sqlite3.Row) -> CourseCapabilityAttempt:
        return CourseCapabilityAttempt(
            id=int(row["id"]),
            course_stable_key=str(row["course_stable_key"]),
            item_stable_key=str(row["item_stable_key"]),
            capability_type=cast(CourseCapabilityType, str(row["capability_type"])),
            status=cast(CourseCapabilityStatus, str(row["status"])),
            score=cls._optional_float(row["score"]),
            accuracy_score=cls._optional_float(row["accuracy_score"]),
            fluency_score=cls._optional_float(row["fluency_score"]),
            completeness_score=cls._optional_float(row["completeness_score"]),
            prosody_score=cls._optional_float(row["prosody_score"]),
            error_count=int(row["error_count"]),
            omitted_count=int(row["omitted_count"]),
            inserted_count=int(row["inserted_count"]),
            replay_count=int(row["replay_count"]),
            duration_ms=int(row["duration_ms"]),
            provider=str(row["provider"]),
            content_version=str(row["content_version"]),
            attempted_at=cls._datetime(row["attempted_at"]),
        )

    @classmethod
    def _map_review_card(cls, row: sqlite3.Row) -> CourseReviewCard:
        return CourseReviewCard(
            id=int(row["id"]),
            course_stable_key=str(row["course_stable_key"]),
            item_stable_key=str(row["item_stable_key"]),
            card_type=cast(CourseReviewCardType, str(row["card_type"])),
            fsrs_card_json=str(row["fsrs_card_json"]),
            due_at_utc=cls._datetime(row["due_at_utc"]),
            last_reviewed_at_utc=cls._optional_datetime(
                row["last_reviewed_at_utc"]
            ),
            state=str(row["state"]),
            is_suspended=bool(row["is_suspended"]),
            content_version=str(row["content_version"]),
            created_at=cls._datetime(row["created_at"]),
            updated_at=cls._datetime(row["updated_at"]),
        )

    @classmethod
    def _map_review_log(cls, row: sqlite3.Row) -> CourseReviewLog:
        return CourseReviewLog(
            id=int(row["id"]),
            course_review_card_id=int(row["course_review_card_id"]),
            rating=str(row["rating"]),
            review_log_json=str(row["review_log_json"]),
            previous_card_json=str(row["previous_card_json"]),
            reviewed_at_utc=cls._datetime(row["reviewed_at_utc"]),
            created_at=cls._datetime(row["created_at"]),
        )

    @staticmethod
    def _optional_float(value: object) -> float | None:
        return float(value) if value is not None else None

    @staticmethod
    def _iso(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")

    @classmethod
    def _optional_iso(cls, value: datetime | None) -> str | None:
        return cls._iso(value) if value is not None else None

    @staticmethod
    def _datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @classmethod
    def _optional_datetime(cls, value: str | None) -> datetime | None:
        return cls._datetime(value) if value else None
