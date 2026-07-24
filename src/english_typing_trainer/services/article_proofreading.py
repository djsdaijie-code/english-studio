from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from threading import Event
from time import monotonic


PROOFREADING_PROMPT_VERSION = "article-proofreading-v1"
PROOFREADING_SYSTEM_PROMPT = """You proofread English articles for language learners. Correct only objective spelling mistakes, obvious word errors, duplicated or missing punctuation, and malformed whitespace or paragraph formatting. Do not rewrite the author's style, simplify vocabulary, add content, translate, or change meaning. Preserve paragraph breaks unless they are clearly malformed. Return strict JSON only with keys corrected_text and issues. issues must be an array of objects with type, original, suggestion, and reason. type must be spelling, word, punctuation, or formatting. reason must be concise Simplified Chinese."""


@dataclass(frozen=True, slots=True)
class ProofreadingIssue:
    issue_type: str
    original: str
    suggestion: str
    reason: str


@dataclass(frozen=True, slots=True)
class ArticleProofreadingResult:
    corrected_text: str
    issues: tuple[ProofreadingIssue, ...]

    def differs_from(self, original_text: str) -> bool:
        return self.corrected_text != original_text


class ArticleProofreadingError(RuntimeError):
    def __init__(self, category: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class DeepSeekArticleProofreadingProvider:
    name = "deepseek"
    endpoint = "https://api.deepseek.com/chat/completions"

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "deepseek-v4-flash",
        timeout: float = 30.0,
        opener=None,
    ) -> None:
        if not api_key.strip():
            raise ArticleProofreadingError("missing_key", "尚未配置 DeepSeek API Key，无法检测文章。")
        self._api_key = api_key.strip()
        self.model = model
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self._logger = logging.getLogger(__name__)

    def proofread(
        self,
        text: str,
        *,
        cancel_event: Event | None = None,
    ) -> ArticleProofreadingResult:
        if cancel_event and cancel_event.is_set():
            raise ArticleProofreadingError("cancelled", "文章检测已取消。")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": PROOFREADING_SYSTEM_PROMPT},
                {"role": "user", "content": f"Proofread this article segment:\n<article>\n{text}\n</article>"},
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "stream": False,
            "max_tokens": 8192,
        }
        started = monotonic()
        self._logger.info("article proofreading request provider=%s model=%s chars=%s", self.name, self.model, len(text))
        try:
            request = urllib.request.Request(
                self.endpoint,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
                method="POST",
            )
            with self._opener(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
            if cancel_event and cancel_event.is_set():
                raise ArticleProofreadingError("cancelled", "文章检测已取消。")
            envelope = json.loads(body)
            content = envelope["choices"][0]["message"]["content"]
            result = parse_proofreading_content(content)
            self._logger.info(
                "article proofreading completed provider=%s model=%s elapsed=%.3f issues=%s",
                self.name,
                self.model,
                monotonic() - started,
                len(result.issues),
            )
            return result
        except urllib.error.HTTPError as exc:
            category = {401: "invalid_key", 402: "quota", 429: "rate_limit"}.get(
                exc.code, "server" if exc.code >= 500 else "request"
            )
            raise ArticleProofreadingError(category, self._message_for(category), exc.code) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            category = "timeout" if isinstance(getattr(exc, "reason", exc), (TimeoutError, socket.timeout)) else "network"
            raise ArticleProofreadingError(category, self._message_for(category)) from exc
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ArticleProofreadingError("invalid_response", "DeepSeek 返回了无法解析的文章检测结果。") from exc

    @staticmethod
    def _message_for(category: str) -> str:
        return {
            "invalid_key": "DeepSeek API Key 无效。",
            "quota": "DeepSeek 余额或额度不足。",
            "rate_limit": "DeepSeek 请求过于频繁，请稍后重试。",
            "server": "DeepSeek 服务暂时不可用。",
            "timeout": "DeepSeek 文章检测请求超时。",
            "network": "网络连接失败，无法检测文章。",
            "request": "DeepSeek 文章检测请求格式错误。",
        }.get(category, "文章检测失败。")


class ArticleProofreadingService:
    def __init__(self, max_chunk_characters: int = 5000) -> None:
        self.max_chunk_characters = max(1000, max_chunk_characters)

    def check(
        self,
        provider: DeepSeekArticleProofreadingProvider,
        text: str,
        *,
        cancel_event: Event | None = None,
    ) -> ArticleProofreadingResult:
        corrected_parts: list[str] = []
        issues: list[ProofreadingIssue] = []
        for chunk in self._split(text):
            if cancel_event and cancel_event.is_set():
                raise ArticleProofreadingError("cancelled", "文章检测已取消。")
            leading_length = len(chunk) - len(chunk.lstrip())
            trailing_start = len(chunk.rstrip())
            leading = chunk[:leading_length]
            trailing = chunk[trailing_start:]
            core_end = max(leading_length, trailing_start)
            core = chunk[leading_length:core_end]
            result = provider.proofread(core, cancel_event=cancel_event)
            corrected_core = result.corrected_text.strip()
            self._validate_chunk(core, corrected_core)
            corrected_parts.append(leading + corrected_core + trailing)
            issues.extend(result.issues)
        return ArticleProofreadingResult("".join(corrected_parts), tuple(issues))

    def _split(self, text: str) -> list[str]:
        if len(text) <= self.max_chunk_characters:
            return [text]
        chunks: list[str] = []
        start = 0
        while start < len(text):
            upper = min(len(text), start + self.max_chunk_characters)
            if upper < len(text):
                lower = start + self.max_chunk_characters // 2
                candidates = [
                    text.rfind("\n\n", lower, upper),
                    text.rfind("\n", lower, upper),
                    text.rfind(". ", lower, upper),
                    text.rfind(" ", lower, upper),
                ]
                boundary = max(candidates)
                if boundary >= lower:
                    separator_length = 2 if text[boundary:boundary + 2] in {"\n\n", ". "} else 1
                    upper = boundary + separator_length
            chunks.append(text[start:upper])
            start = upper
        return chunks

    @staticmethod
    def _validate_chunk(original: str, corrected: str) -> None:
        if not corrected or (len(original) >= 80 and not 0.6 <= len(corrected) / len(original) <= 1.4):
            raise ArticleProofreadingError("unsafe_result", "DeepSeek 建议文本长度异常，已停止应用以保护原文。")


def parse_proofreading_content(content: str) -> ArticleProofreadingResult:
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
    corrected_text = data.get("corrected_text")
    raw_issues = data.get("issues", [])
    if not isinstance(corrected_text, str) or not corrected_text or not isinstance(raw_issues, list):
        raise json.JSONDecodeError("invalid proofreading schema", cleaned, 0)
    issues: list[ProofreadingIssue] = []
    for item in raw_issues[:100]:
        if not isinstance(item, dict):
            continue
        values = [item.get(key) for key in ("type", "original", "suggestion", "reason")]
        if all(isinstance(value, str) for value in values):
            issues.append(ProofreadingIssue(*(value.strip() for value in values)))
    return ArticleProofreadingResult(corrected_text, tuple(issues))
