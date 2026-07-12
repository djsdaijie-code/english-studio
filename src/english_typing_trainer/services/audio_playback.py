from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer


class AudioPlaybackService(QObject):
    state_changed = Signal(str)
    playback_failed = Signal(str)

    def __init__(self, parent: QObject | None = None, *, player=None, audio_output=None) -> None:
        super().__init__(parent)
        self.audio_output = audio_output or QAudioOutput(self)
        self.player = player or QMediaPlayer(self)
        if hasattr(self.player, "setAudioOutput"):
            self.player.setAudioOutput(self.audio_output)
        self.current_path: Path | None = None
        self.player.playbackStateChanged.connect(self._on_state)
        self.player.errorOccurred.connect(lambda _error, message: self.playback_failed.emit(message or "音频播放失败。"))

    def toggle(self, path: Path) -> None:
        if self.current_path == path and self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
            return
        if self.current_path == path and self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self.resume()
            return
        self.stop()
        self.current_path = path
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.player.play()

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
