from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QContextMenuEvent, QMouseEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.vocabulary_quick_access import VocabularyQuickAccess

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
        assert window.windowTitle() == "English Studio"
        assert window.nav_buttons[0].text() == "首页"
        assert window.nav_buttons[1].text() == "学习内容"
        assert window.nav_buttons[2].text() == "专项练习"
        assert window.stack.currentWidget() is window.home_page
        assert window.vocabulary_quick_access.book_button.isVisibleTo(window)
        assert not window.vocabulary_quick_access.book_button.icon().isNull()
        window.vocabulary_quick_access.book_button.click()
        app.processEvents()
        assert window.stack.currentWidget() is window.vocabulary_page
    finally:
        context.database.close()


def test_navigation_switches_pages_and_empty_state_is_visible(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(context)
        window.show()
        app.processEvents()
        assert window.home_page.isVisible()
        window._show_library()
        app.processEvents()
        assert window.stack.currentWidget() is window.learning_content_page
        assert window.learning_content_page.current_section() == "articles"
        assert window.empty_state.isVisible()
        window._show_courses()
        app.processEvents()
        assert window.learning_content_page.current_section() == "courses"
        window.home_page.article_card.action_button.click()
        app.processEvents()
        assert window.learning_content_page.current_section() == "articles"
        window.home_page.course_card.action_button.click()
        app.processEvents()
        assert window.learning_content_page.current_section() == "courses"
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
        assert reopened.database.get_schema_version() == 13
    finally:
        reopened.database.close()


def test_article_preview_context_menu_collects_only_selected_words(tmp_path: Path, monkeypatch) -> None:
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
        monkeypatch.setattr(window, "_start_vocabulary_enrichment", lambda *_args, **_kwargs: None)
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

        cursor=window.preview_content.textCursor()
        start=window.preview_content.toPlainText().index("learn")
        cursor.setPosition(start)
        cursor.setPosition(start+len("learn"),QTextCursor.MoveMode.KeepAnchor)
        window.preview_content.setTextCursor(cursor)
        menu, add_action = window._build_article_preview_menu()
        labels = [action.text() for action in menu.actions()]
        assert add_action.text() == "加入单词本"
        assert add_action.isEnabled()
        assert "重新提取文章单词" not in labels
        assert context.article_word_index_service.list_words(article.id) == []

        window._collect_preview_selected_word()
        app.processEvents()
        learned=context.vocabulary_learning_service.repository.get_by_word("learn")
        assert learned is not None
        assert window.vocabulary_quick_access.added_popup.isVisible()
        assert window.vocabulary_quick_access.word_label.text() == "learn"

        window._show_current_article_words()
        app.processEvents()
        assert window.stack.currentWidget() is window.vocabulary_page
        assert window.vocabulary_page.scope_combo.currentData() == "article"
        assert window.current_vocabulary_article_id == article.id
        assert window.vocabulary_page.table.rowCount() > 0

        displayed={window.vocabulary_page.table.item(row,0).text().lower() for row in range(window.vocabulary_page.table.rowCount())}
        assert displayed == {"you","learn"}
        assert context.article_word_index_service.list_words(article.id) == []
        window.close()
    finally:
        context.database.close()


def test_vocabulary_quick_access_can_be_dragged_without_opening() -> None:
    app = _app()
    host = QWidget()
    host.resize(900, 640)
    host.show()
    quick_access = VocabularyQuickAccess(host)
    opened: list[bool] = []
    quick_access.open_requested.connect(lambda: opened.append(True))
    quick_access.show()
    quick_access.position_in_parent()
    app.processEvents()
    initial_position = quick_access.pos()
    local_center = QPointF(quick_access.book_button.rect().center())
    start_global = QPointF(quick_access.book_button.mapToGlobal(quick_access.book_button.rect().center()))
    target_global = start_global + QPointF(-240, -180)
    QApplication.sendEvent(
        quick_access.book_button,
        QMouseEvent(QMouseEvent.Type.MouseButtonPress, local_center, start_global, Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier),
    )
    QApplication.sendEvent(
        quick_access.book_button,
        QMouseEvent(QMouseEvent.Type.MouseMove, local_center, target_global, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier),
    )
    QApplication.sendEvent(
        quick_access.book_button,
        QMouseEvent(QMouseEvent.Type.MouseButtonRelease, local_center, target_global, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier),
    )
    app.processEvents()
    assert quick_access.has_custom_position
    assert quick_access.pos() != initial_position
    assert not quick_access.book_button.isDown()
    assert opened == []
    host.resize(640, 480)
    quick_access.position_in_parent()
    assert 0 <= quick_access.x() <= host.width() - quick_access.width()
    assert 0 <= quick_access.y() <= host.height() - quick_access.height()
    host.close()


def test_home_dashboard_matches_learning_routes_and_supported_width(tmp_path: Path) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        window = MainWindow(context)
        window.resize(1280, 720)
        window.show()
        app.processEvents()

        assert window.home_page.continue_card.isVisible()
        assert window.home_page.daily_learning_card.isVisible()
        assert window.home_page.weekly_card.isVisible()
        assert window.home_page.recent_card.isVisible()
        assert window.home_page.continue_card.width() > window.home_page.daily_learning_card.width()
        assert len(window.home_page.weekly_card.bars.values) == 7

        window.home_page.history_card.action_button.click()
        app.processEvents()
        assert window.stack.currentWidget() is window.history_page

        window._switch_page(window.PAGE_HOME)
        window.home_page.article_card.action_button.click()
        app.processEvents()
        assert window.learning_content_page.current_section() == "articles"
        window.close()
    finally:
        context.database.close()
