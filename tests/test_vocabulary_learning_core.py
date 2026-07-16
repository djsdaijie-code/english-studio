from __future__ import annotations

import io
import json
import sqlite3
import urllib.error
from datetime import datetime
from pathlib import Path

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.models.vocabulary import VocabularyAttempt
from english_typing_trainer.services.dictionary_provider import DictionaryProviderError, FreeDictionaryProvider, parse_dictionary_payload
from english_typing_trainer.services.word_explanation_provider import parse_word_explanation
from english_typing_trainer.services.translation_provider import TranslationProviderError
from english_typing_trainer.services.word_normalization import WordNormalizationService


class Response:
    def __init__(self, body: bytes, content_type: str="application/json"):
        self.body=body; self.headers={"Content-Type":content_type}
    def __enter__(self): return self
    def __exit__(self,*_args): return False
    def read(self,*_args): return self.body


PAYLOAD=[{"word":"communication","phonetic":"/kəˌmjuːnɪˈkeɪʃn/","phonetics":[
    {"text":"/other/","audio":""},{"text":"/preferred/","audio":"//audio.example/word.mp3"}],
    "meanings":[{"partOfSpeech":"noun","definitions":[{"definition":"The act of sharing information.","example":"Clear communication helps."}]}]}]


def test_schema6_new_install_tables_and_settings(tmp_path: Path):
    context=build_app_context(data_dir=tmp_path/"data")
    try:
        assert context.database.get_schema_version()==13
        names={r[0] for r in context.database.connect().execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"vocabulary_entries","vocabulary_contexts","vocabulary_learning_state","vocabulary_attempts"}<=names
        columns={r[1] for r in context.database.connect().execute("PRAGMA table_info(tts_audio_cache)")}
        assert {"source_type","source_url_hash","content_type"}<=columns
        assert context.settings_service.get_settings().vocabulary_typing_count==5
    finally: context.database.close()


def test_v5_to_v6_backup_and_old_vocabulary_migration(tmp_path: Path):
    db=tmp_path/"data"/"typing_trainer.db"; db.parent.mkdir()
    connection=sqlite3.connect(db); connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)"); runner=MigrationRunner()
    runner._apply_version_1(connection); runner._apply_version_2(connection); runner._apply_version_3(connection); runner._apply_version_4(connection); runner._apply_version_5(connection)
    connection.execute("INSERT INTO vocabulary_items(normalized_word,display_word,meaning,note,status,mastery_level,review_count,correct_review_count,wrong_review_count,created_at,updated_at,is_archived) VALUES ('run','Run','运行','语境说明','learning',2,1,1,0,'2026-01-01','2026-01-01',0)")
    connection.commit(); connection.close()
    manager=DatabaseManager(db); manager.initialize()
    try:
        assert manager.get_schema_version()==13
        assert manager.connect().execute("SELECT display_word FROM vocabulary_entries WHERE normalized_word='run'").fetchone()[0]=="Run"
        assert list((db.parent/"backups").glob("typing_trainer-v5-before-v13-*.db"))
    finally: manager.close()


def test_v6_failure_rolls_back(monkeypatch,tmp_path:Path):
    db=tmp_path/"broken.db"; connection=sqlite3.connect(db); connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)"); runner=MigrationRunner()
    runner._apply_version_1(connection); runner._apply_version_2(connection); runner._apply_version_3(connection); runner._apply_version_4(connection); runner._apply_version_5(connection); connection.commit()
    original=runner._apply_version_6
    def fail(conn): original(conn); raise RuntimeError("fail")
    monkeypatch.setattr(runner,"_apply_version_6",fail)
    with pytest.raises(RuntimeError): runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0]==5
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='vocabulary_entries'").fetchone() is None
    connection.close()


@pytest.mark.parametrize("raw,normalized",[("Word","word"),("don't","don't"),("teacher’s","teacher's"),("well-known","well-known"),("...",""),("123","")])
def test_word_normalization(raw,normalized): assert WordNormalizationService().normalize(raw)==normalized


def test_selection_rejects_sentence_and_safe_lemma_candidates():
    service=WordNormalizationService()
    with pytest.raises(ValueError,match="请选择一个英文单词"): service.validate_selection("two words")
    assert service.safe_lemma_candidates("stories")==["stories","story"]
    assert service.safe_lemma_candidates("walked")==["walked","walk"]


def test_collect_deduplicates_entry_and_context_but_keeps_new_source(tmp_path:Path):
    context=build_app_context(data_dir=tmp_path/"data")
    try:
        a=context.vocabulary_learning_service.collect("Run",sentence="Run locally.",start_offset=0,end_offset=3)
        b=context.vocabulary_learning_service.collect("run",sentence="Run locally.",start_offset=0,end_offset=3)
        c=context.vocabulary_learning_service.collect("run",sentence="I run daily.",start_offset=2,end_offset=5)
        assert a.entry.id==b.entry.id==c.entry.id and not b.context_created and c.context_created
        assert len(context.vocabulary_learning_service.detail(a.entry.id)[1])==2
    finally: context.database.close()


def test_dictionary_request_encoding_and_parse():
    seen={}
    def opener(request,timeout): seen["url"]=request.full_url; seen["agent"]=request.headers["User-agent"]; return Response(json.dumps(PAYLOAD).encode())
    result=FreeDictionaryProvider(opener=opener).lookup("well known")
    assert seen["url"].endswith("well%20known") and "EnglishTypingTrainer" in seen["agent"]
    assert result.phonetic=="/preferred/" and result.audio_url.startswith("https://") and result.primary_part_of_speech=="noun"
    assert result.definitions[0]["definition"]=="The act of sharing information."


def test_dictionary_parse_accepts_phonetic_text_without_audio():
    payload=[{"word":"you","phonetics":[{"text":"/juː/","audio":""}],"meanings":[]}]
    assert parse_dictionary_payload("you",payload).phonetic=="/juː/"


@pytest.mark.parametrize("code,category",[(404,"not_found"),(429,"rate_limit"),(503,"server")])
def test_dictionary_http_errors(code,category):
    def opener(*_args,**_kwargs): raise urllib.error.HTTPError("url",code,"error",{},None)
    with pytest.raises(DictionaryProviderError) as caught: FreeDictionaryProvider(opener=opener).lookup("word")
    assert caught.value.category==category


def test_dictionary_invalid_json():
    with pytest.raises(DictionaryProviderError) as caught: FreeDictionaryProvider(opener=lambda *_a,**_k:Response(b"{" )).lookup("word")
    assert caught.value.category=="invalid_response"


def test_word_explanation_json_validation():
    result=parse_word_explanation(json.dumps({"word":"run","lemma":"run","part_of_speech":"verb","meaning_in_context_zh":"运行","simple_explanation_zh":"让程序开始工作。","collocation":"run a program","example_en":"Run it.","example_zh":"运行它。"}))
    assert result.meaning_in_context_zh=="运行"
    with pytest.raises(TranslationProviderError): parse_word_explanation("{}")


def test_attempts_state_and_review_schedule(tmp_path:Path):
    context=build_app_context(data_dir=tmp_path/"data")
    try:
        collected=context.vocabulary_learning_service.collect("run",sentence="Run it.",typing_target_count=3)
        for _ in range(3): context.vocabulary_learning_service.record_attempt(VocabularyAttempt(collected.entry.id,"typing","run","run",True,100,100, vocabulary_context_id=collected.context.id))
        state=context.vocabulary_learning_service.repository.get_state(collected.entry.id)
        assert state.status=="learning" and state.typing_completed_count==3 and state.correct_attempts==3
        context.vocabulary_learning_service.record_attempt(VocabularyAttempt(collected.entry.id,"meaning_recall",self_rating="known",vocabulary_context_id=collected.context.id))
        state=context.vocabulary_learning_service.repository.get_state(collected.entry.id)
        assert state.status=="reviewing" and 2 <= (state.next_review_at-datetime.now()).days <= 3
        assert context.database.connect().execute("SELECT COUNT(*) FROM vocabulary_attempts").fetchone()[0]==4
    finally: context.database.close()


def test_cloze_uses_exact_source_form(tmp_path:Path):
    context=build_app_context(data_dir=tmp_path/"data")
    try:
        c=context.vocabulary_learning_service.collect("running",sentence="She is running fast.",start_offset=7,end_offset=14).context
        assert context.vocabulary_learning_service.cloze_text(c)=="She is ___ fast."
    finally:context.database.close()
