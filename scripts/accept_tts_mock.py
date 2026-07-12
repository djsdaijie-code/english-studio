from __future__ import annotations

import argparse
import io
import os
import sys
import time
import wave
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/"src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.models.tts import TTSAudioResult
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme
import english_typing_trainer.ui.main_window as main_window_module


def wav_bytes() -> bytes:
    output=io.BytesIO()
    with wave.open(output,"wb") as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(32000); audio.writeframes(b"\0\0"*96000)
    return output.getvalue()


class MockMiniMaxProvider:
    name="minimax"; calls=0
    def __init__(self,key,**_kwargs):
        if not key: raise RuntimeError("尚未配置 MiniMax API Key。")
    def synthesize(self,request,*,cancel_event=None):
        type(self).calls += 1; time.sleep(0.25)
        return TTSAudioResult(wav_bytes(),"wav","minimax",request.model,request.voice_id,duration_ms=3000,usage_characters=len(request.text))


def key_event(char): return QKeyEvent(QKeyEvent.Type.KeyPress,0,Qt.KeyboardModifier.NoModifier,char)
def capture(widget,path,app): app.processEvents(); assert widget.grab().save(str(path))
def wait_for(predicate,app,timeout=5):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        app.processEvents()
        if predicate(): return
        time.sleep(0.02)
    raise RuntimeError("等待异步 TTS 超时")


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--data-dir",type=Path,required=True); parser.add_argument("--screenshots",type=Path,required=True); args=parser.parse_args()
    args.data_dir.mkdir(parents=True,exist_ok=True); args.screenshots.mkdir(parents=True,exist_ok=True)
    app=QApplication.instance() or QApplication([]); app.setCursorFlashTime(0)
    tts_store=MemoryCredentialStore("minimax-mock-key-1234")
    context=build_app_context(data_dir=args.data_dir,credential_store=MemoryCredentialStore(),tts_credential_store=tts_store)
    source=args.data_dir/"语音验收 sentence.txt"; source.write_text("Listening to a clear sentence can improve pronunciation. Cached audio plays without another request. Continuous typing remains focused.",encoding="utf-8")
    article=context.article_library.import_txt_file(source,500).article
    main_window_module.MiniMaxTTSProvider=MockMiniMaxProvider
    window=MainWindow(context); window.show()
    try:
        window._show_settings(); apply_theme(window,"light"); window.resize(1280,720); window.settings_page.set_tts_api_key_status("••••••••1234"); window.settings_page.scroll_area.ensureWidgetVisible(window.settings_page.tts_model_combo, 20, 20)
        capture(window,args.screenshots/"01-settings-speech-light-1280x720.png",app)

        window._show_library(); window.practice_mode_control.button("sentence").click(); window.continue_button.click(); app.processEvents()
        sentence=window.sentence_practice_view; capture(window,args.screenshots/"02-sentence-speech-button-light.png",app)
        sentence.speech_controls.play_button.click(); capture(window,args.screenshots/"03-tts-generating-light.png",app)
        wait_for(lambda: context.tts_service.stats().file_count==1 and not window._tts_workers and window.audio_playback.is_playing(),app)
        capture(window,args.screenshots/"04-tts-playing-light.png",app)
        calls=MockMiniMaxProvider.calls; sentence.speech_controls.play_button.click(); app.processEvents(); assert MockMiniMaxProvider.calls==calls

        first=sentence.current_sentence
        for char in first.text: sentence._handle_key(key_event(char))
        sentence._handle_key(QKeyEvent(QKeyEvent.Type.KeyPress,Qt.Key.Key_Return,Qt.KeyboardModifier.NoModifier,"\r")); app.processEvents()
        assert window.audio_playback.current_path is None

        window.current_practice_saved=True; window._show_library(); window.practice_mode_control.button("continuous").click(); window.continue_button.click(); app.processEvents()
        continuous=window.practice_view; capture(window,args.screenshots/"05-continuous-speech-button-light-1500x1000.png",app)
        continuous.speech_controls.play_button.click(); wait_for(lambda: context.tts_service.stats().file_count>=1,app)
        continuous._handle_input_event(key_event("L")); assert continuous.session.position==1

        apply_theme(window,"dark"); window.resize(1920,1080); capture(window,args.screenshots/"06-continuous-speech-dark-1920x1080.png",app)
        window.current_practice_saved=True; window._show_settings(); stats=context.tts_service.stats(); window.settings_page.set_tts_cache_stats(stats.file_count,stats.total_size_bytes); window.settings_page.scroll_area.ensureWidgetVisible(window.settings_page.tts_cache_label,20,20)
        capture(window,args.screenshots/"07-cache-info-dark.png",app)
        window._show_library(); window.practice_mode_control.button("sentence").click(); window.continue_button.click(); capture(window,args.screenshots/"08-sentence-speech-dark.png",app)
        window.current_practice_saved=True; window.close()
    finally: context.database.close()
    print(f"TTS_MOCK_ACCEPTANCE_OK provider_calls={MockMiniMaxProvider.calls}")
    print(f"DATA_DIR={args.data_dir.resolve()}"); print(f"SCREENSHOTS={args.screenshots.resolve()}")
    return 0
if __name__=="__main__": raise SystemExit(main())
