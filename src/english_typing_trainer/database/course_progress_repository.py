from __future__ import annotations

from datetime import datetime
import sqlite3
from typing import cast

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.models.course_progress import (
    CourseEnrollment,
    CourseItemProgress,
    EnrollmentStatus,
    ItemProgressStatus,
)


class CourseProgressRepository:
    """SQLite persistence for sparse user state; never stores course body content."""

    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def get_enrollment(self, course_stable_key: str) -> CourseEnrollment | None:
        row = self.database.connect().execute(
            "SELECT * FROM course_enrollments WHERE course_stable_key = ?",
            (course_stable_key,),
        ).fetchone()
        return self._map_enrollment(row) if row is not None else None

    def enroll(
        self,
        *,
        course_stable_key: str,
        course_version: str,
        content_version: str,
        current_lesson_stable_key: str | None,
        now: datetime,
    ) -> CourseEnrollment:
        stamp = self._serialize_datetime(now)
        with self.database.transaction() as connection:
            connection.execute(
                """
                INSERT INTO course_enrollments(
                    course_stable_key, status, current_lesson_stable_key,
                    course_version, content_version, enrolled_at, last_studied_at,
                    created_at, updated_at
                ) VALUES (?, 'active', ?, ?, ?, ?, NULL, ?, ?)
                ON CONFLICT(course_stable_key) DO UPDATE SET
                    current_lesson_stable_key = excluded.current_lesson_stable_key,
                    course_version = excluded.course_version,
                    content_version = excluded.content_version,
                    updated_at = excluded.updated_at
                """,
                (
                    course_stable_key,
                    current_lesson_stable_key,
                    course_version,
                    content_version,
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            row = connection.execute(
                "SELECT * FROM course_enrollments WHERE course_stable_key = ?",
                (course_stable_key,),
            ).fetchone()
        assert row is not None
        return self._map_enrollment(row)

    def set_enrollment_status(
        self,
        course_stable_key: str,
        status: EnrollmentStatus,
        now: datetime,
    ) -> CourseEnrollment | None:
        stamp = self._serialize_datetime(now)
        with self.database.transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE course_enrollments
                SET status = ?, updated_at = ?
                WHERE course_stable_key = ?
                """,
                (status, stamp, course_stable_key),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                "SELECT * FROM course_enrollments WHERE course_stable_key = ?",
                (course_stable_key,),
            ).fetchone()
        assert row is not None
        return self._map_enrollment(row)

    def record_activity(
        self,
        *,
        course_stable_key: str,
        course_version: str,
        content_version: str,
        current_lesson_stable_key: str | None,
        now: datetime,
        status: EnrollmentStatus | None = None,
    ) -> CourseEnrollment:
        stamp = self._serialize_datetime(now)
        status_sql = "status = ?," if status is not None else ""
        parameters: list[object] = []
        if status is not None:
            parameters.append(status)
        parameters.extend(
            [
                current_lesson_stable_key,
                course_version,
                content_version,
                stamp,
                stamp,
                course_stable_key,
            ]
        )
        with self.database.transaction() as connection:
            cursor = connection.execute(
                f"""
                UPDATE course_enrollments SET
                    {status_sql}
                    current_lesson_stable_key = ?,
                    course_version = ?,
                    content_version = ?,
                    last_studied_at = ?,
                    updated_at = ?
                WHERE course_stable_key = ?
                """,
                tuple(parameters),
            )
            if cursor.rowcount == 0:
                raise RuntimeError(f"Missing enrollment for {course_stable_key!r}")
            row = connection.execute(
                "SELECT * FROM course_enrollments WHERE course_stable_key = ?",
                (course_stable_key,),
            ).fetchone()
        assert row is not None
        return self._map_enrollment(row)

    def get_item_progress(
        self,
        course_stable_key: str,
        item_stable_key: str,
    ) -> CourseItemProgress | None:
        row = self.database.connect().execute(
            """
            SELECT * FROM course_item_progress
            WHERE course_stable_key = ? AND item_stable_key = ?
            """,
            (course_stable_key, item_stable_key),
        ).fetchone()
        return self._map_item_progress(row) if row is not None else None

    def list_item_progress(self, course_stable_key: str) -> tuple[CourseItemProgress, ...]:
        rows = self.database.connect().execute(
            """
            SELECT * FROM course_item_progress
            WHERE course_stable_key = ? ORDER BY id
            """,
            (course_stable_key,),
        ).fetchall()
        return tuple(self._map_item_progress(row) for row in rows)

    def save_item_progress(self, progress: CourseItemProgress, now: datetime) -> CourseItemProgress:
        stamp = self._serialize_datetime(now)
        created_at = self._serialize_datetime(progress.created_at or now)
        with self.database.transaction() as connection:
            enrollment = connection.execute(
                "SELECT id FROM course_enrollments WHERE course_stable_key = ?",
                (progress.course_stable_key,),
            ).fetchone()
            if enrollment is None:
                raise RuntimeError(f"Missing enrollment for {progress.course_stable_key!r}")
            connection.execute(
                """
                INSERT INTO course_item_progress(
                    enrollment_id, course_stable_key, unit_stable_key,
                    lesson_stable_key, item_stable_key, item_type, status,
                    attempt_count, best_score, latest_score, first_started_at,
                    completed_at, last_studied_at, content_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(enrollment_id, item_stable_key) DO UPDATE SET
                    course_stable_key = excluded.course_stable_key,
                    unit_stable_key = excluded.unit_stable_key,
                    lesson_stable_key = excluded.lesson_stable_key,
                    item_type = excluded.item_type,
                    status = excluded.status,
                    attempt_count = excluded.attempt_count,
                    best_score = excluded.best_score,
                    latest_score = excluded.latest_score,
                    first_started_at = COALESCE(
                        course_item_progress.first_started_at,
                        excluded.first_started_at
                    ),
                    completed_at = COALESCE(
                        course_item_progress.completed_at,
                        excluded.completed_at
                    ),
                    last_studied_at = excluded.last_studied_at,
                    content_version = excluded.content_version,
                    updated_at = excluded.updated_at
                """,
                (
                    int(enrollment["id"]),
                    progress.course_stable_key,
                    progress.unit_stable_key,
                    progress.lesson_stable_key,
                    progress.item_stable_key,
                    progress.item_type,
                    progress.status,
                    progress.attempt_count,
                    progress.best_score,
                    progress.latest_score,
                    self._serialize_optional_datetime(progress.first_started_at),
                    self._serialize_optional_datetime(progress.completed_at),
                    self._serialize_optional_datetime(progress.last_studied_at),
                    progress.content_version,
                    created_at,
                    stamp,
                ),
            )
            row = connection.execute(
                """
                SELECT * FROM course_item_progress
                WHERE enrollment_id = ? AND item_stable_key = ?
                """,
                (int(enrollment["id"]), progress.item_stable_key),
            ).fetchone()
        assert row is not None
        return self._map_item_progress(row)

    @classmethod
    def _map_enrollment(cls, row: sqlite3.Row) -> CourseEnrollment:
        return CourseEnrollment(
            course_stable_key=str(row["course_stable_key"]),
            status=cast(EnrollmentStatus, str(row["status"])),
            current_lesson_stable_key=row["current_lesson_stable_key"],
            course_version=str(row["course_version"]),
            content_version=str(row["content_version"]),
            enrolled_at=cls._parse_datetime(row["enrolled_at"]),
            last_studied_at=cls._parse_optional_datetime(row["last_studied_at"]),
            created_at=cls._parse_datetime(row["created_at"]),
            updated_at=cls._parse_datetime(row["updated_at"]),
        )

    @classmethod
    def _map_item_progress(cls, row: sqlite3.Row) -> CourseItemProgress:
        return CourseItemProgress(
            course_stable_key=str(row["course_stable_key"]),
            unit_stable_key=str(row["unit_stable_key"]),
            lesson_stable_key=str(row["lesson_stable_key"]),
            item_stable_key=str(row["item_stable_key"]),
            item_type=str(row["item_type"]),
            status=cast(ItemProgressStatus, str(row["status"])),
            attempt_count=int(row["attempt_count"]),
            best_score=float(row["best_score"]) if row["best_score"] is not None else None,
            latest_score=float(row["latest_score"]) if row["latest_score"] is not None else None,
            first_started_at=cls._parse_optional_datetime(row["first_started_at"]),
            completed_at=cls._parse_optional_datetime(row["completed_at"]),
            last_studied_at=cls._parse_optional_datetime(row["last_studied_at"]),
            content_version=str(row["content_version"]),
            created_at=cls._parse_datetime(row["created_at"]),
            updated_at=cls._parse_datetime(row["updated_at"]),
        )

    @staticmethod
    def _serialize_datetime(value: datetime) -> str:
        return value.isoformat(timespec="seconds")

    @classmethod
    def _serialize_optional_datetime(cls, value: datetime | None) -> str | None:
        return cls._serialize_datetime(value) if value is not None else None

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        return datetime.fromisoformat(value)

    @classmethod
    def _parse_optional_datetime(cls, value: str | None) -> datetime | None:
        return cls._parse_datetime(value) if value is not None else None
