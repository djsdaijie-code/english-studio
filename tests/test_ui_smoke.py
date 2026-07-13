from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QMessageBox

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
        assert window.nav_buttons[2].text() == "单词本"
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
        assert reopened.database.get_schema_version() == 8
    finally:
        reopened.database.close()


def test_article_preview_context_menu_is_bound_to_viewport_and_actions_work(tmp_path: Path, monkeypatch) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "lesson.txt"
        file_path.write_text("You learn English. You practice every day.", encoding="utf-8")
        article = context.article_library.import_txt_file(file_path, 500).article
        collected = context.vocabulary_learning_service.collect("You", sentence="You learn English.", article_id=article.id, start_offset=0, end_offset=3)

        window = MainWindow(context)
        window.resize(1280, 720)
        window.show()
        window._reload_articles()
        app.processEvents()

        viewport = window.preview_content.viewport()
        assert viewport.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        shown = []
        monkeypatch.setattr(window, "_show_article_preview_menu", lambda position: shown.append(position))
        for position in (QPoint(20, 20), QPoint(20, max(20, viewport.height() - 10))):
            event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, position, viewport.mapToGlobal(position))
            QApplication.sendEvent(viewport, event)
        app.processEvents()
        assert len(shown) == 2

        menu, view_action, rebuild_action = window._build_article_preview_menu()
        labels = [action.text() for action in menu.actions()]
        assert view_action.text() in labels and rebuild_action.text() in labels

        window._show_current_article_words()
        app.processEvents()
        assert window.stack.currentWidget() is window.vocabulary_page
        assert window.vocabulary_page.scope_combo.currentData() == "article"
        assert window.current_vocabulary_article_id == article.id
        assert window.vocabulary_page.table.rowCount() > 0

        before_contexts = context.vocabulary_learning_service.detail(collected.entry.id)[1]
        monkeypatch.setattr(QMessageBox, "question", lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes)
        messages = []
        monkeypatch.setattr(QMessageBox, "information", lambda *_args: messages.append(_args[-1]))
        window._rebuild_current_article_words()
        after_contexts = context.vocabulary_learning_service.detail(collected.entry.id)[1]
        rows = context.article_word_index_service.list_words(article.id)
        assert len(after_contexts) == len(before_contexts) == 1
        assert {row["normalized_word"]: row["occurrence_count"] for row in rows}["you"] == 2
        assert messages and "已记录" in messages[-1]
        window.close()
    finally:
        context.database.close()
