from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication, QMessageBox

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.audio_playback import AudioPlaybackService
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme


def _app(): return QApplication.instance() or QApplication([])


def _window(tmp_path: Path):
    app=_app(); deep=MemoryCredentialStore(); tts=MemoryCredentialStore()
    context=build_app_context(data_dir=tmp_path/"data",credential_store=deep,tts_credential_store=tts)
    source=tmp_path/"speech.txt"; source.write_text("First spoken sentence. Second spoken sentence.",encoding="utf-8")
    article=context.article_library.import_txt_file(source,500).article
    window=MainWindow(context); window.show(); app.processEvents()
    return app,context,window,article,tts


def _close(context,window): window.current_practice_saved=True; window.close(); context.database.close()


def test_settings_exposes_minimax_controls_and_key_management(tmp_path: Path, monkeypatch) -> None:
    app,context,window,_article,store=_window(tmp_path)
    monkeypatch.setattr(QMessageBox,"information",lambda *_args,**_kwargs: QMessageBox.StandardButton.Ok)
    try:
        window._show_settings(); app.processEvents()
        page=window.settings_page
        assert page.tts_model_combo.currentData()=="speech-2.8-hd"
        assert page.tts_voice_combo.count() >= 3
        assert page.tts_speed_combo.currentData()==1.0
        page.tts_api_key_input.setText("minimax-secret-1234"); window._save_tts_key()
        assert store.get()=="minimax-secret-1234"
        assert "1234" in page.tts_api_key_status.text() and "minimax-secret" not in page.tts_api_key_status.text()
        window._delete_tts_key(); assert store.get() is None
        settings=page.build_settings(); assert settings.tts_model=="speech-2.8-hd" and settings.tts_auto_play is False
    finally: _close(context,window)


def test_sentence_and_continuous_views_emit_current_sentence_without_autoplay(tmp_path: Path) -> None:
    app,context,window,article,_store=_window(tmp_path)
    requests=[]
    try:
        material=context.practice_service.load_practice_material(article.id)
        window._begin_practice(material); app.processEvents()
        view=window.sentence_practice_view
        view.speech_requested.connect(lambda text,speed,_controls: requests.append((text,speed)))
        assert view.speech_controls.isVisible() and not window.audio_playback.is_playing()
        view.speech_controls.play_button.click(); app.processEvents()
        assert requests and requests[-1][0].startswith("First spoken")

        window.current_practice_saved=True; window._show_library(); window.practice_mode_control.button("continuous").click(); window.continue_button.click(); app.processEvents()
        continuous=window.practice_view; continuous.speech_requested.connect(lambda text,speed,_controls: requests.append((text,speed)))
        assert continuous.speech_controls.isVisible() and not window.audio_playback.is_playing()
        continuous.speech_controls.play_button.click(); app.processEvents()
        assert requests[-1][0].startswith("First spoken")
        assert continuous.input_edit.hasFocus()
        for theme in ("light","dark"):
            apply_theme(window,theme); window.resize(1280 if theme=="light" else 1920,720 if theme=="light" else 1080); app.processEvents(); assert continuous.speech_controls.play_button.icon().isNull() is False
    finally: _close(context,window)


class FakePlayer(QObject):
    playbackStateChanged=Signal(object); errorOccurred=Signal(object,str)
    def __init__(self): super().__init__(); self.state=QMediaPlayer.PlaybackState.StoppedState; self.source=None
    def setAudioOutput(self,_output): pass
    def setSource(self,source): self.source=source
    def playbackState(self): return self.state
    def play(self): self.state=QMediaPlayer.PlaybackState.PlayingState; self.playbackStateChanged.emit(self.state)
    def pause(self): self.state=QMediaPlayer.PlaybackState.PausedState; self.playbackStateChanged.emit(self.state)
    def stop(self): self.state=QMediaPlayer.PlaybackState.StoppedState; self.playbackStateChanged.emit(self.state)


def test_audio_playback_play_pause_resume_stop(tmp_path: Path) -> None:
    player=FakePlayer(); service=AudioPlaybackService(player=player)
    path=tmp_path/"audio.mp3"; path.write_bytes(b"audio")
    service.toggle(path); assert service.is_playing()
    service.toggle(path); assert player.state==QMediaPlayer.PlaybackState.PausedState
    service.toggle(path); assert service.is_playing()
    service.stop(); assert not service.is_playing() and service.current_path is None
