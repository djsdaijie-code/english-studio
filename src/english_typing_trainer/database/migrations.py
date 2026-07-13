from __future__ import annotations

import sqlite3

LATEST_SCHEMA_VERSION = 7


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
                current_version = 3
            if current_version < 4:
                self._apply_version_4(connection)
                current_version = 4
            if current_version < 5:
                self._apply_version_5(connection)
                current_version = 5
            if current_version < 6:
                self._apply_version_6(connection)
                current_version = 6
            if current_version < 7:
                self._apply_version_7(connection)
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

    def _apply_version_4(self, connection: sqlite3.Connection) -> None:
        for column_name, definition in (
            ("total_elapsed_seconds", "REAL NOT NULL DEFAULT 0"),
            ("learning_seconds", "REAL NOT NULL DEFAULT 0"),
            ("idle_seconds", "REAL NOT NULL DEFAULT 0"),
            ("manual_paused_seconds", "REAL NOT NULL DEFAULT 0"),
        ):
            self._ensure_column(
                connection,
                table_name="practice_sessions",
                column_name=column_name,
                definition=definition,
            )

        statements = [
            """
            CREATE TABLE IF NOT EXISTS article_sentences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                section_id INTEGER NOT NULL,
                sentence_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                normalized_text TEXT NOT NULL,
                sentence_hash TEXT NOT NULL,
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                FOREIGN KEY (section_id) REFERENCES article_sections(id) ON DELETE CASCADE,
                UNIQUE(section_id, sentence_index)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sentence_translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sentence_hash TEXT NOT NULL UNIQUE,
                source_text TEXT NOT NULL,
                chinese_translation TEXT NOT NULL DEFAULT '',
                key_expressions_json TEXT NOT NULL DEFAULT '[]',
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_version TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending', 'completed', 'failed')),
                error_message TEXT NOT NULL DEFAULT '',
                is_user_edited INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sentence_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER,
                article_sentence_id INTEGER,
                sentence_hash TEXT NOT NULL,
                practice_type TEXT NOT NULL DEFAULT 'article_sentence',
                started_at TEXT,
                completed_at TEXT,
                active_seconds REAL NOT NULL DEFAULT 0,
                total_elapsed_seconds REAL NOT NULL DEFAULT 0,
                correct_characters INTEGER NOT NULL DEFAULT 0,
                total_characters INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                cpm REAL NOT NULL DEFAULT 0,
                wpm REAL NOT NULL DEFAULT 0,
                accuracy REAL NOT NULL DEFAULT 100,
                completed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES practice_sessions(id) ON DELETE SET NULL,
                FOREIGN KEY (article_sentence_id) REFERENCES article_sentences(id) ON DELETE SET NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_article_sentences_article ON article_sentences(article_id, section_id, sentence_index)",
            "CREATE INDEX IF NOT EXISTS idx_article_sentences_hash ON article_sentences(sentence_hash)",
            "CREATE INDEX IF NOT EXISTS idx_sentence_translations_status ON sentence_translations(status, updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_sentence_attempts_sentence ON sentence_attempts(sentence_hash, created_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_sentence_attempts_session ON sentence_attempts(session_id)",
        ]
        for statement in statements:
            connection.execute(statement)

        existing_data = connection.execute(
            "SELECT EXISTS(SELECT 1 FROM articles LIMIT 1) OR EXISTS(SELECT 1 FROM practice_sessions LIMIT 1)"
        ).fetchone()[0]
        now = connection.execute("SELECT datetime('now')").fetchone()[0]
        defaults = {
            "sentence_learning_enabled": "0" if existing_data else "1",
            "show_translation_after_sentence": "1",
            "idle_pause_seconds": "3",
            "translation_auto_on_demand": "1",
            "translation_provider": "deepseek",
            "translation_model": "deepseek-v4-flash",
            "translation_prompt_version": "sentence-v1",
        }
        connection.executemany(
            "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
            [(key, value, now) for key, value in defaults.items()],
        )
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (?)", (4,))

    def _apply_version_5(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tts_audio_cache (
                cache_key TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                voice_id TEXT NOT NULL,
                speed REAL NOT NULL,
                volume REAL NOT NULL,
                pitch INTEGER NOT NULL,
                text_hash TEXT NOT NULL,
                text_preview TEXT NOT NULL DEFAULT '',
                file_path TEXT NOT NULL,
                audio_format TEXT NOT NULL,
                duration_ms INTEGER,
                size_bytes INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                last_played_at TEXT,
                status TEXT NOT NULL CHECK(status IN ('completed', 'failed')),
                error_message TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_tts_cache_last_played ON tts_audio_cache(last_played_at, created_at)"
        )
        now = connection.execute("SELECT datetime('now')").fetchone()[0]
        defaults = {
            "tts_provider": "minimax",
            "tts_model": "speech-2.8-hd",
            "tts_voice_id": "English_expressive_narrator",
            "tts_speed": "1.0",
            "tts_auto_play": "0",
        }
        connection.executemany(
            "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
            [(key, value, now) for key, value in defaults.items()],
        )
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (5)")

    def _apply_version_6(self, connection: sqlite3.Connection) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS vocabulary_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                normalized_word TEXT NOT NULL UNIQUE,
                display_word TEXT NOT NULL,
                lemma TEXT NOT NULL DEFAULT '',
                phonetic TEXT NOT NULL DEFAULT '',
                primary_part_of_speech TEXT NOT NULL DEFAULT '',
                dictionary_status TEXT NOT NULL DEFAULT 'pending',
                dictionary_payload_json TEXT NOT NULL DEFAULT '{}',
                dictionary_fetched_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vocabulary_contexts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vocabulary_entry_id INTEGER NOT NULL,
                article_id INTEGER,
                article_sentence_id INTEGER,
                source_word TEXT NOT NULL,
                source_sentence TEXT NOT NULL DEFAULT '',
                start_offset INTEGER NOT NULL DEFAULT 0,
                end_offset INTEGER NOT NULL DEFAULT 0,
                contextual_part_of_speech TEXT NOT NULL DEFAULT '',
                contextual_meaning_zh TEXT NOT NULL DEFAULT '',
                explanation_zh TEXT NOT NULL DEFAULT '',
                common_collocation TEXT NOT NULL DEFAULT '',
                example_en TEXT NOT NULL DEFAULT '',
                example_zh TEXT NOT NULL DEFAULT '',
                ai_status TEXT NOT NULL DEFAULT 'pending',
                ai_prompt_version TEXT NOT NULL DEFAULT 'word-context-v1',
                ai_generated_at TEXT,
                is_manual INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (vocabulary_entry_id) REFERENCES vocabulary_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL,
                FOREIGN KEY (article_sentence_id) REFERENCES article_sentences(id) ON DELETE SET NULL,
                UNIQUE(vocabulary_entry_id, article_id, article_sentence_id, start_offset, end_offset)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vocabulary_learning_state (
                vocabulary_entry_id INTEGER PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new', 'learning', 'reviewing', 'mastered')),
                typing_target_count INTEGER NOT NULL DEFAULT 5,
                typing_completed_count INTEGER NOT NULL DEFAULT 0,
                correct_attempts INTEGER NOT NULL DEFAULT 0,
                incorrect_attempts INTEGER NOT NULL DEFAULT 0,
                familiarity_level INTEGER NOT NULL DEFAULT 0,
                last_practiced_at TEXT,
                next_review_at TEXT,
                mastered_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (vocabulary_entry_id) REFERENCES vocabulary_entries(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS vocabulary_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vocabulary_entry_id INTEGER NOT NULL,
                vocabulary_context_id INTEGER,
                practice_type TEXT NOT NULL CHECK(practice_type IN ('typing', 'sentence_cloze', 'meaning_recall')),
                expected_answer TEXT NOT NULL DEFAULT '',
                user_input TEXT NOT NULL DEFAULT '',
                is_correct INTEGER,
                accuracy REAL NOT NULL DEFAULT 0,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                self_rating TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (vocabulary_entry_id) REFERENCES vocabulary_entries(id) ON DELETE CASCADE,
                FOREIGN KEY (vocabulary_context_id) REFERENCES vocabulary_contexts(id) ON DELETE SET NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_vocab_context_entry ON vocabulary_contexts(vocabulary_entry_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_vocab_context_article ON vocabulary_contexts(article_id, article_sentence_id)",
            "CREATE INDEX IF NOT EXISTS idx_vocab_learning_due ON vocabulary_learning_state(status, next_review_at)",
            "CREATE INDEX IF NOT EXISTS idx_vocab_attempt_entry ON vocabulary_attempts(vocabulary_entry_id, created_at DESC)",
        ]
        for statement in statements:
            connection.execute(statement)
        for column_name, definition in (
            ("source_type", "TEXT NOT NULL DEFAULT 'minimax'"),
            ("source_url_hash", "TEXT NOT NULL DEFAULT ''"),
            ("content_type", "TEXT NOT NULL DEFAULT 'sentence'"),
        ):
            self._ensure_column(connection, table_name="tts_audio_cache", column_name=column_name, definition=definition)

        now = connection.execute("SELECT datetime('now')").fetchone()[0]
        connection.execute(
            """
            INSERT OR IGNORE INTO vocabulary_entries(
                normalized_word, display_word, lemma, dictionary_status, created_at, updated_at
            )
            SELECT normalized_word, display_word, normalized_word, 'pending', created_at, updated_at
            FROM vocabulary_items
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO vocabulary_learning_state(
                vocabulary_entry_id, status, typing_target_count, correct_attempts,
                incorrect_attempts, familiarity_level, last_practiced_at,
                next_review_at, mastered_at, created_at, updated_at
            )
            SELECT e.id, CASE WHEN i.status IN ('new','learning','reviewing','mastered') THEN i.status ELSE 'new' END,
                   5, i.correct_review_count, i.wrong_review_count, i.mastery_level,
                   i.last_reviewed_at, i.next_review_at,
                   CASE WHEN i.status = 'mastered' THEN i.last_reviewed_at ELSE NULL END,
                   i.created_at, i.updated_at
            FROM vocabulary_items i JOIN vocabulary_entries e ON e.normalized_word = i.normalized_word
            """
        )
        connection.execute(
            """
            INSERT OR IGNORE INTO vocabulary_contexts(
                vocabulary_entry_id, article_id, article_sentence_id, source_word,
                source_sentence, start_offset, end_offset, contextual_meaning_zh,
                explanation_zh, ai_status, is_manual, created_at, updated_at
            )
            SELECT e.id, i.source_article_id, NULL, i.display_word, i.source_sentence,
                   COALESCE(i.source_character_index, 0),
                   COALESCE(i.source_character_index, 0) + length(i.display_word),
                   i.meaning, i.note,
                   CASE WHEN i.meaning != '' OR i.note != '' THEN 'ready' ELSE 'pending' END,
                   CASE WHEN i.meaning != '' OR i.note != '' THEN 1 ELSE 0 END,
                   i.created_at, i.updated_at
            FROM vocabulary_items i JOIN vocabulary_entries e ON e.normalized_word = i.normalized_word
            WHERE i.source_sentence != ''
            """
        )
        defaults = {
            "vocabulary_typing_count": "5",
            "vocabulary_auto_enrich": "1",
            "vocabulary_audio_preference": "dictionary",
        }
        connection.executemany(
            "INSERT OR IGNORE INTO settings(key, value, updated_at) VALUES (?, ?, ?)",
            [(key, value, now) for key, value in defaults.items()],
        )
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (6)")

    def _apply_version_7(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS article_word_occurrences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id INTEGER NOT NULL,
                article_sentence_id INTEGER,
                normalized_word TEXT NOT NULL,
                source_word TEXT NOT NULL,
                source_sentence TEXT NOT NULL DEFAULT '',
                start_offset INTEGER NOT NULL,
                end_offset INTEGER NOT NULL,
                occurrence_index INTEGER NOT NULL,
                extraction_version TEXT NOT NULL DEFAULT 'word-v1',
                created_at TEXT NOT NULL,
                FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
                FOREIGN KEY (article_sentence_id) REFERENCES article_sentences(id) ON DELETE SET NULL,
                UNIQUE(article_id, start_offset, end_offset)
            )
            """
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_article_words_article ON article_word_occurrences(article_id, occurrence_index)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_article_words_normalized ON article_word_occurrences(normalized_word, article_id)")
        connection.execute("DELETE FROM schema_version")
        connection.execute("INSERT INTO schema_version(version) VALUES (7)")
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
