from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3

import pytest

from english_typing_trainer.courses.repository import CourseRepository
from english_typing_trainer.database.course_progress_repository import CourseProgressRepository
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.services.course_progress import (
    CourseContentNotFoundError,
    CourseEnrollmentNotFoundError,
    CourseProgressService,
    InvalidEnrollmentStatusError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COURSE_ID = "ai-large-models"
FIRST_ITEM = "ai-large-models-sentence-0001"


@dataclass
class MutableClock:
    value: datetime = datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: int = 60) -> None:
        self.value += timedelta(seconds=seconds)


@pytest.fixture()
def courses_root(tmp_path: Path) -> Path:
    destination = tmp_path / "courses"
    shutil.copytree(PROJECT_ROOT / "courses", destination)
    return destination


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unit_path(root: Path) -> Path:
    return root / "ai-large-models" / "units" / "unit-01-foundations.json"


def _course_path(root: Path) -> Path:
    return root / "ai-large-models" / "course.json"


def _service(
    tmp_path: Path,
    *,
    courses_root: Path | None = None,
    clock: MutableClock | None = None,
) -> tuple[DatabaseManager, CourseProgressService]:
    database = DatabaseManager(tmp_path / "typing_trainer.db")
    database.initialize()
    repository = CourseProgressRepository(database)
    return database, CourseProgressService(
        CourseRepository(courses_root),
        repository,
        now_provider=clock,
    )


def _create_schema_11(connection: sqlite3.Connection) -> MigrationRunner:
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner = MigrationRunner()
    for version in range(1, 12):
        getattr(runner, f"_apply_version_{version}")(connection)
    connection.commit()
    return runner


def test_schema_13_preserves_two_minimal_course_state_tables(tmp_path: Path) -> None:
    database = DatabaseManager(tmp_path / "fresh.db")
    database.initialize()
    try:
        connection = database.connect()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert database.get_schema_version() == 13
        assert {"course_enrollments", "course_item_progress"} <= tables
        assert "course_progress" not in tables
        assert "course_lesson_progress" not in tables
    finally:
        database.close()


def test_schema_11_upgrade_preserves_data_and_is_idempotent(tmp_path: Path) -> None:
    connection = sqlite3.connect(tmp_path / "legacy.db")
    _create_schema_11(connection)
    connection.execute(
        "UPDATE settings SET value = 'legacy-value' WHERE key = 'pronunciation_provider'"
    )
    connection.commit()

    MigrationRunner().migrate(connection)
    MigrationRunner().migrate(connection)

    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 13
    assert connection.execute(
        "SELECT value FROM settings WHERE key = 'pronunciation_provider'"
    ).fetchone()[0] == "legacy-value"
    assert connection.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'course_enrollments'"
    ).fetchone()[0] == 1
    connection.close()


def test_schema_12_failure_rolls_back_to_schema_11(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connection = sqlite3.connect(tmp_path / "legacy.db")
    runner = _create_schema_11(connection)

    def broken_migration(target: sqlite3.Connection) -> None:
        target.execute("CREATE TABLE partial_course_state(id INTEGER PRIMARY KEY)")
        raise RuntimeError("schema 12 failed")

    monkeypatch.setattr(runner, "_apply_version_12", broken_migration)
    with pytest.raises(RuntimeError, match="schema 12 failed"):
        runner.migrate(connection)

    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 11
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name = 'partial_course_state'"
    ).fetchone() is None
    connection.close()


def test_enrollment_is_sparse_idempotent_and_records_content_versions(tmp_path: Path) -> None:
    database, service = _service(tmp_path)
    try:
        assert service.get_enrollment(COURSE_ID) is None
        first = service.enroll(COURSE_ID)
        second = service.enroll(COURSE_ID)

        assert first.course_stable_key == "ai-large-models-course"
        assert first.status == second.status == "active"
        assert first.course_version == second.course_version == "0.1.0"
        assert first.content_version == second.content_version == "0.1.0"
        assert second.current_lesson_stable_key == "ai-large-models-lesson-interface-actions-one"
        connection = database.connect()
        assert connection.execute("SELECT COUNT(*) FROM course_enrollments").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM course_item_progress").fetchone()[0] == 0
    finally:
        database.close()


def test_enrollment_statuses_are_explicit_and_history_is_not_deleted(tmp_path: Path) -> None:
    database, service = _service(tmp_path)
    try:
        service.enroll(COURSE_ID)
        for status in ("paused", "completed", "archived", "active"):
            assert service.set_enrollment_status(COURSE_ID, status).status == status
            assert database.connect().execute(
                "SELECT COUNT(*) FROM course_enrollments"
            ).fetchone()[0] == 1
        with pytest.raises(InvalidEnrollmentStatusError):
            service.set_enrollment_status(COURSE_ID, "deleted")  # type: ignore[arg-type]
    finally:
        database.close()

    other_database, other_service = _service(tmp_path / "other")
    try:
        with pytest.raises(CourseEnrollmentNotFoundError):
            other_service.set_enrollment_status(COURSE_ID, "paused")
    finally:
        other_database.close()


def test_item_start_complete_skip_scores_and_timestamps(tmp_path: Path) -> None:
    clock = MutableClock()
    database, service = _service(tmp_path, clock=clock)
    try:
        untouched = service.get_item_progress(COURSE_ID, FIRST_ITEM)
        assert untouched.status == "not_started"
        assert untouched.created_at is None
        assert service.get_enrollment(COURSE_ID) is None

        started = service.start_item(COURSE_ID, FIRST_ITEM)
        assert started.status == "in_progress"
        assert started.attempt_count == 1
        assert started.first_started_at == clock.value
        assert service.get_enrollment(COURSE_ID) is not None

        clock.advance()
        restarted = service.start_item(COURSE_ID, FIRST_ITEM)
        assert restarted.attempt_count == 2
        assert restarted.first_started_at == started.first_started_at

        clock.advance()
        completed = service.complete_item(COURSE_ID, FIRST_ITEM, score=82.0)
        completed_at = completed.completed_at
        assert completed.status == "completed"
        assert completed.attempt_count == 2
        assert completed.best_score == completed.latest_score == 82.0
        assert completed_at == clock.value

        clock.advance()
        repeated = service.complete_item(COURSE_ID, FIRST_ITEM, score=75.0)
        assert repeated.attempt_count == 2
        assert repeated.best_score == 82.0
        assert repeated.latest_score == 75.0
        assert repeated.completed_at == completed_at

        skipped = service.skip_item(COURSE_ID, "ai-large-models-sentence-0002")
        assert skipped.status == "skipped"
        assert skipped.attempt_count == 0
        assert skipped.first_started_at is None
        assert service.get_course_progress(COURSE_ID).completion_percentage == pytest.approx(8.33)
    finally:
        database.close()


def test_invalid_course_hierarchy_and_item_keys_raise_clear_errors(tmp_path: Path) -> None:
    database, service = _service(tmp_path)
    try:
        with pytest.raises(CourseContentNotFoundError, match="Course not found"):
            service.get_course_progress("missing-course")
        with pytest.raises(CourseContentNotFoundError, match="Unit not found"):
            service.get_unit_progress(COURSE_ID, "missing-unit")
        with pytest.raises(CourseContentNotFoundError, match="Lesson not found"):
            service.get_lesson_progress(COURSE_ID, "missing-lesson")
        with pytest.raises(CourseContentNotFoundError, match="Learning item not found"):
            service.start_item(COURSE_ID, "missing-stable-key")
    finally:
        database.close()


def test_lesson_unit_and_course_progress_are_derived_from_required_items(tmp_path: Path) -> None:
    database, service = _service(tmp_path)
    try:
        for number in range(1, 7):
            service.complete_item(COURSE_ID, f"ai-large-models-sentence-{number:04d}")

        lesson = service.get_lesson_progress(COURSE_ID, "ai-l1-u01-d01")
        unit = service.get_unit_progress(COURSE_ID, "ai-l1-u01")
        course = service.get_course_progress(COURSE_ID)
        assert (lesson.completed_required_items, lesson.total_required_items) == (6, 6)
        assert lesson.is_completed and lesson.completion_percentage == 100.0
        assert (unit.completed_required_items, unit.total_required_items) == (6, 12)
        assert unit.completion_percentage == 50.0
        assert course.completion_percentage == 50.0

        connection = database.connect()
        assert connection.execute("SELECT COUNT(*) FROM course_item_progress").fetchone()[0] == 6
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(course_item_progress)")
        }
        assert {
            "course_stable_key",
            "unit_stable_key",
            "lesson_stable_key",
            "item_stable_key",
        } <= columns
        assert "english" not in columns and "sentence_text" not in columns
    finally:
        database.close()


def test_optional_deprecated_new_and_reordered_items_use_current_json(
    tmp_path: Path,
    courses_root: Path,
) -> None:
    database, service = _service(tmp_path / "state", courses_root=courses_root)
    try:
        service.complete_item(COURSE_ID, FIRST_ITEM)
        assert service.get_course_progress(COURSE_ID).total_required_items == 12

        unit_path = _unit_path(courses_root)
        unit = _read_json(unit_path)
        first, second = unit["sentences"][0], unit["sentences"][1]
        first["order"], second["order"] = second["order"], first["order"]
        new_item = dict(unit["sentences"][-1])
        new_item.update(
            {
                "sentence_id": "ai-s0013",
                "stable_key": "ai-large-models-sentence-0013",
                "order": 7,
                "english": "Use a new stable key when the meaning changes.",
                "chinese": "语义变化时使用新的稳定键。",
                "content_version": "0.2.0",
            }
        )
        unit["sentences"].append(new_item)
        unit["lessons"][1]["new_sentence_ids"].append("ai-s0013")
        unit["lessons"][1]["activities"][0]["sentence_ids"].append("ai-s0013")
        _write_json(unit_path, unit)
        course_document = _read_json(_course_path(courses_root))
        course_document["content_version"] = "0.2.0"
        course_document["estimated_sentences"] = 13
        _write_json(_course_path(courses_root), course_document)

        upgraded = CourseProgressService(
            CourseRepository(courses_root),
            CourseProgressRepository(database),
        )
        current = upgraded.get_course_progress(COURSE_ID)
        historical = upgraded.get_item_progress(COURSE_ID, FIRST_ITEM)
        assert current.total_required_items == 13
        assert current.completed_required_items == 1
        assert current.completion_percentage == pytest.approx(7.69)
        assert historical.status == "completed"
        assert database.connect().execute(
            "SELECT COUNT(*) FROM course_item_progress WHERE item_stable_key = ?",
            (FIRST_ITEM,),
        ).fetchone()[0] == 1

        unit = _read_json(unit_path)
        unit["sentences"][0]["status"] = "deprecated"
        _write_json(unit_path, unit)
        deprecated = CourseProgressService(
            CourseRepository(courses_root),
            CourseProgressRepository(database),
        )
        current = deprecated.get_course_progress(COURSE_ID)
        assert current.total_required_items == 12
        assert current.completed_required_items == 0
        assert deprecated.get_item_progress(COURSE_ID, FIRST_ITEM).status == "completed"

        deprecated.start_item(COURSE_ID, "ai-large-models-sentence-0013")
        assert deprecated.get_enrollment(COURSE_ID).content_version == "0.2.0"  # type: ignore[union-attr]
    finally:
        database.close()


def test_optional_items_and_empty_lessons_have_explicit_behavior(
    tmp_path: Path,
    courses_root: Path,
) -> None:
    unit_path = _unit_path(courses_root)
    unit = _read_json(unit_path)
    unit["lessons"][0]["activities"][0]["sentence_ids"].remove("ai-s0006")
    _write_json(unit_path, unit)

    database, service = _service(tmp_path / "optional", courses_root=courses_root)
    try:
        assert service.get_course_progress(COURSE_ID).total_required_items == 11
    finally:
        database.close()

    unit = _read_json(unit_path)
    for activity in unit["lessons"][0]["activities"]:
        activity["required"] = False
    _write_json(unit_path, unit)
    empty_database, empty_service = _service(tmp_path / "empty", courses_root=courses_root)
    try:
        progress = empty_service.get_lesson_progress(COURSE_ID, "ai-l1-u01-d01")
        assert progress.total_required_items == 0
        assert progress.completion_percentage == 0.0
        assert not progress.is_completed
        assert empty_service.get_next_lesson(COURSE_ID).lesson_id == "ai-l1-u01-d02"  # type: ignore[union-attr]
    finally:
        empty_database.close()


def test_next_lesson_and_item_for_new_partial_skipped_complete_and_paused_users(
    tmp_path: Path,
) -> None:
    database, service = _service(tmp_path)
    try:
        assert service.get_next_lesson(COURSE_ID).lesson_id == "ai-l1-u01-d01"  # type: ignore[union-attr]
        assert service.get_next_required_item(COURSE_ID).stable_key == FIRST_ITEM  # type: ignore[union-attr]
        assert service.get_enrollment(COURSE_ID) is None

        service.complete_item(COURSE_ID, FIRST_ITEM)
        assert service.get_next_required_item(COURSE_ID).stable_key.endswith("0002")  # type: ignore[union-attr]

        for number in range(2, 7):
            service.skip_item(COURSE_ID, f"ai-large-models-sentence-{number:04d}")
        assert service.get_lesson_progress(COURSE_ID, "ai-l1-u01-d01").completion_percentage == pytest.approx(16.67)
        assert service.get_next_lesson(COURSE_ID).lesson_id == "ai-l1-u01-d02"  # type: ignore[union-attr]
        assert service.get_next_required_item(COURSE_ID).stable_key.endswith("0007")  # type: ignore[union-attr]

        service.set_enrollment_status(COURSE_ID, "paused")
        assert service.get_next_lesson(COURSE_ID) is None
        assert service.get_next_required_item(COURSE_ID) is None
        service.set_enrollment_status(COURSE_ID, "archived")
        assert service.get_next_lesson(COURSE_ID) is None
        service.set_enrollment_status(COURSE_ID, "active")

        for number in range(2, 13):
            service.complete_item(COURSE_ID, f"ai-large-models-sentence-{number:04d}")
        assert service.get_course_progress(COURSE_ID).is_completed
        assert service.get_next_lesson(COURSE_ID) is None
        assert service.get_next_required_item(COURSE_ID) is None
        assert service.get_enrollment(COURSE_ID).status == "completed"  # type: ignore[union-attr]
    finally:
        database.close()
