from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from threading import Event
from time import monotonic

PROMPT_VERSION = "sentence-v1"
SYSTEM_PROMPT = """You translate one English sentence for a Chinese learner. Return strict JSON only with keys translation and key_expressions. translation must be concise and natural Chinese. key_expressions must contain 1 to 3 objects with expression and meaning. Do not add grammar lessons or extra commentary."""


@dataclass(slots=True)
class TranslationResult:
    translation: str
    key_expressions: list[dict[str, str]]


class TranslationProviderError(RuntimeError):
    def __init__(self, category: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class TranslationProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def translate(self, sentence: str, *, previous: str = "", following: str = "", cancel_event: Event | None = None) -> TranslationResult:
        raise NotImplementedError

    @abstractmethod
    def test_connection(self) -> None:
        raise NotImplementedError


class DeepSeekTranslationProvider(TranslationProvider):
    name = "deepseek"
    endpoint = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str, *, model: str = "deepseek-v4-flash", timeout: float = 20.0, opener=None) -> None:
        if not api_key.strip():
            raise TranslationProviderError("missing_key", "尚未配置 DeepSeek API Key。")
        self._api_key = api_key.strip()
        self.model = model
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self._logger = logging.getLogger(__name__)

    def translate(self, sentence: str, *, previous: str = "", following: str = "", cancel_event: Event | None = None) -> TranslationResult:
        if cancel_event and cancel_event.is_set():
            raise TranslationProviderError("cancelled", "请求已取消。")
        context_lines = [f"Current sentence: {sentence}"]
        if previous:
            context_lines.insert(0, f"Previous sentence (context only): {previous}")
        if following:
            context_lines.append(f"Next sentence (context only): {following}")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "\n".join(context_lines)},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
            "max_tokens": 500,
        }
        started = monotonic()
        self._logger.info("translation request provider=%s model=%s", self.name, self.model)
        try:
            request = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._api_key}"},
                method="POST",
            )
            with self._opener(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
            if cancel_event and cancel_event.is_set():
                raise TranslationProviderError("cancelled", "请求已取消。")
            envelope = json.loads(body)
            content = envelope["choices"][0]["message"]["content"]
            result = parse_translation_content(content)
            self._logger.info("translation completed provider=%s model=%s elapsed=%.3f", self.name, self.model, monotonic() - started)
            return result
        except urllib.error.HTTPError as exc:
            category = {401: "invalid_key", 402: "quota", 429: "rate_limit"}.get(exc.code, "server" if exc.code >= 500 else "request")
            self._logger.warning("translation http_error provider=%s model=%s status=%s", self.name, self.model, exc.code)
            raise TranslationProviderError(category, self._message_for(category), exc.code) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            category = "timeout" if isinstance(getattr(exc, "reason", exc), (TimeoutError, socket.timeout)) else "network"
            self._logger.warning("translation network_error provider=%s model=%s category=%s", self.name, self.model, category)
            raise TranslationProviderError(category, self._message_for(category)) from exc
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise TranslationProviderError("invalid_response", "翻译服务返回了无法解析的数据。") from exc

    def test_connection(self) -> None:
        self.translate("Hello.")

    @staticmethod
    def _message_for(category: str) -> str:
        return {
            "invalid_key": "DeepSeek API Key 无效。",
            "quota": "DeepSeek 余额或额度不足。",
            "rate_limit": "DeepSeek 请求过于频繁，请稍后重试。",
            "server": "DeepSeek 服务暂时不可用。",
            "timeout": "DeepSeek 请求超时。",
            "network": "网络连接失败。",
            "request": "DeepSeek 请求格式错误。",
        }.get(category, "翻译请求失败。")


def parse_translation_content(content: str) -> TranslationResult:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        raise json.JSONDecodeError("missing JSON object", cleaned, 0)
    data = json.loads(cleaned[start:end + 1])
    translation = data.get("translation")
    expressions = data.get("key_expressions", [])
    if not isinstance(translation, str) or not translation.strip() or not isinstance(expressions, list):
        raise json.JSONDecodeError("invalid translation schema", cleaned, 0)
    valid = []
    for item in expressions[:3]:
        if isinstance(item, dict) and isinstance(item.get("expression"), str) and isinstance(item.get("meaning"), str):
            valid.append({"expression": item["expression"].strip(), "meaning": item["meaning"].strip()})
    return TranslationResult(translation.strip(), valid)