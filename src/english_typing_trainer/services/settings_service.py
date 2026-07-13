from __future__ import annotations

from dataclasses import asdict

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import SettingsRepository
from english_typing_trainer.models.settings import AppSettings


class SettingsService:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database
        self._repository = SettingsRepository(database.connect)

    def get_settings(self) -> AppSettings:
        raw_values = self._repository.get_all()
        return AppSettings(
            section_target_characters=int(raw_values.get("section_target_characters", 500)),
            case_sensitive=self._to_bool(raw_values.get("case_sensitive"), True),
            show_live_stats=self._to_bool(raw_values.get("show_live_stats"), True),
            target_wpm=int(raw_values.get("target_wpm", 60)),
            target_accuracy=float(raw_values.get("target_accuracy", 98.0)),
            theme=raw_values.get("theme", "light"),
            font_size=int(raw_values.get("font_size", 18)),
            sentence_learning_enabled=self._to_bool(raw_values.get("sentence_learning_enabled"), True),
            show_translation_after_sentence=self._to_bool(raw_values.get("show_translation_after_sentence"), True),
            idle_pause_seconds=int(raw_values.get("idle_pause_seconds", 3)),
            translation_auto_on_demand=self._to_bool(raw_values.get("translation_auto_on_demand"), True),
            translation_provider=raw_values.get("translation_provider", "deepseek"),
            translation_model=raw_values.get("translation_model", "deepseek-v4-flash"),
            translation_prompt_version=raw_values.get("translation_prompt_version", "sentence-v1"),
            tts_provider=raw_values.get("tts_provider", "minimax"),
            tts_model=raw_values.get("tts_model", "speech-2.8-hd"),
            tts_voice_id=raw_values.get("tts_voice_id", "English_expressive_narrator"),
            tts_speed=float(raw_values.get("tts_speed", 1.0)),
            tts_auto_play=self._to_bool(raw_values.get("tts_auto_play"), False),
            vocabulary_typing_count=int(raw_values.get("vocabulary_typing_count", 5)),
            vocabulary_auto_enrich=self._to_bool(raw_values.get("vocabulary_auto_enrich"), True),
            vocabulary_audio_preference=raw_values.get("vocabulary_audio_preference", "dictionary"),
            daily_learning_goal_minutes=int(raw_values.get("daily_learning_goal_minutes", 15)),
            learning_idle_timeout_seconds=int(raw_values.get("learning_idle_timeout_seconds", 90)),
            checkin_animation_enabled=self._to_bool(raw_values.get("checkin_animation_enabled"), True),
            health_reminders_enabled=self._to_bool(raw_values.get("health_reminders_enabled"), True),
            reduce_motion=self._to_bool(raw_values.get("reduce_motion"), False),
        )

    def save_settings(self, settings: AppSettings) -> AppSettings:
        values = {
            "section_target_characters": str(settings.section_target_characters),
            "case_sensitive": "1" if settings.case_sensitive else "0",
            "show_live_stats": "1" if settings.show_live_stats else "0",
            "target_wpm": str(settings.target_wpm),
            "target_accuracy": str(settings.target_accuracy),
            "theme": settings.theme,
            "font_size": str(settings.font_size),
            "sentence_learning_enabled": "1" if settings.sentence_learning_enabled else "0",
            "show_translation_after_sentence": "1" if settings.show_translation_after_sentence else "0",
            "idle_pause_seconds": str(settings.idle_pause_seconds),
            "translation_auto_on_demand": "1" if settings.translation_auto_on_demand else "0",
            "translation_provider": settings.translation_provider,
            "translation_model": settings.translation_model,
            "translation_prompt_version": settings.translation_prompt_version,
            "tts_provider": settings.tts_provider,
            "tts_model": settings.tts_model,
            "tts_voice_id": settings.tts_voice_id,
            "tts_speed": str(settings.tts_speed),
            "tts_auto_play": "1" if settings.tts_auto_play else "0",
            "vocabulary_typing_count": str(settings.vocabulary_typing_count),
            "vocabulary_auto_enrich": "1" if settings.vocabulary_auto_enrich else "0",
            "vocabulary_audio_preference": settings.vocabulary_audio_preference,
            "daily_learning_goal_minutes": str(settings.daily_learning_goal_minutes),
            "learning_idle_timeout_seconds": str(settings.learning_idle_timeout_seconds),
            "checkin_animation_enabled": "1" if settings.checkin_animation_enabled else "0",
            "health_reminders_enabled": "1" if settings.health_reminders_enabled else "0",
            "reduce_motion": "1" if settings.reduce_motion else "0",
        }
        with self._database.transaction() as connection:
            self._repository.set_many(connection, values)
        return self.get_settings()

    def _to_bool(self, value: str | None, default: bool) -> bool:
        if value is None:
            return default
        return value in {"1", "true", "True", "yes"}
