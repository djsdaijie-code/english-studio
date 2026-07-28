from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import shutil
import sys

import pytest

from english_typing_trainer.courses import (
    CourseLoadError,
    CourseRepository,
    CourseValidationError,
)
from english_typing_trainer.courses.models import Course, CourseCatalog
from english_typing_trainer.courses.paths import default_courses_root


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def courses_root(tmp_path: Path) -> Path:
    destination = tmp_path / "courses"
    shutil.copytree(PROJECT_ROOT / "courses", destination)
    return destination


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def course_path(root: Path) -> Path:
    return root / "ai-large-models" / "course.json"


def unit_path(root: Path) -> Path:
    return root / "ai-large-models" / "units" / "unit-01-foundations.json"


def add_second_valid_course(root: Path) -> None:
    catalog = read_json(root / "catalog.json")
    next_order = max(item["default_order"] for item in catalog["courses"]) + 1
    catalog["courses"].append(
        {
            "course_id": "second-course",
            "title": "Second Course",
            "path": "second-course/course.json",
            "version": "1.0.0",
            "content_status": "reviewed",
            "default_order": next_order,
            "built_in": True,
            "read_only": True,
        }
    )
    write_json(root / "catalog.json", catalog)

    source = read_json(course_path(root))
    source.update(
        {
            "course_id": "second-course",
            "stable_key": "second-course-root",
            "title": "Second Course",
            "subtitle": "",
            "description": "A second valid course used for isolation tests.",
            "topics": ["testing"],
            "estimated_days": 1,
            "estimated_sentences": 1,
            "prerequisites": [],
            "learning_goals": ["Verify isolated loading"],
        }
    )
    source["levels"] = [
        {
            "level_id": "second-l1",
            "stable_key": "second-course-level-one",
            "order": 1,
            "title": "Level 1",
            "description": "",
            "difficulty": "beginner",
            "learning_goals": [],
            "units": [
                {
                    "unit_id": "second-l1-u01",
                    "stable_key": "second-course-unit-one",
                    "order": 1,
                    "title": "Unit 1",
                    "status": "planned",
                    "content_path": None,
                }
            ],
        }
    ]
    destination = root / "second-course" / "course.json"
    destination.parent.mkdir(parents=True)
    write_json(destination, source)


def test_loads_catalog_hierarchy_and_read_only_models() -> None:
    repository = CourseRepository()
    catalog = repository.load_catalog()

    assert isinstance(catalog, CourseCatalog)
    assert catalog.catalog_version == "1.3.0"
    assert [item.course_id for item in catalog.courses] == [
        "ai-large-models",
        "global-car-logos",
        "crypto-blockchain-english",
    ]
    assert catalog.failures == ()
    course = repository.get_course("ai-large-models")
    assert course is not None
    assert isinstance(course, Course)
    assert course.course_id == "ai-large-models"
    assert len(course.levels) == 5
    assert sum(len(level.units) for level in course.levels) == 8
    assert [level.order for level in course.levels] == [1, 2, 3, 4, 5]
    sample = repository.get_unit(course.course_id, "ai-l1-u01")
    assert sample is not None and sample.is_materialized
    assert len(sample.lessons) == 7
    assert len(sample.sentences) == 22
    assert isinstance(sample.sentences, tuple)
    with pytest.raises(FrozenInstanceError):
        course.title = "Changed"  # type: ignore[misc]


def test_queries_by_id_and_stable_key_and_returns_none_when_missing() -> None:
    repository = CourseRepository()

    assert repository.get_course("ai-large-models") is not None
    assert repository.get_level("ai-large-models", "ai-l1") is not None
    assert repository.get_unit("ai-large-models", "ai-l1-u01") is not None
    assert repository.get_lesson("ai-large-models", "ai-l1-u01-d01") is not None
    sentence = repository.get_sentence("ai-large-models", "ai-s0001")
    assert sentence is not None
    assert repository.get_sentence_by_stable_key("ai-large-models-sentence-0001") is sentence
    assert repository.get_course("missing") is None
    assert repository.get_sentence("ai-large-models", "missing") is None
    assert repository.get_sentence_by_stable_key("missing") is None


def test_loader_sorts_hierarchy_by_explicit_order(courses_root: Path) -> None:
    course = read_json(course_path(courses_root))
    course["levels"].reverse()
    for level in course["levels"]:
        level["units"].reverse()
    write_json(course_path(courses_root), course)
    unit = read_json(unit_path(courses_root))
    unit["lessons"].reverse()
    unit["sentences"].reverse()
    write_json(unit_path(courses_root), unit)

    loaded = CourseRepository(courses_root).get_course("ai-large-models")

    assert loaded is not None
    assert [level.order for level in loaded.levels] == [1, 2, 3, 4, 5]
    sample = loaded.levels[0].units[0]
    assert [lesson.order for lesson in sample.lessons] == [1, 2, 3, 4, 5, 6, 7]
    assert [(sentence.day, sentence.order) for sentence in sample.sentences] == sorted(
        (sentence.day, sentence.order) for sentence in sample.sentences
    )


def test_missing_catalog_is_a_clear_root_error(courses_root: Path) -> None:
    (courses_root / "catalog.json").unlink()

    with pytest.raises(CourseLoadError) as captured:
        CourseRepository(courses_root).load_catalog()

    assert captured.value.course_id is None
    assert captured.value.path == courses_root / "catalog.json"
    assert "missing" in captured.value.reason


def test_invalid_catalog_json_is_a_clear_validation_error(courses_root: Path) -> None:
    (courses_root / "catalog.json").write_text("{not-json", encoding="utf-8")

    with pytest.raises(CourseValidationError) as captured:
        CourseRepository(courses_root).load_catalog()

    assert "invalid JSON" in captured.value.reason
    assert captured.value.path.name == "catalog.json"


@pytest.mark.parametrize("failure", ["missing", "invalid_json", "schema"])
def test_bad_course_file_is_isolated(courses_root: Path, failure: str) -> None:
    add_second_valid_course(courses_root)
    path = course_path(courses_root)
    if failure == "missing":
        path.unlink()
    elif failure == "invalid_json":
        path.write_text("[broken", encoding="utf-8")
    else:
        course = read_json(path)
        del course["title"]
        write_json(path, course)

    catalog = CourseRepository(courses_root).load_catalog()

    assert [course.course_id for course in catalog.courses] == [
        "global-car-logos",
        "crypto-blockchain-english",
        "second-course",
    ]
    assert len(catalog.failures) == 1
    assert catalog.failures[0].course_id == "ai-large-models"
    assert catalog.failures[0].path == path
    assert catalog.failures[0].reason


def test_broken_lesson_reference_is_isolated(courses_root: Path) -> None:
    unit = read_json(unit_path(courses_root))
    unit["lessons"][0]["new_sentence_ids"].append("missing-sentence")
    write_json(unit_path(courses_root), unit)

    catalog = CourseRepository(courses_root).load_catalog()

    assert [course.course_id for course in catalog.courses] == [
        "global-car-logos",
        "crypto-blockchain-english",
    ]
    assert len(catalog.failures) == 1
    assert "missing-sentence" in catalog.failures[0].reason


def test_missing_materialized_unit_is_isolated(courses_root: Path) -> None:
    path = unit_path(courses_root)
    path.unlink()

    catalog = CourseRepository(courses_root).load_catalog()

    assert [course.course_id for course in catalog.courses] == [
        "global-car-logos",
        "crypto-blockchain-english",
    ]
    assert catalog.failures[0].path == path
    assert "missing" in catalog.failures[0].reason


@pytest.mark.parametrize("field", ["sentence_id", "stable_key"])
def test_duplicate_sentence_identity_is_rejected(courses_root: Path, field: str) -> None:
    unit = read_json(unit_path(courses_root))
    duplicate = dict(unit["sentences"][1])
    duplicate[field] = unit["sentences"][0][field]
    unit["sentences"][1] = duplicate
    write_json(unit_path(courses_root), unit)

    catalog = CourseRepository(courses_root).load_catalog()

    assert [course.course_id for course in catalog.courses] == [
        "global-car-logos",
        "crypto-blockchain-english",
    ]
    assert len(catalog.failures) == 1
    assert "duplicate" in catalog.failures[0].reason


def test_unsupported_specification_version_has_distinct_failure(courses_root: Path) -> None:
    course = read_json(course_path(courses_root))
    course["specification_version"] = "2.0"
    write_json(course_path(courses_root), course)

    catalog = CourseRepository(courses_root).load_catalog()

    assert [course.course_id for course in catalog.courses] == [
        "global-car-logos",
        "crypto-blockchain-english",
    ]
    assert catalog.failures[0].error_type == "UnsupportedCourseVersionError"
    assert "2.0" in catalog.failures[0].reason


def test_injected_root_and_default_root_do_not_depend_on_working_directory(
    courses_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    assert CourseRepository(courses_root).get_course("ai-large-models") is not None
    assert CourseRepository().get_course("ai-large-models") is not None


def test_pyinstaller_course_root_uses_meipass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shutil.copytree(PROJECT_ROOT / "courses", tmp_path / "courses")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert default_courses_root() == tmp_path / "courses"
    assert CourseRepository().get_course("ai-large-models") is not None


def test_cache_reuse_clear_and_reload(courses_root: Path) -> None:
    repository = CourseRepository(courses_root)
    first_catalog = repository.load_catalog()
    assert repository.load_catalog() is first_catalog
    original = repository.get_course("ai-large-models")
    assert original is not None

    course = read_json(course_path(courses_root))
    course["title"] = "Reloaded Course"
    write_json(course_path(courses_root), course)
    assert repository.get_course("ai-large-models") is original

    second_catalog = repository.reload()
    reloaded = repository.get_course("ai-large-models")
    assert second_catalog is not first_catalog
    assert reloaded is not None and reloaded.title == "Reloaded Course"

    repository.clear_cache()
    assert repository.load_catalog() is not second_catalog


def test_unsafe_catalog_path_is_isolated(courses_root: Path) -> None:
    catalog = read_json(courses_root / "catalog.json")
    catalog["courses"][0]["path"] = "../outside.json"
    write_json(courses_root / "catalog.json", catalog)

    loaded = CourseRepository(courses_root).load_catalog()

    assert [course.course_id for course in loaded.courses] == [
        "global-car-logos",
        "crypto-blockchain-english",
    ]
    assert "escapes" in loaded.failures[0].reason
