from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.sentence_learning import SentenceLearningState
from english_typing_trainer.services.translation_provider import TranslationResult
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme


def _app():
    return QApplication.instance() or QApplication([])


def _key(character: str) -> QKeyEvent:
    if character == "\n":
        return QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r")
    if character == " ":
        return QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Space, Qt.NoModifier, " ")
    return QKeyEvent(QKeyEvent.KeyPress, 0, Qt.NoModifier, character)


def _window(tmp_path: Path, text: str = "Hi. Bye."):
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data", credential_store=MemoryCredentialStore())
    path = tmp_path / "lesson.txt"
    path.write_text(text, encoding="utf-8")
    imported = context.article_library.import_txt_file(path, 500)
    material = context.practice_service.load_practice_material(imported.article.id)
    sentences = context.sentence_service.ensure_for_section(material.section_id)
    window = MainWindow(context)
    window.show()
    window._begin_practice(material)
    app.processEvents()
    return app, context, window, sentences


def test_sentence_ui_uses_cached_translation_and_enter_moves_once(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path)
    try:
        first = sentences[0]
        context.translation_service.prepare(first, provider="deepseek", model="deepseek-v4-flash")
        context.translation_service.complete(first.sentence_hash, TranslationResult("你好。", [{"expression": "Hi", "meaning": "你好"}]), provider="deepseek", model="deepseek-v4-flash")
        view = window.sentence_practice_view
        assert window.stack.currentWidget() is view
        assert not window.sidebar.isVisible()
        for character in first.text:
            view._handle_key(_key("x" if view.learning.current_session.position == 0 else character))
        app.processEvents()
        assert view.learning.state == SentenceLearningState.LEARNING_PAUSED
        assert view.learning.current_session.position == len(first.text)
        assert view.learning.current_session.error_keystrokes == 1
        assert view.translation_text.text() == "你好。"
        assert "Hi：你好" in view.expressions_label.text()
        assert context.database.connect().execute("SELECT COUNT(*) FROM sentence_attempts").fetchone()[0] == 1

        before_active = view.learning.timing_snapshot().active_seconds
        view._handle_key(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r"))
        app.processEvents()
        assert view.learning.current_index == 1
        assert view.learning.state == SentenceLearningState.WAITING_FIRST_INPUT
        assert view.learning.timing_snapshot().active_seconds == before_active
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_sentence_attempt_attaches_to_interrupted_session(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path)
    try:
        view = window.sentence_practice_view
        for character in sentences[0].text:
            view._handle_key(_key(character))
        app.processEvents()
        window._persist_current_practice()
        row = context.database.connect().execute("SELECT session_id, completed FROM sentence_attempts").fetchone()
        session = context.database.connect().execute("SELECT total_elapsed_seconds, learning_seconds, idle_seconds, manual_paused_seconds FROM practice_sessions").fetchone()
        assert row["session_id"] is not None
        assert row["completed"] == 1
        assert session is not None
    finally:
        window.close(); context.database.close()


def test_sentence_translation_panel_states_and_responsive_sizes(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path, "A realistic sentence remains readable across desktop sizes. Another sentence follows.")
    try:
        view = window.sentence_practice_view
        for width, height in ((1280, 720), (1500, 1000), (1920, 1080)):
            window.resize(width, height); app.processEvents()
            assert view.main_splitter.orientation() == Qt.Orientation.Horizontal
            total = sum(view.main_splitter.sizes())
            ratio = view.main_splitter.sizes()[1] / total
            assert 0.28 <= ratio <= 0.42
        view.translation_status.setText("正在翻译……")
        assert "正在翻译" in view.translation_status.text()
        view.show_translation_failed("网络连接失败。")
        assert view.translation_status.text() == "翻译失败"
        apply_theme(window, "dark")
        app.processEvents()
        assert window.styleSheet()
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_completed_sentence_auto_reads_once_and_translation_has_clear_hierarchy(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path)
    requests: list[tuple[str, float]] = []
    try:
        view = window.sentence_practice_view
        view.speech_requested.connect(lambda text, speed, _controls: requests.append((text, speed)))
        assert view.translation_text.objectName() == "SentenceTranslationText"
        assert view.translation_body.objectName() == "SentenceTranslationBody"
        assert view.translation_source.objectName() == "SentenceTranslationSource"

        for character in sentences[0].text:
            view._handle_key(_key(character))
        app.processEvents()

        assert requests == [(sentences[0].normalized_text, 1.0)]
        assert view.learning.state == SentenceLearningState.LEARNING_PAUSED
        view._handle_key(_key("x"))
        app.processEvents()
        assert len(requests) == 1
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_settings_page_exposes_sentence_and_masked_deepseek_controls(tmp_path: Path) -> None:
    app = _app()
    store = MemoryCredentialStore("sk-test-abcd")
    context = build_app_context(data_dir=tmp_path / "data", credential_store=store)
    try:
        window = MainWindow(context); window.show(); window._show_settings(); app.processEvents()
        assert not hasattr(window.settings_page, "sentence_learning_checkbox")
        assert window.practice_mode_control.value() == "sentence"
        assert window.settings_page.idle_pause_combo.currentData() == 3
        assert window.settings_page.translation_model_combo.currentData() == "deepseek-v4-flash"
        assert "abcd" in window.settings_page.api_key_status.text()
        assert "sk-test-abcd" not in window.settings_page.api_key_status.text()
        window.current_practice_saved = True; window.close()
    finally:
        context.database.close()
