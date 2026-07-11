from __future__ import annotations

import sqlite3

LATEST_SCHEMA_VERSION = 3


class MigrationRunner:
    def migrate(self, connection: sqlite3.Connection) -> None:
        connection.execute("SAVEPOINT migrate_schema")
        try:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)"
            )
            row = connection.execute(
                "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
            ).fetchone()
            current_version = int(row[0]) if row else 0
            if current_version > LATEST_SCHEMA_VERSION:
                raise RuntimeError(
                    f"Database schema version {current_version} is newer than supported version {LATEST_SCHEMA_VERSION}."
                )
            if current_version < 1:
                self._apply_version_1(connection)
                current_version = 1
            if current_version < 2:
                self._apply_version_2(connection)
                current_version = 2
            if current_version < 3:
                self._apply_version_3(connection)
            connection.execute("RELEASE SAVEPOINT migrate_schema")
        except Exception:
            connection.execute("ROLLBACK TO SAVEPOINT migrate_schema")
            connection.execute("RELEASE SAVEPOINT migrate_schema")
            raise

    def _apply_version_1(self, connection: sqlite3.Connection) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                source_path TEXT NOT NULL,
                content_hash TEXT NOT NULL UNIQUE,
                full_text TEXT NOT NULL,
                character_count INTEGER NOT NULL,
                word_count INTEGER NOT NULL,
                section_count INTEGER NOT NULL DEFAULT 0,
                imported_at TEXT NOT NULL,
                last_practiced_at TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS article_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                section_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                character_count INTEGER NOT NULL,
                word_count INTEGER NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS practice_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER,
                section_id INTEGER,
                started_at TEXT,
                finished_at TEXT,
                active_seconds REAL NOT NULL,
                paused_seconds REAL NOT NULL,
                total_keystrokes INTEGER NOT NULL,
                correct_keystrokes INTEGER NOT NULL,
                error_keystrokes INTEGER NOT NULL,
                correct_characters INTEGER NOT NULL,
                wpm REAL NOT NULL,
                cpm REAL NOT NULL,
                accuracy REAL NOT NULL,
                completion_rate REAL NOT NULL,
                completed INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL,
                FOREIGN KEY (section_id) REFERENCES article_sections(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS article_progress (
                article_id INTEGER PRIMARY KEY,
                current_section_index INTEGER NOT NULL DEFAULT 0,
                current_character_index INTEGER NOT NULL DEFAULT 0,
                completed_section_count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_articles_active ON articles(is_deleted, imported_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title COLLATE NOCASE)",
            "CREATE INDEX IF NOT EXISTS idx_sections_article_active ON article_sections(article_id, is_active, section_index)",
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_sections_active_unique
                ON article_sections(article_id, section_index)
                WHERE is_active = 1
            """,
            "CREATE INDEX IF NOT EXISTS idx_sessions_article_created ON practice_sessions(article_id, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_progress_updated ON article_progress(updated_at DESC)",
        ]
        for statement in statements:
            connection.execute(statement)
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (?)", (1,))

    def _apply_version_2(self, connection: sqlite3.Connection) -> None:
        self._ensure_column(
            connection,
            table_name="practice_sessions",
            column_name="practice_type",
            definition="TEXT NOT NULL DEFAULT 'article_section'",
        )
        self._ensure_column(
            connection,
            table_name="practice_sessions",
            column_name="longest_correct_streak",
            definition="INTEGER NOT NULL DEFAULT 0",
        )
        self._ensure_column(
            connection,
            table_name="practice_sessions",
            column_name="average_wpm",
            definition="REAL",
        )
        self._ensure_column(
            connection,
            table_name="practice_sessions",
            column_name="app_version",
            definition="TEXT NOT NULL DEFAULT '0.1.0'",
        )

        statements = [
            """
            CREATE TABLE IF NOT EXISTS typing_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                article_id INTEGER,
                section_id INTEGER,
                character_index INTEGER NOT NULL,
                expected_character TEXT NOT NULL,
                actual_character TEXT NOT NULL,
                target_word TEXT NOT NULL DEFAULT '',
                error_type TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES practice_sessions(id) ON DELETE CASCADE,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL,
                FOREIGN KEY (section_id) REFERENCES article_sections(id) ON DELETE SET NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_typing_errors_session_id ON typing_errors(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_typing_errors_article_id ON typing_errors(article_id)",
            "CREATE INDEX IF NOT EXISTS idx_typing_errors_expected_character ON typing_errors(expected_character)",
            "CREATE INDEX IF NOT EXISTS idx_typing_errors_target_word ON typing_errors(target_word)",
            "CREATE INDEX IF NOT EXISTS idx_typing_errors_occurred_at ON typing_errors(occurred_at)",
        ]
        for statement in statements:
            connection.execute(statement)
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (?)", (2,))

    def _apply_version_3(self, connection: sqlite3.Connection) -> None:
        self._ensure_column(
            connection,
            table_name="practice_sessions",
            column_name="practice_set_id",
            definition="INTEGER",
        )
        statements = [
            """
            CREATE TABLE IF NOT EXISTS vocabulary_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                normalized_word TEXT NOT NULL UNIQUE,
                display_word TEXT NOT NULL,
                meaning TEXT NOT NULL DEFAULT '',
                note TEXT NOT NULL DEFAULT '',
                source_article_id INTEGER,
                source_section_id INTEGER,
                source_character_index INTEGER,
                source_sentence TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'new',
                mastery_level INTEGER NOT NULL DEFAULT 0,
                review_count INTEGER NOT NULL DEFAULT 0,
                correct_review_count INTEGER NOT NULL DEFAULT 0,
                wrong_review_count INTEGER NOT NULL DEFAULT 0,
                next_review_at TEXT,
                last_reviewed_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                is_archived INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (source_article_id) REFERENCES articles(id) ON DELETE SET NULL,
                FOREIGN KEY (source_section_id) REFERENCES article_sections(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS practice_sets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                practice_mode TEXT NOT NULL,
                source_type TEXT NOT NULL,
                generated_text TEXT NOT NULL,
                item_count INTEGER NOT NULL,
                configuration_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_practiced_at TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS practice_set_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                practice_set_id INTEGER NOT NULL,
                item_type TEXT NOT NULL,
                item_value TEXT NOT NULL,
                source_article_id INTEGER,
                source_section_id INTEGER,
                source_character_index INTEGER,
                source_sentence TEXT NOT NULL DEFAULT '',
                error_count INTEGER NOT NULL DEFAULT 0,
                sort_order INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (practice_set_id) REFERENCES practice_sets(id) ON DELETE CASCADE,
                FOREIGN KEY (source_article_id) REFERENCES articles(id) ON DELETE SET NULL,
                FOREIGN KEY (source_section_id) REFERENCES article_sections(id) ON DELETE SET NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_vocabulary_normalized_word ON vocabulary_items(normalized_word)",
            "CREATE INDEX IF NOT EXISTS idx_vocabulary_next_review_at ON vocabulary_items(next_review_at)",
            "CREATE INDEX IF NOT EXISTS idx_vocabulary_status ON vocabulary_items(status, is_archived)",
            "CREATE INDEX IF NOT EXISTS idx_practice_sessions_type ON practice_sessions(practice_type, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_practice_sessions_set_id ON practice_sessions(practice_set_id)",
            "CREATE INDEX IF NOT EXISTS idx_practice_sets_mode ON practice_sets(practice_mode, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_practice_set_items_set_id ON practice_set_items(practice_set_id, sort_order)",
        ]
        for statement in statements:
            connection.execute(statement)
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (?)", (3,))

    def _ensure_column(
        self,
        connection: sqlite3.Connection,
        *,
        table_name: str,
        column_name: str,
        definition: str,
    ) -> None:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row[1] for row in rows}
        if column_name not in existing:
            connection.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            )
