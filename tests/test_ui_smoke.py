from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.ui.main_window import MainWindow

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_main_window_can_be_created_and_uses_chinese_navigation(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(context)
        window.show()
        app.processEvents()
        assert window.windowTitle() == "英语打字练习"
        assert window.nav_buttons[0].text() == "文章库"
        assert window.nav_buttons[1].text() == "专项练习"
        assert window.nav_buttons[2].text() == "生词本"
    finally:
        context.database.close()


def test_navigation_switches_pages_and_empty_state_is_visible(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(context)
        window.show()
        app.processEvents()
        assert window.empty_state.isVisible()
        window._show_special_practice()
        app.processEvents()
        assert window.stack.currentWidget() is window.special_practice_page
        window._show_vocabulary()
        app.processEvents()
        assert window.stack.currentWidget() is window.vocabulary_page
    finally:
        context.database.close()


def test_import_refreshes_article_list_and_preview(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "lesson.txt"
        file_path.write_text("Hello world.\n\nSecond paragraph.", encoding="utf-8")
        context.article_library.import_txt_file(file_path, 500)

        window = MainWindow(context)
        window.show()
        window._reload_articles()
        app.processEvents()

        assert window.article_list.count() == 1
        assert window.empty_state.isVisible() is False
        assert "Hello world." in window.preview_content.toPlainText()
    finally:
        context.database.close()


def test_settings_page_reads_and_saves_theme(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(context)
        window.show()
        app.processEvents()
        window._show_settings()
        index = window.settings_page.theme_combo.findData("dark")
        window.settings_page.theme_combo.setCurrentIndex(index)
        window._save_settings()
        app.processEvents()
        assert context.settings_service.get_settings().theme == "dark"
    finally:
        context.database.close()


def test_existing_schema3_database_opens_in_new_ui(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    context.database.close()
    reopened = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(reopened)
        window.show()
        app.processEvents()
        assert reopened.database.get_schema_version() == 5
    finally:
        reopened.database.close()
