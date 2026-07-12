from __future__ import annotations

from dataclasses import dataclass
from threading import Lock

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.sentence_repositories import TranslationCacheRepository
from english_typing_trainer.models.sentence import ArticleSentence, SentenceTranslation
from english_typing_trainer.services.translation_provider import PROMPT_VERSION, TranslationProvider, TranslationProviderError, TranslationResult


@dataclass(slots=True)
class TranslationDecision:
    cached: SentenceTranslation | None
    should_request: bool


class TranslationService:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database
        self._cache = TranslationCacheRepository(database.connect)
        self._inflight: set[str] = set()
        self._lock = Lock()

    def prepare(self, sentence: ArticleSentence, *, provider: str, model: str, prompt_version: str = PROMPT_VERSION, retry: bool = False) -> TranslationDecision:
        cached = self._cache.get(sentence.sentence_hash)
        if cached and (cached.status == "completed" or cached.is_user_edited) and not retry:
            return TranslationDecision(cached, False)
        with self._lock:
            if sentence.sentence_hash in self._inflight:
                return TranslationDecision(cached, False)
            claimed = False
            with self._database.transaction() as connection:
                if cached and retry:
                    claimed = self._cache.mark_pending_for_retry(connection, sentence.sentence_hash)
                elif cached is None:
                    claimed = self._cache.claim_pending(
                        connection,
                        sentence_hash=sentence.sentence_hash,
                        source_text=sentence.normalized_text,
                        provider=provider,
                        model=model,
                        prompt_version=prompt_version,
                    )
            if claimed:
                self._inflight.add(sentence.sentence_hash)
            return TranslationDecision(self._cache.get(sentence.sentence_hash), claimed)

    def request(self, provider: TranslationProvider, sentence: ArticleSentence, *, previous: str = "", following: str = "", cancel_event=None) -> TranslationResult:
        return provider.translate(sentence.normalized_text, previous=previous, following=following, cancel_event=cancel_event)

    def complete(self, sentence_hash: str, result: TranslationResult, *, provider: str, model: str, prompt_version: str = PROMPT_VERSION) -> SentenceTranslation | None:
        try:
            with self._database.transaction() as connection:
                self._cache.complete(connection, sentence_hash, result.translation, result.key_expressions, provider, model, prompt_version)
            return self._cache.get(sentence_hash)
        finally:
            with self._lock:
                self._inflight.discard(sentence_hash)

    def fail(self, sentence_hash: str, error: TranslationProviderError) -> SentenceTranslation | None:
        try:
            with self._database.transaction() as connection:
                self._cache.fail(connection, sentence_hash, error.category)
            return self._cache.get(sentence_hash)
        finally:
            with self._lock:
                self._inflight.discard(sentence_hash)

    def edit(self, sentence_hash: str, translation: str, expressions: list[dict[str, str]]) -> SentenceTranslation | None:
        with self._database.transaction() as connection:
            self._cache.edit(connection, sentence_hash, translation, expressions)
        return self._cache.get(sentence_hash)

    def get(self, sentence_hash: str) -> SentenceTranslation | None:
        return self._cache.get(sentence_hash)
