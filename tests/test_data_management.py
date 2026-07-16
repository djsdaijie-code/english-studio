from __future__ import annotations

import sqlite3
import zipfile

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.data_management import DataManagementService


def test_backup_is_consistent_sqlite_snapshot(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        service = DataManagementService(context.database, context.paths.backups_dir, context.paths.logs_dir)
        backup = service.backup_database()
        assert backup.parent == context.paths.backups_dir
        assert service.validate_backup(backup) == 13
        assert sqlite3.connect(backup).execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        context.database.close()


def test_restore_rejects_non_database_without_overwriting_user_data(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        service = DataManagementService(context.database, context.paths.backups_dir, context.paths.logs_dir)
        invalid = tmp_path / "not-a-backup.db"
        invalid.write_text("not sqlite", encoding="utf-8")
        with pytest.raises(ValueError):
            service.restore_database(invalid)
        assert context.database.get_schema_version() == 13
    finally:
        context.database.close()


def test_diagnostics_export_excludes_database_and_credentials(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        (context.paths.logs_dir / "app.log").write_text("safe diagnostic", encoding="utf-8")
        service = DataManagementService(context.database, context.paths.backups_dir, context.paths.logs_dir)
        archive = service.export_diagnostics(tmp_path / "exports")
        with zipfile.ZipFile(archive) as bundle:
            assert "diagnostics.json" in bundle.namelist()
            assert "logs/app.log" in bundle.namelist()
            assert not any(name.endswith(".db") for name in bundle.namelist())
    finally:
        context.database.close()
