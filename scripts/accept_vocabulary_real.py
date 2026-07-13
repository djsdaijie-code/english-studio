from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.models.tts import TTSRequest
from english_typing_trainer.services.credential_store import WindowsCredentialStore
from english_typing_trainer.services.dictionary_provider import FreeDictionaryProvider
from english_typing_trainer.services.dictionary_provider import DictionaryProviderError
from english_typing_trainer.services.tts_provider import MiniMaxTTSProvider
from english_typing_trainer.services.word_explanation_provider import DeepSeekWordExplanationProvider


def verify_playback(path: Path) -> bool:
    from PySide6.QtWidgets import QApplication
    from english_typing_trainer.services.audio_playback import AudioPlaybackService
    app=QApplication.instance() or QApplication([]); player=AudioPlaybackService(); states=[]; player.state_changed.connect(states.append)
    player.toggle(path); deadline=time.monotonic()+5
    while time.monotonic()<deadline and "playing" not in states:
        app.processEvents(); time.sleep(0.02)
    player.stop(); app.processEvents(); return "playing" in states


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("--data-dir",type=Path,required=True); args=parser.parse_args()
    context=build_app_context(data_dir=args.data_dir)
    try:
        dictionary_provider=FreeDictionaryProvider()
        results={}
        for word in ("English","learn","communicate","record","present","learning","friends","don't","I'm"):
            try:
                item=dictionary_provider.lookup(word); results[word]={"word":item.word,"phonetic":bool(item.phonetic),"audio":bool(item.audio_url),"parts":sorted({str(d.get('part_of_speech','')) for d in item.definitions}),"definitions":len(item.definitions)}
            except DictionaryProviderError as exc: results[word]={"status":exc.category}
        print("FREE_DICTIONARY_MATRIX="+json.dumps(results,ensure_ascii=True,sort_keys=True))
        dictionary=dictionary_provider.lookup("communication")
        print(f"FREE_DICTIONARY_OK word={dictionary.word} phonetic={bool(dictionary.phonetic)} audio={bool(dictionary.audio_url)} definitions={len(dictionary.definitions)}")
        if dictionary.audio_url:
            audio=context.dictionary_audio_service.get_or_download(dictionary.audio_url,dictionary.word)
            cached=context.dictionary_audio_service.get_or_download(dictionary.audio_url,dictionary.word)
            print(f"DICTIONARY_AUDIO_OK format={audio.audio_format} bytes={audio.size_bytes} cache_reused={audio.file_path==cached.file_path} playback={verify_playback(audio.file_path)}")
        try: dictionary_provider.lookup("zzzznotarealwordzzzz")
        except DictionaryProviderError as exc: print(f"FREE_DICTIONARY_NOT_FOUND_OK category={exc.category}")

        deepseek_key=WindowsCredentialStore().get()
        if deepseek_key:
            settings=context.settings_service.get_settings()
            class CountingDeepSeek(DeepSeekWordExplanationProvider):
                calls=0
                def explain(self,**kwargs): type(self).calls+=1; return super().explain(**kwargs)
            provider=CountingDeepSeek(deepseek_key,model=settings.translation_model)
            explanations=[]
            for word,sentence in (("run","I can run the program locally."),("run","I run every morning."),("communication","Clear communication helps teams work together.")):
                start=sentence.index(word); collected=context.vocabulary_learning_service.collect(word,sentence=sentence,start_offset=start,end_offset=start+len(word))
                if collected.entry.dictionary_status=="pending":
                    lookup=dictionary_provider.lookup(collected.entry.normalized_word)
                    context.vocabulary_learning_service.apply_dictionary_result(collected.entry.id,lookup)
                explanation=context.vocabulary_learning_service.explain_context(collected.context.id,provider)
                context.vocabulary_learning_service.explain_context(collected.context.id,provider)
                explanations.append({"word":word,"sentence":sentence,"meaning":explanation.contextual_meaning_zh,"pos":explanation.contextual_part_of_speech})
            print("DEEPSEEK_WORD_CONTEXTS="+json.dumps(explanations,ensure_ascii=True))
            print(f"DEEPSEEK_CACHE_OK provider_calls_this_run={provider.calls}")
        else: print("DEEPSEEK_WORD_SKIPPED no_credential")

        minimax_key=WindowsCredentialStore("English Studio/MiniMax TTS","MiniMax TTS").get()
        if minimax_key:
            settings=context.settings_service.get_settings()
            class CountingMiniMax(MiniMaxTTSProvider):
                calls=0
                def synthesize(self,*args,**kwargs): type(self).calls+=1; return super().synthesize(*args,**kwargs)
            provider=CountingMiniMax(minimax_key)
            request=TTSRequest(text="codexophone",content_type="word",model=settings.tts_model,voice_id=settings.tts_voice_id,speed=settings.tts_speed)
            audio=context.pronunciation_service.get_word_audio(provider,"codexophone",request_template=request)
            cached=context.pronunciation_service.get_word_audio(provider,"codexophone",request_template=request)
            sentence_request=TTSRequest(text="I can run the program locally.",content_type="sentence",model=settings.tts_model,voice_id=settings.tts_voice_id,speed=settings.tts_speed)
            sentence_audio=context.pronunciation_service.get_sentence_audio(provider,sentence_request)
            sentence_cached=context.pronunciation_service.get_sentence_audio(provider,sentence_request)
            print(f"MINIMAX_WORD_FALLBACK_OK format={audio.audio_format} bytes={audio.size_bytes} cache_reused={audio.file_path==cached.file_path} playback={verify_playback(audio.file_path)}")
            print(f"MINIMAX_SENTENCE_CACHE_OK cache_reused={sentence_audio.file_path==sentence_cached.file_path} provider_calls_this_run={provider.calls} playback={verify_playback(sentence_audio.file_path)}")
        else: print("MINIMAX_WORD_FALLBACK_SKIPPED no_credential")
    finally: context.database.close()


if __name__=="__main__": main()
