from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.services.word_normalization import WordNormalizationService
from english_typing_trainer.services.article_word_index import ArticleWordIndexService


def test_new_article_is_indexed_with_offsets_duplicates_and_no_external_calls(tmp_path:Path,monkeypatch):
    context=build_app_context(data_dir=tmp_path/"data")
    try:
        text="English learning isn't hard. I'm learning with a well-known teacher. learning 123 https://bad.example/path user@example.com"
        source=tmp_path/"article.txt"; source.write_text(text,encoding="utf-8")
        article=context.article_library.import_txt_file(source,500).article
        rows=context.database.connect().execute("SELECT * FROM article_word_occurrences WHERE article_id=? ORDER BY occurrence_index",(article.id,)).fetchall()
        words=[row["normalized_word"] for row in rows]
        assert "english" in words and "isn't" in words and "i'm" in words and "well-known" in words
        assert words.count("learning")==3 and "123" not in words and "example" not in words
        for row in rows: assert text[row["start_offset"]:row["end_offset"]]==row["source_word"]
        assert context.database.connect().execute("SELECT COUNT(*) FROM vocabulary_entries").fetchone()[0]==0
        assert context.database.connect().execute("SELECT COUNT(*) FROM tts_audio_cache").fetchone()[0]==0
    finally:context.database.close()


def test_lazy_ensure_and_rebuild_are_idempotent(tmp_path:Path):
    context=build_app_context(data_dir=tmp_path/"data")
    try:
        source=tmp_path/"a.txt"; source.write_text("One word. One more word.",encoding="utf-8"); article=context.article_library.import_txt_file(source,500).article
        connection=context.database.connect(); connection.execute("DELETE FROM article_word_occurrences WHERE article_id=?",(article.id,)); connection.commit()
        first=context.article_word_index_service.ensure(article.id); second=context.article_word_index_service.ensure(article.id)
        assert first==second==5
        assert context.article_word_index_service.rebuild(article.id)==5
        assert connection.execute("SELECT COUNT(*) FROM article_word_occurrences WHERE article_id=?",(article.id,)).fetchone()[0]==5
    finally:context.database.close()


def test_article_word_aggregation_scopes_and_mastered_filter(tmp_path:Path):
    context=build_app_context(data_dir=tmp_path/"data")
    try:
        article_ids=[]
        for index,text in enumerate(("Run run learn.","Learn English.")):
            path=tmp_path/f"{index}.txt"; path.write_text(text,encoding="utf-8"); article_ids.append(context.article_library.import_txt_file(path,500).article.id)
        rows=context.article_word_index_service.list_words(article_ids[0])
        assert {row["normalized_word"]:row["occurrence_count"] for row in rows}["run"]==2
        all_rows=context.article_word_index_service.list_words(); learn=next(row for row in all_rows if row["normalized_word"]=="learn")
        assert learn["article_count"]==2
        collected=context.vocabulary_learning_service.collect("learn"); context.vocabulary_learning_service.set_mastered(collected.entry.id,True)
        assert "learn" not in [row["normalized_word"] for row in context.article_word_index_service.list_words(hide_mastered=True)]
    finally:context.database.close()


def test_v6_to_v7_migration_and_rollback(tmp_path:Path,monkeypatch):
    connection=sqlite3.connect(tmp_path/"legacy.db"); connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)"); runner=MigrationRunner()
    for method in (runner._apply_version_1,runner._apply_version_2,runner._apply_version_3,runner._apply_version_4,runner._apply_version_5,runner._apply_version_6):method(connection)
    connection.commit(); original=runner._apply_version_7
    def fail(conn):original(conn);raise RuntimeError("fail")
    monkeypatch.setattr(runner,"_apply_version_7",fail)
    with pytest.raises(RuntimeError):runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0]==6
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='article_word_occurrences'").fetchone() is None
    monkeypatch.setattr(runner,"_apply_version_7",original);runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0]==12
    connection.close()
