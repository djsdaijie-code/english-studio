from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.repositories import HistoryQuery, PracticeRepository
from english_typing_trainer.statistics.metrics import (
    MIN_EFFECTIVE_CHARACTERS,
    calculate_cpm,
    calculate_wpm,
    is_effective_result,
)
from english_typing_trainer.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _insert_session(
    connection,
    *,
    created_at: str,
    active_seconds: float,
    correct_characters: int,
    wpm: float,
    cpm: float,
    completed: int = 1,
    app_version: str = "0.1.0",
) -> None:
    connection.execute(
        """
        INSERT INTO practice_sessions(
            article_id, section_id, started_at, finished_at, active_seconds, paused_seconds,
            total_keystrokes, correct_keystrokes, error_keystrokes, correct_characters,
            wpm, cpm, accuracy, completion_rate, completed, practice_type,
            longest_correct_streak, average_wpm, app_version, created_at
        ) VALUES (
            NULL, NULL, ?, ?, ?, 0, ?, ?, 0, ?, ?, ?, 100.0, 1.0, ?, 'article_section',
            ?, ?, ?, ?
        )
        """,
        (
            created_at,
            created_at,
            active_seconds,
            correct_characters,
            correct_characters,
            correct_characters,
            wpm,
            cpm,
            completed,
            correct_characters,
            wpm if completed else None,
            app_version,
            created_at,
        ),
    )


def test_speed_calculation_has_minimum_duration_floor() -> None:
    assert calculate_wpm(50, 0.0) == 0.0
    assert calculate_wpm(50, 0.1) == 0.0
    assert calculate_cpm(50, 0.1) == 0.0
    assert calculate_wpm(50, 1.0) > 0.0


def test_effective_result_boundaries() -> None:
    assert not is_effective_result(completed=True, correct_characters=MIN_EFFECTIVE_CHARACTERS, active_seconds=0.0)
    assert not is_effective_result(completed=True, correct_characters=MIN_EFFECTIVE_CHARACTERS, active_seconds=0.1)
    assert not is_effective_result(completed=True, correct_characters=MIN_EFFECTIVE_CHARACTERS, active_seconds=1.0)
    assert not is_effective_result(completed=True, correct_characters=MIN_EFFECTIVE_CHARACTERS, active_seconds=29.0)
    assert is_effective_result(completed=True, correct_characters=MIN_EFFECTIVE_CHARACTERS, active_seconds=30.0)


def test_statistics_exclude_invalid_and_automated_sessions(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        connection = context.database.connect()
        _insert_session(
            connection,
            created_at="2026-06-20T10:00:00",
            active_seconds=60,
            correct_characters=150,
            wpm=30,
            cpm=150,
        )
        _insert_session(
            connection,
            created_at="2026-06-20T10:05:00",
            active_seconds=29,
            correct_characters=150,
            wpm=9999,
            cpm=99999,
        )
        _insert_session(
            connection,
            created_at="2026-06-20T10:10:00",
            active_seconds=60,
            correct_characters=150,
            wpm=250,
            cpm=1250,
            app_version="0.1.0+acceptance",
        )
        connection.commit()

        overview = context.statistics_service.overview()
        assert overview["average_wpm"] == 30
        assert overview["highest_effective_wpm"] == 30

        trend = [row for row in context.statistics_service.trend_data("all") if row["date"] == "2026-06-20"]
        assert len(trend) == 1
        assert trend[0]["average_wpm"] == 30
    finally:
        context.database.close()


def test_history_valid_filter_and_flags(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        connection = context.database.connect()
        _insert_session(
            connection,
            created_at="2026-06-21T10:00:00",
            active_seconds=60,
            correct_characters=150,
            wpm=30,
            cpm=150,
        )
        _insert_session(
            connection,
            created_at="2026-06-21T10:05:00",
            active_seconds=1,
            correct_characters=20,
            wpm=240,
            cpm=1200,
        )
        _insert_session(
            connection,
            created_at="2026-06-21T10:10:00",
            active_seconds=60,
            correct_characters=150,
            wpm=250,
            cpm=1250,
            app_version="0.1.0+runtime-check",
        )
        connection.commit()

        repo = PracticeRepository(context.database.connect)
        rows = repo.list_history(HistoryQuery())
        assert len(rows) == 2
        assert any(row["is_effective_result"] == 0 for row in rows)

        valid_rows = repo.list_history(HistoryQuery(valid_only=True))
        assert len(valid_rows) == 1
        assert valid_rows[0]["wpm"] == 30
    finally:
        context.database.close()


def test_practice_focus_mode_hides_sidebar(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "lesson.txt"
        file_path.write_text("A" * 180, encoding="utf-8")
        imported = context.article_library.import_txt_file(file_path, 300)
        assert imported.article is not None

        window = MainWindow(context)
        window.show()
        material = context.practice_service.load_practice_material(imported.article.id, mode="resume")
        window._begin_practice(material)
        app.processEvents()

        assert not window.sidebar.isVisible()
        assert window.practice_view.title_label.text() == imported.article.title
    finally:
        context.database.close()


def test_statistics_cards_fit_small_window(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(context)
        window.resize(1280, 720)
        window._show_statistics()
        window.show()
        app.processEvents()

        metrics_layout = window.statistics_page.metrics_layout
        for index in range(metrics_layout.count()):
            widget = metrics_layout.itemAt(index).widget()
            assert widget is not None
            assert widget.geometry().right() <= window.statistics_page.width()
    finally:
        context.database.close()
