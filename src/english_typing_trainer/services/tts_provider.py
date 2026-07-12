from __future__ import annotations

import json
import logging
import socket
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from threading import Event

from english_typing_trainer.models.tts import TTSAudioResult, TTSRequest


SUPPORTED_MINIMAX_MODELS = ("speech-2.8-hd", "speech-2.8-turbo")
MINIMAX_ENGLISH_VOICES = (
    ("English_expressive_narrator", "英语 · 表现力旁白"),
    ("English_magnetic_voiced_man", "英语 · 磁性男声"),
    ("English_radiant_girl", "英语 · 明亮女声"),
)


class TTSProviderError(RuntimeError):
    def __init__(self, category: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.category = category
        self.status_code = status_code


class TTSProvider(ABC):
    name: str

    @abstractmethod
    def synthesize(self, request: TTSRequest, *, cancel_event: Event | None = None) -> TTSAudioResult: ...

    @abstractmethod
    def test_connection(self) -> None: ...

    @abstractmethod
    def list_supported_models(self) -> tuple[str, ...]: ...


class MiniMaxTTSProvider(TTSProvider):
    name = "minimax"
    endpoint = "https://api.minimax.io/v1/t2a_v2"

    def __init__(self, api_key: str, *, timeout: float = 20.0, opener=None) -> None:
        if not api_key.strip():
            raise TTSProviderError("missing_key", "尚未配置 MiniMax API Key。")
        self._api_key = api_key.strip()
        self.timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self._logger = logging.getLogger(__name__)

    def list_supported_models(self) -> tuple[str, ...]:
        return SUPPORTED_MINIMAX_MODELS

    def test_connection(self) -> None:
        self.synthesize(TTSRequest(text="Hello."))

    def synthesize(self, request: TTSRequest, *, cancel_event: Event | None = None) -> TTSAudioResult:
        self._validate(request)
        if cancel_event and cancel_event.is_set():
            raise TTSProviderError("cancelled", "语音生成已取消。")
        payload = {
            "model": request.model,
            "text": request.text,
            "stream": False,
            "language_boost": request.language_boost,
            "output_format": "hex",
            "voice_setting": {
                "voice_id": request.voice_id,
                "speed": request.speed,
                "vol": request.volume,
                "pitch": request.pitch,
            },
            "audio_setting": {
                "sample_rate": request.sample_rate,
                "bitrate": request.bitrate,
                "format": request.audio_format,
                "channel": request.channel,
            },
        }
        http_request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        started = time.monotonic()
        self._logger.info("tts request provider=minimax model=%s voice=%s chars=%s", request.model, request.voice_id, len(request.text))
        try:
            with self._opener(http_request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise self._http_error(exc.code) from None
        except (TimeoutError, socket.timeout) as exc:
            raise TTSProviderError("timeout", "MiniMax 请求超时。") from exc
        except urllib.error.URLError as exc:
            raise TTSProviderError("network", "无法连接 MiniMax，请检查网络。") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise TTSProviderError("invalid_response", "MiniMax 返回格式异常。") from exc
        if cancel_event and cancel_event.is_set():
            raise TTSProviderError("cancelled", "语音生成已取消。")
        base = body.get("base_resp") or {}
        if int(base.get("status_code", 0)) != 0:
            raise self._api_error(int(base.get("status_code", -1)), str(base.get("status_msg", "")))
        audio_hex = (body.get("data") or {}).get("audio")
        try:
            audio = bytes.fromhex(audio_hex) if isinstance(audio_hex, str) else b""
        except ValueError as exc:
            raise TTSProviderError("invalid_response", "MiniMax 音频数据无法解析。") from exc
        if not audio:
            raise TTSProviderError("invalid_response", "MiniMax 未返回有效音频。")
        extra = body.get("extra_info") or {}
        self._logger.info("tts completed provider=minimax model=%s voice=%s elapsed_ms=%s", request.model, request.voice_id, int((time.monotonic()-started)*1000))
        return TTSAudioResult(
            audio, request.audio_format, self.name, request.model, request.voice_id,
            request_id=str(body.get("trace_id", "")),
            duration_ms=int(extra["audio_length"]) if extra.get("audio_length") is not None else None,
            usage_characters=int(extra.get("usage_characters", len(request.text))),
        )

    def _validate(self, request: TTSRequest) -> None:
        if request.model not in SUPPORTED_MINIMAX_MODELS:
            raise TTSProviderError("model_unavailable", "不支持所选 MiniMax 语音模型。")
        if not request.text.strip() or len(request.text) >= 10000:
            raise TTSProviderError("invalid_request", "语音文本为空或过长。")
        if not 0.5 <= request.speed <= 2.0:
            raise TTSProviderError("invalid_request", "语速参数无效。")

    def _http_error(self, status: int) -> TTSProviderError:
        mapping = {
            401: ("invalid_key", "MiniMax API Key 无效。"),
            402: ("quota", "MiniMax 余额或额度不足。"),
            429: ("rate_limit", "MiniMax 请求过于频繁。"),
        }
        category, message = mapping.get(status, ("server" if status >= 500 else "invalid_request", "MiniMax 服务暂时不可用。" if status >= 500 else "MiniMax 请求参数无效。"))
        return TTSProviderError(category, message, status_code=status)

    def _api_error(self, code: int, message: str) -> TTSProviderError:
        lowered = message.lower()
        if "voice" in lowered:
            return TTSProviderError("voice_unavailable", "所选 MiniMax 音色不可用。")
        if "model" in lowered:
            return TTSProviderError("model_unavailable", "所选 MiniMax 模型不可用。")
        if "balance" in lowered or "quota" in lowered:
            return TTSProviderError("quota", "MiniMax 余额或额度不足。")
        return TTSProviderError("api_error", f"MiniMax 语音生成失败（错误码 {code}）。")
