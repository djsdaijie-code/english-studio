from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.sentence_learning import SentenceLearningState
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _key(character: str) -> QKeyEvent:
    if character == "\n":
        return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r")
    return QKeyEvent(QKeyEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character)


def _library_window(tmp_path: Path, text: str = "First sentence. Second sentence."):
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data", credential_store=MemoryCredentialStore())
    source = tmp_path / "article.txt"
    source.write_text(text, encoding="utf-8")
    imported = context.article_library.import_txt_file(source, 500)
    window = MainWindow(context)
    window.show()
    app.processEvents()
    return app, context, window, imported.article


def _close(context, window) -> None:
    window.current_practice_saved = True
    window.close()
    context.database.close()


def test_article_detail_segmented_mode_persists_and_removes_bulk_button(tmp_path: Path) -> None:
    app, context, window, _article = _library_window(tmp_path)
    try:
        control = window.practice_mode_control
        assert control.value() == "sentence"
        assert control.button("sentence").isChecked()
        assert not hasattr(window, "translate_article_button")
        detail_card = control.parentWidget()
        assert "翻译整篇文章" not in {button.text() for button in detail_card.findChildren(type(control.button("sentence")))}

        control.button("continuous").click()
        app.processEvents()
        assert window.settings.sentence_learning_enabled is False
        assert context.settings_service.get_settings().sentence_learning_enabled is False

        control.button("sentence").click()
        app.processEvents()
        assert window.settings.sentence_learning_enabled is True
        assert context.settings_service.get_settings().sentence_learning_enabled is True
    finally:
        _close(context, window)


def test_continue_and_start_over_route_to_selected_mode(tmp_path: Path) -> None:
    app, context, window, _article = _library_window(tmp_path)
    try:
        window.continue_button.click()
        app.processEvents()
        assert window.stack.currentWidget() is window.sentence_practice_view
        window.current_practice_saved = True
        window._show_library()

        window.practice_mode_control.button("continuous").click()
        window.restart_button.click()
        app.processEvents()
        assert window.stack.currentWidget() is window.practice_view
        assert window.practice_view.session.start_position == 0
    finally:
        _close(context, window)


def test_practice_mode_is_loaded_after_restart(tmp_path: Path) -> None:
    app, context, window, _article = _library_window(tmp_path)
    data_dir = context.paths.data_dir
    window.practice_mode_control.button("continuous").click()
    app.processEvents()
    _close(context, window)

    reopened = build_app_context(data_dir=data_dir, credential_store=MemoryCredentialStore())
    second_window = MainWindow(reopened)
    try:
        second_window.show()
        app.processEvents()
        assert reopened.settings_service.get_settings().sentence_learning_enabled is False
        assert second_window.practice_mode_control.value() == "continuous"
    finally:
        _close(reopened, second_window)


def test_sentence_bulk_translation_button_uses_current_article(tmp_path: Path) -> None:
    app, context, window, article = _library_window(tmp_path)
    called: list[int] = []
    try:
        window._translate_article = called.append
        window.continue_button.click()
        app.processEvents()
        assert window.sentence_practice_view.translate_article_button.text() == "翻译整篇文章"
        window.sentence_practice_view.translate_article_button.click()
        assert called == [article.id]
    finally:
        _close(context, window)


def test_controlled_input_uses_native_caret_at_document_end(tmp_path: Path) -> None:
    app, context, window, _article = _library_window(tmp_path)
    try:
        window.continue_button.click()
        app.processEvents()
        view = window.sentence_practice_view
        assert view.input_edit.isReadOnly() is False
        assert view.input_edit.hasFocus()
        assert view.input_edit.cursorWidth() == 2
        view._handle_key(_key(view.current_sentence.text[0]))
        app.processEvents()
        assert view.input_edit.textCursor().position() == len(view.input_edit.toPlainText())

        cursor = view.input_edit.textCursor()
        cursor.setPosition(0)
        view.input_edit.setTextCursor(cursor)
        view._restore_focus()
        assert view.input_edit.textCursor().position() == len(view.input_edit.toPlainText())
    finally:
        _close(context, window)


def test_idle_and_enter_restore_sentence_caret(tmp_path: Path) -> None:
    app, context, window, _article = _library_window(tmp_path)
    try:
        window.continue_button.click()
        view = window.sentence_practice_view
        first = view.current_sentence
        view._handle_key(_key(first.text[0]))
        view.learning._last_input_at -= 4
        assert view.learning.check_idle()
        assert view.learning.state == SentenceLearningState.IDLE_PAUSED
        view._restore_focus()
        assert view.input_edit.cursorWidth() == 2

        while view.learning.current_session.position < len(first.text):
            position = view.learning.current_session.position
            view._handle_key(_key(first.text[position]))
        assert view.input_edit.cursorWidth() == 0
        view._handle_key(_key("\n"))
        app.processEvents()
        assert view.learning.state == SentenceLearningState.WAITING_FIRST_INPUT
        assert view.input_edit.hasFocus()
        assert view.input_edit.cursorWidth() == 2
    finally:
        _close(context, window)


def test_current_target_has_background_without_underline_in_both_views(tmp_path: Path) -> None:
    app, context, window, _article = _library_window(tmp_path)
    try:
        window.continue_button.click()
        sentence_view = window.sentence_practice_view
        sentence_selection = sentence_view.text_browser.extraSelections()[-1]
        assert not sentence_selection.format.fontUnderline()
        assert sentence_selection.format.background().style() != Qt.BrushStyle.NoBrush

        window.current_practice_saved = True
        window._show_library()
        window.practice_mode_control.button("continuous").click()
        window.continue_button.click()
        app.processEvents()
        continuous_selection = window.practice_view.text_browser.extraSelections()[-1]
        assert not continuous_selection.format.fontUnderline()
        assert continuous_selection.format.background().style() != Qt.BrushStyle.NoBrush

        for theme in ("light", "dark"):
            apply_theme(window, theme)
            window.practice_view._render_text()
            selection = window.practice_view.text_browser.extraSelections()[-1]
            assert not selection.format.fontUnderline()
            assert selection.format.background().style() != Qt.BrushStyle.NoBrush
    finally:
        _close(context, window)
