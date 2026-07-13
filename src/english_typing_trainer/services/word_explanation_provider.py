from __future__ import annotations

import json
from dataclasses import dataclass
from threading import Event

from english_typing_trainer.services.translation_provider import DeepSeekTranslationProvider, TranslationProviderError

WORD_PROMPT_VERSION = "word-context-v1"


@dataclass(slots=True)
class WordExplanationResult:
    word: str
    lemma: str
    part_of_speech: str
    meaning_in_context_zh: str
    simple_explanation_zh: str
    collocation: str
    example_en: str
    example_zh: str


class DeepSeekWordExplanationProvider(DeepSeekTranslationProvider):
    def explain(self, *, word: str, lemma: str, sentence: str, dictionary_summary: list[dict[str, object]], cancel_event: Event | None = None) -> WordExplanationResult:
        if cancel_event and cancel_event.is_set(): raise TranslationProviderError("cancelled", "请求已取消。")
        system = ("Explain one English word in its sentence for a beginner Chinese learner. Return strict JSON only with keys "
                  "word, lemma, part_of_speech, meaning_in_context_zh, simple_explanation_zh, collocation, example_en, example_zh. "
                  "meaning_in_context_zh must be 2-10 Chinese characters. No markdown or reasoning.")
        user = json.dumps({"word":word, "suggested_lemma":lemma, "source_sentence":sentence,
                           "dictionary_definitions":dictionary_summary[:3], "learner_language":"zh-CN", "level":"beginner"}, ensure_ascii=False)
        content = self._chat_json(system, user, cancel_event=cancel_event)
        return parse_word_explanation(content)

    def _chat_json(self, system: str, user: str, *, cancel_event=None) -> str:
        import socket
        import urllib.error
        import urllib.request
        payload={"model":self.model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],
                 "response_format":{"type":"json_object"},"thinking":{"type":"disabled"},"stream":False,"max_tokens":500}
        request=urllib.request.Request(self.endpoint,data=json.dumps(payload,ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type":"application/json","Authorization":f"Bearer {self._api_key}"},method="POST")
        try:
            with self._opener(request,timeout=self.timeout) as response: body=response.read().decode("utf-8")
            if cancel_event and cancel_event.is_set(): raise TranslationProviderError("cancelled", "请求已取消。")
            return json.loads(body)["choices"][0]["message"]["content"]
        except TranslationProviderError: raise
        except urllib.error.HTTPError as exc:
            category={401:"invalid_key",402:"quota",429:"rate_limit"}.get(exc.code,"server" if exc.code>=500 else "request")
            raise TranslationProviderError(category,self._message_for(category),exc.code) from exc
        except (urllib.error.URLError,TimeoutError,socket.timeout) as exc:
            reason=getattr(exc,"reason",exc); category="timeout" if isinstance(reason,(TimeoutError,socket.timeout)) else "network"
            raise TranslationProviderError(category,self._message_for(category)) from exc
        except (json.JSONDecodeError,KeyError,IndexError,TypeError) as exc:
            raise TranslationProviderError("invalid_response", "单词讲解服务返回了无法解析的数据。") from exc


def parse_word_explanation(content: str) -> WordExplanationResult:
    try:
        data=json.loads(content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        fields=("word","lemma","part_of_speech","meaning_in_context_zh","simple_explanation_zh","collocation","example_en","example_zh")
        if not all(isinstance(data.get(key),str) for key in fields): raise ValueError
        if not data["meaning_in_context_zh"].strip() or len(data["meaning_in_context_zh"].strip()) > 20: raise ValueError
        return WordExplanationResult(*(data[key].strip()[:500] for key in fields))
    except (json.JSONDecodeError, ValueError, TypeError, KeyError) as exc:
        raise TranslationProviderError("invalid_response", "单词讲解 JSON 格式无效。") from exc
