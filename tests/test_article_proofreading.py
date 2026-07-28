from __future__ import annotations

import json
import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.article_proofreading import (
    ArticleProofreadingResult,
    ArticleProofreadingService,
    DeepSeekArticleProofreadingProvider,
    ProofreadingIssue,
    parse_proofreading_content,
)
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.typing_engine.session import TypingSession
from english_typing_trainer.ui.main_window import MainWindow


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return json.dumps(
            {"choices": [{"message": {"content": self.content}}]},
            ensure_ascii=False,
        ).encode("utf-8")


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_proofreading_parser_and_deepseek_request_preserve_corrected_text() -> None:
    raw = json.dumps(
        {
            "corrected_text": "This article is correct.",
            "issues": [
                {
                    "type": "word",
                    "original": "are",
                    "suggestion": "is",
                    "reason": "主谓一致错误",
                }
            ],
        },
        ensure_ascii=False,
    )
    parsed = parse_proofreading_content(f"```json\n{raw}\n```")
    assert parsed.corrected_text == "This article is correct."
    assert parsed.issues[0].reason == "主谓一致错误"

    captured = {}

    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse(raw)

    provider = DeepSeekArticleProofreadingProvider("sk-test-secret", opener=opener)
    result = provider.proofread("This article are correct.")
    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert result.corrected_text == "This article is correct."
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["thinking"] == {"type": "disabled"}
    assert captured["request"].get_header("Authorization") == "Bearer sk-test-secret"


def test_proofreading_service_chunks_without_losing_boundary_whitespace() -> None:
    class EchoProvider:
        def __init__(self) -> None:
            self.calls = 0

        def proofread(self, text, *, cancel_event=None):
            self.calls += 1
            return ArticleProofreadingResult(text, ())

    text = ("A complete sentence remains unchanged.\n\n" * 60).strip()
    provider = EchoProvider()
    result = ArticleProofreadingService(max_chunk_characters=1000).check(provider, text)
    assert provider.calls > 1
    assert result.corrected_text == text


def test_applying_proofreading_updates_article_transactionally_and_keeps_history(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        source = tmp_path / "article.txt"
        source.write_text("This article are wrong. Another sentence follows.", encoding="utf-8")
        article = context.article_library.import_txt_file(source, 300).article
        material = context.practice_service.load_practice_material(article.id)
        old_section_id = material.section_id
        session = TypingSession(material.section_text)
        session.handle_character(material.section_text[0])
        context.practice_service.save_interrupted_session(material, session, session.snapshot())
        session_count = context.database.connect().execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0]

        updated = context.article_library.replace_article_content(
            article.id,
            "This article is correct.\n\nAnother sentence follows.",
            300,
        )

        assert updated.full_text == "This article is correct.\n\nAnother sentence follows."
        updated_sections = context.article_library.get_sections(article.id)
        assert len(updated_sections) == 1
        assert updated_sections[0].text == updated.full_text
        assert updated.current_character_index == 0
        assert updated.completed_section_count == 0
        assert context.database.connect().execute("SELECT is_active FROM article_sections WHERE id = ?", (old_section_id,)).fetchone()[0] == 0
        assert context.database.connect().execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0] == session_count
        assert context.article_word_index_service.list_words(article.id) == []
    finally:
        context.database.close()


def test_applying_proofreading_does_not_trigger_word_index_refresh(tmp_path: Path, monkeypatch) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        source = tmp_path / "rollback.txt"
        source.write_text("Original article text.", encoding="utf-8")
        article = context.article_library.import_txt_file(source, 500).article
        calls = []

        def fail(*_args, **_kwargs):
            calls.append(True)
            raise RuntimeError("index failed")

        monkeypatch.setattr(context.article_word_index_service, "replace_in_transaction", fail)
        updated = context.article_library.replace_article_content(
            article.id, "Corrected article text.", 500
        )
        assert updated.full_text == "Corrected article text."
        assert calls == []
        assert context.article_word_index_service.list_words(article.id) == []
    finally:
        context.database.close()


def test_article_detail_recheck_button_and_import_start_proofreading(tmp_path: Path, monkeypatch) -> None:
    app = _app()
    context = build_app_context(
        data_dir=tmp_path / "data",
        credential_store=MemoryCredentialStore("sk-test"),
    )
    source = tmp_path / "new article.txt"
    source.write_text("This article are wrong.", encoding="utf-8")
    try:
        existing = context.article_library.import_txt_file(source, 500).article
        window = MainWindow(context)
        window.show()
        window._reload_articles()
        app.processEvents()
        calls = []
        monkeypatch.setattr(
            window,
            "_start_article_proofreading",
            lambda article_id, *, automatic: calls.append((article_id, automatic)),
        )
        window.proofread_button.click()
        assert calls == [(existing.id, False)]

        second = tmp_path / "second.txt"
        second.write_text("A second article.", encoding="utf-8")
        monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *_args, **_kwargs: ([str(second)], ""))
        monkeypatch.setattr(QMessageBox, "information", lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok)
        window._import_articles()
        app.processEvents()
        imported = next(item for item in context.article_library.list_articles() if item.title == "second")
        assert calls[-1] == (imported.id, True)
        window.close()
    finally:
        context.database.close()


def test_proofreading_result_model_detects_changes() -> None:
    result = ArticleProofreadingResult(
        "Correct text.",
        (ProofreadingIssue("spelling", "Corect", "Correct", "拼写错误"),),
    )
    assert result.differs_from("Corect text.")
    assert not result.differs_from("Correct text.")
