from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextBlockFormat
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.translation_provider import TranslationResult
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _key(character: str) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character)


def _window(tmp_path: Path, *, cache_translations: bool):
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data", credential_store=MemoryCredentialStore())
    source = tmp_path / "continuous.txt"
    source.write_text("First sentence. Second sentence. Third sentence.", encoding="utf-8")
    article = context.article_library.import_txt_file(source, 500).article
    material = context.practice_service.load_practice_material(article.id)
    sentences = context.sentence_service.ensure_for_section(material.section_id)
    if cache_translations:
        for index, sentence in enumerate(sentences, start=1):
            context.translation_service.prepare(sentence, provider="mock", model="mock-v1")
            context.translation_service.complete(
                sentence.sentence_hash,
                TranslationResult(f"第 {index} 句中文。", []),
                provider="mock",
                model="mock-v1",
            )
    settings = context.settings_service.get_settings()
    settings.sentence_learning_enabled = False
    context.settings_service.save_settings(settings)
    window = MainWindow(context)
    window.show()
    app.processEvents()
    window._begin_practice(material)
    app.processEvents()
    return app, context, window, sentences


def _close(context, window) -> None:
    window.current_practice_saved = True
    window.close()
    context.database.close()


def test_continuous_panel_reads_cache_and_tracks_current_sentence(tmp_path: Path) -> None:
    app, context, window, sentences = _window(tmp_path, cache_translations=True)
    try:
        view = window.practice_view
        assert view.translation_card.isVisible()
        assert view.translation_text.text() == "第 1 句中文。"
        for character in sentences[0].text:
            view._handle_input_event(_key(character))
        app.processEvents()
        assert view.translation_text.text() == "第 2 句中文。"
    finally:
        _close(context, window)


def test_continuous_panel_never_requests_missing_translation(tmp_path: Path, monkeypatch) -> None:
    app = _app()
    context = build_app_context(data_dir=tmp_path / "data", credential_store=MemoryCredentialStore())
    source = tmp_path / "missing.txt"
    source.write_text("No cached translation. Another sentence.", encoding="utf-8")
    article = context.article_library.import_txt_file(source, 500).article
    material = context.practice_service.load_practice_material(article.id)
    settings = context.settings_service.get_settings()
    settings.sentence_learning_enabled = False
    context.settings_service.save_settings(settings)
    monkeypatch.setattr(context.translation_service, "prepare", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("prepare called")))
    monkeypatch.setattr(context.translation_service, "request", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("request called")))
    window = MainWindow(context)
    try:
        window.show()
        window._begin_practice(material)
        app.processEvents()
        assert window.practice_view.translation_text.text() == "暂无翻译"
    finally:
        _close(context, window)


def test_eye_toggle_is_temporary_and_does_not_change_input_state(tmp_path: Path) -> None:
    app, context, window, _sentences = _window(tmp_path, cache_translations=True)
    try:
        view = window.practice_view
        before = view.session.snapshot()
        view.translation_toggle.click()
        app.processEvents()
        hidden = view.session.snapshot()
        assert view.translation_text.text() == "中文意思已隐藏"
        assert hidden.position == before.position
        assert hidden.total_keystrokes == before.total_keystrokes
        assert hidden.wpm == before.wpm
        assert not view.session.is_paused
        assert view.input_edit.hasFocus()

        view._handle_input_event(_key("F"))
        assert view.session.position == 1
        view.translation_toggle.click()
        app.processEvents()
        assert view.translation_text.text() == "第 1 句中文。"
    finally:
        _close(context, window)


def test_continuous_line_spacing_and_responsive_themes(tmp_path: Path) -> None:
    app, context, window, _sentences = _window(tmp_path, cache_translations=True)
    try:
        view = window.practice_view
        view._handle_input_event(_key("F"))
        for editor in (view.text_browser, view.input_edit):
            block_format = editor.document().firstBlock().blockFormat()
            assert block_format.lineHeight() == 160.0
            assert block_format.lineHeightType() == QTextBlockFormat.LineHeightTypes.ProportionalHeight.value

        for theme in ("light", "dark"):
            apply_theme(window, theme)
            window.resize(1280, 720)
            app.processEvents()
            assert view.continuous_splitter.orientation() == Qt.Orientation.Horizontal
            assert view.translation_text.text() == "第 1 句中文。"
        window.resize(1920, 1080)
        app.processEvents()
        assert view.continuous_splitter.orientation() == Qt.Orientation.Horizontal
        assert not view.text_browser.horizontalScrollBar().isVisible()
        assert not view.input_edit.horizontalScrollBar().isVisible()
    finally:
        _close(context, window)
