from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.models.vocabulary import VocabularyContext, VocabularyEntry, VocabularyLearningState
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.practice_view import FocusTextBrowser
from english_typing_trainer.ui.theme import apply_theme
from english_typing_trainer.ui.word_learning_page import WordLearningPage


def app(): return QApplication.instance() or QApplication([])
def key(char): return QKeyEvent(QKeyEvent.Type.KeyPress,0,Qt.KeyboardModifier.NoModifier,char)


def data():
    entry=VocabularyEntry("run","Run",lemma="run",phonetic="/rʌn/",primary_part_of_speech="verb",dictionary_status="ready",id=1)
    contexts=[VocabularyContext(1,"running","She is running fast.",start_offset=7,end_offset=14,
        contextual_part_of_speech="verb",contextual_meaning_zh="跑步",explanation_zh="这里表示正在快速跑。",common_collocation="run fast",id=2),
        VocabularyContext(1,"run","You can run the program.",start_offset=8,end_offset=11,contextual_meaning_zh="运行",id=3)]
    state=VocabularyLearningState(1,typing_target_count=5)
    return entry,contexts,state


def test_source_browser_emits_selected_word_and_offsets():
    app(); browser=FocusTextBrowser(); browser.setPlainText("A well-known teacher."); cursor=browser.textCursor(); cursor.setPosition(2); cursor.setPosition(12,QTextCursor.MoveMode.KeepAnchor); browser.setTextCursor(cursor)
    captured=[]; browser.word_selected.connect(lambda *args:captured.append(args)); browser._emit_selection()
    assert captured==[("well-known",2,12)]


def test_word_learning_page_typing_errors_backspace_and_completion():
    app(); page=WordLearningPage(); entry,contexts,state=data(); page.load(entry,contexts,state); attempts=[]; page.attempt_completed.connect(attempts.append)
    page._key(key("r")); page._key(key("x")); assert page.input.toPlainText()=="rx" and page.errors==1
    page._key(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_Backspace,Qt.KeyboardModifier.NoModifier,"")); page._key(key("u")); page._key(key("n"))
    assert attempts and attempts[0].user_input=="run" and attempts[0].is_correct and attempts[0].accuracy<100
    assert page.input.textCursor().position()==len(page.input.toPlainText())


def test_word_learning_cloze_and_meaning_recall_do_not_grade_chinese():
    app(); page=WordLearningPage(); entry,contexts,state=data(); page.load(entry,contexts,state); attempts=[]; page.attempt_completed.connect(attempts.append)
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("sentence_cloze")); assert "___" in page.prompt.text() and "running" not in page.prompt.text()
    for char in "running": page._key(key(char))
    assert attempts[-1].practice_type=="sentence_cloze" and attempts[-1].expected_answer=="running"
    page.mode_combo.setCurrentIndex(page.mode_combo.findData("meaning_recall")); page._reveal(); assert all(not button.isHidden() for button in page.rating_buttons)
    page._rate("fuzzy"); assert attempts[-1].is_correct is None and attempts[-1].self_rating=="fuzzy"


def test_multiple_context_switch_updates_explanation_without_resetting_progress():
    app(); page=WordLearningPage(); entry,contexts,state=data(); page.load(entry,contexts,state); page.repeat_index=2
    page.context_combo.setCurrentIndex(1)
    assert page.meaning.text()=="运行" and page.repeat_index==2 and "program" in page.sentence.text()
    page.load(entry,[],state)
    assert page.current_context is None and "等待获取" in page.meaning.text()


def test_main_window_vocabulary_list_settings_and_themes(tmp_path:Path):
    application=app(); context=build_app_context(data_dir=tmp_path/"data")
    try:
        context.vocabulary_learning_service.collect("communication",sentence="Clear communication helps.")
        window=MainWindow(context); window.show(); window._show_vocabulary(); application.processEvents()
        assert window.vocabulary_page.table.rowCount()==1 and window.vocabulary_page.open_button.isEnabled()
        assert window.settings_page.vocabulary_typing_combo.currentData()==5 and window.settings_page.vocabulary_auto_checkbox.isChecked()
        for theme in ("light","dark"):
            apply_theme(window,theme); window.resize(1280,720); application.processEvents(); assert window.vocabulary_page.width()>700
        window.close()
    finally:context.database.close()


def test_practice_views_share_collection_signal(tmp_path:Path):
    application=app(); context=build_app_context(data_dir=tmp_path/"data")
    try:
        window=MainWindow(context)
        assert hasattr(window.practice_view,"word_collection_requested") and hasattr(window.sentence_practice_view,"word_collection_requested")
        assert window.stack.indexOf(window.word_learning_page)>=0
        window.close()
    finally:context.database.close()


def test_continuous_practice_collects_selected_word_without_losing_focus(tmp_path:Path,monkeypatch):
    application=app(); context=build_app_context(data_dir=tmp_path/"data")
    try:
        source=tmp_path/"article.txt"; source.write_text("You can run the program locally. Keep learning.",encoding="utf-8")
        article=context.article_library.import_txt_file(source,500).article
        settings=context.settings_service.get_settings(); settings.sentence_learning_enabled=False; settings.vocabulary_auto_enrich=False; context.settings_service.save_settings(settings)
        window=MainWindow(context); window.show(); window._start_selected_article("start_over"); application.processEvents()
        monkeypatch.setattr(QMessageBox,"information",lambda *_a,**_k:QMessageBox.StandardButton.Ok)
        start=window.current_material.section_text.index("program"); window._collect_selected_word("program",start,start+7); application.processEvents()
        assert context.vocabulary_learning_service.repository.get_by_word("program") is not None
        assert window.practice_view.input_edit.hasFocus()
        window.current_practice_saved=True; window.close()
    finally:context.database.close()
