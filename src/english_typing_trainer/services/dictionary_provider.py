from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(slots=True)
class DictionaryResult:
    query_word: str
    word: str
    phonetic: str = ""
    audio_url: str = ""
    primary_part_of_speech: str = ""
    definitions: list[dict[str, object]] = field(default_factory=list)
    payload: list[dict[str, object]] = field(default_factory=list)


class DictionaryProviderError(RuntimeError):
    def __init__(self, category: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message); self.category = category; self.status_code = status_code


class DictionaryProvider(ABC):
    name: str
    @abstractmethod
    def lookup(self, word: str) -> DictionaryResult: raise NotImplementedError


class FreeDictionaryProvider(DictionaryProvider):
    name = "free_dictionary"
    endpoint = "https://api.dictionaryapi.dev/api/v2/entries/en/"

    def __init__(self, *, timeout: float = 12.0, opener=None) -> None:
        self.timeout = timeout; self._opener = opener or urllib.request.urlopen

    def lookup(self, word: str) -> DictionaryResult:
        encoded = urllib.parse.quote(word, safe="")
        request = urllib.request.Request(self.endpoint + encoded, headers={"User-Agent": "EnglishTypingTrainer/0.2"})
        try:
            with self._opener(request, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            category = "not_found" if exc.code == 404 else "rate_limit" if exc.code == 429 else "server" if exc.code >= 500 else "request"
            raise DictionaryProviderError(category, self._message(category), exc.code) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            reason = getattr(exc, "reason", exc)
            category = "timeout" if isinstance(reason, (TimeoutError, socket.timeout)) else "network"
            raise DictionaryProviderError(category, self._message(category)) from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise DictionaryProviderError("invalid_response", self._message("invalid_response")) from exc
        return parse_dictionary_payload(word, payload)

    @staticmethod
    def _message(category: str) -> str:
        return {"not_found":"词典中未找到该词条。", "rate_limit":"词典请求过于频繁。", "server":"词典服务暂时不可用。",
                "timeout":"词典请求超时。", "network":"无法连接词典服务。", "invalid_response":"词典返回数据无法解析。"}.get(category, "词典请求失败。")


def parse_dictionary_payload(query_word: str, payload) -> DictionaryResult:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], dict):
        raise DictionaryProviderError("invalid_response", "词典返回数据无法解析。")
    entry = payload[0]
    phonetics = entry.get("phonetics") if isinstance(entry.get("phonetics"), list) else []
    selected = next((p for p in phonetics if isinstance(p, dict) and p.get("audio") and p.get("text")), None)
    selected = selected or next((p for p in phonetics if isinstance(p, dict) and p.get("audio")), None) or {}
    phonetic = str(selected.get("text") or entry.get("phonetic") or "")
    audio = str(selected.get("audio") or "")
    if audio.startswith("//"): audio = "https:" + audio
    meanings = entry.get("meanings") if isinstance(entry.get("meanings"), list) else []
    definitions: list[dict[str, object]] = []
    for meaning in meanings:
        if not isinstance(meaning, dict): continue
        pos = str(meaning.get("partOfSpeech") or "")
        for definition in (meaning.get("definitions") or [])[:3]:
            if isinstance(definition, dict) and isinstance(definition.get("definition"), str):
                definitions.append({"part_of_speech": pos, "definition": definition["definition"],
                                    "example": definition.get("example", ""), "synonyms": definition.get("synonyms", [])[:5],
                                    "antonyms": definition.get("antonyms", [])[:5]})
    return DictionaryResult(query_word, str(entry.get("word") or query_word), phonetic, audio,
                            str(meanings[0].get("partOfSpeech") or "") if meanings and isinstance(meanings[0], dict) else "",
                            definitions, payload)
