from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, QRunnable, Signal


class TTSWorkerSignals(QObject):
    completed = Signal(object, object)
    failed = Signal(object, object)


class TTSWorker(QRunnable):
    def __init__(self, service, provider, request, content_ref=None) -> None:
        super().__init__(); self.service=service; self.provider=provider; self.request=request; self.content_ref=content_ref
        self.signals=TTSWorkerSignals(); self.cancel_event=Event(); self.setAutoDelete(False)

    def run(self) -> None:
        try:
            if self.content_ref is None:
                audio=self.service.get_or_generate(self.provider, self.request, cancel_event=self.cancel_event)
            else:
                audio=self.service.get_or_generate_course(
                    self.provider,
                    self.request,
                    self.content_ref,
                    cancel_event=self.cancel_event,
                )
            self.signals.completed.emit(self.request, audio)
        except Exception as exc:
            self.signals.failed.emit(self.request, exc)

    def cancel(self) -> None:
        self.cancel_event.set()
