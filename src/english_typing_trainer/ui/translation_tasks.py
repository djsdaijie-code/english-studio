from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class TranslationWorkerSignals(QObject):
    completed = Signal(object, object)
    failed = Signal(object, object)


class TranslationWorker(QRunnable):
    def __init__(self, service, provider, sentence, *, previous: str = "", following: str = "", cancel_event=None) -> None:
        super().__init__()
        self.service = service
        self.provider = provider
        self.sentence = sentence
        self.previous = previous
        self.following = following
        self.cancel_event = cancel_event
        self.signals = TranslationWorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.request(
                self.provider,
                self.sentence,
                previous=self.previous,
                following=self.following,
                cancel_event=self.cancel_event,
            )
            self.signals.completed.emit(self.sentence, result)
        except Exception as exc:
            self.signals.failed.emit(self.sentence, exc)