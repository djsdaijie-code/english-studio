from __future__ import annotations

import json
from pathlib import Path

from english_typing_trainer.database.migrations import LATEST_SCHEMA_VERSION
from scripts.validate_courses import main as validate_courses


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_course_content_contract_and_references_are_valid() -> None:
    assert validate_courses() == 0


def test_foundations_sample_stays_small_and_spans_two_days() -> None:
    path = PROJECT_ROOT / "courses" / "ai-large-models" / "units" / "unit-01-foundations.json"
    unit = json.loads(path.read_text(encoding="utf-8"))

    assert len(unit["sentences"]) == 12
    assert {sentence["day"] for sentence in unit["sentences"]} == {1, 2}
    assert all(sentence["status"] == "draft" for sentence in unit["sentences"])


def test_course_architecture_round_does_not_upgrade_database_schema() -> None:
    assert LATEST_SCHEMA_VERSION == 11
