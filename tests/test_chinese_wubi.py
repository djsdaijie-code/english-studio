from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QInputMethodEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.repositories import PracticeRepository
from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.typing_engine.language import count_cjk_characters
from english_typing_trainer.typing_engine.session import TypingSession
from english_typing_trainer.ui.practice_view import PracticeView


def test_pasted_chinese_import_keeps_title_and_whole_text_in_one_section(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        text = "五笔输入按汉字计算速度。\n第二行也保留。"
        result = context.article_library.import_pasted_chinese("  中文练习  ", text)

        assert result.status == "imported"
        assert result.article is not None
        assert result.article.title == "中文练习"
        assert result.article.section_count == 1
        assert result.article.word_count == count_cjk_characters(text)
        sections = context.article_library.get_sections(result.article.id)
        assert len(sections) == 1
        assert sections[0].text == text
        assert context.practice_service.load_practice_material(result.article.id).speed_mode == "chinese"
    finally:
        context.database.close()


def test_pasted_chinese_import_rejects_empty_non_chinese_and_duplicate_content(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        assert context.article_library.import_pasted_chinese("", "中文").status == "error"
        assert context.article_library.import_pasted_chinese("标题", "English only.").status == "error"
        first = context.article_library.import_pasted_chinese("第一篇", "重复的中文正文。")
        second = context.article_library.import_pasted_chinese("另一个标题", "重复的中文正文。")
        assert first.status == "imported"
        assert second.status == "duplicate"
        assert len(context.article_library.list_articles()) == 1
    finally:
        context.database.close()


def test_chinese_speed_counts_correct_hanzi_instead_of_english_wpm() -> None:
    session = TypingSession("中文，A", speed_mode="chinese")
    for character in "中文，A":
        session.handle_character(character)
    session._active_seconds_accumulator = 60.0

    snapshot = session.snapshot()

    assert snapshot.correct_characters == 4
    assert snapshot.speed_characters == 2
    assert snapshot.wpm == 0.0
    assert 1.9 <= snapshot.cpm <= 2.0


def test_chinese_ime_commit_is_visible_and_advances_one_target_per_character() -> None:
    app = QApplication.instance() or QApplication([])
    view = PracticeView()
    view.show()
    view.start_practice(
        PracticeMaterial(
            article_id=1,
            article_title="五笔练习",
            section_id=1,
            section_index=0,
            section_count=1,
            section_text="中文输入",
            speed_mode="chinese",
        ),
        AppSettings(),
    )
    event = QInputMethodEvent("", [])
    event.setCommitString("中文")

    view.input_edit.inputMethodEvent(event)
    app.processEvents()

    assert view.session is not None
    assert view.session.position == 2
    assert view.session.correct_keystrokes == 2
    assert view.input_edit.toPlainText() == "中文"
    assert view.wpm_title.text() == "字/分钟"
    assert view.section_label.text() == "整篇文章"
    view.close()


def test_chinese_session_persists_separate_practice_type_and_character_speed(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        imported = context.article_library.import_pasted_chinese("保存测试", "中文测试").article
        assert imported is not None
        material = context.practice_service.load_practice_material(imported.id)
        session = TypingSession(material.section_text, speed_mode=material.speed_mode)
        for character in material.section_text:
            session.handle_character(character)
        session._active_seconds_accumulator = 60.0

        context.practice_service.save_completed_session(material, session, session.snapshot())
        row = PracticeRepository(context.database.connect).list_sessions_for_article(imported.id)[0]

        assert row["practice_type"] == "chinese_article"
        assert row["wpm"] == 0.0
        assert row["cpm"] > 0.0
        assert row["correct_characters"] == 4
    finally:
        context.database.close()
