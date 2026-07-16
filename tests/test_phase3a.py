import sqlite3
from datetime import date, datetime
from pathlib import Path

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.database.repositories import PracticeRepository
from english_typing_trainer.models.practice import PracticeSessionRecord, TypingErrorEventRecord
from english_typing_trainer.services.app_paths import AppPathService
from english_typing_trainer.typing_engine.session import TypingSession
from english_typing_trainer.typing_engine.text_analysis import (
    classify_error,
    extract_target_word,
)


def _create_v1_database(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    runner = MigrationRunner()
    runner._apply_version_1(connection)
    connection.commit()
    return connection


def test_migration_upgrades_v1_to_v2_and_preserves_data(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = _create_v1_database(db_path)
    connection.execute(
        """
        INSERT INTO articles(title, original_filename, source_path, content_hash, full_text, character_count, word_count, section_count, imported_at, is_deleted)
        VALUES ('Lesson', 'lesson.txt', 'C:/lesson.txt', 'hash1', 'hello', 5, 1, 1, '2026-01-01T10:00:00', 0)
        """
    )
    connection.execute(
        """
        INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds,
        total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate, completed, created_at)
        VALUES (1, NULL, '2026-01-01T10:00:00', '2026-01-01T10:01:00', 60, 0, 50, 48, 2, 48, 48, 240, 96, 1.0, 1, '2026-01-01T10:01:00')
        """
    )
    connection.commit()

    MigrationRunner().migrate(connection)
    version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
    article_count = connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
    session_count = connection.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0]
    typing_errors_exists = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='typing_errors'"
    ).fetchone()

    assert version == 13
    assert article_count == 1
    assert session_count == 1
    assert typing_errors_exists is not None
    connection.close()


def test_repeat_migration_does_not_duplicate_schema_changes(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = _create_v1_database(db_path)
    MigrationRunner().migrate(connection)
    MigrationRunner().migrate(connection)
    columns = connection.execute("PRAGMA table_info(practice_sessions)").fetchall()
    column_names = [row[1] for row in columns]
    assert column_names.count("practice_type") == 1
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 13
    connection.close()


def test_migration_failure_rolls_back(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "legacy.db"
    connection = _create_v1_database(db_path)
    runner = MigrationRunner()

    def broken_apply_version_2(conn):
        conn.execute("CREATE TABLE IF NOT EXISTS typing_errors_broken(id INTEGER PRIMARY KEY)")
        raise RuntimeError("migration failed")

    monkeypatch.setattr(runner, "_apply_version_2", broken_apply_version_2)
    with pytest.raises(RuntimeError):
        runner.migrate(connection)

    version = connection.execute("SELECT version FROM schema_version").fetchone()[0]
    broken_table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='typing_errors_broken'"
    ).fetchone()
    assert version == 1
    assert broken_table is None
    connection.close()


def test_error_classification_rules() -> None:
    assert classify_error("A", "a") == "case_error"
    assert classify_error(" ", "x") == "space_error"
    assert classify_error("\n", "x") == "newline_error"
    assert classify_error(",", ".") == "punctuation_error"
    assert classify_error("e", "r") == "wrong_character"


def test_target_word_extraction_variants() -> None:
    text = "don't stop the well-known teacher's friend."
    assert extract_target_word(text, text.index("n")) == "don't"
    assert extract_target_word(text, text.index("k")) == "well-known"
    assert extract_target_word(text, text.index("r", text.index("teacher"))) == "teacher's"
    assert extract_target_word(text, text.index(".")) == ""
    assert extract_target_word("line one\nline two", 4) == ""


def test_consecutive_position_errors_are_all_recorded() -> None:
    session = TypingSession("ab")
    assert session.handle_character("x") is False
    assert session.handle_character("y") is False
    assert session.is_complete
    assert len(session.errors) == 2
    assert [error.position for error in session.errors] == [0, 1]

def test_session_and_errors_saved_together_and_not_duplicated(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "lesson.txt"
        file_path.write_text("Ab", encoding="utf-8")
        imported = context.article_library.import_txt_file(file_path, 300)
        material = context.practice_service.load_practice_material(imported.article.id)
        session = TypingSession(material.section_text)
        session.handle_character("a")
        session.handle_character("b")

        context.practice_service.save_completed_session(material, session, session.snapshot())
        context.practice_service.save_completed_session(material, session, session.snapshot())

        repo = PracticeRepository(context.database.connect)
        detail_session, errors = repo.get_session_detail(session.persisted_session_id)
        assert detail_session is not None
        assert len(errors) == 1
        assert errors[0]["error_type"] == "case_error"
    finally:
        context.database.close()


def test_history_filters_sorting_and_delete_cascade(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        connection = context.database.connect()
        connection.execute(
            "INSERT INTO articles(title, original_filename, source_path, content_hash, full_text, character_count, word_count, section_count, imported_at, is_deleted) VALUES ('A', 'a.txt', 'a', 'h1', 'text', 4, 1, 1, '2026-01-01T10:00:00', 0)"
        )
        connection.execute(
            "INSERT INTO articles(title, original_filename, source_path, content_hash, full_text, character_count, word_count, section_count, imported_at, is_deleted) VALUES ('B', 'b.txt', 'b', 'h2', 'text', 4, 1, 1, '2026-01-01T10:00:00', 0)"
        )
        connection.execute(
            "INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds, total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate, completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at) VALUES (1, NULL, '2026-01-10T10:00:00', '2026-01-10T10:01:00', 60, 0, 50, 48, 2, 48, 40, 200, 96, 1.0, 1, 'article_section', 12, 40, '0.1.0', '2026-01-10T10:01:00')"
        )
        connection.execute(
            "INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds, total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate, completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at) VALUES (2, NULL, '2026-01-11T10:00:00', NULL, 20, 0, 20, 10, 10, 10, 20, 60, 50, 0.5, 0, 'article_section', 3, NULL, '0.1.0', '2026-01-11T10:00:00')"
        )
        connection.execute(
            "INSERT INTO typing_errors(session_id, article_id, section_id, character_index, expected_character, actual_character, target_word, error_type, occurred_at) VALUES (1, 1, NULL, 0, 'e', 'r', 'example', 'wrong_character', '2026-01-10T10:00:30')"
        )
        connection.commit()

        rows = context.history_service.list_history(article_id=1, completed=True, order_by="wpm")
        assert len(rows) == 1
        assert rows[0]["article_title"] == "A"

        context.history_service.delete_session(1)
        errors_left = connection.execute("SELECT COUNT(*) FROM typing_errors").fetchone()[0]
        assert errors_left == 0
    finally:
        context.database.close()


def test_statistics_rules_and_trend_fill_zero(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        connection = context.database.connect()
        connection.execute(
            "INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds, total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate, completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at) VALUES (NULL, NULL, '2025-12-31T10:00:00', '2025-12-31T10:01:00', 60, 10, 50, 48, 2, 120, 80, 400, 96, 1.0, 1, 'article_section', 12, 80, '0.1.0', '2025-12-31T10:01:00')"
        )
        connection.execute(
            "INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds, total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate, completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at) VALUES (NULL, NULL, '2026-01-01T10:00:00', NULL, 20, 5, 20, 10, 10, 20, 60, 120, 50, 0.5, 0, 'article_section', 5, NULL, '0.1.0', '2026-01-01T10:00:00')"
        )
        connection.execute(
            "INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds, total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate, completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at) VALUES (NULL, NULL, '2026-01-02T10:00:00', '2026-01-02T10:00:10', 10, 0, 10, 10, 0, 30, 300, 600, 100, 1.0, 1, 'article_section', 10, 300, '0.1.0', '2026-01-02T10:00:10')"
        )
        connection.commit()

        overview = context.statistics_service.overview()
        assert overview["total_practice_seconds"] == 90
        assert overview["completed_sessions"] == 2
        assert overview["average_wpm"] == 80
        assert overview["highest_effective_wpm"] == 80

        trends = context.statistics_service.trend_data("7d")
        assert len(trends) == 7
        assert [row["date"] for row in trends] == sorted(row["date"] for row in trends)
    finally:
        context.database.close()


def test_default_localappdata_path_computation(monkeypatch) -> None:
    monkeypatch.delenv("ENGLISH_TYPING_TRAINER_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\TestUser\AppData\Local")
    paths = AppPathService().get_paths()
    assert str(paths.database_path) == r"C:\Users\TestUser\AppData\Local\EnglishStudio\typing_trainer.db"
