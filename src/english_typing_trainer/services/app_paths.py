from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppPaths:
    data_dir: Path
    database_path: Path
    logs_dir: Path
    backups_dir: Path
    audio_cache_dir: Path


class AppPathService:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir

    def get_paths(self) -> AppPaths:
        data_dir = self._base_dir or self._environment_override() or self._default_data_dir()
        logs_dir = data_dir / "logs"
        backups_dir = data_dir / "backups"
        audio_cache_dir = data_dir / "audio_cache"
        return AppPaths(
            data_dir=data_dir,
            database_path=data_dir / "typing_trainer.db",
            logs_dir=logs_dir,
            backups_dir=backups_dir,
            audio_cache_dir=audio_cache_dir,
        )

    def ensure_directories(self) -> AppPaths:
        paths = self.get_paths()
        paths.data_dir.mkdir(parents=True, exist_ok=True)
        paths.logs_dir.mkdir(parents=True, exist_ok=True)
        paths.backups_dir.mkdir(parents=True, exist_ok=True)
        paths.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        return paths

    def _default_data_dir(self) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "EnglishTypingTrainer"
        return Path.home() / "AppData" / "Local" / "EnglishTypingTrainer"

    def _environment_override(self) -> Path | None:
        override = os.environ.get("ENGLISH_TYPING_TRAINER_DATA_DIR")
        if override:
            return Path(override)
        return None
