from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import shutil
import sqlite3

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.models.pronunciation import PronunciationResult
from english_typing_trainer.models.tts import TTSAudioResult, TTSRequest
from english_typing_trainer.services.course_capabilities import (
    CourseCapabilityContentError,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COURSE_ID = "ai-large-models"
COURSE_STABLE_KEY = "ai-large-models-course"
FIRST_ITEM = "ai-large-models-sentence-0001"
SECOND_CHAT_ITEM = "ai-large-models-sentence-0012"
DAY_TWO = "ai-l1-u01-d02"


class FakeTTSProvider:
    name = "minimax"

    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, request, *, cancel_event=None):
        self.calls += 1
        return TTSAudioResult(
            b"ID3-course-audio",
            request.audio_format,
            request.provider,
            request.model,
            request.voice_id,
            duration_ms=900,
            usage_characters=len(request.text),
        )


def _copy_courses(tmp_path: Path) -> Path:
    destination = tmp_path / "courses"
    shutil.copytree(PROJECT_ROOT / "courses", destination)
    return destination


def _unit_path(courses_root: Path) -> Path:
    return courses_root / "ai-large-models" / "units" / "unit-01-foundations.json"


def _read_unit(courses_root: Path) -> dict:
    return json.loads(_unit_path(courses_root).read_text(encoding="utf-8"))


def _write_unit(courses_root: Path, payload: dict) -> None:
    _unit_path(courses_root).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _create_legacy_database(path: Path, version: int) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner = MigrationRunner()
    for target in range(1, version + 1):
        getattr(runner, f"_apply_version_{target}")(connection)

    stamp = "2026-07-16T08:00:00+00:00"
    connection.execute(
        """
        INSERT INTO articles(
            title, original_filename, source_path, content_hash, full_text,
            character_count, word_count, section_count, imported_at
        ) VALUES ('Legacy', 'legacy.txt', 'legacy.txt', 'legacy-hash',
                  'Legacy article body.', 20, 3, 0, ?)
        """,
        (stamp,),
    )
    connection.execute(
        """
        INSERT INTO vocabulary_entries(
            normalized_word, display_word, lemma, created_at, updated_at
        ) VALUES ('legacy', 'Legacy', 'legacy', ?, ?)
        """,
        (stamp, stamp),
    )
    connection.execute(
        """
        INSERT INTO vocabulary_contexts(
            vocabulary_entry_id, article_id, source_word, source_sentence,
            start_offset, end_offset, created_at, updated_at
        ) VALUES (1, 1, 'Legacy', 'Legacy article body.', 0, 6, ?, ?)
        """,
        (stamp, stamp),
    )
    connection.execute(
        """
        INSERT INTO vocabulary_review_cards(
            vocabulary_entry_id, vocabulary_context_id, card_type,
            fsrs_card_json, due_at_utc, state, created_at, updated_at
        ) VALUES (1, 1, 'spelling', '{"legacy":true}', ?, 'learning', ?, ?)
        """,
        (stamp, stamp, stamp),
    )
    connection.execute(
        """
        INSERT INTO dictation_attempts(
            vocabulary_entry_id, vocabulary_context_id, dictation_type,
            comparison_mode, expected_text, user_input, normalized_comparison,
            reviewed_at_utc, created_at
        ) VALUES (1, 1, 'word', 'strict', 'Legacy', 'Legacy',
                  'legacy => legacy', ?, ?)
        """,
        (stamp, stamp),
    )
    connection.execute(
        """
        INSERT INTO pronunciation_attempts(
            target_type, vocabulary_entry_id, vocabulary_context_id,
            reference_text_hash, provider, locale, status, recorded_at,
            created_at
        ) VALUES ('word', 1, 1, 'legacy-reference-hash', 'azure', 'en-US',
                  'completed', ?, ?)
        """,
        (stamp, stamp),
    )
    if version >= 12:
        connection.execute(
            """
            INSERT INTO course_enrollments(
                course_stable_key, status, course_version, content_version,
                enrolled_at, created_at, updated_at
            ) VALUES (?, 'active', '0.1.0', '0.1.0', ?, ?, ?)
            """,
            (COURSE_STABLE_KEY, stamp, stamp, stamp),
        )
    connection.commit()
    connection.close()


def _columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"PRAGMA table_info({table})")}


def test_schema_13_fresh_install_is_minimal_and_body_free(tmp_path: Path) -> None:
    manager = DatabaseManager(tmp_path / "fresh.db")
    manager.initialize()
    try:
        connection = manager.connect()
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert manager.get_schema_version() == 13
        assert {
            "course_activity_progress",
            "course_capability_attempts",
            "course_review_cards",
            "course_review_logs",
        } <= tables
        assert "learning_content_links" not in tables
        assert {
            "source_type",
            "course_stable_key",
            "item_stable_key",
            "content_version",
        } <= _columns(connection, "vocabulary_contexts")
        assert not {
            "course_stable_key",
            "item_stable_key",
            "content_version",
        } & _columns(connection, "tts_audio_cache")
        assert not {
            "course_stable_key",
            "item_stable_key",
            "content_version",
        } & _columns(connection, "pronunciation_attempts")
        assert not {
            "expected_text",
            "user_input",
            "source_sentence",
            "course_text",
        } & _columns(connection, "course_capability_attempts")
        activity_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='course_activity_progress'"
        ).fetchone()[0]
        assert "UNIQUE(enrollment_id, item_stable_key, activity_type)" in activity_sql
        review_sql = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name='course_review_cards'"
        ).fetchone()[0]
        assert "UNIQUE(enrollment_id, item_stable_key, card_type)" in review_sql
    finally:
        manager.close()


@pytest.mark.parametrize("source_version", [11, 12])
def test_schema_11_or_12_upgrade_preserves_data_backs_up_and_is_idempotent(
    tmp_path: Path,
    source_version: int,
) -> None:
    data_dir = tmp_path / f"v{source_version}"
    data_dir.mkdir()
    database_path = data_dir / "typing_trainer.db"
    _create_legacy_database(database_path, source_version)
    before = sqlite3.connect(database_path)
    unchanged_tables = {
        table: _columns(before, table)
        for table in (
            "tts_audio_cache",
            "dictation_attempts",
            "pronunciation_attempts",
            "vocabulary_review_cards",
        )
    }
    vocabulary_columns = _columns(before, "vocabulary_contexts")
    before.close()

    manager = DatabaseManager(database_path)
    manager.initialize()
    manager.initialize()
    try:
        connection = manager.connect()
        assert manager.get_schema_version() == 13
        assert connection.execute("SELECT full_text FROM articles").fetchone()[0] == "Legacy article body."
        assert connection.execute("SELECT source_sentence FROM vocabulary_contexts").fetchone()[0] == "Legacy article body."
        assert tuple(
            connection.execute(
                "SELECT expected_text,user_input FROM dictation_attempts"
            ).fetchone()
        ) == ("Legacy", "Legacy")
        assert connection.execute("SELECT reference_text_hash FROM pronunciation_attempts").fetchone()[0] == "legacy-reference-hash"
        assert connection.execute("SELECT fsrs_card_json FROM vocabulary_review_cards").fetchone()[0] == '{"legacy":true}'
        for table, columns in unchanged_tables.items():
            assert _columns(connection, table) == columns
        assert _columns(connection, "vocabulary_contexts") - vocabulary_columns == {
            "source_type",
            "course_stable_key",
            "item_stable_key",
            "content_version",
        }
        if source_version == 12:
            assert connection.execute("SELECT course_stable_key FROM course_enrollments").fetchone()[0] == COURSE_STABLE_KEY
        assert connection.execute("SELECT COUNT(*) FROM course_activity_progress").fetchone()[0] == 0
        backups = list(
            (data_dir / "backups").glob(
                f"typing_trainer-v{source_version}-before-v13-*.db"
            )
        )
        assert len(backups) == 1
    finally:
        manager.close()


def test_schema_13_failure_rolls_back_all_ddl_to_schema_12(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "rollback.db"
    _create_legacy_database(database_path, 12)
    connection = sqlite3.connect(database_path)
    runner = MigrationRunner()
    original = runner._apply_version_13

    def broken(target: sqlite3.Connection) -> None:
        original(target)
        target.execute("CREATE TABLE partial_schema_13(id INTEGER PRIMARY KEY)")
        raise RuntimeError("schema 13 failed")

    monkeypatch.setattr(runner, "_apply_version_13", broken)
    with pytest.raises(RuntimeError, match="schema 13 failed"):
        runner.migrate(connection)

    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 12
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name='partial_schema_13'"
    ).fetchone() is None
    assert "source_type" not in _columns(connection, "vocabulary_contexts")
    assert connection.execute(
        "SELECT name FROM sqlite_master WHERE name='course_activity_progress'"
    ).fetchone() is None
    connection.close()


def test_course_tts_uses_stable_versioned_cache_without_body_preview(
    tmp_path: Path,
) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    provider = FakeTTSProvider()
    try:
        item = context.course_capability_service.item(COURSE_ID, FIRST_ITEM)
        request = TTSRequest(text=item.text, speed=0.8)
        first = context.tts_service.get_or_generate_course(provider, request, item.ref)
        second = context.tts_service.get_or_generate_course(provider, request, item.ref)
        assert first.file_path == second.file_path
        assert provider.calls == 1
        assert context.tts_service.course_cache_key(item.ref, request) == context.tts_service.course_cache_key(
            item.ref,
            replace(request, text="Body text is not part of the course cache identity."),
        )
        row = context.database.connect().execute(
            "SELECT text_preview FROM tts_audio_cache WHERE cache_key=?",
            (first.cache_key,),
        ).fetchone()
        assert row[0] == ""
        context.course_capability_service.start_listening(item.ref)
        assert context.course_progress_service.get_activity_progress(
            COURSE_ID, FIRST_ITEM, "review"
        ).status == "in_progress"
        context.course_capability_service.complete_listening(item.ref)
        assert context.course_progress_service.get_activity_progress(
            COURSE_ID, FIRST_ITEM, "review"
        ).status == "completed"

        newer_ref = replace(item.ref, content_version="0.1.1")
        assert context.tts_service.course_cache_key(newer_ref, request) != first.cache_key
        context.tts_service.get_or_generate_course(provider, request, newer_ref)
        assert provider.calls == 2

        ordinary = TTSRequest(text="Ordinary article sentence.", speed=0.8)
        ordinary_audio = context.tts_service.get_or_generate(provider, ordinary)
        ordinary_preview = context.database.connect().execute(
            "SELECT text_preview FROM tts_audio_cache WHERE cache_key=?",
            (ordinary_audio.cache_key,),
        ).fetchone()[0]
        assert ordinary_preview == ordinary.text
        assert context.database.connect().execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
    finally:
        context.database.close()


def test_course_dictation_and_speaking_use_independent_state_and_history(
    tmp_path: Path,
) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        item = context.course_capability_service.item(COURSE_ID, FIRST_ITEM)
        first = context.course_capability_service.record_dictation(
            item.ref,
            score=0.0,
            error_count=4,
            omitted_count=2,
            inserted_count=1,
            replay_count=3,
            duration_ms=1500,
        )
        completed_at = context.course_progress_service.get_activity_progress(
            COURSE_ID, FIRST_ITEM, "dictation"
        ).completed_at
        context.course_capability_service.record_dictation(
            item.ref,
            score=92.0,
            error_count=1,
            omitted_count=0,
            inserted_count=0,
            replay_count=1,
            duration_ms=700,
        )
        speaking = context.course_capability_service.record_speaking(
            item.ref,
            PronunciationResult(
                status="completed",
                provider="fake-speech",
                overall_score=61.0,
                accuracy_score=60.0,
                fluency_score=62.0,
                completeness_score=100.0,
                prosody_score=58.0,
            ),
            duration_ms=1200,
        )
        dictation_state = context.course_progress_service.get_activity_progress(
            COURSE_ID, FIRST_ITEM, "dictation"
        )
        speaking_state = context.course_progress_service.get_activity_progress(
            COURSE_ID, FIRST_ITEM, "speaking"
        )
        assert first.score == 0.0
        assert speaking.provider == "fake-speech"
        assert dictation_state.status == speaking_state.status == "completed"
        assert dictation_state.attempt_count == 2
        assert dictation_state.best_score == 92.0
        assert dictation_state.completed_at == completed_at
        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM course_capability_attempts").fetchone()[0] == 3
        assert connection.execute("SELECT COUNT(*) FROM dictation_attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM pronunciation_attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        columns = _columns(connection, "course_capability_attempts")
        assert not {"expected_text", "user_input", "reference_text", "source_sentence"} & columns
    finally:
        context.database.close()


def test_course_vocabulary_uses_shared_entries_and_dynamic_contexts(
    tmp_path: Path,
) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        first_item = context.course_capability_service.item(COURSE_ID, FIRST_ITEM)
        second_item = context.course_capability_service.item(
            COURSE_ID, SECOND_CHAT_ITEM
        )
        first_start = first_item.text.index("chat")
        second_start = second_item.text.index("chat")
        first = context.course_capability_service.collect_word(
            first_item.ref,
            "chat",
            start_offset=first_start,
            end_offset=first_start + 4,
        )
        second = context.course_capability_service.collect_word(
            second_item.ref,
            "chat",
            start_offset=second_start,
            end_offset=second_start + 4,
        )
        article = context.vocabulary_learning_service.collect(
            "chat",
            sentence="Chat here.",
            start_offset=0,
            end_offset=4,
        )
        assert first.entry.id == second.entry.id == article.entry.id
        entry, contexts, _state = context.vocabulary_learning_service.detail(
            first.entry.id or 0
        )
        assert entry is not None
        assert len(contexts) == 3
        course_contexts = [
            value for value in contexts if value.source_type == "built_in_course"
        ]
        assert {value.source_sentence for value in course_contexts} == {
            first_item.text,
            second_item.text,
        }
        rows = context.database.connect().execute(
            """
            SELECT source_sentence,course_stable_key,item_stable_key,content_version
            FROM vocabulary_contexts WHERE source_type='built_in_course'
            """
        ).fetchall()
        assert len(rows) == 2
        assert all(row[0] == "" and row[1] == COURSE_STABLE_KEY for row in rows)
        assert {row[2] for row in rows} == {FIRST_ITEM, SECOND_CHAT_ITEM}
        cards = context.course_capability_service.ensure_vocabulary_review(
            first_item.ref,
            first.entry.id or 0,
            first.context.id,
        )
        assert {card.card_type for card in cards} == {"spelling", "meaning"}
        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM course_review_cards").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
    finally:
        context.database.close()


def test_course_fsrs_is_stable_across_reorder_and_pauses_deprecated_items(
    tmp_path: Path,
) -> None:
    courses_root = _copy_courses(tmp_path)
    context = build_app_context(
        data_dir=tmp_path / "data",
        courses_root=courses_root,
    )
    try:
        service = context.course_capability_service
        original_ref = service.content_ref(COURSE_ID, FIRST_ITEM)
        first = service.ensure_sentence_review(original_ref)
        again = service.ensure_sentence_review(original_ref)
        assert first.id == again.id
        assert len(service.due_sentence_reviews()) == 1
        rated = service.rate_sentence_review(first.id or 0, "good")
        assert rated.last_reviewed_at_utc is not None
        assert context.database.connect().execute("SELECT COUNT(*) FROM course_review_logs").fetchone()[0] == 1

        payload = _read_unit(courses_root)
        first_sentence = next(
            item for item in payload["sentences"] if item["stable_key"] == FIRST_ITEM
        )
        second_sentence = next(
            item
            for item in payload["sentences"]
            if item["stable_key"] == "ai-large-models-sentence-0002"
        )
        first_sentence["chinese"] = "新建一段对话。"
        first_sentence["content_version"] = "0.1.1"
        first_sentence["order"], second_sentence["order"] = (
            second_sentence["order"],
            first_sentence["order"],
        )
        payload["sentences"].sort(key=lambda item: (item["day"], item["order"]))
        _write_unit(courses_root, payload)
        context.course_repository.reload()

        updated_ref = service.content_ref(COURSE_ID, FIRST_ITEM)
        updated = service.ensure_sentence_review(updated_ref)
        assert updated.id == first.id
        assert updated.content_version == "0.1.1"
        assert context.database.connect().execute("SELECT COUNT(*) FROM course_review_cards").fetchone()[0] == 1
        listening = service.ensure_sentence_review(
            updated_ref,
            "sentence_listening",
        )
        assert listening.id != first.id

        payload = _read_unit(courses_root)
        deprecated = next(
            item for item in payload["sentences"] if item["stable_key"] == FIRST_ITEM
        )
        deprecated["status"] = "deprecated"
        _write_unit(courses_root, payload)
        context.course_repository.reload()
        deprecated_ref = service.content_ref(COURSE_ID, FIRST_ITEM)
        with pytest.raises(CourseCapabilityContentError, match="Deprecated"):
            service.ensure_sentence_review(deprecated_ref)
        assert service.due_sentence_reviews() == ()
        assert context.database.connect().execute("SELECT COUNT(*) FROM course_review_cards").fetchone()[0] == 2
        assert context.database.connect().execute("SELECT COUNT(*) FROM course_review_logs").fetchone()[0] == 1
    finally:
        context.database.close()


def test_required_activities_drive_progress_without_score_threshold(
    tmp_path: Path,
) -> None:
    courses_root = _copy_courses(tmp_path)
    payload = _read_unit(courses_root)
    lesson = next(item for item in payload["lessons"] if item["lesson_id"] == DAY_TWO)
    lesson["activities"] = [
        {
            "activity_type": "typing",
            "sentence_ids": ["ai-s0007"],
            "required": True,
        },
        {
            "activity_type": "dictation",
            "sentence_ids": ["ai-s0008"],
            "required": True,
        },
        {
            "activity_type": "speaking",
            "sentence_ids": ["ai-s0009"],
            "required": False,
        },
    ]
    _write_unit(courses_root, payload)
    context = build_app_context(
        data_dir=tmp_path / "data",
        courses_root=courses_root,
    )
    try:
        typing = context.course_capability_service.content_ref(
            COURSE_ID,
            "ai-large-models-sentence-0007",
        )
        dictation = context.course_capability_service.content_ref(
            COURSE_ID,
            "ai-large-models-sentence-0008",
        )
        context.course_progress_service.complete_item(
            COURSE_ID,
            typing.item_stable_key,
        )
        partial = context.course_progress_service.get_lesson_progress(
            COURSE_ID,
            DAY_TWO,
        )
        assert (partial.completed_required_items, partial.total_required_items) == (1, 2)
        context.course_capability_service.record_dictation(
            dictation,
            score=0.0,
            error_count=99,
            omitted_count=5,
            inserted_count=4,
            replay_count=0,
            duration_ms=100,
        )
        completed = context.course_progress_service.get_lesson_progress(
            COURSE_ID,
            DAY_TWO,
        )
        assert completed.is_completed
        original_time = context.course_progress_service.get_activity_progress(
            COURSE_ID,
            dictation.item_stable_key,
            "dictation",
        ).completed_at
        context.course_capability_service.record_dictation(
            dictation,
            score=100.0,
            error_count=0,
            omitted_count=0,
            inserted_count=0,
            replay_count=0,
            duration_ms=100,
        )
        repeated = context.course_progress_service.get_activity_progress(
            COURSE_ID,
            dictation.item_stable_key,
            "dictation",
        )
        assert repeated.completed_at == original_time
        assert context.course_progress_service.get_activity_progress(
            COURSE_ID,
            "ai-large-models-sentence-0009",
            "speaking",
        ).status == "not_started"
    finally:
        context.database.close()
