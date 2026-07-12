from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from english_typing_trainer.database.migrations import LATEST_SCHEMA_VERSION, MigrationRunner


class DatabaseManager:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._connection: sqlite3.Connection | None = None
        self._migrations = MigrationRunner()

    def initialize(self) -> None:
        connection = self.connect()
        current_version = self._current_version(connection)
        if 0 < current_version < LATEST_SCHEMA_VERSION:
            self._backup_before_migration(connection, current_version)
        self._migrations.migrate(connection)
        connection.commit()

    def connect(self) -> sqlite3.Connection:
        if self._connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.db_path)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            self._connection = connection
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def get_schema_version(self) -> int:
        return self._current_version(self.connect())

    def get_foreign_keys_enabled(self) -> bool:
        row = self.connect().execute("PRAGMA foreign_keys").fetchone()
        return bool(row[0]) if row else False

    @property
    def latest_schema_version(self) -> int:
        return LATEST_SCHEMA_VERSION

    def _current_version(self, connection: sqlite3.Connection) -> int:
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
        ).fetchone()
        if table is None:
            return 0
        row = connection.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return int(row[0]) if row else 0

    def _backup_before_migration(self, connection: sqlite3.Connection, version: int) -> Path:
        backups_dir = self.db_path.parent / "backups"
        backups_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = backups_dir / f"typing_trainer-v{version}-before-v{LATEST_SCHEMA_VERSION}-{stamp}.db"
        target = sqlite3.connect(backup_path)
        try:
            connection.backup(target)
        finally:
            target.close()
        return backup_path