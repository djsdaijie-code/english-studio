from __future__ import annotations

import argparse,os,sys
from pathlib import Path
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication,QMenu

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme

def capture(window,path,app):app.processEvents();assert window.grab().save(str(path))
def key(char):return QKeyEvent(QKeyEvent.Type.KeyPress,0,Qt.KeyboardModifier.NoModifier,char)

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--data-dir",type=Path,required=True);parser.add_argument("--screenshots",type=Path,required=True);args=parser.parse_args();args.data_dir.mkdir(parents=True,exist_ok=True);args.screenshots.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]);context=build_app_context(data_dir=args.data_dir,credential_store=MemoryCredentialStore(),tts_credential_store=MemoryCredentialStore())
    settings=context.settings_service.get_settings();settings.vocabulary_auto_enrich=False;settings.vocabulary_typing_count=1;context.settings_service.save_settings(settings)
    text=("English learning helps friends communicate. I don't think a well-known teacher's method is difficult. "
          "Students record progress and present ideas clearly. English learning builds confidence. ")*3
    source=args.data_dir/"中文路径 article words.txt";source.write_text(text,encoding="utf-8");article=context.article_library.import_txt_file(source,500).article
    assert context.database.connect().execute("SELECT COUNT(*) FROM article_word_occurrences WHERE article_id=?",(article.id,)).fetchone()[0]>30
    window=MainWindow(context);window.show();window.resize(1280,720);apply_theme(window,"light")
    try:
        capture(window,args.screenshots/"01-article-preview-light-1280x720.png",app)
        menu=QMenu(window.preview_content);menu.addAction("查看当前文章单词");menu.addAction("重新提取文章单词");menu.show();app.processEvents();assert menu.grab().save(str(args.screenshots/"02-article-preview-context-menu.png"));menu.close()
        index=window.vocabulary_page.scope_combo.findData("article");window.vocabulary_page.scope_combo.setCurrentIndex(index);window._show_vocabulary();app.processEvents();assert window.vocabulary_page.table.rowCount()>10
        capture(window,args.screenshots/"03-current-article-words-counts.png",app)
        window.vocabulary_page.search_input.setText("learn");capture(window,args.screenshots/"04-three-scopes-and-search.png",app);window.vocabulary_page.search_input.clear();window._refresh_vocabulary_page()
        first=window.vocabulary_page._rows[0];window._start_vocabulary_row(first);app.processEvents();page=window.word_learning_page;assert len(page.queue)>5
        page._key(key(page._expected()[0]));capture(window,args.screenshots/"05-input-stable-loading-light.png",app);QTest.qWait(3100);assert page.input.toPlainText()==page._expected()[0]
        entry_id=page.entry.id;entry,contexts,state=context.vocabulary_learning_service.detail(entry_id);page.update_details(entry,contexts,state);assert page.input.toPlainText()
        capture(window,args.screenshots/"06-right-panel-update-input-preserved.png",app)
        page._reset_round();first_id=page.entry.id
        for char in page._expected():page._key(key(char))
        QTest.qWait(500);assert page.entry.id!=first_id;capture(window,args.screenshots/"07-auto-next-queue-position.png",app)
        page.skip_word();assert page.skipped_words==1;page.previous_word();capture(window,args.screenshots/"08-queue-navigation.png",app)
        while page.entry is not None and page.completed_words<5:
            for char in page._expected():page._key(key(char))
            QTest.qWait(500)
        while page.entry is not None:page.skip_word()
        capture(window,args.screenshots/"09-queue-results.png",app)
        learned_id=page.queue[0][0].id;context.vocabulary_learning_service.set_mastered(learned_id,True);window._show_vocabulary();window.vocabulary_page.scope_combo.setCurrentIndex(window.vocabulary_page.scope_combo.findData("learning"));window._refresh_vocabulary_page();assert all(row["id"]!=learned_id for row in window.vocabulary_page._rows)
        capture(window,args.screenshots/"10-learning-scope-mastered-excluded.png",app)
        apply_theme(window,"dark");window.resize(1920,1080);window.vocabulary_page.scope_combo.setCurrentIndex(window.vocabulary_page.scope_combo.findData("all"));window._refresh_vocabulary_page();capture(window,args.screenshots/"11-all-scope-dark-1920x1080.png",app)
        window.close();reopened=MainWindow(context);reopened.show();reopened._update_preview(0);assert context.article_word_index_service.ensure(article.id)>0;reopened.resize(1500,1000);capture(reopened,args.screenshots/"12-restart-persistence-light-1500x1000.png",app);reopened.close()
    finally:context.database.close()
    print(f"ARTICLE_WORD_QUEUE_ACCEPTANCE_OK screenshots={args.screenshots.resolve()}")

if __name__=="__main__":main()
