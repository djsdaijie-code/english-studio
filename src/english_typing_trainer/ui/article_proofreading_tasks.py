from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class ArticleProofreadingWorkerSignals(QObject):
    completed = Signal(int, object)
    failed = Signal(int, object)


class ArticleProofreadingWorker(QRunnable):
    def __init__(self, article_id: int, service, provider, text: str) -> None:
        super().__init__()
        self.article_id = article_id
        self.service = service
        self.provider = provider
        self.text = text
        self.cancel_event = Event()
        self.signals = ArticleProofreadingWorkerSignals()

    def cancel(self) -> None:
        self.cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.check(
                self.provider,
                self.text,
                cancel_event=self.cancel_event,
            )
            self.signals.completed.emit(self.article_id, result)
        except Exception as exc:
            self.signals.failed.emit(self.article_id, exc)
