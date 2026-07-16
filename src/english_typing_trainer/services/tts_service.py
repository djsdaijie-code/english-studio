from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from threading import Event, Lock

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.tts_repository import TTSAudioCacheRepository
from english_typing_trainer.models.tts import AudioCacheStats, CachedAudio, TTSRequest
from english_typing_trainer.models.learning_content import LearningContentRef
from english_typing_trainer.services.tts_provider import TTSProvider, TTSProviderError


class TTSService:
    def __init__(self, database: DatabaseManager, cache_dir: Path) -> None:
        self._database = database
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._repository = TTSAudioCacheRepository()
        self._lock = Lock()
        self._inflight: dict[str, Event] = {}

    @staticmethod
    def normalize_text(text: str) -> str:
        return text.replace("\r\n", "\n").replace("\r", "\n").strip()

    def cache_key(self, request: TTSRequest) -> str:
        payload = {
            "provider": request.provider, "model": request.model, "voice_id": request.voice_id,
            "speed": request.speed, "volume": request.volume, "pitch": request.pitch,
            "format": request.audio_format, "text": self.normalize_text(request.text),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

    def course_cache_key(
        self, content_ref: LearningContentRef, request: TTSRequest
    ) -> str:
        payload = {
            "source_type": content_ref.source_type,
            "item_stable_key": content_ref.item_stable_key,
            "content_version": content_ref.content_version,
            "provider": request.provider,
            "model": request.model,
            "voice_id": request.voice_id,
            "speed": request.speed,
            "volume": request.volume,
            "pitch": request.pitch,
            "format": request.audio_format,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

    def get_cached(self, request: TTSRequest) -> CachedAudio | None:
        return self._get_cached_by_key(self.cache_key(request))

    def get_cached_course(
        self, content_ref: LearningContentRef, request: TTSRequest
    ) -> CachedAudio | None:
        return self._get_cached_by_key(self.course_cache_key(content_ref, request))

    def _get_cached_by_key(self, key: str) -> CachedAudio | None:
        with self._database.independent_connection() as connection:
            row = self._repository.get(connection, key)
        if row is None:
            return None
        path = self.cache_dir / row["file_path"]
        if not path.is_file() or path.stat().st_size != row["size_bytes"] or path.stat().st_size <= 0:
            with self._database.independent_transaction() as connection:
                self._repository.delete(connection, key)
            path.unlink(missing_ok=True)
            return None
        return CachedAudio(key, path, row["audio_format"], row["size_bytes"], row["duration_ms"])

    def get_or_generate(self, provider: TTSProvider, request: TTSRequest, *, cancel_event: Event | None = None) -> CachedAudio:
        return self._get_or_generate(
            provider,
            request,
            key=self.cache_key(request),
            course_content=False,
            cancel_event=cancel_event,
        )

    def get_or_generate_course(
        self,
        provider: TTSProvider,
        request: TTSRequest,
        content_ref: LearningContentRef,
        *,
        cancel_event: Event | None = None,
    ) -> CachedAudio:
        return self._get_or_generate(
            provider,
            request,
            key=self.course_cache_key(content_ref, request),
            course_content=True,
            cancel_event=cancel_event,
        )

    def _get_or_generate(
        self,
        provider: TTSProvider,
        request: TTSRequest,
        *,
        key: str,
        course_content: bool,
        cancel_event: Event | None,
    ) -> CachedAudio:
        cached = self._get_cached_by_key(key)
        if cached:
            return cached
        with self._lock:
            event = self._inflight.get(key)
            owner = event is None
            if owner:
                event = Event()
                self._inflight[key] = event
        if not owner:
            while not event.wait(0.05):
                if cancel_event and cancel_event.is_set():
                    raise TTSProviderError("cancelled", "语音生成已取消。")
            cached = self._get_cached_by_key(key)
            if cached:
                return cached
            raise TTSProviderError("generation_failed", "语音生成未能完成。")
        try:
            result = self._generate_with_retry(provider, request, cancel_event)
            file_name = f"{key}.{result.audio_format}"
            destination = self.cache_dir / file_name
            temporary = self.cache_dir / f"{file_name}.tmp"
            try:
                temporary.write_bytes(result.audio_bytes)
                os.replace(temporary, destination)
            except OSError as exc:
                temporary.unlink(missing_ok=True)
                raise TTSProviderError("save_failed", "音频缓存保存失败。") from exc
            text_hash = hashlib.sha256(self.normalize_text(request.text).encode("utf-8")).hexdigest()
            with self._database.independent_transaction() as connection:
                complete = (
                    self._repository.complete_course
                    if course_content
                    else self._repository.complete
                )
                complete(
                    connection,
                    cache_key=key,
                    request=request,
                    text_hash=text_hash,
                    file_path=file_name,
                    duration_ms=result.duration_ms,
                    size_bytes=destination.stat().st_size,
                )
            return CachedAudio(key, destination, result.audio_format, destination.stat().st_size, result.duration_ms)
        finally:
            with self._lock:
                pending = self._inflight.pop(key, None)
                if pending:
                    pending.set()

    def _generate_with_retry(self, provider: TTSProvider, request: TTSRequest, cancel_event: Event | None):
        retryable = {"network", "timeout", "rate_limit", "server"}
        for attempt in range(3):
            if cancel_event and cancel_event.is_set():
                raise TTSProviderError("cancelled", "语音生成已取消。")
            try:
                return provider.synthesize(request, cancel_event=cancel_event)
            except TTSProviderError as exc:
                if exc.category not in retryable or attempt == 2:
                    raise
                delay = 0.2 * (2 ** attempt)
                if cancel_event and cancel_event.wait(delay):
                    raise TTSProviderError("cancelled", "语音生成已取消。")
                if not cancel_event:
                    time.sleep(delay)
        raise TTSProviderError("generation_failed", "语音生成失败。")

    def mark_played(self, cache_key: str) -> None:
        with self._database.independent_transaction() as connection:
            self._repository.mark_played(connection, cache_key)

    def stats(self) -> AudioCacheStats:
        files = [path for path in self.cache_dir.iterdir() if path.is_file() and not path.name.endswith(".tmp")]
        return AudioCacheStats(len(files), sum(path.stat().st_size for path in files))

    def clear_cache(self) -> None:
        for path in self.cache_dir.iterdir():
            if path.is_file():
                path.unlink(missing_ok=True)
        with self._database.independent_transaction() as connection:
            self._repository.clear(connection)


class PronunciationService:
    def __init__(self, tts_service: TTSService) -> None:
        self.tts_service = tts_service

    def get_sentence_audio(self, provider: TTSProvider, request: TTSRequest, *, cancel_event: Event | None = None) -> CachedAudio:
        return self.tts_service.get_or_generate(provider, request, cancel_event=cancel_event)

    def get_word_audio(self, provider: TTSProvider, word: str, *, context_sentence: str | None = None, request_template: TTSRequest | None = None, cancel_event: Event | None = None) -> CachedAudio:
        template = request_template or TTSRequest(text=word, content_type="word")
        request = TTSRequest(
            text=context_sentence or word, content_type="word", language=template.language,
            provider=template.provider, model=template.model, voice_id=template.voice_id,
            speed=template.speed, volume=template.volume, pitch=template.pitch,
            audio_format=template.audio_format, sample_rate=template.sample_rate,
            bitrate=template.bitrate, channel=template.channel, language_boost=template.language_boost,
        )
        return self.tts_service.get_or_generate(provider, request, cancel_event=cancel_event)
