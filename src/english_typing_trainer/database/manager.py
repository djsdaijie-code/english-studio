from __future__ import annotations

import sqlite3
from contextlib import contextmanager
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
        row = self.connect().execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        return int(row["version"]) if row else 0

    def get_foreign_keys_enabled(self) -> bool:
        row = self.connect().execute("PRAGMA foreign_keys").fetchone()
        return bool(row[0]) if row else False

    @property
    def latest_schema_version(self) -> int:
        return LATEST_SCHEMA_VERSION
