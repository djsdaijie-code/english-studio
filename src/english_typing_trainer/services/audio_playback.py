from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaDevices, QMediaPlayer


class AudioPlaybackService(QObject):
    state_changed = Signal(str)
    playback_failed = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        player=None,
        audio_output=None,
        output_available=None,
    ) -> None:
        super().__init__(parent)
        custom_transport = player is not None or audio_output is not None
        self.audio_output = audio_output or QAudioOutput(self)
        self.player = player or QMediaPlayer(self)
        self._output_available = output_available or (
            (lambda: True)
            if custom_transport
            else (lambda: not QMediaDevices.defaultAudioOutput().isNull())
        )
        if hasattr(self.player, "setAudioOutput"):
            self.player.setAudioOutput(self.audio_output)
        self.current_path: Path | None = None
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.errorOccurred.connect(lambda _error, message: self.playback_failed.emit(message or "音频播放失败。"))

    def toggle(self, path: Path) -> None:
        try:
            valid_file = path.is_file() and path.stat().st_size > 0
        except OSError:
            valid_file = False
        if not valid_file:
            self.playback_failed.emit("音频文件缺失或损坏，请重新生成。")
            return
        try:
            output_available = self._output_available()
        except Exception:
            self.playback_failed.emit("无法检查音频播放设备，请稍后重试。")
            return
        if not output_available:
            self.playback_failed.emit("未检测到可用的音频播放设备。")
            return
        if self.current_path == path and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
            return
        if self.current_path == path and self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self.resume()
            return
        try:
            self.stop()
            self.current_path = path
            self.player.setSource(QUrl.fromLocalFile(str(path)))
            self.player.play()
        except Exception:
            self.current_path = None
            self.playback_failed.emit("无法启动音频播放，请检查设备状态。")

    def pause(self) -> None:
        self.player.pause()

    def resume(self) -> None:
        self.player.play()

    def stop(self) -> None:
        self.player.stop()
        self.current_path = None

    def is_playing(self) -> bool:
        return self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def _on_state(self, state) -> None:
        labels = {
            QMediaPlayer.PlaybackState.PlayingState: "playing",
            QMediaPlayer.PlaybackState.PausedState: "paused",
            QMediaPlayer.PlaybackState.StoppedState: "stopped",
        }
        self.state_changed.emit(labels.get(state, "stopped"))
