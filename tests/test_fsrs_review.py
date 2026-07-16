from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.services.fsrs_review import FsrsReviewService
from english_typing_trainer.ui.fsrs_review_page import FsrsReviewPage
from english_typing_trainer.ui.main_window import MainWindow
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication


class Clock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def make_service(tmp_path: Path, clock: Clock):
    context = build_app_context(data_dir=tmp_path / "data")
    service = FsrsReviewService(context.database, now_provider=clock)
    context.fsrs_review_service = service
    return context, service


def add_word(context, word: str = "English", sentence: str = "English helps people communicate."):
    return context.vocabulary_learning_service.collect(word, sentence=sentence)


def test_schema_10_creates_fsrs_tables_and_defaults(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        connection = context.database.connect()
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert context.database.get_schema_version() == 12
        assert {"fsrs_profiles", "vocabulary_review_cards", "vocabulary_review_logs", "dictation_attempts"} <= tables
        values = {row[0]: row[1] for row in connection.execute("SELECT key,value FROM settings")}
        assert values["fsrs_desired_retention"] == "0.90"
        assert values["fsrs_new_cards_per_day"] == "20"
    finally:
        context.database.close()


def test_v8_to_v10_backup_and_rollback(tmp_path: Path, monkeypatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    database_path = data / "typing_trainer.db"
    connection = sqlite3.connect(database_path)
    runner = MigrationRunner()
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    for version in range(1, 9):
        getattr(runner, f"_apply_version_{version}")(connection)
    connection.commit()
    connection.close()
    manager = DatabaseManager(database_path)
    manager.initialize()
    try:
        assert manager.get_schema_version() == 12
        assert list((data / "backups").glob("typing_trainer-v8-*.db"))
    finally:
        manager.close()

    broken = tmp_path / "broken.db"
    connection = sqlite3.connect(broken)
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner = MigrationRunner()
    for version in range(1, 9):
        getattr(runner, f"_apply_version_{version}")(connection)
    original = runner._apply_version_10
    monkeypatch.setattr(runner, "_apply_version_10", lambda _connection: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 8
    monkeypatch.setattr(runner, "_apply_version_10", original)
    connection.close()


def test_new_cards_keep_spelling_and_meaning_independent(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc))
    context, service = make_service(tmp_path, clock)
    try:
        add_word(context, "OpenAI")
        queue = service.build_today_queue(new_limit=20)
        assert [(item.card.card_type, item.target_word) for item in queue.items] == [("spelling", "OpenAI"), ("meaning", "OpenAI")]
        spelling, meaning = queue.items
        updated = service.rate(spelling.card.id or 0, "good")
        assert updated.last_reviewed_at_utc == clock.now
        assert service.repository.get_card(meaning.card.id or 0).last_reviewed_at_utc is None
        log = context.database.connect().execute("SELECT rating,review_log_json FROM vocabulary_review_logs").fetchone()
        assert log["rating"] == "good" and '"rating": 3' in log["review_log_json"]
    finally:
        context.database.close()


@pytest.mark.parametrize("rating", ["again", "hard", "good", "easy"])
def test_fsrs_accepts_all_ratings_and_persists_restart(tmp_path: Path, rating: str) -> None:
    clock = Clock(datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc))
    context, service = make_service(tmp_path, clock)
    try:
        add_word(context)
        card = service.build_today_queue().items[0].card
        updated = service.rate(card.id or 0, rating)
        assert updated.state in {"learning", "review", "relearning"}
        context.database.close()
        reopened = build_app_context(data_dir=tmp_path / "data")
        try:
            stored = reopened.fsrs_review_service.repository.get_card(card.id or 0)
            assert stored is not None and stored.fsrs_card_json.startswith("{")
            assert reopened.database.connect().execute("SELECT COUNT(*) FROM vocabulary_review_logs").fetchone()[0] == 1
        finally:
            reopened.database.close()
    finally:
        context.database.close()


def test_old_next_review_is_initial_due_reference_and_queue_limits(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc))
    context, service = make_service(tmp_path, clock)
    try:
        collected = add_word(context)
        state = context.vocabulary_learning_service.repository.get_state(collected.entry.id)
        state.next_review_at = clock.now + timedelta(days=2)
        with context.database.transaction() as connection:
            context.vocabulary_learning_service.repository.update_state(connection, state)
        assert service.build_today_queue(new_limit=1).items == []
        cards = service._create_initial_cards(collected.entry.id, collected.context.id, state.next_review_at.isoformat(), clock.now)
        assert all(item.card.due_at_utc > clock.now for item in cards)
        assert service.build_today_queue(new_limit=1).items == []
    finally:
        context.database.close()


def test_defer_suspend_and_delete_do_not_create_fake_rating(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc))
    context, service = make_service(tmp_path, clock)
    try:
        collected = add_word(context, "API")
        card = service.build_today_queue().items[0].card
        service.defer(card.id or 0)
        assert context.database.connect().execute("SELECT COUNT(*) FROM vocabulary_review_logs").fetchone()[0] == 0
        service.suspend_entry(collected.entry.id or 0)
        assert service.build_today_queue().items == []
        context.vocabulary_learning_service.delete(collected.entry.id or 0)
        assert context.database.connect().execute("SELECT COUNT(*) FROM vocabulary_review_cards").fetchone()[0] == 0
    finally:
        context.database.close()


def test_retention_profiles_and_local_midnight_bounds(tmp_path: Path) -> None:
    clock = Clock(datetime(2026, 7, 13, 15, 59, tzinfo=timezone.utc))
    context, service = make_service(tmp_path, clock)
    try:
        assert service.set_desired_retention(0.93).desired_retention == 0.93
        with pytest.raises(ValueError):
            service.set_desired_retention(0.91)
        start, end = service._utc_day_bounds(clock.now)
        assert end > start and end - start in {timedelta(hours=23), timedelta(hours=24), timedelta(hours=25)}
    finally:
        context.database.close()


def test_review_page_strict_spelling_and_rating_ui(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    clock = Clock(datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc))
    context, service = make_service(tmp_path, clock)
    try:
        add_word(context, "English")
        item = service.build_today_queue().items[0]
        page = FsrsReviewPage()
        ratings: list[tuple[int, str]] = []
        page.rating_requested.connect(lambda card_id, rating: ratings.append((card_id, rating)))
        page.load_queue([item])
        for character in "english":
            page._key(QKeyEvent(QKeyEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character))
        assert page.input.toPlainText() == "english"
        assert page.errors == 1
        assert all(not button.isHidden() for button in page.rating_buttons)
        page._rate("again")
        application.processEvents()
        assert ratings == [(item.card.id, "again")]
    finally:
        context.database.close()


def test_special_practice_today_review_routes_to_fsrs_queue(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        context.vocabulary_learning_service.collect("English", sentence="English helps people communicate.")
        window = MainWindow(context)
        window.special_practice_page.start_today_review_requested.emit()
        application.processEvents()
        assert window.stack.currentWidget() is window.fsrs_review_page
        assert window.fsrs_review_page.current is not None
        window.close()
    finally:
        context.database.close()
