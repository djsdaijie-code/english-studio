from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.courses import CourseRepository
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.ui.course_page import CoursePage


COURSE_ID = "crypto-blockchain-english"
TVL_ITEM = "crypto-blockchain-english-sentence-0026"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _context(tmp_path: Path):
    return build_app_context(
        data_dir=tmp_path / "data",
        credential_store=MemoryCredentialStore(),
    )


def test_crypto_course_has_complete_mvp_shape_and_no_audio_configuration() -> None:
    repository = CourseRepository()
    course = repository.get_course(COURSE_ID)

    assert course is not None
    assert course.version == "0.1.0"
    assert course.specification_version == "1.0"
    assert course.status == "draft"
    assert len(course.levels) == 1
    units = [unit for level in course.levels for unit in level.units]
    lessons = [lesson for unit in units for lesson in unit.lessons]
    sentences = [sentence for unit in units for sentence in unit.sentences]
    activities = {
        activity.activity_type
        for lesson in lessons
        for activity in lesson.activities
    }

    assert len(units) == 2
    assert len(lessons) == 14
    assert len(sentences) == 40
    assert all(len(unit.lessons) == 7 and len(unit.sentences) == 20 for unit in units)
    assert all(unit.lessons[-1].lesson_type == "review" for unit in units)
    assert len({sentence.sentence_id for sentence in sentences}) == 40
    assert len({sentence.stable_key for sentence in sentences}) == 40
    assert len({sentence.english for sentence in sentences}) == 40
    assert all(8 <= len(sentence.english.split()) <= 11 for sentence in sentences)
    assert activities == {"typing", "fsrs"}
    assert all(sentence.audio_hint is None for sentence in sentences)
    assert all(
        not ({"speaking", "listening", "dictation"} & set(sentence.skill_tags))
        for sentence in sentences
    )


def test_crypto_course_defines_tvl_as_total_value_locked() -> None:
    repository = CourseRepository()
    sentence = repository.get_sentence_by_stable_key(TVL_ITEM)

    assert sentence is not None
    assert sentence.english == "TVL stands for Total Value Locked in DeFi."
    assert sentence.chinese == "TVL 指 DeFi 中的总锁定价值（Total Value Locked）。"
    assert sentence.core_words == ("TVL", "Total Value Locked", "DeFi")
    assert repository.get_sentence(COURSE_ID, "crypto-s0026") is sentence


def test_every_crypto_day_builds_a_typing_session_without_article_rows(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path)
    try:
        course = context.course_repository.get_course(COURSE_ID)
        assert course is not None
        lessons = [
            lesson
            for level in course.levels
            for unit in level.units
            for lesson in unit.lessons
        ]
        assert len(lessons) == 14
        for lesson in lessons:
            session = context.course_learning_service.build_session(
                COURSE_ID,
                lesson.lesson_id,
                "manual",
            )
            assert session.typing_sentences
            assert len(session.typing_sentences) == len(session.chinese_translations)
            assert all(
                "speaking" not in activity_types
                and "listening" not in activity_types
                and "dictation" not in activity_types
                for activity_types in session.activity_types_by_item
            )

        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM article_sentences").fetchone()[0] == 0
    finally:
        context.database.close()


def test_crypto_day_page_exposes_text_learning_without_speaking(tmp_path: Path) -> None:
    app = _app()
    context = _context(tmp_path)
    page = CoursePage(context.course_repository, context.course_progress_service)
    try:
        page.show()
        page.show_lesson(COURSE_ID, "crypto-l1-u01-d01")
        app.processEvents()

        assert page.lesson_items.count() == 5
        assert "A crypto wallet manages" in page.lesson_items.item(0).text()
        assert "打字" in page.lesson_counts_label.text()
        assert "听写" not in page.lesson_counts_label.text()
        assert "朗读" not in page.lesson_counts_label.text()
        assert "跟读" not in page.lesson_counts_label.text()
        assert "speaking" not in page.capability_buttons
        assert not page.capability_buttons["tts"].isVisibleTo(page)
        assert page.capability_buttons["vocabulary"].isVisibleTo(page)
    finally:
        page.close()
        context.database.close()
