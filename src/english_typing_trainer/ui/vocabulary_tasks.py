from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal


class VocabularyTaskSignals(QObject):
    completed=Signal(object); failed=Signal(str)


class VocabularyTask(QRunnable):
    def __init__(self, operation) -> None:
        super().__init__(); self.operation=operation; self.signals=VocabularyTaskSignals()

    def run(self) -> None:
        try: self.signals.completed.emit(self.operation())
        except Exception as exc: self.signals.failed.emit(str(exc))
