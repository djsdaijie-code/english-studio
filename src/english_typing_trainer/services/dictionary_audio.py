from __future__ import annotations

import hashlib
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from threading import Lock

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.tts_repository import TTSAudioCacheRepository
from english_typing_trainer.models.tts import CachedAudio


class DictionaryAudioError(RuntimeError): pass


class DictionaryAudioService:
    def __init__(self, database: DatabaseManager, cache_dir: Path, *, opener=None, max_bytes: int = 5_000_000) -> None:
        self.database=database; self.cache_dir=cache_dir; self.opener=opener or urllib.request.urlopen
        self.max_bytes=max_bytes; self.repository=TTSAudioCacheRepository(); self._lock=Lock()

    @staticmethod
    def cache_key(url: str) -> str:
        return "dictionary-" + hashlib.sha256(url.encode("utf-8")).hexdigest()

    def get_cached(self, url: str) -> CachedAudio | None:
        key=self.cache_key(url)
        with self.database.independent_connection() as connection: row=self.repository.get(connection,key)
        if not row: return None
        path=self.cache_dir/row["file_path"]
        if not path.is_file() or path.stat().st_size != row["size_bytes"]:
            with self.database.independent_transaction() as connection: self.repository.delete(connection,key)
            path.unlink(missing_ok=True); return None
        return CachedAudio(key,path,row["audio_format"],row["size_bytes"],row["duration_ms"])

    def get_or_download(self, url: str, word: str, *, timeout: float = 12.0) -> CachedAudio:
        if url.startswith("//"): url="https:"+url
        if not url.lower().startswith("https://"): raise DictionaryAudioError("词典音频地址必须使用 HTTPS。")
        cached=self.get_cached(url)
        if cached: return cached
        key=self.cache_key(url)
        with self._lock:
            cached=self.get_cached(url)
            if cached: return cached
            request=urllib.request.Request(url,headers={"User-Agent":"EnglishTypingTrainer/0.2"})
            try:
                with self.opener(request,timeout=timeout) as response:
                    content_type=response.headers.get("Content-Type","").split(";",1)[0].lower()
                    if not (content_type.startswith("audio/") or content_type=="application/octet-stream"):
                        raise DictionaryAudioError("词典返回的不是有效音频。")
                    data=response.read(self.max_bytes+1)
            except (urllib.error.URLError,TimeoutError,socket.timeout) as exc:
                raise DictionaryAudioError("词典音频下载失败。") from exc
            if not data or len(data)>self.max_bytes: raise DictionaryAudioError("词典音频为空或超过大小限制。")
            fmt={"audio/mpeg":"mp3","audio/ogg":"ogg","audio/wav":"wav","audio/x-wav":"wav"}.get(content_type,"mp3")
            name=f"{key}.{fmt}"; target=self.cache_dir/name; temporary=self.cache_dir/(name+".tmp")
            temporary.write_bytes(data); os.replace(temporary,target)
            source_hash=hashlib.sha256(url.encode("utf-8")).hexdigest()
            with self.database.independent_transaction() as connection:
                self.repository.complete_external(connection,cache_key=key,source_url_hash=source_hash,
                    text_preview=word,file_path=name,audio_format=fmt,size_bytes=len(data))
            return CachedAudio(key,target,fmt,len(data))
