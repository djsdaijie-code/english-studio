from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.services.sentence_segmentation import SentenceSegmentationService


def _reconstructed(text: str, target: int = 500):
    segments = SentenceSegmentationService(target).split(text)
    assert "".join(item.text for item in segments) == text
    assert all(item.text and item.text.strip() for item in segments)
    for item in segments:
        assert text[item.start_offset:item.end_offset] == item.text
    return segments


def test_sentence_segmentation_handles_basic_terminal_marks() -> None:
    text = "First sentence. Is this working? Yes, it is! Done"
    segments = _reconstructed(text)
    assert len(segments) == 4
    assert segments[0].text == "First sentence. "
    assert segments[1].text == "Is this working? "


def test_sentence_segmentation_keeps_quotes_and_continuous_punctuation() -> None:
    text = 'He asked, "Really?!" Then she answered (quietly). Next.'
    segments = _reconstructed(text)
    assert len(segments) == 3
    assert segments[0].text.endswith('" ')
    assert "Really?!" in segments[0].text


def test_sentence_segmentation_protects_abbreviations_and_decimals() -> None:
    text = "Mr. Smith met Dr. Brown in the U.S. today. They used e.g. 3.14 as a value."
    segments = _reconstructed(text)
    assert len(segments) == 2
    assert "Mr. Smith" in segments[0].text
    assert "U.S. today." in segments[0].text
    assert "e.g. 3.14" in segments[1].text


def test_sentence_segmentation_preserves_newlines() -> None:
    text = "A line without punctuation\nAnother line.\n\nFinal line!"
    segments = _reconstructed(text)
    assert len(segments) == 3
    assert segments[0].text.endswith("\n")
    assert "\n\n" in segments[1].text


def test_sentence_segmentation_falls_back_for_long_unpunctuated_text() -> None:
    text = ("alpha beta gamma delta " * 30).strip()
    segments = _reconstructed(text, target=100)
    assert len(segments) > 1
    assert all(len(item.text) <= 110 for item in segments)


def test_sentence_hash_reuses_normalized_equivalent_text() -> None:
    service = SentenceSegmentationService()
    first = service.split("Hello   world.")[0]
    second = service.split("Hello world.")[0]
    assert first.normalized_text == second.normalized_text
    assert first.sentence_hash == second.sentence_hash


def test_sentence_service_lazily_persists_active_section_sentences(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        path = tmp_path / "lesson.txt"
        path.write_text("First sentence. Second sentence? Third!", encoding="utf-8")
        imported = context.article_library.import_txt_file(path, 500)
        material = context.practice_service.load_practice_material(imported.article.id)
        first = context.sentence_service.ensure_for_section(material.section_id)
        second = context.sentence_service.ensure_for_section(material.section_id)
        assert len(first) == 3
        assert [item.id for item in first] == [item.id for item in second]
        assert "".join(item.text for item in first) == material.section_text
        section = context.article_library.get_article(imported.article.id)
        assert section is not None
        active = context.database.connect().execute("SELECT start_offset FROM article_sections WHERE id = ?", (material.section_id,)).fetchone()
        assert first[0].start_offset == active[0]
    finally:
        context.database.close()


def test_schema4_tables_columns_and_new_install_defaults(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        connection = context.database.connect()
        assert context.database.get_schema_version() == 10
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"article_sentences", "sentence_translations", "sentence_attempts"} <= tables
        session_columns = {row[1] for row in connection.execute("PRAGMA table_info(practice_sessions)")}
        assert {"total_elapsed_seconds", "learning_seconds", "idle_seconds", "manual_paused_seconds"} <= session_columns
        assert context.settings_service.get_settings().sentence_learning_enabled is True
    finally:
        context.database.close()


def test_v4_migration_failure_rolls_back_to_v3(tmp_path: Path, monkeypatch) -> None:
    connection = sqlite3.connect(tmp_path / "legacy.db")
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner = MigrationRunner()
    runner._apply_version_1(connection)
    runner._apply_version_2(connection)
    runner._apply_version_3(connection)
    connection.commit()

    def broken_v4(conn):
        conn.execute("CREATE TABLE should_rollback(id INTEGER)")
        raise RuntimeError("v4 failed")

    monkeypatch.setattr(runner, "_apply_version_4", broken_v4)
    with pytest.raises(RuntimeError):
        runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 3
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='should_rollback'").fetchone() is None
    connection.close()
