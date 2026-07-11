from pathlib import Path

from english_typing_trainer.application.context import build_app_context


def test_first_start_creates_database_and_directories(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "appdata")
    try:
        assert context.paths.data_dir.exists()
        assert context.paths.logs_dir.exists()
        assert context.paths.backups_dir.exists()
        assert context.paths.database_path.exists()
    finally:
        context.database.close()


def test_repeat_start_keeps_schema_intact(tmp_path: Path) -> None:
    data_dir = tmp_path / "appdata"
    first = build_app_context(data_dir=data_dir)
    first.database.close()

    second = build_app_context(data_dir=data_dir)
    try:
        assert second.database.get_schema_version() == 3
        assert second.database.get_foreign_keys_enabled() is True
    finally:
        second.database.close()


def test_temp_data_dir_does_not_use_real_user_location(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "isolated")
    try:
        assert context.paths.data_dir == tmp_path / "isolated"
    finally:
        context.database.close()
