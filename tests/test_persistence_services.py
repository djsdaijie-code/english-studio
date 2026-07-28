from pathlib import Path

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.repositories import ArticleRepository, PracticeRepository
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.typing_engine.session import TypingSession


def test_import_article_success_and_duplicate_block(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "lesson.txt"
        file_path.write_text("Hello world.\n\nThis is a test.", encoding="utf-8")

        first = context.article_library.import_txt_file(file_path, 500)
        second = context.article_library.import_txt_file(file_path, 500)

        assert first.status == "imported"
        assert second.status == "duplicate"
        assert len(context.article_library.list_articles()) == 1
    finally:
        context.database.close()


def test_import_preserves_long_article_as_one_complete_section(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        text = ("A deliberately long paragraph keeps every character in place. " * 30).strip()
        file_path = tmp_path / "long article.txt"
        file_path.write_text(text, encoding="utf-8")

        imported = context.article_library.import_txt_file(file_path, 300)

        assert imported.article is not None
        assert imported.article.section_count == 1
        sections = context.article_library.get_sections(imported.article.id)
        assert len(sections) == 1
        assert sections[0].text == text
        assert sections[0].start_offset == 0
        assert sections[0].end_offset == len(text)
    finally:
        context.database.close()


def test_import_supports_chinese_filename_and_path(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        folder = tmp_path / "中文目录"
        folder.mkdir()
        file_path = folder / "文章示例.txt"
        file_path.write_text("Typing survives unicode paths.", encoding="utf-8")

        result = context.article_library.import_txt_file(file_path, 500)

        assert result.status == "imported"
        assert result.article is not None
        assert result.article.title == "文章示例"
        assert "中文目录" in result.article.source_path
    finally:
        context.database.close()


def test_soft_delete_and_restore_by_duplicate_import(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "restore.txt"
        file_path.write_text("Duplicate me once.", encoding="utf-8")
        imported = context.article_library.import_txt_file(file_path, 500)
        assert imported.article is not None

        context.article_library.soft_delete_article(imported.article.id)
        assert context.article_library.list_articles() == []

        restored = context.article_library.import_txt_file(file_path, 500)
        assert restored.status == "restored"
        assert len(context.article_library.list_articles()) == 1
    finally:
        context.database.close()


def test_resegment_transaction_rolls_back_on_failure(tmp_path: Path, monkeypatch) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "resegment.txt"
        file_path.write_text("Sentence one. Sentence two. Sentence three.", encoding="utf-8")
        imported = context.article_library.import_txt_file(file_path, 300)
        assert imported.article is not None

        original_sections = context.article_library.get_sections(imported.article.id)

        def fail_insert(*args, **kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(context.article_library._repository, "insert_sections", fail_insert)

        try:
            context.article_library.resegment_article(imported.article.id, 500)
        except RuntimeError:
            pass

        after_sections = context.article_library.get_sections(imported.article.id)
        assert [section.text for section in after_sections] == [section.text for section in original_sections]
    finally:
        context.database.close()


def test_progress_and_sessions_are_saved_for_complete_and_incomplete_runs(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        file_path = tmp_path / "practice.txt"
        file_path.write_text("abcdef", encoding="utf-8")
        imported = context.article_library.import_txt_file(file_path, 300)
        assert imported.article is not None

        material = context.practice_service.load_practice_material(imported.article.id, mode="resume")
        interrupted = TypingSession(material.section_text, start_position=material.resume_character_index)
        interrupted.handle_character("a")
        interrupted.handle_character("b")
        context.practice_service.save_interrupted_session(material, interrupted, interrupted.snapshot())

        resumed = context.practice_service.load_practice_material(imported.article.id, mode="resume")
        assert resumed.resume_character_index == 2

        completed = TypingSession(resumed.section_text, start_position=resumed.resume_character_index)
        for char in resumed.section_text[resumed.resume_character_index :]:
            completed.handle_character(char)
        context.practice_service.save_completed_session(resumed, completed, completed.snapshot())

        article = context.article_library.get_article(imported.article.id)
        assert article is not None
        assert article.completed_section_count == article.section_count

        practice_repo = PracticeRepository(context.database.connect)
        rows = practice_repo.list_sessions_for_article(imported.article.id)
        assert len(rows) == 2
        assert {int(row["completed"]) for row in rows} == {0, 1}
    finally:
        context.database.close()


def test_settings_defaults_and_updates_roundtrip(tmp_path: Path) -> None:
    context = build_app_context(data_dir=tmp_path / "data")
    try:
        defaults = context.settings_service.get_settings()
        assert defaults.section_target_characters == 500
        assert defaults.case_sensitive is True

        updated = context.settings_service.save_settings(
            AppSettings(
                section_target_characters=800,
                case_sensitive=False,
                show_live_stats=False,
                target_wpm=75,
                target_accuracy=97.5,
                theme="dark",
                font_size=22,
            )
        )
        assert updated.section_target_characters == 800
        assert updated.case_sensitive is False
        assert updated.theme == "dark"
        assert updated.font_size == 22
    finally:
        context.database.close()
