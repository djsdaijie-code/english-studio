from pathlib import Path

from english_typing_trainer.application.context import build_app_context


def test_first_start_creates_database_and_directories(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "appdata")
    try:
        assert context.paths.data_dir.exists()
        assert context.paths.logs_dir.exists()
        assert context.paths.backups_dir.exists()
        assert context.paths.database_path.exists()
    finally:
        context.database.close()


def test_repeat_start_keeps_schema_intact(tmp_path: Path) -> None:
    data_dir = tmp_path / "appdata"
    first = build_app_context(data_dir=data_dir)
    first.database.close()

    second = build_app_context(data_dir=data_dir)
    try:
        assert second.database.get_schema_version() == 8
        assert second.database.get_foreign_keys_enabled() is True
    finally:
        second.database.close()


def test_temp_data_dir_does_not_use_real_user_location(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "isolated")
    try:
        assert context.paths.data_dir == tmp_path / "isolated"
    finally:
        context.database.close()


def test_v3_database_is_backed_up_before_v4_migration(tmp_path: Path) -> None:
    import sqlite3

    from english_typing_trainer.database.migrations import MigrationRunner

    data_dir = tmp_path / "appdata"
    data_dir.mkdir()
    db_path = data_dir / "typing_trainer.db"
    connection = sqlite3.connect(db_path)
    runner = MigrationRunner()
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner._apply_version_1(connection)
    runner._apply_version_2(connection)
    runner._apply_version_3(connection)
    connection.execute(
        "INSERT INTO articles(title, original_filename, source_path, content_hash, full_text, character_count, word_count, section_count, imported_at, is_deleted) VALUES ('Legacy', 'legacy.txt', 'legacy.txt', 'legacy', 'Hello.', 6, 1, 0, '2026-01-01T00:00:00', 0)"
    )
    connection.commit()
    connection.close()

    context = build_app_context(data_dir=data_dir)
    try:
        assert context.database.get_schema_version() == 8
        mode = context.database.connect().execute(
            "SELECT value FROM settings WHERE key = 'sentence_learning_enabled'"
        ).fetchone()[0]
        assert mode == "0"
        backups = list((data_dir / "backups").glob("typing_trainer-v3-before-v8-*.db"))
        assert len(backups) == 1
        backup = sqlite3.connect(backups[0])
        assert backup.execute("SELECT version FROM schema_version").fetchone()[0] == 3
        assert backup.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
        backup.close()
    finally:
        context.database.close()
