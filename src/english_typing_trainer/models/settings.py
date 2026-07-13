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
    tts_provider: str = "minimax"
    tts_model: str = "speech-2.8-hd"
    tts_voice_id: str = "English_expressive_narrator"
    tts_speed: float = 1.0
    tts_auto_play: bool = False
    vocabulary_typing_count: int = 5
    vocabulary_auto_enrich: bool = True
    vocabulary_audio_preference: str = "dictionary"
    daily_learning_goal_minutes: int = 15
    learning_idle_timeout_seconds: int = 90
    checkin_animation_enabled: bool = True
    health_reminders_enabled: bool = True
    reduce_motion: bool = False
    fsrs_desired_retention: float = 0.90
    fsrs_new_cards_per_day: int = 20
    fsrs_review_soft_limit: int = 100
    pronunciation_provider: str = "azure"
    pronunciation_region: str = ""
    pronunciation_locale: str = "en-US"
    pronunciation_keep_recordings: bool = False
