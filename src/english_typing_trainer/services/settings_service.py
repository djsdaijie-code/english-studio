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
        }
        with self._database.transaction() as connection:
            self._repository.set_many(connection, values)
        return self.get_settings()

    def _to_bool(self, value: str | None, default: bool) -> bool:
        if value is None:
            return default
        return value in {"1", "true", "True", "yes"}
