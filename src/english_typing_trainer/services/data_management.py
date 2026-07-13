from __future__ import annotations

import json
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path

from english_typing_trainer import __version__
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import LATEST_SCHEMA_VERSION


class DataManagementService:
    """Explicit, local-only maintenance actions for a user's app data."""

    def __init__(self, database: DatabaseManager, backups_dir: Path, logs_dir: Path) -> None:
        self._database = database
        self._backups_dir = backups_dir
        self._logs_dir = logs_dir

    def backup_database(self, destination_dir: Path | None = None) -> Path:
        directory = destination_dir or self._backups_dir
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = directory / f"EnglishStudio-backup-{stamp}.db"
        source = self._database.connect()
        target = sqlite3.connect(path)
        try:
            source.backup(target)
        finally:
            target.close()
        return path

    def validate_backup(self, backup_path: Path) -> int:
        if not backup_path.is_file():
            raise ValueError("请选择有效的 SQLite 数据库备份文件。")
        connection = sqlite3.connect(backup_path)
        try:
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()
            except sqlite3.DatabaseError as exc:
                raise ValueError("所选文件不是有效的 SQLite 数据库备份。") from exc
            if not integrity or str(integrity[0]).lower() != "ok":
                raise ValueError("所选备份未通过 SQLite 完整性检查。")
            try:
                row = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
                ).fetchone()
            except sqlite3.DatabaseError as exc:
                raise ValueError("所选文件不是 English Studio 数据库备份。") from exc
            if row is None:
                raise ValueError("所选文件不是 English Studio 数据库备份。")
            version_row = connection.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            version = int(version_row[0]) if version_row else 0
            if version > LATEST_SCHEMA_VERSION:
                raise ValueError("备份的数据库版本比当前程序新，无法安全恢复。")
            return version
        finally:
            connection.close()

    def restore_database(self, backup_path: Path) -> Path:
        self.validate_backup(backup_path)
        safety_backup = self.backup_database()
        self._database.close()
        source = sqlite3.connect(backup_path)
        target = sqlite3.connect(self._database.db_path)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        self._database.initialize()
        return safety_backup

    def export_diagnostics(self, destination_dir: Path) -> Path:
        destination_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        archive = destination_dir / f"EnglishStudio-diagnostics-{stamp}.zip"
        diagnostics = {
            "application": "English Studio",
            "version": __version__,
            "schema_version": self._database.get_schema_version(),
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("diagnostics.json", json.dumps(diagnostics, ensure_ascii=False, indent=2))
            for log_path in sorted(self._logs_dir.glob("*.log")):
                bundle.write(log_path, f"logs/{log_path.name}")
        return archive
