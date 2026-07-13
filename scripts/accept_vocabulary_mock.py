from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.dictionary_provider import DictionaryResult
from english_typing_trainer.services.word_explanation_provider import WordExplanationResult
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme


def capture(window,path,app): app.processEvents(); assert window.grab().save(str(path))
def key(char): return QKeyEvent(QKeyEvent.Type.KeyPress,0,Qt.KeyboardModifier.NoModifier,char)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument("--data-dir",type=Path,required=True); parser.add_argument("--screenshots",type=Path,required=True); args=parser.parse_args()
    args.data_dir.mkdir(parents=True,exist_ok=True); args.screenshots.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([])
    context=build_app_context(data_dir=args.data_dir,credential_store=MemoryCredentialStore(),tts_credential_store=MemoryCredentialStore())
    settings=context.settings_service.get_settings(); settings.vocabulary_auto_enrich=False; context.settings_service.save_settings(settings)
    article_text=("Clear communication helps teams work together effectively. You can run the program locally and review every result carefully. "
                  "A well-known teacher explains difficult ideas with simple examples. Running short practice sessions builds confidence. ")*3
    source=args.data_dir/"中文路径 单词学习.txt"; source.write_text(article_text,encoding="utf-8")
    article=context.article_library.import_txt_file(source,500).article; material=context.practice_service.load_practice_material(article.id); sentences=context.sentence_service.ensure_for_section(material.section_id)
    sentence=sentences[0]; start=sentence.normalized_text.index("communication")
    first=context.vocabulary_learning_service.collect("communication",sentence=sentence.normalized_text,article_id=article.id,article_sentence_id=sentence.id,start_offset=start,end_offset=start+13)
    second_sentence=sentences[1]; second_start=second_sentence.normalized_text.index("run")
    context.vocabulary_learning_service.collect("communication",sentence="Good communication prevents mistakes.",article_id=article.id,start_offset=5,end_offset=18)
    dictionary=DictionaryResult("communication","communication","/kəˌmjuːnɪˈkeɪʃn/","https://audio.example/communication.mp3","noun",[{"part_of_speech":"noun","definition":"The act of sharing information."}],[])
    context.vocabulary_learning_service.apply_dictionary_result(first.entry.id,dictionary)
    explanation=WordExplanationResult("communication","communication","noun","交流；沟通","这里表示团队成员之间清楚地传递信息。","clear communication","Clear communication improves teamwork.","清晰沟通能改善团队合作。")
    context.vocabulary_learning_service.apply_explanation_result(first.context.id,explanation)
    run=context.vocabulary_learning_service.collect("run",sentence=second_sentence.normalized_text,article_id=article.id,article_sentence_id=second_sentence.id,start_offset=second_start,end_offset=second_start+3)
    context.vocabulary_learning_service.apply_dictionary_result(run.entry.id,DictionaryResult("run","run","/rʌn/","","verb",[{"part_of_speech":"verb","definition":"To operate."}],[]))
    context.vocabulary_learning_service.apply_explanation_result(run.context.id,WordExplanationResult("run","run","verb","运行","这里表示让程序开始工作。","run a program","Run the program.","运行程序。"))
    window=MainWindow(context); window.show(); apply_theme(window,"light"); window.resize(1280,720)
    try:
        window._begin_practice(material); browser=window.sentence_practice_view.text_browser
        cursor=browser.textCursor(); cursor.setPosition(start); cursor.setPosition(start+13,QTextCursor.MoveMode.KeepAnchor); browser.setTextCursor(cursor)
        capture(window,args.screenshots/"01-article-word-selection-light-1280x720.png",app)
        menu=QMenu(browser); menu.addAction("加入单词本"); menu.show(); app.processEvents(); assert menu.grab().save(str(args.screenshots/"02-sentence-collection-menu.png")); menu.close()
        original_information=QMessageBox.information; QMessageBox.information=lambda *_args,**_kwargs: QMessageBox.StandardButton.Ok
        window._collect_selected_word("Clear",0,5); app.processEvents(); assert browser.hasFocus() or window.sentence_practice_view.input_edit.hasFocus()
        QMessageBox.information=original_information
        window.current_practice_saved=True; window._show_vocabulary(); capture(window,args.screenshots/"02-word-book-list-light.png",app)
        window.vocabulary_page.search_input.setText("comm"); capture(window,args.screenshots/"03-search-and-status-filter.png",app); window.vocabulary_page.search_input.clear()
        window._open_word_learning(first.entry.id); capture(window,args.screenshots/"03-word-learning-light.png",app)
        page=window.word_learning_page
        for char in "commxnication": page._key(key(char))
        capture(window,args.screenshots/"04-word-typing-error.png",app)
        page._reset_round(); page._key(key("c")); page._key(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_Backspace,Qt.KeyboardModifier.NoModifier,"")); assert page.typed==""
        page.input.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_V,Qt.KeyboardModifier.ControlModifier,"v")); assert page.typed==""
        for repetition in range(5):
            for char in "communication": page._key(key(char))
            if repetition<4: page._reset_round()
        assert page.repeat_index==5 and not page.input.isEnabled()
        page.mode_combo.setCurrentIndex(page.mode_combo.findData("sentence_cloze")); capture(window,args.screenshots/"05-sentence-cloze.png",app)
        for char in "communication": page._key(key(char))
        page.mode_combo.setCurrentIndex(page.mode_combo.findData("meaning_recall")); page._reveal(); capture(window,args.screenshots/"06-meaning-recall-rating.png",app)
        page._rate("known"); assert context.vocabulary_learning_service.repository.get_state(first.entry.id).status=="reviewing"
        page.context_combo.setCurrentIndex(1); capture(window,args.screenshots/"07-multiple-contexts.png",app)
        window.resize(1920,1080); capture(window,args.screenshots/"08-word-learning-light-1920x1080.png",app)
        apply_theme(window,"dark"); capture(window,args.screenshots/"09-word-learning-dark-1920x1080.png",app)
        window.resize(1280,720); capture(window,args.screenshots/"10-word-learning-dark-1280x720.png",app)
        window.current_practice_saved=True; window._show_library(); window.practice_mode_control.button("continuous").click(); window.continue_button.click(); capture(window,args.screenshots/"11-continuous-regression.png",app)
        continuous=window.practice_view.text_browser; cursor=continuous.textCursor(); cursor.setPosition(second_start); cursor.setPosition(second_start+3,QTextCursor.MoveMode.KeepAnchor); continuous.setTextCursor(cursor)
        menu=QMenu(continuous); menu.addAction("加入单词本"); menu.show(); app.processEvents(); assert menu.grab().save(str(args.screenshots/"14-continuous-right-click-menu.png")); menu.close()
        program_offset=continuous.toPlainText().index("program"); original_information=QMessageBox.information; QMessageBox.information=lambda *_args,**_kwargs: QMessageBox.StandardButton.Ok
        window._collect_selected_word("program",program_offset,program_offset+7); app.processEvents(); assert window.practice_view.input_edit.hasFocus()
        QMessageBox.information=original_information
        window.current_practice_saved=True; window._show_library(); window.practice_mode_control.button("sentence").click(); window.continue_button.click(); capture(window,args.screenshots/"12-sentence-regression.png",app)
        window.current_practice_saved=True; window._show_vocabulary(); capture(window,args.screenshots/"13-word-book-dark.png",app)
        context.vocabulary_learning_service.set_mastered(first.entry.id,True); window._refresh_vocabulary_page(); capture(window,args.screenshots/"15-mastered-status-dark.png",app)
        context.vocabulary_learning_service.set_mastered(first.entry.id,False); apply_theme(window,"light"); window.resize(1500,1000); window._open_word_learning(first.entry.id); capture(window,args.screenshots/"16-word-learning-light-1500x1000.png",app)
        page.mode_combo.setCurrentIndex(page.mode_combo.findData("sentence_cloze")); capture(window,args.screenshots/"17-cloze-light-1500x1000.png",app)
        page.mode_combo.setCurrentIndex(page.mode_combo.findData("meaning_recall")); page._reveal(); capture(window,args.screenshots/"18-rating-light-1500x1000.png",app)
        window.close(); reopened=MainWindow(context); reopened.show(); reopened._show_vocabulary(); app.processEvents(); assert reopened.vocabulary_page.table.rowCount()>=4; reopened.close()
    finally: context.database.close()
    print(f"VOCABULARY_MOCK_ACCEPTANCE_OK entry={first.entry.id} screenshots={args.screenshots.resolve()}")


if __name__=="__main__": main()
