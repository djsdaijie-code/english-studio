from __future__ import annotations

import os
import sqlite3
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.learning_repository import LearningRepository, rank_for_days
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.models.learning import LearningEvent
from english_typing_trainer.services.learning_progress import LearningProgressService
from english_typing_trainer.services.learning_time import LearningTimeTracker
from english_typing_trainer.ui.daily_learning_card import DailyLearningCard
from english_typing_trainer.ui.main_window import MainWindow


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class FakeClock:
    def __init__(self, wall: datetime) -> None:
        self.monotonic_value = 100.0
        self.wall_value = wall

    def monotonic(self) -> float:
        return self.monotonic_value

    def wall(self) -> datetime:
        return self.wall_value

    def advance(self, seconds: float) -> None:
        self.monotonic_value += seconds
        self.wall_value += timedelta(seconds=seconds)


def _tracker(tmp_path: Path, wall: datetime | None = None, idle: int = 90):
    context = build_app_context(data_dir=tmp_path / "data")
    clock = FakeClock(wall or datetime(2026, 7, 13, 12, 0, 0))
    tracker = LearningTimeTracker(
        context.learning_repository,
        context.learning_progress_service,
        monotonic_clock=clock.monotonic,
        wall_clock=clock.wall,
        idle_timeout_seconds=idle,
        flush_interval_seconds=20,
    )
    return context, clock, tracker


def _save_seconds(repository: LearningRepository, when: datetime, seconds: float) -> None:
    repository.save_events([LearningEvent("typing_activity", seconds, when)])


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_schema_8_creates_learning_tables_and_defaults(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        assert context.database.get_schema_version() == 10
        names = {row[0] for row in context.database.connect().execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        assert {"daily_learning_stats", "learning_events", "achievements", "profile_progress"} <= names
        settings = context.settings_service.get_settings()
        assert settings.daily_learning_goal_minutes == 15
        assert settings.learning_idle_timeout_seconds == 90
        assert settings.checkin_animation_enabled is True
    finally:
        context.database.close()


def test_v7_migration_creates_backup_and_preserves_existing_data(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db_path = data_dir / "typing_trainer.db"
    connection = sqlite3.connect(db_path)
    runner = MigrationRunner()
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    for version in range(1, 8):
        getattr(runner, f"_apply_version_{version}")(connection)
    connection.execute(
        "INSERT INTO articles(title,original_filename,source_path,content_hash,full_text,character_count,word_count,section_count,imported_at,is_deleted) "
        "VALUES ('Legacy','legacy.txt','legacy.txt','legacy','Hello.',6,1,0,'2026-01-01T00:00:00',0)"
    )
    connection.commit()
    connection.close()

    database = DatabaseManager(db_path)
    try:
        database.initialize()
        assert database.get_schema_version() == 10
        assert database.connect().execute("SELECT title FROM articles").fetchone()[0] == "Legacy"
        backups = list((data_dir / "backups").glob("typing_trainer-v7-before-v10-*.db"))
        assert len(backups) == 1
        backup = sqlite3.connect(backups[0])
        try:
            assert backup.execute("SELECT version FROM schema_version").fetchone()[0] == 7
            assert backup.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1
        finally:
            backup.close()
    finally:
        database.close()


def test_v7_migration_rolls_back_when_schema_8_fails(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "data" / "typing_trainer.db"
    db_path.parent.mkdir()
    connection = sqlite3.connect(db_path)
    runner = MigrationRunner()
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    for version in range(1, 8):
        getattr(runner, f"_apply_version_{version}")(connection)
    connection.commit()
    connection.close()

    def fail_version_8(self, migration_connection):
        migration_connection.execute("CREATE TABLE should_rollback(value INTEGER)")
        raise RuntimeError("simulated migration failure")

    monkeypatch.setattr(MigrationRunner, "_apply_version_8", fail_version_8)
    database = DatabaseManager(db_path)
    with pytest.raises(RuntimeError, match="simulated migration failure"):
        database.initialize()
    database.close()
    verification = sqlite3.connect(db_path)
    try:
        assert verification.execute("SELECT version FROM schema_version").fetchone()[0] == 7
        assert verification.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='should_rollback'"
        ).fetchone()[0] == 0
    finally:
        verification.close()


def test_learning_timer_counts_activity_caps_idle_and_resumes(tmp_path: Path) -> None:
    context, clock, tracker = _tracker(tmp_path)
    try:
        tracker.tick()
        assert context.learning_repository.dashboard(clock.wall().date()).effective_seconds == 0
        tracker.activity("typing_activity")
        clock.advance(95)
        tracker.tick()
        assert tracker.active is False
        assert context.learning_repository.dashboard(clock.wall().date()).effective_seconds == pytest.approx(90)
        tracker.activity("typing_activity")
        clock.advance(12)
        tracker.stop()
        assert context.learning_repository.dashboard(clock.wall().date()).effective_seconds == pytest.approx(102)
    finally:
        context.database.close()


def test_network_wait_and_non_learning_page_time_are_excluded(tmp_path: Path) -> None:
    context, clock, tracker = _tracker(tmp_path)
    try:
        tracker.activity("typing_activity")
        clock.advance(10)
        tracker.tick()
        tracker.suspend_for_network()
        clock.advance(300)
        tracker.tick()
        assert context.learning_repository.dashboard(clock.wall().date()).effective_seconds == pytest.approx(10)
        tracker.activity("meaning_revealed")
        clock.advance(8)
        tracker.stop()
        clock.advance(60)
        tracker.tick()
        assert context.learning_repository.dashboard(clock.wall().date()).effective_seconds == pytest.approx(18)
    finally:
        context.database.close()


def test_audio_and_reading_time_stop_at_idle_limit(tmp_path: Path) -> None:
    context, clock, tracker = _tracker(tmp_path)
    try:
        tracker.activity("audio_started", related_sentence_id=None)
        clock.advance(30)
        tracker.activity("audio_finished")
        clock.advance(100)
        tracker.tick()
        assert context.learning_repository.dashboard(clock.wall().date()).effective_seconds == pytest.approx(120)
    finally:
        context.database.close()


def test_learning_timer_splits_time_across_midnight_and_batches_rows(tmp_path: Path) -> None:
    context, clock, tracker = _tracker(tmp_path, datetime(2026, 7, 13, 23, 59, 30))
    try:
        tracker.activity("typing_activity")
        for _ in range(6):
            clock.advance(10)
            tracker.tick()
        tracker.stop()
        rows = context.database.connect().execute(
            "SELECT date,effective_seconds FROM daily_learning_stats ORDER BY date"
        ).fetchall()
        assert [(row["date"], row["effective_seconds"]) for row in rows] == [
            ("2026-07-13", 30.0), ("2026-07-14", 30.0)
        ]
        event_count = context.database.connect().execute(
            "SELECT COUNT(*) FROM learning_events WHERE active_seconds>0"
        ).fetchone()[0]
        assert event_count == 4
    finally:
        context.database.close()


@pytest.mark.parametrize(
    ("total_minutes", "xp", "tier"),
    [(15, 100, 15), (30, 160, 30), (45, 200, 45), (60, 230, 60), (90, 250, 90), (240, 250, 90)],
)
def test_daily_tiers_award_xp_once_and_cap_at_90_minutes(
    tmp_path: Path, total_minutes: int, xp: int, tier: int
) -> None:
    context = build_app_context(data_dir=tmp_path / f"data-{total_minutes}")
    when = datetime(2026, 7, 13, 12, 0, 0)
    try:
        _save_seconds(context.learning_repository, when, total_minutes * 60)
        dashboard = context.learning_repository.dashboard(when.date())
        assert dashboard.awarded_xp == xp
        assert dashboard.current_tier_minutes == tier
        assert dashboard.checked_in is True
        _save_seconds(context.learning_repository, when, 0)
        assert context.learning_repository.dashboard(when.date()).awarded_xp == xp
    finally:
        context.database.close()


def test_health_reminders_are_idempotent_per_day(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        when = datetime(2026, 7, 13, 12, 0, 0)
        _save_seconds(context.learning_repository, when, 240 * 60)
        for minutes in (120, 180, 240):
            assert context.learning_repository.mark_reminder(when.date().isoformat(), minutes) is True
            assert context.learning_repository.mark_reminder(when.date().isoformat(), minutes) is False
    finally:
        context.database.close()


def test_disabled_health_reminders_do_not_consume_daily_notice(tmp_path: Path) -> None:
    context, clock, tracker = _tracker(tmp_path)
    try:
        _save_seconds(context.learning_repository, clock.wall(), 120 * 60)
        tracker.configure(90, health_reminders_enabled=False)
        tracker.activity("meaning_revealed")
        assert tracker.flush().reminders == []
        row = context.database.connect().execute(
            "SELECT reminder_120_shown FROM daily_learning_stats WHERE date=?",
            (clock.wall().date().isoformat(),),
        ).fetchone()
        assert row[0] == 0
        tracker.configure(90, health_reminders_enabled=True)
        tracker.activity("meaning_revealed")
        assert tracker.flush().reminders == [120]
    finally:
        context.database.close()


@pytest.mark.parametrize(
    ("days", "rank"),
    [(0, "启程 III"), (1, "启程 III"), (3, "启程 II"), (30, "微光 I"),
     (90, "晨星 I"), (240, "星河 I"), (365, "极光"), (500, "天穹"), (730, "恒星")],
)
def test_rank_thresholds(days: int, rank: str) -> None:
    assert rank_for_days(days)[0] == rank


def test_streak_week_month_and_rank_survive_a_missed_day(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    today = date(2026, 7, 13)
    try:
        for offset in (0, 2, 3):
            _save_seconds(context.learning_repository, datetime.combine(today - timedelta(days=offset), datetime.min.time()), 900)
        dashboard = context.learning_repository.dashboard(today)
        assert dashboard.total_checkin_days == 3
        assert dashboard.current_streak == 1
        assert dashboard.longest_streak == 2
        assert dashboard.week_completed == 1
        assert dashboard.month_completed == 3
        assert dashboard.current_rank == "启程 II"
    finally:
        context.database.close()


def test_achievements_unlock_once_and_track_calendar_habits(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        for day_number in range(13, 18):
            day = date(2026, 7, day_number)
            _save_seconds(context.learning_repository, datetime.combine(day, datetime.min.time()), 900)
        unlocked = context.learning_progress_service.evaluate_achievements(date(2026, 7, 17))
        assert "初次启程" in unlocked
        assert "一周同行" in unlocked
        for day_number in list(range(1, 13)) + list(range(18, 21)):
            day = date(2026, 7, day_number)
            _save_seconds(context.learning_repository, datetime.combine(day, datetime.min.time()), 900)
        unlocked = context.learning_progress_service.evaluate_achievements(date(2026, 7, 20))
        assert "稳定一月" in unlocked
        assert context.learning_progress_service.evaluate_achievements(date(2026, 7, 20)) == []
    finally:
        context.database.close()


def test_learning_settings_round_trip(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        settings = context.settings_service.get_settings()
        saved = context.settings_service.save_settings(replace(
            settings,
            daily_learning_goal_minutes=45,
            learning_idle_timeout_seconds=120,
            checkin_animation_enabled=False,
            health_reminders_enabled=False,
            reduce_motion=True,
        ))
        assert saved.daily_learning_goal_minutes == 45
        assert saved.learning_idle_timeout_seconds == 120
        assert saved.checkin_animation_enabled is False
        assert saved.health_reminders_enabled is False
        assert saved.reduce_motion is True
    finally:
        context.database.close()


def test_daily_learning_card_and_settings_fit_supported_sizes_and_themes(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(context)
        for theme in ("light", "dark"):
            context.settings_service.save_settings(replace(context.settings_service.get_settings(), theme=theme))
            window.settings = context.settings_service.get_settings()
            window._apply_settings()
            for width, height in ((1280, 720), (1500, 1000), (1920, 1080)):
                window.resize(width, height)
                window.show()
                app.processEvents()
                assert window.daily_learning_card.isVisible()
                assert window.daily_learning_card.width() > 800
                assert window.daily_learning_card.height() <= 196
                assert window.article_list.height() > 100
        assert window.settings_page.daily_goal_combo.count() == 4
        assert window.settings_page.learning_idle_combo.count() == 3
        window.close()
    finally:
        context.database.close()


def test_milestone_animation_is_not_replayed() -> None:
    _app()
    card = DailyLearningCard()
    assert card.play_milestone(15, reduce_motion=True) is True
    assert card.play_milestone(15, reduce_motion=True) is False
