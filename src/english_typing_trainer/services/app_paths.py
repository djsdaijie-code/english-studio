from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class AppPaths:
    data_dir: Path
    database_path: Path
    logs_dir: Path
    backups_dir: Path
    audio_cache_dir: Path
    recordings_dir: Path


class AppPathService:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir

    def get_paths(self) -> AppPaths:
        data_dir = self._base_dir or self._environment_override() or self._default_data_dir()
        logs_dir = data_dir / "logs"
        backups_dir = data_dir / "backups"
        audio_cache_dir = data_dir / "audio_cache"
        recordings_dir = data_dir / "recordings"
        return AppPaths(
            data_dir=data_dir,
            database_path=data_dir / "typing_trainer.db",
            logs_dir=logs_dir,
            backups_dir=backups_dir,
            audio_cache_dir=audio_cache_dir,
            recordings_dir=recordings_dir,
        )

    def ensure_directories(self) -> AppPaths:
        if self._base_dir is None and self._environment_override() is None:
            self._migrate_legacy_default_data()
        paths = self.get_paths()
        paths.data_dir.mkdir(parents=True, exist_ok=True)
        paths.logs_dir.mkdir(parents=True, exist_ok=True)
        paths.backups_dir.mkdir(parents=True, exist_ok=True)
        paths.audio_cache_dir.mkdir(parents=True, exist_ok=True)
        paths.recordings_dir.mkdir(parents=True, exist_ok=True)
        return paths

    def _default_data_dir(self) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "EnglishStudio"
        return Path.home() / "AppData" / "Local" / "EnglishStudio"

    def _legacy_data_dir(self) -> Path:
        local_app_data = os.environ.get("LOCALAPPDATA")
        return (Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local") / "EnglishTypingTrainer"

    def _migrate_legacy_default_data(self) -> None:
        source=self._legacy_data_dir(); destination=self._default_data_dir(); marker=destination / ".legacy-migration-complete"
        if marker.exists() or not source.exists() or (destination / "typing_trainer.db").exists(): return
        staging=destination.with_name(destination.name + ".migration-staging")
        try:
            if staging.exists(): shutil.rmtree(staging)
            shutil.copytree(source, staging, dirs_exist_ok=True)
            if not (staging / "typing_trainer.db").exists(): return
            destination.mkdir(parents=True, exist_ok=True)
            for child in staging.iterdir():
                target=destination / child.name
                if not target.exists(): shutil.move(str(child), str(target))
            marker.write_text("migrated from EnglishTypingTrainer; source retained\n",encoding="utf-8")
        finally:
            if staging.exists(): shutil.rmtree(staging, ignore_errors=True)

    def _environment_override(self) -> Path | None:
        override = os.environ.get("ENGLISH_TYPING_TRAINER_DATA_DIR")
        if override:
            return Path(override)
        return None
