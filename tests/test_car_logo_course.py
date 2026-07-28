from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.courses import CourseRepository
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.ui.course_page import CoursePage
from english_typing_trainer.ui.main_window import MainWindow


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COURSES_ROOT = PROJECT_ROOT / "courses"
COURSE_ID = "global-car-logos"
DAY_ONE = "car-logo-u01-d01"
FIRST_ITEM = "global-car-logos-brand-toyota"
TOYOTA_PROFILE = "Toyota. This Japanese brand makes cars, SUVs, and hybrid vehicles."
FIRST_DAY_PROFILES = [
    TOYOTA_PROFILE,
    "Volkswagen. This German brand produces cars, SUVs, and electric vehicles.",
    "Ford. This American brand makes cars, pickup trucks, and SUVs.",
    "Honda. This Japanese company makes both cars and motorcycles.",
    "BMW. This German brand makes premium cars and motorcycles.",
]


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _context(tmp_path: Path, *, courses_root: Path | None = None):
    return build_app_context(
        data_dir=tmp_path / "data",
        credential_store=MemoryCredentialStore(),
        courses_root=courses_root,
    )


def _key(character: str) -> QKeyEvent:
    key = Qt.Key.Key_Space if character == " " else 0
    return QKeyEvent(
        QKeyEvent.Type.KeyPress,
        key,
        Qt.KeyboardModifier.NoModifier,
        character,
    )


def test_car_logo_course_has_mvp_shape_and_traceable_visual_assets() -> None:
    repository = CourseRepository()
    course = repository.get_course(COURSE_ID)

    assert course is not None
    assert course.specification_version == "1.1"
    assert course.version == "0.1.1"
    assert course.status == "draft"
    assert len(course.levels) == 1
    units = [unit for level in course.levels for unit in level.units]
    lessons = [lesson for unit in units for lesson in unit.lessons]
    sentences = [sentence for unit in units for sentence in unit.sentences]
    assert len(units) == 2
    assert len(lessons) == 14
    assert len(sentences) == 40
    assert all(len(unit.lessons) == 7 and len(unit.sentences) == 20 for unit in units)
    assert all(unit.lessons[-1].lesson_type == "review" for unit in units)
    assert all(unit.lessons[-1].assessment is None for unit in units)
    assert all(
        [activity.activity_type for activity in unit.lessons[-1].activities]
        == ["typing", "fsrs"]
        for unit in units
    )
    assert len({sentence.english for sentence in sentences}) == 40
    brands = {
        sentence.audio_hint.stress_words[0]
        for sentence in sentences
        if sentence.audio_hint is not None
    }
    assert {"Mercedes-Benz", "BYD", "Lexus", "Land Rover", "MINI", "XPENG"} <= brands
    assert all(sentence.content_version == "0.1.1" for sentence in sentences)
    assert all(8 <= len(sentence.english.split()) <= 12 for sentence in sentences)

    manifest = json.loads(
        (COURSES_ROOT / "global-car-logos" / "ASSET_SOURCES.json").read_text(
            encoding="utf-8"
        )
    )
    sources = {item["path"]: item for item in manifest["assets"]}
    assert len(sources) == 40
    for sentence in sentences:
        prompt = sentence.visual_prompt
        assert prompt is not None
        assert sentence.audio_hint is not None
        brand = sentence.audio_hint.stress_words[0]
        assert prompt.prompt_type == "illustrated_word"
        assert not prompt.hide_answer
        assert sentence.english.startswith(f"{brand}. ")
        assert sentence.audio_hint.pause_after == (brand,)
        assert brand in prompt.alt_text
        assert prompt.instruction_zh == "先读品牌名，再跟打一条简短介绍；车标用于辅助记忆。"
        assert prompt.resolved_asset_path.is_absolute()
        assert prompt.resolved_asset_path.is_file()
        assert prompt.asset_path in sources
        assert sources[prompt.asset_path]["brand"] == brand
        assert prompt.source_url == sources[prompt.asset_path]["source_url"]
        assert sha256(prompt.resolved_asset_path.read_bytes()).hexdigest() == sources[
            prompt.asset_path
        ]["sha256"]
        assert repository.get_sentence_by_stable_key(sentence.stable_key) is sentence


def test_car_logo_session_reuses_course_progress_without_article_rows(tmp_path: Path) -> None:
    context = _context(tmp_path)
    try:
        session = context.course_learning_service.build_session(COURSE_ID, DAY_ONE, "manual")

        assert [item.text for item in session.typing_sentences] == FIRST_DAY_PROFILES
        assert len(session.visual_prompts) == 5
        assert all(prompt is not None for prompt in session.visual_prompts)
        assert session.has_vocabulary_by_item == (False,) * 5
        assert all(session.core_patterns_by_item)
        assert session.item_stable_keys[0] == FIRST_ITEM
        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM article_sentences").fetchone()[0] == 0
    finally:
        context.database.close()


def test_visual_course_shows_brand_profile_while_logo_supports_typing(
    tmp_path: Path,
) -> None:
    app = _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        window.show()
        window._start_course_lesson(COURSE_ID, DAY_ONE, "manual")
        app.processEvents()

        view = window.sentence_practice_view
        assert view.visual_prompt_panel.isVisibleTo(view)
        assert not view.visual_prompt_image.pixmap().isNull()
        assert view.text_browser.isVisibleTo(view)
        assert view.text_browser.toPlainText() == TOYOTA_PROFILE
        assert view.source_title.text() == "品牌名与介绍"
        assert view.translation_source.text() == TOYOTA_PROFILE
        assert view.current_sentence is not None
        assert view.current_sentence.text == TOYOTA_PROFILE

        for character in TOYOTA_PROFILE:
            view._handle_key(_key(character))
        app.processEvents()

        assert not view.text_browser.isHidden()
        assert view.text_browser.toPlainText() == TOYOTA_PROFILE
        assert view.translation_source.text() == TOYOTA_PROFILE
        assert view.translation_text.text() == "丰田。这个日本品牌生产轿车、SUV 和混合动力汽车。"
        assert context.course_progress_service.get_item_progress(
            COURSE_ID, FIRST_ITEM
        ).status == "completed"
        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM article_sentences").fetchone()[0] == 0
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_car_course_typing_has_ai_read_aloud_controls(tmp_path: Path) -> None:
    app = _app()
    context = _context(tmp_path)
    window = MainWindow(context)
    try:
        window.show()
        window._start_course_lesson(COURSE_ID, DAY_ONE, "manual")
        app.processEvents()

        view = window.sentence_practice_view
        assert hasattr(view, "speech_controls")
        requested = []
        view.content_preparation_requested.disconnect(window._prepare_sentence_content)
        view.speech_requested.disconnect(window._request_speech)
        view.speech_requested.connect(lambda text, speed, controls: requested.append(text))

        for character in TOYOTA_PROFILE:
            view._handle_key(_key(character))
        app.processEvents()
        assert view.translation_status.text() == "课程译文"
        assert requested == [TOYOTA_PROFILE]
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_day_preview_lists_brand_profiles_for_learning(tmp_path: Path) -> None:
    _app()
    context = _context(tmp_path)
    page = CoursePage(context.course_repository, context.course_progress_service)
    try:
        page.show_lesson(COURSE_ID, DAY_ONE)
        assert page.lesson_items.count() == 5
        labels = [page.lesson_items.item(index).text() for index in range(5)]
        assert TOYOTA_PROFILE in labels[0]
        assert FIRST_DAY_PROFILES[1] in labels[1]
        assert not any("车标识别题" in label for label in labels)
    finally:
        page.close()
        context.database.close()


def test_missing_or_unsafe_logo_isolates_only_the_visual_course(tmp_path: Path) -> None:
    for mode in ("missing", "unsafe"):
        copied = tmp_path / mode / "courses"
        shutil.copytree(COURSES_ROOT, copied)
        asset = copied / "global-car-logos" / "assets" / "logos" / "toyota.svg"
        if mode == "missing":
            asset.unlink()
        else:
            asset.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
                encoding="utf-8",
            )

        catalog = CourseRepository(copied).load_catalog()

        assert [course.course_id for course in catalog.courses] == [
            "ai-large-models",
            "crypto-blockchain-english",
        ]
        assert len(catalog.failures) == 1
        assert catalog.failures[0].course_id == COURSE_ID
        assert "visual asset" in catalog.failures[0].reason


def test_specification_10_course_remains_backward_compatible() -> None:
    repository = CourseRepository()
    course = repository.get_course("ai-large-models")

    assert course is not None and course.specification_version == "1.0"
    sample = repository.get_sentence("ai-large-models", "ai-s0001")
    assert sample is not None and sample.visual_prompt is None
