from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import (
    QAudioInput,
    QMediaCaptureSession,
    QMediaDevices,
    QMediaRecorder,
)


class RecordingService(QObject):
    state_changed = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        directory: Path,
        parent: QObject | None = None,
        *,
        device_provider: Callable[[], object] | None = None,
    ) -> None:
        super().__init__(parent)
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._device_provider = device_provider or QMediaDevices.defaultAudioInput
        self.session: QMediaCaptureSession | None = None
        self.recorder: QMediaRecorder | None = None
        self.path: Path | None = None

    def start(self) -> Path | None:
        if self.recorder is not None:
            return self.path
        try:
            device = self._device_provider()
            if getattr(device, "isNull")():
                self.failed.emit("未检测到可用麦克风。")
                return None
            self.path = self.directory / (
                f"pronunciation-{datetime.now():%Y%m%d-%H%M%S-%f}.m4a"
            )
            self.session = QMediaCaptureSession(self)
            self.session.setAudioInput(QAudioInput(self))
            self.recorder = QMediaRecorder(self)
            self.recorder.errorOccurred.connect(self._recording_error)
            self.session.setRecorder(self.recorder)
            self.recorder.setOutputLocation(QUrl.fromLocalFile(str(self.path)))
            self.recorder.record()
        except Exception:
            self.recorder = None
            self.session = None
            self.path = None
            self.failed.emit("无法启动麦克风录音，请检查设备和系统权限。")
            return None
        self.state_changed.emit("recording")
        return self.path

    def stop(self) -> Path | None:
        if self.recorder is None:
            return None
        self.recorder.stop()
        path = self.path
        self.recorder = None
        self.session = None
        self.state_changed.emit("recorded")
        return path

    def cancel(self) -> None:
        path = self.stop()
        if path and not self._remove_file(path):
            self.failed.emit("临时录音无法清理，请稍后重试。")
        self.path = None
        self.state_changed.emit("cancelled")

    def _recording_error(self, _error, message: str) -> None:
        detail = message.strip() if message else "请检查麦克风权限和设备状态。"
        failed_path = self.path
        self.recorder = None
        self.session = None
        self.path = None
        if failed_path:
            self._remove_file(failed_path)
        self.failed.emit(f"麦克风录音失败：{detail}")
        self.state_changed.emit("error")

    @staticmethod
    def _remove_file(path: Path) -> bool:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return False
        return True


__all__ = ["RecordingService"]
