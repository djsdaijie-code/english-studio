from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.database.repositories import PracticeRepository, PracticeSetRepository, VocabularyRepository
from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.vocabulary import VocabularyItem
from english_typing_trainer.services.review_planning import ReviewPlanningService
from english_typing_trainer.services.word_normalization import WordNormalizationService
from english_typing_trainer.typing_engine.session import TypingSession


def _create_v2_database(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    runner = MigrationRunner()
    connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    runner._apply_version_1(connection)
    runner._apply_version_2(connection)
    connection.commit()
    return connection


def test_v2_database_upgrades_to_v3_and_preserves_existing_data(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy_v2.db"
    connection = _create_v2_database(db_path)
    connection.execute(
        """
        INSERT INTO articles(title, original_filename, source_path, content_hash, full_text, character_count, word_count, section_count, imported_at, is_deleted)
        VALUES ('Legacy', 'legacy.txt', 'C:/legacy.txt', 'legacy-hash', 'Because different words.', 24, 3, 1, '2026-06-20T10:00:00', 0)
        """
    )
    connection.execute(
        """
        INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds,
        total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate,
        completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at)
        VALUES (1, NULL, '2026-06-20T10:00:00', '2026-06-20T10:01:00', 60, 0, 40, 35, 5, 35, 35, 175, 87.5, 1.0, 1,
        'article_section', 10, 35, '0.1.0', '2026-06-20T10:01:00')
        """
    )
    connection.execute(
        """
        INSERT INTO typing_errors(session_id, article_id, section_id, character_index, expected_character, actual_character, target_word, error_type, occurred_at)
        VALUES (1, 1, NULL, 0, 'B', 'b', 'Because', 'case_error', '2026-06-20T10:00:10')
        """
    )
    connection.commit()

    MigrationRunner().migrate(connection)

    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 7
    assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM typing_errors").fetchone()[0] == 1
    practice_set_id_column = {row[1] for row in connection.execute("PRAGMA table_info(practice_sessions)").fetchall()}
    assert "practice_set_id" in practice_set_id_column
    assert connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vocabulary_items'").fetchone() is not None
    connection.close()


def test_word_normalization_rules() -> None:
    service = WordNormalizationService()
    assert service.normalize("Because") == "because"
    assert service.normalize("“different”") == "different"
    assert service.normalize("don't") == "don't"
    assert service.normalize("well-known") == "well-known"
    assert service.normalize("teacher's") == "teacher's"
    assert service.normalize("...") == ""
    assert service.normalize("   ") == ""


def test_error_word_special_practice_generation_is_deduplicated_and_sorted(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        connection = context.database.connect()
        connection.execute(
            """
            INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds,
            total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate,
            completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at)
            VALUES (NULL, NULL, '2026-06-22T10:00:00', '2026-06-22T10:01:00', 60, 0, 40, 35, 5, 35, 35, 175, 87.5, 1.0, 1,
            'article_section', 10, 35, '0.1.0', '2026-06-22T10:01:00')
            """
        )
        connection.execute(
            "INSERT INTO typing_errors(session_id, article_id, section_id, character_index, expected_character, actual_character, target_word, error_type, occurred_at) VALUES (1, NULL, NULL, 0, 'e', 'r', 'Because', 'wrong_character', '2026-06-22T10:00:00')"
        )
        connection.execute(
            "INSERT INTO typing_errors(session_id, article_id, section_id, character_index, expected_character, actual_character, target_word, error_type, occurred_at) VALUES (1, NULL, NULL, 0, 'e', 'r', 'because', 'wrong_character', '2026-06-23T10:00:00')"
        )
        connection.execute(
            "INSERT INTO typing_errors(session_id, article_id, section_id, character_index, expected_character, actual_character, target_word, error_type, occurred_at) VALUES (1, NULL, NULL, 0, 'd', 'f', 'Different', 'wrong_character', '2026-06-21T10:00:00')"
        )
        connection.commit()

        generated = context.special_practice_service.generate_error_word_set(
            range_key="all",
            word_count=10,
            repeat_count=3,
            arrangement="repeat",
        )

        assert generated is not None
        assert generated.practice_set.item_count == 2
        assert generated.items[0].item_value == "because"
        assert "because because because" in generated.preview_text
    finally:
        context.database.close()


def test_vocabulary_add_duplicate_review_and_due_summary(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        first = context.special_practice_service.add_vocabulary_word("Different")
        second = context.special_practice_service.add_vocabulary_word("different")
        assert first.id == second.id

        summary = context.special_practice_service.due_summary()
        assert summary["due_count"] >= 1

        generated = context.special_practice_service.generate_vocabulary_review_set(due_only=False, item_ids=[first.id])
        assert generated is not None

        session = TypingSession(generated.material.section_text)
        for character in generated.material.section_text:
            session.handle_character(character)
        context.practice_service.save_completed_session(generated.material, session, session.snapshot())
        changes = context.special_practice_service.apply_review_results(
            generated.practice_set.id,
            mistaken_words=set(),
            completed=True,
        )

        assert changes
        item = VocabularyRepository(context.database.connect).get_item(first.id)
        assert item is not None
        assert item.mastery_level >= 1
    finally:
        context.database.close()


def test_review_planning_downgrades_mastered_word_after_error() -> None:
    planning = ReviewPlanningService()
    item = VocabularyItem(
        id=1,
        normalized_word="because",
        display_word="Because",
        status="mastered",
        mastery_level=5,
        next_review_at=date(2026, 6, 23),
    )
    outcome = planning.mark_wrong(item, today=date(2026, 6, 23))
    assert outcome.status == "reviewing"
    assert outcome.mastery_level == 4
    assert outcome.next_review_at == date(2026, 6, 24)


def test_history_filter_by_special_practice_type(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        repo = PracticeRepository(context.database.connect)
        set_repo = PracticeSetRepository(context.database.connect)
        generated = context.special_practice_service.generate_error_word_set(
            range_key="all",
            word_count=10,
            repeat_count=1,
            arrangement="repeat",
        )
        if generated is None:
            connection = context.database.connect()
            connection.execute(
                """
                INSERT INTO practice_sessions(article_id, section_id, started_at, finished_at, active_seconds, paused_seconds,
                total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters, wpm, cpm, accuracy, completion_rate,
                completed, practice_type, longest_correct_streak, average_wpm, app_version, created_at)
                VALUES (NULL, NULL, '2026-06-23T10:00:00', '2026-06-23T10:01:00', 60, 0, 40, 35, 5, 35, 35, 175, 87.5, 1.0, 1,
                'article_section', 10, 35, '0.1.0', '2026-06-23T10:01:00')
                """
            )
            connection.execute(
                "INSERT INTO typing_errors(session_id, article_id, section_id, character_index, expected_character, actual_character, target_word, error_type, occurred_at) VALUES (1, NULL, NULL, 0, 'e', 'r', 'Because', 'wrong_character', '2026-06-23T10:00:00')"
            )
            connection.commit()
            generated = context.special_practice_service.generate_error_word_set(
                range_key="all",
                word_count=10,
                repeat_count=1,
                arrangement="repeat",
            )
        assert generated is not None

        session = TypingSession(generated.material.section_text)
        for character in generated.material.section_text:
            session.handle_character(character)
        context.practice_service.save_completed_session(generated.material, session, session.snapshot())
        context.special_practice_service.note_set_practiced(generated.practice_set.id)

        rows = context.history_service.list_history(practice_type="error_words")
        assert rows
        assert all(row["practice_type"] == "error_words" for row in rows)
        assert set_repo.get_set(generated.practice_set.id) is not None
        assert repo.get_session_detail(rows[0]["id"])[0] is not None
    finally:
        context.database.close()
