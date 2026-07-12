from __future__ import annotations

import io
import json
import logging
import urllib.error
from threading import Event

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.services.credential_store import MemoryCredentialStore, mask_api_key
from english_typing_trainer.services.translation_provider import DeepSeekTranslationProvider, TranslationProviderError, TranslationResult, parse_translation_content
from english_typing_trainer.services.translation_service import TranslationService


def _sentence(sentence_hash: str = "same-hash", article_id: int = 1) -> ArticleSentence:
    return ArticleSentence(id=article_id, article_id=article_id, section_id=article_id, sentence_index=0, text="Hello world.", normalized_text="Hello world.", sentence_hash=sentence_hash, start_offset=0, end_offset=12)


def test_translation_json_parser_accepts_json_and_code_fence() -> None:
    raw = '{"translation":"你好，世界。","key_expressions":[{"expression":"hello world","meaning":"你好，世界"}]}'
    result = parse_translation_content(raw)
    fenced = parse_translation_content("```json\n" + raw + "\n```")
    assert result.translation == "你好，世界。"
    assert fenced.key_expressions[0]["expression"] == "hello world"


def test_translation_json_parser_rejects_invalid_payload() -> None:
    with pytest.raises(json.JSONDecodeError):
        parse_translation_content("not json")
    with pytest.raises(json.JSONDecodeError):
        parse_translation_content('{"key_expressions": []}')


def test_translation_cache_claim_deduplicates_and_reuses_across_articles(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        service = TranslationService(context.database)
        first = service.prepare(_sentence(article_id=1), provider="deepseek", model="deepseek-v4-flash")
        concurrent = service.prepare(_sentence(article_id=2), provider="deepseek", model="deepseek-v4-flash")
        assert first.should_request is True
        assert concurrent.should_request is False
        service.complete("same-hash", TranslationResult("你好，世界。", []), provider="deepseek", model="deepseek-v4-flash")
        cached = service.prepare(_sentence(article_id=2), provider="deepseek", model="deepseek-v4-flash")
        assert cached.should_request is False
        assert cached.cached.chinese_translation == "你好，世界。"
    finally:
        context.database.close()


def test_failed_translation_can_retry_without_duplicate_row(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        service = TranslationService(context.database)
        sentence = _sentence("failed-hash")
        assert service.prepare(sentence, provider="deepseek", model="deepseek-v4-flash").should_request
        service.fail(sentence.sentence_hash, TranslationProviderError("timeout", "timeout"))
        assert service.get(sentence.sentence_hash).status == "failed"
        assert service.prepare(sentence, provider="deepseek", model="deepseek-v4-flash", retry=True).should_request
        count = context.database.connect().execute("SELECT COUNT(*) FROM sentence_translations WHERE sentence_hash = ?", (sentence.sentence_hash,)).fetchone()[0]
        assert count == 1
    finally:
        context.database.close()


def test_user_edited_translation_is_not_overwritten(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        service = TranslationService(context.database)
        sentence = _sentence("edited-hash")
        service.prepare(sentence, provider="deepseek", model="deepseek-v4-flash")
        service.complete(sentence.sentence_hash, TranslationResult("AI 翻译", []), provider="deepseek", model="deepseek-v4-flash")
        service.edit(sentence.sentence_hash, "人工翻译", [{"expression": "Hello", "meaning": "你好"}])
        service.complete(sentence.sentence_hash, TranslationResult("新 AI 翻译", []), provider="deepseek", model="deepseek-v4-flash")
        cached = service.get(sentence.sentence_hash)
        assert cached.chinese_translation == "人工翻译"
        assert cached.is_user_edited is True
    finally:
        context.database.close()


def test_user_can_explicitly_regenerate_ai_translation(tmp_path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        service = TranslationService(context.database)
        sentence = _sentence("regenerate-hash")
        assert service.prepare(sentence, provider="deepseek", model="deepseek-v4-flash").should_request
        service.complete(sentence.sentence_hash, TranslationResult("AI 初稿", []), provider="deepseek", model="deepseek-v4-flash")
        service.edit(sentence.sentence_hash, "人工翻译", [])

        decision = service.prepare(sentence, provider="deepseek", model="deepseek-v4-flash", retry=True)
        assert decision.should_request
        service.complete(sentence.sentence_hash, TranslationResult("AI 新稿", []), provider="deepseek", model="deepseek-v4-flash")
        cached = service.get(sentence.sentence_hash)
        assert cached.chinese_translation == "AI 新稿"
        assert cached.is_user_edited is False
    finally:
        context.database.close()


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def test_deepseek_provider_uses_current_model_and_does_not_log_key(caplog) -> None:
    captured = {}
    def opener(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"content": '{"translation":"你好。","key_expressions":[]}'}}]})
    key = "sk-secret-value-1234"
    provider = DeepSeekTranslationProvider(key, opener=opener)
    with caplog.at_level(logging.INFO):
        result = provider.translate("Hello.")
    payload = json.loads(captured["request"].data.decode("utf-8"))
    assert result.translation == "你好。"
    assert payload["model"] == "deepseek-v4-flash"
    assert payload["thinking"] == {"type": "disabled"}
    assert key not in caplog.text


@pytest.mark.parametrize("status,category", [(401, "invalid_key"), (402, "quota"), (429, "rate_limit"), (500, "server"), (503, "server")])
def test_deepseek_provider_maps_http_errors(status, category) -> None:
    def opener(request, timeout):
        raise urllib.error.HTTPError(request.full_url, status, "error", {}, io.BytesIO(b"{}"))
    provider = DeepSeekTranslationProvider("sk-fake", opener=opener)
    with pytest.raises(TranslationProviderError) as exc:
        provider.translate("Hello.")
    assert exc.value.category == category


def test_provider_cancellation_and_credential_mask() -> None:
    event = Event(); event.set()
    provider = DeepSeekTranslationProvider("sk-fake", opener=lambda *args, **kwargs: None)
    with pytest.raises(TranslationProviderError) as exc:
        provider.translate("Hello.", cancel_event=event)
    assert exc.value.category == "cancelled"
    store = MemoryCredentialStore()
    store.set("sk-secret-abcd")
    assert store.get() == "sk-secret-abcd"
    assert mask_api_key(store.get()) == "sk-****abcd"
    store.delete()
    assert mask_api_key(store.get()) == "未保存"
