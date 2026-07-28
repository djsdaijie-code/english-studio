from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
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


def test_sentence_translation_preparation_starts_on_first_input_once(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path, "Prepare this sentence. Then continue.")
    prepared: list[tuple[object, float]] = []
    try:
        view = window.sentence_practice_view
        view.content_preparation_requested.disconnect(window._prepare_sentence_content)
        view.content_preparation_requested.connect(
            lambda sentence, speed: prepared.append((sentence, speed))
        )

        view._handle_key(_key(sentences[0].text[0]))
        view._handle_key(_key(sentences[0].text[1]))
        app.processEvents()

        assert prepared and prepared[0][0] == sentences[0]
        assert view.translation_text.text() == "翻译尚未显示"
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_sentence_content_is_prefetched_without_early_reveal(tmp_path: Path, monkeypatch) -> None:
    class FakeTranslationProvider:
        name = "deepseek"
        calls = 0

        def __init__(self, *_args, model: str, **_kwargs) -> None:
            self.model = model

        def translate(self, _text, **_kwargs):
            type(self).calls += 1
            return TranslationResult("提前准备的翻译。", [{"expression": "prepare", "meaning": "准备"}])

    monkeypatch.setattr(
        "english_typing_trainer.ui.main_window.DeepSeekTranslationProvider",
        FakeTranslationProvider,
    )
    app, context, window, sentences = _window(tmp_path, "Prepare this sentence. Then continue.")
    try:
        context.credential_store.set("deepseek-test-key")
        view = window.sentence_practice_view
        first = sentences[0]
        prefetched = []
        window._prefetch_sentence_speech = lambda text, speed, content_ref=None: prefetched.append((text, speed, content_ref))

        view._handle_key(_key(first.text[0]))
        assert window._thread_pool.waitForDone(5000)
        app.processEvents()

        translation = context.translation_service.get(first.sentence_hash)
        assert translation and translation.status == "completed"
        assert prefetched and prefetched[0][0] == first.normalized_text
        assert view.translation_text.text() == "翻译尚未显示"
        assert not window.audio_playback.is_playing()
        assert FakeTranslationProvider.calls == 1

        for character in first.text[1:]:
            view._handle_key(_key(character))
        app.processEvents()

        assert view.translation_text.text() == "提前准备的翻译。"
        assert FakeTranslationProvider.calls == 1
        assert not window.audio_playback.is_playing()
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_completed_sentence_shows_translation_and_auto_reads(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path)
    try:
        view = window.sentence_practice_view
        assert view.translation_text.objectName() == "SentenceTranslationText"
        assert view.translation_body.objectName() == "SentenceTranslationBody"
        assert view.translation_source.objectName() == "SentenceTranslationSource"
        requested = []
        view.speech_requested.disconnect(window._request_speech)
        view.speech_requested.connect(lambda text, speed, controls: requested.append(text))

        for character in sentences[0].text:
            view._handle_key(_key(character))
        app.processEvents()

        assert view.learning.state == SentenceLearningState.LEARNING_PAUSED
        assert requested == [sentences[0].normalized_text]
        view._handle_key(_key("x"))
        app.processEvents()
        assert view.learning.state == SentenceLearningState.LEARNING_PAUSED
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_space_replays_completed_sentence(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path)
    try:
        view = window.sentence_practice_view
        requested = []
        view.speech_requested.disconnect(window._request_speech)
        view.speech_requested.connect(lambda text, speed, controls: requested.append(text))
        for character in sentences[0].text:
            view._handle_key(_key(character))
        app.processEvents()

        position = view.session.position
        view.copy_button.setFocus()
        QTest.keyClick(view.copy_button, Qt.Key.Key_Space)
        app.processEvents()

        assert view.session.position == position
        assert view.learning.state == SentenceLearningState.LEARNING_PAUSED
        assert "Space" in view.state_label.text()
        assert requested == [sentences[0].normalized_text, sentences[0].normalized_text]
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_space_remains_typing_input_before_sentence_completion(tmp_path: Path) -> None:
    app, context, window, _sentences = _window(tmp_path, "A B.")
    try:
        view = window.sentence_practice_view

        QTest.keyClicks(view.input_edit, "A B")
        app.processEvents()

        assert "".join(item.actual_char for item in view.learning.current_session.typed_characters) == "A B"
        assert view.input_edit.toPlainText() == "A B"
        assert view.learning.current_session.position == 3
    finally:
        window.current_practice_saved = True
        window.close(); context.database.close()


def test_sentence_practice_skips_boundary_whitespace_without_counting_it(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path, "First sentence. \t\n\n Second sentence.")
    try:
        view = window.sentence_practice_view
        assert [item.text for item in sentences] == ["First sentence.", "Second sentence."]
        for character in sentences[0].text:
            view._handle_key(_key(character))
        first_end = view.session.position
        view._handle_key(QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r"))
        app.processEvents()
        assert view.session.position > first_end
        assert view.session.total_keystrokes == len(sentences[0].text)
        for character in sentences[1].text:
            view._handle_key(_key(character))
        assert view.session.error_keystrokes == 0
        assert view.session.total_keystrokes == sum(len(item.text) for item in sentences)
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
