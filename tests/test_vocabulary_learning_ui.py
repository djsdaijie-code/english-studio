from __future__ import annotations

import os
from pathlib import Path
from time import monotonic

import pytest

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QMessageBox
from PySide6.QtTest import QTest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.models.vocabulary import VocabularyContext, VocabularyEntry, VocabularyLearningState
from english_typing_trainer.services.dictionary_provider import DictionaryResult, DictionaryProviderError
from english_typing_trainer.services.word_explanation_provider import WordExplanationResult
from english_typing_trainer.ui.main_window import MainWindow
import english_typing_trainer.ui.main_window as main_window_module
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
    page.context_combo.setCurrentIndex(1)
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
        start=window.current_material.section_text.index("program"); window._collect_selected_word("program",start,start+7); application.processEvents()
        assert context.vocabulary_learning_service.repository.get_by_word("program") is not None
        assert window.vocabulary_quick_access.added_popup.isVisibleTo(window)
        assert window.vocabulary_quick_access.word_label.text()=="program"
        assert not window.vocabulary_quick_access.book_button.isVisible()
        assert window.practice_view.input_edit.hasFocus()
        window.current_practice_saved=True; window.close()
    finally:context.database.close()


def test_input_survives_time_and_right_panel_updates():
    app(); page=WordLearningPage(); entry,contexts,state=data(); page.load(entry,contexts,state); page._key(key("r")); QTest.qWait(2100)
    assert page.input.toPlainText()=="r"
    updated=VocabularyEntry("run","Run",lemma="run",phonetic="/new/",primary_part_of_speech="verb",dictionary_status="ready",id=1)
    updated_context=[VocabularyContext(1,"running","She is running fast.",start_offset=7,end_offset=14,contextual_meaning_zh="跑步",explanation_zh="新讲解",id=2)]
    assert page.update_details(updated,updated_context,state)
    assert page.input.toPlainText()=="r" and page.typed=="r" and page.repeat_index==0 and page.input.textCursor().position()==1
    page.context_combo.setCurrentIndex(0); page._update_prompt(); assert page.input.toPlainText()=="r"


def test_learning_queue_navigation_auto_next_and_results():
    app(); page=WordLearningPage(); first,contexts,state=data(); state.typing_target_count=1
    contexts=[contexts[1]]
    second=VocabularyEntry("learn","learn",id=4); second_context=[VocabularyContext(4,"learn","I learn English.",start_offset=2,end_offset=7,id=5)]; second_state=VocabularyLearningState(4,typing_target_count=1)
    page.load_queue([(first,contexts,state),(second,second_context,second_state)]); attempts=[]; results=[]; page.attempt_completed.connect(attempts.append); page.queue_finished.connect(results.append)
    for char in "run":page._key(key(char))
    QTest.qWait(500); assert page.entry.id==4 and page.queue_position.text()=="第 2 / 2 个"
    page.previous_word(); assert page.entry.id==1; page.next_word(); page.skip_word()
    assert results and results[-1]["total"]==2 and results[-1]["skipped"]==1


@pytest.mark.parametrize(("target","typed","is_correct"),(
    ("English","English",True),
    ("English","english",False),
    ("english","English",False),
    ("API","API",True),
    ("API","api",False),
    ("OpenAI","OpenAI",True),
    ("OpenAI","openai",False),
))
def test_vocabulary_typing_preserves_target_casing(target,typed,is_correct):
    app(); page=WordLearningPage()
    entry=VocabularyEntry(target.lower(),target,id=20)
    context=VocabularyContext(20,target,f"Learn {target} today.",start_offset=6,end_offset=6+len(target),id=21)
    state=VocabularyLearningState(20,typing_target_count=1); attempts=[]
    page.load(entry,[context],state); page.attempt_completed.connect(attempts.append)
    for char in typed:page._key(key(char))
    assert page.prompt.text()==target
    assert attempts[-1].expected_answer==target
    assert attempts[-1].is_correct is is_correct


def test_partial_cased_word_is_correct_so_far_and_waits_for_last_character():
    app(); page=WordLearningPage()
    entry=VocabularyEntry("english","English",id=20)
    context=VocabularyContext(20,"English","Learn English today.",start_offset=6,end_offset=13,id=21)
    page.load(entry,[context],VocabularyLearningState(20,typing_target_count=1)); attempts=[]; page.attempt_completed.connect(attempts.append)
    for char in "Englis":page._key(key(char))
    assert page.input.toPlainText()=="Englis" and page.errors==0 and not attempts
    assert all(page._character_format(index,page._expected()).foreground().color()!=QColor("#c74444") for index in range(6))


def test_cloze_and_context_switch_use_source_word_casing():
    app(); page=WordLearningPage()
    entry=VocabularyEntry("openai","OpenAI",id=20)
    contexts=[
        VocabularyContext(20,"OpenAI","OpenAI builds tools.",start_offset=0,end_offset=6,id=21),
        VocabularyContext(20,"OPENAI","We wrote OPENAI here.",start_offset=9,end_offset=15,id=22),
    ]
    page.load(entry,contexts,VocabularyLearningState(20,typing_target_count=1)); page.mode_combo.setCurrentIndex(page.mode_combo.findData("sentence_cloze"))
    assert page._expected()=="OpenAI" and "___" in page.prompt.text()
    page.context_combo.setCurrentIndex(1)
    assert page._expected()=="OPENAI" and "___" in page.prompt.text()
    attempts=[]; page.attempt_completed.connect(attempts.append)
    for char in "OpenAI":page._key(key(char))
    assert attempts[-1].expected_answer=="OPENAI" and attempts[-1].is_correct is False


def test_auto_enrichment_for_queue_word_updates_details_in_place_and_reuses_cache(tmp_path:Path,monkeypatch):
    application=app(); calls={"dictionary":0,"ai":0}
    class FakeDictionary:
        def lookup(self,word):
            calls["dictionary"]+=1
            return DictionaryResult(word,word,"/juː/","","pronoun",[],[{"word":word,"phonetic":"/juː/"}])
    class FakeDeepSeek:
        def __init__(self,*_args,**_kwargs):pass
        def explain(self,**_kwargs):
            calls["ai"]+=1
            return WordExplanationResult("you","you","pronoun","你","当前句中的你。","you can","You can do it.","你可以做到。")
    monkeypatch.setattr(main_window_module,"FreeDictionaryProvider",FakeDictionary)
    monkeypatch.setattr(main_window_module,"DeepSeekWordExplanationProvider",FakeDeepSeek)
    context=build_app_context(data_dir=tmp_path/"data")
    window=None
    try:
        collected=context.vocabulary_learning_service.collect("you",sentence="You can do it.",start_offset=0,end_offset=3)
        window=MainWindow(context); window.show(); window._open_word_learning(collected.entry.id); application.processEvents()
        deadline=monotonic()+4
        while monotonic()<deadline:
            application.processEvents(); QTest.qWait(25)
            entry,contexts,_=context.vocabulary_learning_service.detail(collected.entry.id)
            if entry.dictionary_status=="ready" and contexts[0].ai_status=="ready":break
        assert entry.phonetic=="/juː/" and contexts[0].contextual_meaning_zh=="你"
        window.word_learning_page._key(key("y")); assert window.word_learning_page.input.toPlainText()=="y"
        QTest.qWait(100); assert window.word_learning_page.input.toPlainText()=="y"
        first_counts=dict(calls); window._open_word_learning(collected.entry.id); application.processEvents(); QTest.qWait(100)
        assert calls==first_counts
    finally:
        if window:window.close()
        context.database.close()


def test_dictionary_and_ai_fail_independently_with_retry_status(tmp_path:Path,monkeypatch):
    application=app(); calls={"dictionary":0,"ai":0}; succeed={"dictionary":False,"ai":False}
    class FakeDictionary:
        def lookup(self,_word):
            calls["dictionary"]+=1
            if not succeed["dictionary"]:raise DictionaryProviderError("network","无法连接词典服务。")
            return DictionaryResult("you","you","/juː/","","pronoun",[],[])
    class FakeDeepSeek:
        def __init__(self,*_args,**_kwargs):pass
        def explain(self,**_kwargs):
            calls["ai"]+=1
            if not succeed["ai"]:raise RuntimeError("DeepSeek 暂时不可用")
            return WordExplanationResult("you","you","pronoun","你","解释","you can","You can.","你可以。")
    monkeypatch.setattr(main_window_module,"FreeDictionaryProvider",FakeDictionary)
    monkeypatch.setattr(main_window_module,"DeepSeekWordExplanationProvider",FakeDeepSeek)
    context=build_app_context(data_dir=tmp_path/"data"); window=None
    try:
        collected=context.vocabulary_learning_service.collect("you",sentence="You can.",start_offset=0,end_offset=3)
        window=MainWindow(context); window.show(); window._open_word_learning(collected.entry.id); application.processEvents(); QTest.qWait(300); application.processEvents()
        assert "可重试" in window.word_learning_page.enrichment_status.text()
        succeed["dictionary"]=True; succeed["ai"]=True; window._retry_current_word_enrichment(collected.entry.id,collected.context.id)
        deadline=monotonic()+4
        while monotonic()<deadline:
            application.processEvents(); QTest.qWait(25)
            entry,contexts,_=context.vocabulary_learning_service.detail(collected.entry.id)
            if entry.dictionary_status=="ready" and contexts[0].ai_status=="ready":break
        assert entry.dictionary_status=="ready" and contexts[0].ai_status=="ready"
    finally:
        if window:window.close()
        context.database.close()


def test_old_enrichment_callback_does_not_replace_current_queue_word(tmp_path:Path):
    application=app(); context=build_app_context(data_dir=tmp_path/"data"); window=None
    try:
        first=context.vocabulary_learning_service.collect("you",sentence="You can.",start_offset=0,end_offset=3)
        second=context.vocabulary_learning_service.collect("learn",sentence="Learn more.",start_offset=0,end_offset=5)
        settings=context.settings_service.get_settings(); settings.vocabulary_auto_enrich=False; context.settings_service.save_settings(settings)
        window=MainWindow(context); window.show(); window._open_word_learning(first.entry.id); window._open_word_learning(second.entry.id); application.processEvents()
        result=WordExplanationResult("you","you","pronoun","你","旧词讲解","you can","You can.","你可以。")
        window._word_explained(first.context.id,result,object()); application.processEvents()
        assert window.word_learning_page.entry.id==second.entry.id
        assert "旧词讲解" not in window.word_learning_page.explanation.text()
    finally:
        if window:window.close()
        context.database.close()
