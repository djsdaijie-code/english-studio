from __future__ import annotations

import json
from pathlib import Path

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.migrations import LATEST_SCHEMA_VERSION
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from scripts.qa_course_content import main as qa_course_content
from scripts.validate_courses import main as validate_courses


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_course_content_contract_and_references_are_valid() -> None:
    assert validate_courses() == 0


def test_ai_course_candidate_has_complete_reviewed_shape() -> None:
    course_root = PROJECT_ROOT / "courses" / "ai-large-models"
    course = json.loads((course_root / "course.json").read_text(encoding="utf-8"))
    units = [unit for level in course["levels"] for unit in level["units"]]
    unit_documents = [
        json.loads((course_root / unit["content_path"]).read_text(encoding="utf-8"))
        for unit in units
    ]

    assert course["version"] == "1.0.0"
    assert course["content_version"] == "1.0.0"
    assert course["status"] == "reviewed"
    assert len(course["levels"]) == 5
    assert len(units) == 8
    assert sum(len(unit["lessons"]) for unit in unit_documents) == 56
    assert sum(len(unit["sentences"]) for unit in unit_documents) == 176
    assert all(unit["status"] == "reviewed" for unit in unit_documents)
    assert all(len(unit["lessons"]) == 7 for unit in unit_documents)
    assert all(len(unit["sentences"]) == 22 for unit in unit_documents)
    day_six_lessons = [unit["lessons"][5] for unit in unit_documents]
    assert all(lesson["lesson_type"] == "review" for lesson in day_six_lessons)
    assert all("朗读" not in lesson["title"] for lesson in day_six_lessons)
    assert all(
        any(
            activity["activity_type"] == "reinforcement" and activity["required"]
            for activity in lesson["activities"]
        )
        for lesson in day_six_lessons
    )


def test_original_foundations_samples_and_stable_keys_are_preserved() -> None:
    path = PROJECT_ROOT / "courses" / "ai-large-models" / "units" / "unit-01-foundations.json"
    unit = json.loads(path.read_text(encoding="utf-8"))
    original = unit["sentences"][:12]
    expected_text = [
        ("Start a new chat.", "新建一个对话。"),
        ("Type your message here.", "在这里输入你的消息。"),
        ("Send the message when ready.", "准备好后发送消息。"),
        ("Stop generating the response.", "停止生成回答。"),
        ("Try the request again.", "再次尝试这个请求。"),
        ("Copy the answer to your notes.", "把回答复制到你的笔记中。"),
        ("Save this useful response.", "保存这个有用的回答。"),
        ("Upload the file here.", "把文件上传到这里。"),
        ("Open the uploaded file.", "打开已上传的文件。"),
        ("Check the answer before saving it.", "保存前检查一下回答。"),
        ("Download the result to your computer.", "把结果下载到你的电脑。"),
        ("Delete the empty chat.", "删除这个空对话。"),
    ]

    assert [sentence["stable_key"] for sentence in original] == [
        f"ai-large-models-sentence-{number:04d}" for number in range(1, 13)
    ]
    assert [(sentence["english"], sentence["chinese"]) for sentence in original] == expected_text
    assert all(sentence["status"] == "reviewed" for sentence in unit["sentences"])


def test_ai_course_content_quality_policy() -> None:
    assert qa_course_content() == 0


def test_every_unit_new_and_review_day_builds_a_typing_session_without_articles(tmp_path: Path) -> None:
    context = build_app_context(
        data_dir=tmp_path / "data",
        credential_store=MemoryCredentialStore(),
    )
    try:
        course = context.course_repository.get_course("ai-large-models")
        assert course is not None
        units = [unit for level in course.levels for unit in level.units]
        assert len(units) == 8
        for unit in units:
            assert len(unit.lessons) == 7
            first_day = context.course_learning_service.build_session(
                course.course_id,
                unit.lessons[0].lesson_id,
                "manual",
            )
            review_day = context.course_learning_service.build_session(
                course.course_id,
                unit.lessons[-1].lesson_id,
                "review",
            )
            assert first_day.typing_sentences
            assert review_day.typing_sentences
            assert len(first_day.chinese_translations) == len(first_day.typing_sentences)
            assert len(review_day.activity_types_by_item) == len(review_day.typing_sentences)
            assert len(first_day.has_vocabulary_by_item) == len(first_day.typing_sentences)
            assert len(first_day.core_words_by_item) == len(first_day.typing_sentences)
            assert len(first_day.core_patterns_by_item) == len(first_day.typing_sentences)
            assert all(first_day.chinese_translations)

        connection = context.database.connect()
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM article_sentences").fetchone()[0] == 0
    finally:
        context.database.close()


def test_course_progress_round_upgrades_database_schema_once() -> None:
    assert LATEST_SCHEMA_VERSION == 13
