from __future__ import annotations

import json
import logging
import threading
import urllib.error
from pathlib import Path

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.models.tts import TTSAudioResult, TTSRequest
from english_typing_trainer.services.tts_provider import MiniMaxTTSProvider, TTSProviderError


class Response:
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self): return json.dumps(self.payload).encode()


class FakeProvider:
    name = "minimax"
    def __init__(self, failures=0, category="network"):
        self.calls = 0; self.failures = failures; self.category = category
    def synthesize(self, request, *, cancel_event=None):
        self.calls += 1
        if cancel_event and cancel_event.is_set(): raise TTSProviderError("cancelled", "cancelled")
        if self.calls <= self.failures: raise TTSProviderError(self.category, "failed")
        return TTSAudioResult(b"ID3-fake-audio", request.audio_format, "minimax", request.model, request.voice_id, duration_ms=1200, usage_characters=len(request.text))


def _payload():
    return {"data":{"audio":b"ID3-audio".hex(),"status":2},"extra_info":{"audio_length":1234,"usage_characters":6},"trace_id":"trace-1","base_resp":{"status_code":0,"status_msg":"success"}}


def test_minimax_request_and_audio_response(caplog) -> None:
    captured = {}
    def opener(request, timeout): captured.update(request=request, timeout=timeout); return Response(_payload())
    caplog.set_level(logging.INFO)
    provider = MiniMaxTTSProvider("secret-key-value", opener=opener)
    request = TTSRequest(text="Hello.", model="speech-2.8-turbo", voice_id="English_magnetic_voiced_man", speed=0.8)
    result = provider.synthesize(request)
    body = json.loads(captured["request"].data)
    assert captured["request"].full_url == "https://api.minimax.io/v1/t2a_v2"
    assert body["model"] == "speech-2.8-turbo"
    assert body["voice_setting"] == {"voice_id":"English_magnetic_voiced_man","speed":0.8,"vol":1.0,"pitch":0}
    assert body["audio_setting"] == {"sample_rate":32000,"bitrate":128000,"format":"mp3","channel":1}
    assert body["language_boost"] == "English"
    assert result.audio_bytes == b"ID3-audio" and result.duration_ms == 1234
    assert "secret-key-value" not in caplog.text


@pytest.mark.parametrize("status,category", [(401,"invalid_key"),(402,"quota"),(429,"rate_limit"),(500,"server")])
def test_minimax_http_error_categories(status, category) -> None:
    def opener(*_args, **_kwargs): raise urllib.error.HTTPError("url", status, "", {}, None)
    with pytest.raises(TTSProviderError) as caught:
        MiniMaxTTSProvider("key", opener=opener).synthesize(TTSRequest(text="Hello"))
    assert caught.value.category == category


def test_invalid_audio_response_and_cancel() -> None:
    provider = MiniMaxTTSProvider("key", opener=lambda *_args, **_kwargs: Response({"base_resp":{"status_code":0},"data":{"audio":"bad-hex"}}))
    with pytest.raises(TTSProviderError, match="解析"):
        provider.synthesize(TTSRequest(text="Hello"))
    event = threading.Event(); event.set()
    with pytest.raises(TTSProviderError) as caught:
        provider.synthesize(TTSRequest(text="Hello"), cancel_event=event)
    assert caught.value.category == "cancelled"


def test_cache_key_varies_by_generation_parameters(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        base = TTSRequest(text="Hello")
        keys = {
            context.tts_service.cache_key(base),
            context.tts_service.cache_key(TTSRequest(text="Hello", speed=0.8)),
            context.tts_service.cache_key(TTSRequest(text="Hello", voice_id="English_radiant_girl")),
            context.tts_service.cache_key(TTSRequest(text="Hello", model="speech-2.8-turbo")),
        }
        assert len(keys) == 4
    finally: context.database.close()


def test_cache_hit_corruption_stats_and_clear(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    provider = FakeProvider(); request = TTSRequest(text="Cache me.")
    try:
        first = context.tts_service.get_or_generate(provider, request)
        second = context.tts_service.get_or_generate(provider, request)
        assert first.file_path == second.file_path and provider.calls == 1
        assert context.tts_service.stats().file_count == 1
        assert context.tts_service.stats().total_size_bytes == len(b"ID3-fake-audio")
        first.file_path.write_bytes(b"")
        context.tts_service.get_or_generate(provider, request)
        assert provider.calls == 2
        context.tts_service.clear_cache()
        assert context.tts_service.stats().file_count == 0
        assert context.database.connect().execute("SELECT COUNT(*) FROM tts_audio_cache").fetchone()[0] == 0
    finally: context.database.close()


def test_retry_policy_and_nonretryable_error(tmp_path: Path, monkeypatch) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    monkeypatch.setattr("english_typing_trainer.services.tts_service.time.sleep", lambda _delay: None)
    try:
        retrying = FakeProvider(failures=2, category="network")
        context.tts_service.get_or_generate(retrying, TTSRequest(text="Retry."))
        assert retrying.calls == 3
        invalid = FakeProvider(failures=3, category="invalid_key")
        with pytest.raises(TTSProviderError): context.tts_service.get_or_generate(invalid, TTSRequest(text="No retry."))
        assert invalid.calls == 1
    finally: context.database.close()


def test_concurrent_requests_are_deduplicated(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    provider = FakeProvider(); request = TTSRequest(text="Concurrent.")
    results=[]
    try:
        threads=[threading.Thread(target=lambda: results.append(context.tts_service.get_or_generate(provider, request))) for _ in range(4)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        assert len(results) == 4 and provider.calls == 1
    finally: context.database.close()


def test_schema5_cache_table_defaults_and_v4_backup(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "new")
    try:
        assert context.database.get_schema_version() == 11
        columns={row[1] for row in context.database.connect().execute("PRAGMA table_info(tts_audio_cache)")}
        assert {"cache_key","voice_id","file_path","size_bytes","status"} <= columns
        assert context.settings_service.get_settings().tts_model == "speech-2.8-hd"
        assert context.paths.audio_cache_dir.is_dir()
    finally: context.database.close()

    legacy_dir=tmp_path / "legacy"; legacy_dir.mkdir()
    from english_typing_trainer.database.manager import DatabaseManager
    from english_typing_trainer.database.migrations import MigrationRunner
    import sqlite3
    db=legacy_dir / "typing_trainer.db"; connection=sqlite3.connect(db); runner=MigrationRunner()
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner._apply_version_1(connection); runner._apply_version_2(connection); runner._apply_version_3(connection); runner._apply_version_4(connection); connection.commit(); connection.close()
    manager=DatabaseManager(db); manager.initialize()
    try:
        assert manager.get_schema_version() == 11
        backups=list((legacy_dir / "backups").glob("typing_trainer-v4-before-v11-*.db"))
        assert len(backups) == 1
    finally: manager.close()


def test_v5_migration_failure_rolls_back_to_v4(tmp_path: Path, monkeypatch) -> None:
    import sqlite3
    from english_typing_trainer.database.migrations import MigrationRunner
    db=tmp_path / "rollback.db"; connection=sqlite3.connect(db); runner=MigrationRunner()
    connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner._apply_version_1(connection); runner._apply_version_2(connection); runner._apply_version_3(connection); runner._apply_version_4(connection); connection.commit()
    def broken(conn): conn.execute("CREATE TABLE partial_tts(id INTEGER)"); raise RuntimeError("v5 failed")
    monkeypatch.setattr(runner,"_apply_version_5",broken)
    with pytest.raises(RuntimeError): runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 4
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='partial_tts'").fetchone() is None
    connection.close()
