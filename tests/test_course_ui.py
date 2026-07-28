from __future__ import annotations

import os
from pathlib import Path
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.courses.repository import CourseRepository
from english_typing_trainer.services.course_learning import CourseLearningService
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.ui.course_page import (
    CourseListCard,
    CoursePage,
    CourseStructureRow,
)
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.result_dialog import ResultDialog


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COURSE_ID = "ai-large-models"
DAY_ONE = "ai-l1-u01-d01"
DAY_TWO = "ai-l1-u01-d02"
DAY_SIX = "ai-l1-u01-d06"
FIRST_ITEM = "ai-large-models-sentence-0001"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _context(tmp_path: Path, *, courses_root: Path | None = None):
    return build_app_context(
        data_dir=tmp_path / "data",
        credential_store=MemoryCredentialStore(),
        courses_root=courses_root,
    )


def _key(character: str) -> QKeyEvent:
    if character == " ":
        return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, " ")
    return QKeyEvent(QKeyEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character)


def test_course_learning_session_adapts_stable_order_without_persistence(tmp_path: Path) -> None:
    context = _context(tmp_path)
    try:
        session = context.course_learning_service.build_session(COURSE_ID, DAY_ONE, "recommended")
        assert session.course_id == COURSE_ID
        assert session.course_stable_key == "ai-large-models-course"
        assert session.unit_id == "ai-l1-u01"
        assert session.lesson_id == DAY_ONE
        assert session.sentence_ids == tuple(f"ai-s{index:04d}" for index in range(1, 7))
        assert session.item_stable_keys[0] == FIRST_ITEM
        assert session.current_item_stable_key == FIRST_ITEM
        assert session.section_text == "".join(item.text for item in session.typing_sentences)
        assert [item.start_offset for item in session.typing_sentences] == sorted(
            item.start_offset for item in session.typing_sentences
        )
        assert all(
            item.id is None and item.article_id is None and item.section_id is None
            for item in session.typing_sentences
        )
        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0] == 0
    finally:
        context.database.close()


def test_continue_skips_completed_items_and_review_restores_all(tmp_path: Path) -> None:
    context = _context(tmp_path)
    try:
        context.course_progress_service.start_item(COURSE_ID, FIRST_ITEM)
        context.course_progress_service.complete_item(COURSE_ID, FIRST_ITEM)
        continued = context.course_learning_service.build_session(COURSE_ID, DAY_ONE, "manual")
        review = context.course_learning_service.build_session(COURSE_ID, DAY_ONE, "review")
        assert FIRST_ITEM not in continued.item_stable_keys
        assert FIRST_ITEM in review.item_stable_keys
        completed = context.course_progress_service.get_item_progress(COURSE_ID, FIRST_ITEM)
        assert completed.status == "completed"
        assert completed.completed_at is not None
        original_completed_at = completed.completed_at
        context.course_progress_service.start_item(COURSE_ID, FIRST_ITEM)
        context.course_progress_service.complete_item(COURSE_ID, FIRST_ITEM)
        repeated = context.course_progress_service.get_item_progress(COURSE_ID, FIRST_ITEM)
        assert repeated.status == "completed"
        assert repeated.completed_at == original_completed_at
    finally:
        context.database.close()


def test_course_page_lists_hierarchy_progress_and_arbitrary_day(tmp_path: Path) -> None:
    app = _app()
    context = _context(tmp_path)
    page = CoursePage(context.course_repository, context.course_progress_service)
    requested: list[tuple[str, str, str]] = []
    page.lesson_start_requested.connect(lambda course, lesson, mode: requested.append((course, lesson, mode)))
    try:
        page.show()
        app.processEvents()
        assert page.course_list.count() == 3
        assert "5 个 Level" in page.course_list.item(0).text()
        assert "8 个 Unit" in page.course_list.item(0).text()
        card = page.course_list.itemWidget(page.course_list.item(0))
        assert isinstance(card, CourseListCard)
        assert card.property("selected") is True
        assert card.title_label.text() == "AI 与大模型英语"
        assert card.description_label.property("role") == "course-card-description"
        assert "5 个 Level · 8 个 Unit" in card.statistics_label.text()
        page.show_course(COURSE_ID)
        summary = context.course_progress_service.get_course_progress(COURSE_ID)
        assert page.back_to_courses_button.text().startswith("←")
        assert page.back_to_courses_button.objectName() == "CourseBackButton"
        assert page.course_progress_bar.objectName() == "CourseOverallProgress"
        assert page.course_progress_card.minimumHeight() >= 104
        assert page.course_progress_bar.value() == round(summary.completion_percentage)
        assert page.course_progress_percent_label.text() == f"{round(summary.completion_percentage)}%"
        assert page.course_progress_label.text() == (
            f"已完成 {summary.completed_required_items} / {summary.total_required_items} 项"
        )
        assert page._progress_activity_type("listening") == "review"
        page.back_to_courses_button.click()
        assert page.view_stack.currentWidget() is page.list_view
        page.show_course(COURSE_ID)
        assert page.hierarchy_tree.topLevelItemCount() == 5
        assert page.hierarchy_tree.header().isHidden()
        level_item = page.hierarchy_tree.topLevelItem(0)
        level_row = page.hierarchy_tree.itemWidget(level_item, 0)
        assert isinstance(level_row, CourseStructureRow)
        assert level_row.property("kind") == "level"
        assert level_row.progress_bar.objectName() == "CourseStructureProgress"
        unit_row = page.hierarchy_tree.itemWidget(level_item.child(0), 0)
        assert isinstance(unit_row, CourseStructureRow)
        assert unit_row.property("kind") == "unit"
        lesson_row = page.hierarchy_tree.itemWidget(level_item.child(0).child(0), 0)
        assert isinstance(lesson_row, CourseStructureRow)
        assert lesson_row.property("kind") == "lesson"
        assert lesson_row.title_label.text().startswith("Day 1")
        unit_count = sum(
            page.hierarchy_tree.topLevelItem(index).childCount()
            for index in range(page.hierarchy_tree.topLevelItemCount())
        )
        assert unit_count == 8
        page.show_lesson(COURSE_ID, DAY_TWO)
        assert page.back_to_course_button.text().startswith("←")
        assert page.back_to_course_button.objectName() == "CourseBackButton"
        assert "Day 2" in page.lesson_title_label.text()
        assert "前面的 Day 尚未全部完成" in page.lesson_warning_label.text()
        assert page.capability_buttons["tts"].isVisibleTo(page)
        assert page.capability_buttons["vocabulary"].isVisibleTo(page)
        assert set(page.capability_buttons) == {"tts", "vocabulary"}
        page.start_lesson_button.click()
        assert requested == [(COURSE_ID, DAY_TWO, "manual")]
    finally:
        page.close()
        context.database.close()


def test_course_page_progress_and_completed_day_switch_to_review(tmp_path: Path) -> None:
    _app()
    context = _context(tmp_path)
    page = CoursePage(context.course_repository, context.course_progress_service)
    try:
        lesson = context.course_repository.get_lesson(COURSE_ID, DAY_ONE)
        assert lesson is not None
        for sentence_id in lesson.new_sentence_ids:
            sentence = context.course_repository.get_sentence(COURSE_ID, sentence_id)
            assert sentence is not None
            context.course_progress_service.complete_item(COURSE_ID, sentence.stable_key)
        page.reload()
        page.show_lesson(COURSE_ID, DAY_ONE)
        assert "6/6" in page.lesson_progress_label.text()
        assert page.start_lesson_button.text() == "重新复习"
        assert page.start_lesson_button.property("sessionMode") == "review"
        next_lesson = context.course_progress_service.get_next_lesson(COURSE_ID)
        assert next_lesson is not None and next_lesson.lesson_id == DAY_TWO
    finally:
        page.close()
        context.database.close()


def test_main_window_course_typing_updates_state_without_article_writes(tmp_path: Path) -> None:
    app = _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        window.show()
        window._start_course_lesson(COURSE_ID, DAY_ONE, "manual")
        app.processEvents()
        assert window.stack.currentWidget() is window.sentence_practice_view
        assert window.current_course_session is not None
        first = window.sentence_practice_view.current_sentence
        assert first is not None
        for character in first.text:
            window.sentence_practice_view._handle_key(_key(character))
        app.processEvents()
        state = context.course_progress_service.get_item_progress(COURSE_ID, FIRST_ITEM)
        assert state.status == "completed"
        assert window.sentence_practice_view.translation_status.text() == "课程译文"
        assert "句型：Start + noun." in window.sentence_practice_view.expressions_label.text()
        assert "核心词：start · chat" in window.sentence_practice_view.expressions_label.text()
        assert "未接入课程词汇能力" not in window.sentence_practice_view.expressions_label.text()
        assert window.sentence_practice_view.text_browser._word_collection_enabled
        assert hasattr(window.sentence_practice_view, "speech_controls")
        assert window.sentence_practice_view.course_words_button.isVisibleTo(
            window.sentence_practice_view
        )
        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM sentence_attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM practice_sessions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM tts_audio_cache").fetchone()[0] == 0
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_course_typing_prefetches_and_auto_reads_audio(tmp_path: Path) -> None:
    app = _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        window.show()
        window._start_course_lesson(COURSE_ID, DAY_ONE, "manual")
        app.processEvents()
        view = window.sentence_practice_view
        first = view.current_sentence
        assert first is not None
        prepared = []
        requested = []
        view.content_preparation_requested.disconnect(window._prepare_sentence_content)
        view.content_preparation_requested.connect(lambda sentence, speed: prepared.append((sentence, speed)))
        view.speech_requested.disconnect(window._request_speech)
        view.speech_requested.connect(lambda text, speed, controls: requested.append((text, speed, controls)))

        view._handle_key(_key(first.text[0]))
        app.processEvents()
        assert prepared and prepared[0][0] == first

        for character in first.text[1:]:
            view._handle_key(_key(character))
        app.processEvents()

        assert view.translation_status.text() == "课程译文"
        assert hasattr(view, "speech_controls")
        assert requested and requested[-1][0] == first.normalized_text
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_course_reinforcement_day_completes_independent_review_progress(
    tmp_path: Path,
) -> None:
    app = _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        window.show()
        window._start_course_lesson(COURSE_ID, DAY_SIX, "manual")
        app.processEvents()
        session = window.current_course_session
        sentence = window.sentence_practice_view.current_sentence
        assert session is not None and sentence is not None
        assert "reinforcement" in session.activity_types_by_item[0]
        stable_key = session.item_stable_keys[0]

        for character in sentence.text:
            window.sentence_practice_view._handle_key(_key(character))
        app.processEvents()

        assert context.course_progress_service.get_activity_progress(
            COURSE_ID, stable_key, "review"
        ).status == "completed"
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_course_capability_ui_exposes_ai_read_aloud_without_follow_reading(
    tmp_path: Path,
) -> None:
    app = _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        window.show()
        assert not hasattr(window, "dictation_page")
        assert not hasattr(window, "pronunciation_page")
        requested = []
        window._request_course_speech = lambda *args, **kwargs: requested.append((args, kwargs))
        window._start_course_capability(COURSE_ID, DAY_TWO, "tts")
        app.processEvents()
        assert requested
        assert requested[0][0][0] == "Save this useful response."

        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM course_capability_attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_course_exit_preserves_in_progress_and_reopens_at_unfinished_item(tmp_path: Path) -> None:
    app = _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        window.show()
        window._start_course_lesson(COURSE_ID, DAY_ONE, "manual")
        first = window.sentence_practice_view.current_sentence
        assert first is not None
        window.sentence_practice_view._handle_key(_key(first.text[0]))
        app.processEvents()
        assert context.course_progress_service.get_item_progress(COURSE_ID, FIRST_ITEM).status == "in_progress"
        window._leave_practice_view()
        assert window.stack.currentWidget() is window.learning_content_page
        assert window.learning_content_page.current_section() == "courses"
        assert "学习中" in window.course_page.lesson_progress_label.text()
        window._start_course_lesson(COURSE_ID, DAY_ONE, "manual")
        assert window.current_course_session is not None
        assert window.current_course_session.current_item_stable_key == FIRST_ITEM
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_course_result_next_action_opens_recommended_day_without_practice_row(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        lesson = context.course_repository.get_lesson(COURSE_ID, DAY_ONE)
        assert lesson is not None
        for sentence_id in lesson.new_sentence_ids:
            sentence = context.course_repository.get_sentence(COURSE_ID, sentence_id)
            assert sentence is not None
            context.course_progress_service.complete_item(COURSE_ID, sentence.stable_key)
        window._start_course_lesson(COURSE_ID, DAY_ONE, "review")

        def choose_next(dialog: ResultDialog) -> int:
            dialog.action = "next"
            return 0

        monkeypatch.setattr(ResultDialog, "exec", choose_next)
        window._handle_course_session_completed(window.sentence_practice_view.current_snapshot())
        assert window.current_course_session is not None
        assert window.current_course_session.lesson_id == DAY_TWO
        assert context.database.connect().execute(
            "SELECT COUNT(*) FROM practice_sessions"
        ).fetchone()[0] == 0
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_broken_course_is_isolated_and_missing_catalog_is_a_page_error(tmp_path: Path) -> None:
    app = _app()
    copied = tmp_path / "broken-courses"
    shutil.copytree(PROJECT_ROOT / "courses", copied)
    (copied / "ai-large-models" / "course.json").write_text("{", encoding="utf-8")
    broken_context = _context(tmp_path / "broken", courses_root=copied)
    broken_page = CoursePage(
        broken_context.course_repository,
        broken_context.course_progress_service,
    )
    missing_context = _context(tmp_path / "missing", courses_root=tmp_path / "no-courses")
    missing_page = CoursePage(
        missing_context.course_repository,
        missing_context.course_progress_service,
    )
    try:
        app.processEvents()
        assert broken_page.course_list.count() == 2
        assert broken_page.course_list.item(0).data(Qt.ItemDataRole.UserRole) == "global-car-logos"
        assert broken_page.failure_label.isVisibleTo(broken_page) or broken_page.failure_label.text()
        assert "部分课程加载失败" in broken_page.failure_label.text()
        assert missing_page.course_list.count() == 0
        assert "课程目录暂时无法读取" in missing_page.catalog_error_label.text()
        assert missing_page.reload_button.isEnabled()
        missing_page.show_lesson(COURSE_ID, DAY_ONE)
        assert "课程目录暂时无法读取" in missing_page.catalog_error_label.text()
    finally:
        broken_page.close()
        missing_page.close()
        broken_context.database.close()
        missing_context.database.close()


def test_paused_course_has_no_automatic_next_but_day_remains_browsable(tmp_path: Path) -> None:
    _app()
    context = _context(tmp_path)
    page = CoursePage(context.course_repository, context.course_progress_service)
    try:
        context.course_progress_service.enroll(COURSE_ID)
        context.course_progress_service.set_enrollment_status(COURSE_ID, "paused")
        page.reload()
        page.show_course(COURSE_ID)
        assert not page.recommended_button.isEnabled()
        assert "不提供自动下一课" in page.recommended_label.text()
        page.show_lesson(COURSE_ID, DAY_TWO)
        assert page.start_lesson_button.isEnabled()
    finally:
        page.close()
        context.database.close()
