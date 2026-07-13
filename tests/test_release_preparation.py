from __future__ import annotations

from pathlib import Path

from english_typing_trainer.services.app_paths import AppPathService
from english_typing_trainer.services.credential_store import FallbackCredentialStore, MemoryCredentialStore


def test_new_default_data_directory_is_english_studio(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ENGLISH_TYPING_TRAINER_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert AppPathService().get_paths().data_dir == tmp_path / "EnglishStudio"


def test_legacy_data_is_copied_once_and_source_is_retained(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ENGLISH_TYPING_TRAINER_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    legacy=tmp_path / "EnglishTypingTrainer"; legacy.mkdir(); (legacy / "typing_trainer.db").write_bytes(b"legacy-db")
    paths=AppPathService().ensure_directories()
    assert paths.database_path.read_bytes() == b"legacy-db"
    assert (legacy / "typing_trainer.db").exists()
    assert (paths.data_dir / ".legacy-migration-complete").exists()


def test_environment_override_never_migrates_user_data(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path)); monkeypatch.setenv("ENGLISH_TYPING_TRAINER_DATA_DIR", str(tmp_path / "isolated"))
    legacy=tmp_path / "EnglishTypingTrainer"; legacy.mkdir(); (legacy / "typing_trainer.db").write_bytes(b"legacy-db")
    paths=AppPathService().ensure_directories()
    assert paths.data_dir == tmp_path / "isolated" and not paths.database_path.exists()


def test_credential_fallback_copies_legacy_without_deleting_it() -> None:
    primary=MemoryCredentialStore(); legacy=MemoryCredentialStore("legacy-key")
    store=FallbackCredentialStore(primary, legacy)
    assert store.get() == "legacy-key" and primary.get() == "legacy-key" and legacy.get() == "legacy-key"
    store.delete()
    assert primary.get() is None and legacy.get() == "legacy-key"
