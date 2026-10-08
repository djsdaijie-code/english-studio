from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, QTimer, Signal

from english_typing_trainer.services.reading_service import ReadingService
from english_typing_trainer.services.translation_provider import DeepSeekTranslationProvider, TranslationProviderError
from english_typing_trainer.ui.translation_tasks import TranslationWorker


class ReadingController(QObject):
    cache_updated = Signal(str)
    network_waiting = Signal()

    def __init__(self, context, page, thread_pool, settings_provider, parent=None) -> None:
        super().__init__(parent)
        self.context = context
        self.page = page
        self.pool = thread_pool
        self.settings_provider = settings_provider
        self.service = ReadingService(context)
        self.workers: set[TranslationWorker] = set()
        self._closing = False
        self.provider_factory = self._provider
        page.sentence_requested.connect(self._sentence_changed)
        page.translation_requested.connect(self.request_translation)
        self._cache_timer = QTimer(self)
        self._cache_timer.setInterval(500)
        self._cache_timer.timeout.connect(self._refresh_pending)
        self._cache_timer.start()

    def _provider(self):
        settings = self.settings_provider()
        return DeepSeekTranslationProvider(
            self.context.credential_store.get() or "", model=settings.translation_model, timeout=10.0
        )

    def open_article(self, article_id: int) -> None:
        material = self.service.load(article_id)
        self.page.speech_controls.set_speed(self.settings_provider().tts_speed)
        self.page.next_button.setEnabled(not material.completed)
        self.page.load(material)

    def _sentence_changed(self) -> None:
        if self.page.material:
            self.service.save_position(self.page.material)
        self.request_translation()

    def request_translation(self, retry: bool = False) -> None:
        sentence = self.page.current_sentence
        if sentence is None or self._closing:
            return
        cached = self.context.translation_service.get(sentence.sentence_hash)
        if cached and cached.status == "pending":
            self.context.translation_service.recover_interrupted(sentence.sentence_hash)
            cached = self.context.translation_service.get(sentence.sentence_hash)
        if cached and (cached.status == "completed" or cached.is_user_edited) and not retry:
            self.page.show_translation(cached)
            self.page.learning_activity.emit("meaning_revealed")
            return
        if cached and cached.status == "failed" and not retry:
            self.page.show_status("获取讲解失败，请点击重试。")
            return
        try:
            provider = self.provider_factory()
        except Exception as exc:
            message = str(exc) if isinstance(exc, TranslationProviderError) else "无法读取 DeepSeek 配置，请在设置中检查。"
            self.page.show_status(message)
            return
        settings = self.settings_provider()
        decision = self.context.translation_service.prepare(
            sentence, provider=provider.name, model=provider.model,
            prompt_version=settings.translation_prompt_version, retry=retry,
        )
        if not decision.should_request:
            self.page.show_status("本句讲解正在获取，请稍候……", loading=True)
            self.network_waiting.emit()
            return
        material = self.page.material
        index = material.index
        cancel_event = Event()
        worker = TranslationWorker(
            self.context.translation_service, provider, sentence,
            previous=material.sentences[index - 1].normalized_text if index else "",
            following=material.sentences[index + 1].normalized_text if index + 1 < len(material.sentences) else "",
            cancel_event=cancel_event,
        )
        self.workers.add(worker)
        worker.signals.completed.connect(lambda item, result, w=worker: self._completed(item, result, w))
        worker.signals.failed.connect(lambda item, error, w=worker: self._failed(item, error, w))
        self.page.show_status("正在理解这一句，请稍候……", loading=True)
        self.network_waiting.emit()
        self.pool.start(worker)

    def _completed(self, sentence, result, worker) -> None:
        self.workers.discard(worker)
        if self._closing:
            return
        self.context.translation_service.complete(
            sentence.sentence_hash, result, provider=worker.provider.name,
            model=worker.provider.model, prompt_version=self.settings_provider().translation_prompt_version,
        )
        self.refresh_cache(sentence.sentence_hash)
        self.cache_updated.emit(sentence.sentence_hash)

    def _failed(self, sentence, error, worker) -> None:
        self.workers.discard(worker)
        if self._closing:
            return
        safe_error = error if isinstance(error, TranslationProviderError) else TranslationProviderError("unknown", "翻译请求失败，请稍后重试。")
        self.context.translation_service.fail(sentence.sentence_hash, safe_error)
        if self._is_current(sentence.sentence_hash):
            self.page.show_status(str(safe_error))

    def _is_current(self, sentence_hash: str) -> bool:
        current = self.page.current_sentence
        return bool(current and current.sentence_hash == sentence_hash and self.page.reader.isVisible())

    def refresh_cache(self, sentence_hash: str) -> None:
        if self._is_current(sentence_hash):
            cached = self.context.translation_service.get(sentence_hash)
            if cached and cached.status == "completed":
                self.page.show_translation(cached)
                self.page.learning_activity.emit("meaning_revealed")
            elif cached and cached.status == "failed":
                self.page.show_status("获取讲解失败，请点击重试。")

    def _refresh_pending(self) -> None:
        current = self.page.current_sentence
        if current and self.page.reader.isVisible() and not self.page.retry_button.isEnabled():
            self.refresh_cache(current.sentence_hash)

    def shutdown(self) -> None:
        self._closing = True
        self._cache_timer.stop()
        for worker in self.workers:
            worker.cancel_event.set()
            self.context.translation_service.fail(
                worker.sentence.sentence_hash, TranslationProviderError("cancelled", "请求已取消。")
            )
