from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.services.migration_verification import (
    MigrationVerificationError,
    verify_migration_copy,
)


def _schema_11_database(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner = MigrationRunner()
    for version in range(1, 12):
        getattr(runner, f"_apply_version_{version}")(connection)
    connection.execute(
        """
        INSERT INTO articles(
            title,original_filename,source_path,content_hash,full_text,
            character_count,word_count,section_count,imported_at
        ) VALUES ('Private title','private.txt','private.txt','private-hash',
                  'Private article body.',21,3,0,'2026-07-16T08:00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO vocabulary_entries(
            normalized_word,display_word,lemma,created_at,updated_at
        ) VALUES ('private','Private','private','2026-07-16T08:00:00',
                  '2026-07-16T08:00:00')
        """
    )
    connection.execute(
        """
        INSERT INTO vocabulary_contexts(
            vocabulary_entry_id,article_id,source_word,source_sentence,
            start_offset,end_offset,created_at,updated_at
        ) VALUES (1,1,'Private','Private article body.',0,7,
                  '2026-07-16T08:00:00','2026-07-16T08:00:00')
        """
    )
    connection.commit()
    connection.close()


def test_schema_11_copy_migrates_to_13_and_preserves_counts(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "outside-copy.db"
    _schema_11_database(source)
    before_bytes = source.read_bytes()
    source_files_before = {
        path.name: path.read_bytes()
        for path in tmp_path.glob("source.db*")
    }

    report = verify_migration_copy(source, output)

    assert report.source_schema_version == 11
    assert report.target_schema_version == 13
    assert report.source_integrity == report.target_integrity == "ok"
    assert report.source_unchanged
    assert report.existing_table_counts_preserved
    assert report.critical_counts_before["articles"] == 1
    assert report.critical_counts_before["vocabulary_entries"] == 1
    assert report.critical_counts_before == report.critical_counts_after
    assert {
        "course_enrollments",
        "course_item_progress",
        "course_activity_progress",
        "course_capability_attempts",
        "course_review_cards",
        "course_review_logs",
    } <= set(report.new_tables)
    assert source.read_bytes() == before_bytes
    assert {
        path.name: path.read_bytes()
        for path in tmp_path.glob("source.db*")
    } == source_files_before
    assert not list(tmp_path.glob(".*.verification-*"))
    assert not (tmp_path / "backups").exists()
    migrated = sqlite3.connect(output)
    try:
        assert migrated.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert migrated.execute("SELECT version FROM schema_version").fetchone()[0] == 13
        assert migrated.execute("SELECT full_text FROM articles").fetchone()[0] == "Private article body."
    finally:
        migrated.close()


def test_migration_verifier_refuses_in_place_or_existing_output(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    _schema_11_database(source)
    with pytest.raises(MigrationVerificationError, match="in-place"):
        verify_migration_copy(source, source)
    output = tmp_path / "existing.db"
    output.write_bytes(b"do not overwrite")
    with pytest.raises(MigrationVerificationError, match="already exists"):
        verify_migration_copy(source, output)
    assert output.read_bytes() == b"do not overwrite"


def test_migration_verifier_failure_keeps_source_and_removes_partial_copy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source.db"
    output = tmp_path / "failed-copy.db"
    _schema_11_database(source)
    before_bytes = source.read_bytes()

    def fail_initialize(_self: DatabaseManager) -> None:
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(DatabaseManager, "initialize", fail_initialize)
    with pytest.raises(MigrationVerificationError):
        verify_migration_copy(source, output)
    assert source.read_bytes() == before_bytes
    assert not output.exists()
    assert not list(tmp_path.glob(".*.verification-*"))
