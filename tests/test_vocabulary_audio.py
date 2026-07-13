from __future__ import annotations

from pathlib import Path

import pytest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.dictionary_audio import DictionaryAudioError, DictionaryAudioService


class Response:
    def __init__(self,data:bytes,content_type="audio/mpeg"): self.data=data; self.headers={"Content-Type":content_type}
    def __enter__(self): return self
    def __exit__(self,*_args): return False
    def read(self,*_args): return self.data


def test_dictionary_audio_download_cache_and_offline_reuse(tmp_path:Path):
    context=build_app_context(data_dir=tmp_path/"data"); calls=[]
    service=DictionaryAudioService(context.database,context.paths.audio_cache_dir,opener=lambda *_a,**_k:(calls.append(1) or Response(b"ID3audio")))
    try:
        first=service.get_or_download("//audio.example/word.mp3","word")
        second=service.get_or_download("https://audio.example/word.mp3","word")
        assert first.file_path==second.file_path and first.file_path.read_bytes()==b"ID3audio" and len(calls)==1
        row=context.database.connect().execute("SELECT source_type,content_type FROM tts_audio_cache WHERE cache_key=?",(first.cache_key,)).fetchone()
        assert tuple(row)==("dictionary","word")
    finally:context.database.close()


@pytest.mark.parametrize("url,ctype,data",[("http://bad/audio.mp3","audio/mpeg",b"x"),("https://bad/text","text/html",b"html"),("https://bad/empty","audio/mpeg",b"")])
def test_dictionary_audio_rejects_unsafe_or_invalid(tmp_path:Path,url,ctype,data):
    context=build_app_context(data_dir=tmp_path/"data"); service=DictionaryAudioService(context.database,context.paths.audio_cache_dir,opener=lambda *_a,**_k:Response(data,ctype))
    try:
        with pytest.raises(DictionaryAudioError): service.get_or_download(url,"word")
    finally:context.database.close()
