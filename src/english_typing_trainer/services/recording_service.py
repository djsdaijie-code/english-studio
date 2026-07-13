from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioInput, QMediaCaptureSession, QMediaDevices, QMediaRecorder


class RecordingService(QObject):
    state_changed=Signal(str); failed=Signal(str)
    def __init__(self, directory: Path, parent=None) -> None:
        super().__init__(parent); self.directory=directory; self.directory.mkdir(parents=True,exist_ok=True); self.session=None; self.recorder=None; self.path:Path|None=None

    def start(self) -> Path | None:
        if self.recorder is not None: return self.path
        if QMediaDevices.defaultAudioInput().isNull(): self.failed.emit("未检测到可用麦克风。"); return None
        self.path=self.directory / f"pronunciation-{datetime.now():%Y%m%d-%H%M%S-%f}.m4a"
        self.session=QMediaCaptureSession(self); self.session.setAudioInput(QAudioInput(self)); self.recorder=QMediaRecorder(self); self.session.setRecorder(self.recorder); self.recorder.setOutputLocation(QUrl.fromLocalFile(str(self.path))); self.recorder.record(); self.state_changed.emit("recording"); return self.path

    def stop(self) -> Path | None:
        if self.recorder is None:return None
        self.recorder.stop(); path=self.path; self.recorder=None; self.session=None; self.state_changed.emit("recorded"); return path

    def cancel(self) -> None:
        path=self.stop()
        if path:path.unlink(missing_ok=True)
        self.path=None; self.state_changed.emit("cancelled")
