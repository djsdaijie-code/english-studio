from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TTSRequest:
    text: str
    content_type: str = "sentence"
    language: str = "English"
    provider: str = "minimax"
    model: str = "speech-2.8-hd"
    voice_id: str = "English_expressive_narrator"
    speed: float = 1.0
    volume: float = 1.0
    pitch: int = 0
    audio_format: str = "mp3"
    sample_rate: int = 32000
    bitrate: int = 128000
    channel: int = 1
    language_boost: str = "English"


@dataclass(frozen=True, slots=True)
class TTSAudioResult:
    audio_bytes: bytes
    audio_format: str
    provider: str
    model: str
    voice_id: str
    request_id: str = ""
    duration_ms: int | None = None
    usage_characters: int = 0


@dataclass(frozen=True, slots=True)
class CachedAudio:
    cache_key: str
    file_path: Path
    audio_format: str
    size_bytes: int
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class AudioCacheStats:
    file_count: int
    total_size_bytes: int
