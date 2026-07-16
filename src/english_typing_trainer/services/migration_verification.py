from __future__ import annotations

from contextlib import closing
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import LATEST_SCHEMA_VERSION


CRITICAL_TABLES = (
    "articles",
    "article_sections",
    "article_sentences",
    "article_progress",
    "sentence_attempts",
    "practice_sessions",
    "typing_errors",
    "vocabulary_entries",
    "vocabulary_contexts",
    "vocabulary_learning_state",
    "vocabulary_attempts",
    "article_word_occurrences",
    "fsrs_profiles",
    "vocabulary_review_cards",
    "vocabulary_review_logs",
    "dictation_attempts",
    "pronunciation_attempts",
    "daily_learning_stats",
    "learning_events",
    "achievements",
    "profile_progress",
)


class MigrationVerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MigrationVerificationReport:
    source_schema_version: int
    target_schema_version: int
    source_integrity: str
    target_integrity: str
    source_unchanged: bool
    existing_table_counts_preserved: bool
    critical_counts_before: dict[str, int]
    critical_counts_after: dict[str, int]
    new_tables: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def verify_migration_copy(
    source_path: Path,
    output_path: Path,
) -> MigrationVerificationReport:
    """Back up a read-only source, migrate only the copy, and compare row counts."""
    source = source_path.expanduser().resolve()
    output = output_path.expanduser().resolve()
    if source == output:
        raise MigrationVerificationError("Refusing an in-place database migration.")
    if not source.is_file():
        raise MigrationVerificationError("The source database does not exist.")
    if output.exists():
        raise MigrationVerificationError("The output database already exists.")
    output.parent.mkdir(parents=True, exist_ok=True)
    source_fingerprint = _database_fingerprint(source)
    staging_root = output.parent / f".{output.name}.verification-{uuid4().hex}"
    staging_root.mkdir()
    staging = staging_root / "migration-copy.db"
    manager: DatabaseManager | None = None
    try:
        with closing(_read_only_connection(source)) as connection:
            source_integrity = _integrity(connection)
            source_version = _schema_version(connection)
            if source_integrity != "ok":
                raise MigrationVerificationError(
                    "The source database failed its integrity check."
                )
            if source_version <= 0 or source_version > LATEST_SCHEMA_VERSION:
                raise MigrationVerificationError(
                    "The source schema version is not supported."
                )
            before_counts = _table_counts(connection)
            target = sqlite3.connect(staging)
            try:
                connection.backup(target)
            finally:
                target.close()

        if _database_fingerprint(source) != source_fingerprint:
            raise MigrationVerificationError(
                "The source database changed during snapshot creation."
            )

        manager = DatabaseManager(staging)
        manager.initialize()
        target_connection = manager.connect()
        target_integrity = _integrity(target_connection)
        target_version = manager.get_schema_version()
        after_counts = _table_counts(target_connection)
        if target_integrity != "ok":
            raise MigrationVerificationError(
                "The migrated copy failed its integrity check."
            )
        if target_version != LATEST_SCHEMA_VERSION:
            raise MigrationVerificationError(
                "The migrated copy did not reach the expected schema version."
            )
        preserved = all(
            after_counts.get(table_name) == row_count
            for table_name, row_count in before_counts.items()
        )
        if not preserved:
            raise MigrationVerificationError(
                "One or more existing table row counts changed during migration."
            )
        if _database_fingerprint(source) != source_fingerprint:
            raise MigrationVerificationError(
                "The source database changed while the copy was being verified."
            )
        manager.close()
        manager = None
        staging.replace(output)
        return MigrationVerificationReport(
            source_schema_version=source_version,
            target_schema_version=target_version,
            source_integrity=source_integrity,
            target_integrity=target_integrity,
            source_unchanged=True,
            existing_table_counts_preserved=preserved,
            critical_counts_before=_critical_counts(before_counts),
            critical_counts_after=_critical_counts(after_counts),
            new_tables=tuple(sorted(set(after_counts) - set(before_counts))),
        )
    except (MigrationVerificationError, sqlite3.Error):
        raise
    except Exception as exc:
        raise MigrationVerificationError(
            "The migration copy could not be verified."
        ) from exc
    finally:
        if manager is not None:
            manager.close()
        shutil.rmtree(staging_root, ignore_errors=True)


def _read_only_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(
        f"{path.as_uri()}?mode=ro&immutable=1", uri=True
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _integrity(connection: sqlite3.Connection) -> str:
    rows = connection.execute("PRAGMA integrity_check").fetchall()
    return "ok" if rows and all(str(row[0]).lower() == "ok" for row in rows) else "failed"


def _schema_version(connection: sqlite3.Connection) -> int:
    table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if table is None:
        return 0
    row = connection.execute(
        "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
    ).fetchone()
    return int(row[0]) if row else 0


def _table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    names = [
        str(row[0])
        for row in connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
    ]
    return {
        name: int(
            connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(name)}"
            ).fetchone()[0]
        )
        for name in names
    }


def _critical_counts(counts: dict[str, int]) -> dict[str, int]:
    return {name: counts.get(name, 0) for name in CRITICAL_TABLES}


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_fingerprint(
    path: Path,
) -> tuple[tuple[str, bool, int, int, str], ...]:
    candidates = (
        path,
        path.with_name(path.name + "-wal"),
        path.with_name(path.name + "-shm"),
    )
    values: list[tuple[str, bool, int, int, str]] = []
    for candidate in candidates:
        exists = candidate.is_file()
        stat = candidate.stat() if exists else None
        values.append(
            (
                candidate.name.removeprefix(path.name),
                exists,
                stat.st_size if stat else 0,
                stat.st_mtime_ns if stat else 0,
                _sha256(candidate) if exists else "",
            )
        )
    return tuple(values)


__all__ = [
    "MigrationVerificationError",
    "MigrationVerificationReport",
    "verify_migration_copy",
]
