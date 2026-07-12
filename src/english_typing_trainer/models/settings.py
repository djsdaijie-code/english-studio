from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AppSettings:
    section_target_characters: int = 500
    case_sensitive: bool = True
    show_live_stats: bool = True
    target_wpm: int = 60
    target_accuracy: float = 98.0
    theme: str = "light"
    font_size: int = 18
    sentence_learning_enabled: bool = True
    show_translation_after_sentence: bool = True
    idle_pause_seconds: int = 3
    translation_auto_on_demand: bool = True
    translation_provider: str = "deepseek"
    translation_model: str = "deepseek-v4-flash"
    translation_prompt_version: str = "sentence-v1"