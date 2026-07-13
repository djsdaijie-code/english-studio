from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.models.fsrs_review import ReviewQueueItem, VocabularyReviewCard
from english_typing_trainer.services.dictation_service import DictationService
from english_typing_trainer.ui.dictation_page import DictationPage


def _app(): return QApplication.instance() or QApplication([])


def test_word_dictation_is_strict_about_casing_apostrophes_and_hyphens(tmp_path: Path) -> None:
    service = DictationService(build_app_context(data_dir=tmp_path / "data").database)
    assert service.compare("OpenAI", "OpenAI", dictation_type="word").correct
    assert not service.compare("OpenAI", "openai", dictation_type="word").correct
    assert not service.compare("don't", "dont", dictation_type="word").correct
    assert not service.compare("well-known", "well known", dictation_type="word").correct


def test_sentence_dictation_learning_mode_normalizes_only_boundary_rules(tmp_path: Path) -> None:
    service = DictationService(build_app_context(data_dir=tmp_path / "data").database)
    assert service.compare("English helps people.", "english   helps people", dictation_type="sentence", mode="learning").correct
    assert not service.compare("English helps people.", "english helps person", dictation_type="sentence", mode="learning").correct
    assert not service.compare("English helps people.", "english helps people", dictation_type="sentence", mode="strict").correct


def test_diff_is_deterministic_and_attempt_persists(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    comparison = context.dictation_service.compare("one two", "one three", dictation_type="sentence")
    assert comparison.error_count > 0 and comparison.operations
    from english_typing_trainer.models.dictation import DictationAttempt
    attempt = context.dictation_service.save(DictationAttempt("sentence", "strict", "one two", "one three", "one two => one three", comparison.error_count, comparison.omitted_count, comparison.inserted_count))
    assert attempt.id
    assert context.database.connect().execute("SELECT count(*) FROM dictation_attempts").fetchone()[0] == 1


def test_dictation_page_keeps_controlled_input_and_renders_result(tmp_path: Path) -> None:
    app = _app(); context = build_app_context(data_dir=tmp_path / "data")
    collected = context.vocabulary_learning_service.collect("OpenAI", sentence="OpenAI helps people.")
    entry, contexts, _ = context.vocabulary_learning_service.detail(collected.entry.id)
    card = VocabularyReviewCard(entry.id or 0, "listening", "{}", context.fsrs_review_service.now(), contexts[0].id if contexts else None)
    page = DictationPage(context.dictation_service); page.load_queue([ReviewQueueItem(card, entry, contexts[0] if contexts else None)])
    for char in "openai":
        page._key(QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_unknown, Qt.KeyboardModifier.NoModifier, char))
    assert page.input.toPlainText() == "openai"
    page._submit(); app.processEvents()
    assert "标准答案：OpenAI" in page.feedback.text()
    assert all(not button.isHidden() for button in page.rating_buttons)
