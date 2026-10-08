from __future__ import annotations

import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.reading_service import ReadingService, clean_reading_text
from english_typing_trainer.services.translation_provider import TranslationProviderError, TranslationResult
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.reading_controller import ReadingController
from english_typing_trainer.ui.reading_import_dialog import ReadingImportDialog
from english_typing_trainer.ui.reading_page import ReadingPage
from english_typing_trainer.ui.theme import apply_theme


@pytest.fixture
def context(tmp_path):
    app = QApplication.instance() or QApplication([])
    result = build_app_context(data_dir=tmp_path / "data")
    yield result
    app.processEvents()
    result.database.close()


class QueuePool:
    def __init__(self):
        self.jobs = []

    def start(self, worker):
        self.jobs.append(worker)


class MockProvider:
    name = "test"
    model = "test"

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def translate(self, text, **kwargs):
        self.calls.append((text, kwargs))
        if self.fail:
            raise TranslationProviderError("network", "网络连接失败。")
        return TranslationResult("测试中文意思：" + text, [{"expression": "read slowly", "meaning": "慢慢阅读"}])


def _setup_reader(context, pool=None):
    article = ReadingService(context).import_article("Reading", "Read slowly. Think carefully. Keep learning.")
    page = ReadingPage()
    page.show()
    pool = pool or QueuePool()
    controller = ReadingController(context, page, pool, context.settings_service.get_settings)
    provider = MockProvider()
    controller.provider_factory = lambda: provider
    controller.open_article(article.id)
    QApplication.processEvents()
    return page, controller, pool, provider


def _cache(context, sentence, chinese="缓存的中文意思"):
    context.translation_service.prepare(sentence, provider="test", model="test")
    return context.translation_service.complete(
        sentence.sentence_hash, TranslationResult(chinese, [{"expression": "read slowly", "meaning": "慢慢阅读"}]),
        provider="test", model="test",
    )


def test_reading_cleanup_preserves_paragraphs_and_joins_web_wrapping():
    assert clean_reading_text("  Read\u00a0 carefully.\n Keep\t learning.\n\nNext\u200b paragraph.\x00 ") == "Read carefully. Keep learning.\n\nNext paragraph."


def test_reading_import_deduplicates_restores_and_keeps_one_article(context):
    service = ReadingService(context)
    article = service.import_article("Title", "One sentence. Another sentence.", "https://example.com/post")
    duplicate = service.import_article("Another title", article.full_text)
    assert duplicate.id == article.id
    assert len(context.article_library.get_sections(article.id)) == 1
    assert len(service.load(article.id).sentences) == 2
    assert service.list_articles()[0][1]["source_url"] == "https://example.com/post"
    context.article_library.soft_delete_article(article.id)
    assert service.list_articles() == []
    restored = service.import_article("Title", article.full_text)
    assert restored.id == article.id
    assert context.database.get_schema_version() == 13


def test_reading_bookmark_survives_restart_without_changing_typing_progress(context):
    service = ReadingService(context)
    article = service.import_article("Title", "One sentence. Another sentence.")
    material = service.load(article.id)
    material.index = 1
    service.save_position(material)
    path = context.paths.data_dir
    context.database.close()
    restarted = build_app_context(data_dir=path)
    try:
        loaded = ReadingService(restarted).load(article.id)
        assert loaded.index == 1
        assert restarted.practice_service.load_practice_material(article.id).resume_character_index == 0
        assert restarted.database.connect().execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0] == 0
    finally:
        restarted.database.close()


def test_reading_resets_bookmark_after_article_content_changes(context):
    service = ReadingService(context)
    article = service.import_article("Title", "One sentence. Another sentence.")
    material = service.load(article.id)
    material.index = 1
    material.completed = True
    service.save_position(material)
    context.article_library.replace_article_content(article.id, "A changed sentence.", 500)
    loaded = service.load(article.id)
    assert loaded.index == 0 and not loaded.completed
    assert loaded.sentences[0].normalized_text == "A changed sentence."


def test_import_preview_requires_confirmation_before_acceptance(context):
    dialog = ReadingImportDialog()
    dialog.title_input.setText("Title")
    dialog.text_input.setPlainText("One\n sentence.\n\nAnother sentence.")
    dialog._advance()
    assert dialog.result() == 0
    assert dialog.text_input.toPlainText() == "One sentence.\n\nAnother sentence."
    assert dialog.next_button.text() == "开始精读"
    dialog._advance()
    assert dialog.result() == dialog.DialogCode.Accepted


def test_async_translation_does_not_overwrite_new_sentence(context):
    page, controller, pool, provider = _setup_reader(context)
    try:
        assert provider.calls == []
        first = page.current_sentence
        page.move(1)
        second = page.current_sentence
        pool.jobs[0].run()
        QApplication.processEvents()
        assert context.translation_service.get(first.sentence_hash).status == "completed"
        assert page.current_sentence is second
        assert first.normalized_text not in page.translation_label.text()
        pool.jobs[1].run()
        QApplication.processEvents()
        assert second.normalized_text in page.translation_label.text()
        assert "慢慢阅读" in page.expressions_label.text()
        assert provider.calls[0][1]["following"] == second.normalized_text
    finally:
        controller.shutdown()
        page.close()


def test_reader_reuses_cache_without_creating_provider(context):
    article = ReadingService(context).import_article("Title", "Read slowly.")
    material = ReadingService(context).load(article.id)
    _cache(context, material.sentences[0])
    page = ReadingPage()
    page.show()
    pool = QueuePool()
    controller = ReadingController(context, page, pool, context.settings_service.get_settings)
    controller.provider_factory = lambda: pytest.fail("缓存命中不应创建 Provider")
    try:
        controller.open_article(article.id)
        assert page.translation_label.text() == "缓存的中文意思"
        assert pool.jobs == []
    finally:
        controller.shutdown()
        page.close()


def test_missing_key_and_network_failure_allow_retry(context):
    page, controller, pool, provider = _setup_reader(context)
    try:
        provider.fail = True
        pool.jobs[0].run()
        QApplication.processEvents()
        assert "网络连接失败" in page.translation_label.text()
        assert page.retry_button.isEnabled()
        provider.fail = False
        page.retry_button.click()
        pool.jobs[-1].run()
        QApplication.processEvents()
        assert "测试中文意思" in page.translation_label.text()
        page.move(1)
        controller.shutdown()
    finally:
        page.close()


def test_unconfigured_provider_shows_actionable_message(context):
    article = ReadingService(context).import_article("Title", "Read slowly.")
    page = ReadingPage()
    page.show()
    pool = QueuePool()
    controller = ReadingController(context, page, pool, context.settings_service.get_settings)
    try:
        controller.open_article(article.id)
        assert "尚未配置" in page.translation_label.text()
        assert page.retry_button.isEnabled()
        assert pool.jobs == []
    finally:
        controller.shutdown()
        page.close()


def test_completed_reading_and_keyboard_navigation_persist(context):
    page, controller, pool, _provider = _setup_reader(context)
    try:
        QTest.keyClick(page.source_text, Qt.Key_Return)
        QApplication.processEvents()
        assert page.material.index == 1
        page.move(1)
        page.move(1)
        assert controller.service.load(page.material.article.id).completed
        assert page.progress.value() == 3
        page.move(-1)
        assert page.material.index == 1
        assert page.next_button.isEnabled()
    finally:
        controller.shutdown()
        page.close()


def test_shutdown_cancels_requests_and_orphaned_pending_can_retry(context):
    page, controller, pool, provider = _setup_reader(context)
    sentence = page.current_sentence
    controller.shutdown()
    assert pool.jobs[0].cancel_event.is_set()
    assert context.translation_service.get(sentence.sentence_hash).status == "failed"
    page.close()
    other = ReadingService(context).load(page.material.article.id).sentences[1]
    context.translation_service.prepare(other, provider="test", model="test")
    from english_typing_trainer.services.translation_service import TranslationService
    service = TranslationService(context.database)
    service.recover_interrupted(other.sentence_hash)
    assert service.get(other.sentence_hash).status == "failed"
    assert service.prepare(other, provider="test", model="test", retry=True).should_request


def test_real_qthread_worker_updates_reader_on_gui_thread(context):
    pool = QThreadPool()
    page, controller, _pool, _provider = _setup_reader(context, pool)
    try:
        assert pool.waitForDone(5000)
        QApplication.processEvents()
        assert "测试中文意思" in page.translation_label.text()
        assert context.translation_service.get(page.current_sentence.sentence_hash).status == "completed"
    finally:
        controller.shutdown()
        page.close()


@pytest.mark.parametrize("theme,size", [("light", (1280, 720)), ("light", (1500, 1000)), ("dark", (1920, 1080))])
def test_main_window_reading_routes_vocabulary_and_responsive_layout(context, theme, size):
    context.settings_service.save_settings(replace(context.settings_service.get_settings(), vocabulary_auto_enrich=False))
    window = MainWindow(context)
    article = window.reading_controller.service.import_article("Title", "Read slowly. Keep learning.")
    material = window.reading_controller.service.load(article.id)
    for sentence in material.sentences:
        _cache(context, sentence)
    window.resize(*size)
    window.show()
    apply_theme(window, theme)
    QApplication.processEvents()
    try:
        window.home_page.reading_card.action_button.click()
        assert window.learning_content_page.current_section() == "reading"
        window.reading_page.resume_button.click()
        QApplication.processEvents()
        assert window.reading_page.current_sentence.normalized_text == "Read slowly."
        assert window.reading_page.translation_label.text() == "缓存的中文意思"
        window._collect_reading_word("Read", 0, 4)
        assert len(context.vocabulary_learning_service.list_entries()) == 1
        assert window.reading_page.source_text.width() > 250
        assert window.reading_page.splitter.width() <= window.width()
        assert window.reading_page.source_text.horizontalScrollBar().maximum() == 0
        window.reading_page.move(1)
        assert context.learning_time_tracker.active
        window._show_library()
        assert not context.learning_time_tracker.active
        assert context.practice_service.load_practice_material(article.id).resume_character_index == 0
    finally:
        window.close()
