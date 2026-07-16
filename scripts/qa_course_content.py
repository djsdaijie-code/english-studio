from __future__ import annotations

from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
COURSES_ROOT = PROJECT_ROOT / "courses"
COURSE_ROOT = COURSES_ROOT / "ai-large-models"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from english_typing_trainer.courses.errors import CourseLoadError  # noqa: E402
from english_typing_trainer.courses.validation import CourseValidator  # noqa: E402


LEVEL_WORD_LIMITS = {
    "ai-l1": 10,
    "ai-l2": 12,
    "ai-l3": 16,
    "ai-l4": 20,
    "ai-l5": 20,
}

LEVEL_WORD_MINIMUMS = {
    "ai-l1": 4,
    "ai-l2": 6,
    "ai-l3": 8,
    "ai-l4": 10,
    "ai-l5": 10,
}

REQUIRED_COVERAGE = (
    "open",
    "start",
    "stop",
    "send",
    "copy",
    "save",
    "upload",
    "download",
    "use",
    "choose",
    "switch",
    "compare",
    "check",
    "fix",
    "retry",
    "explain",
    "summarize",
    "translate",
    "rewrite",
    "generate",
    "create",
    "add",
    "remove",
    "keep",
    "include",
    "exclude",
    "follow",
    "request",
    "response",
    "result",
    "output",
    "input",
    "prompt",
    "model",
    "file",
    "document",
    "image",
    "error",
    "format",
    "context",
    "token",
    "api key",
    "parameter",
    "endpoint",
    "rate limit",
    "system message",
    "agent",
    "tool",
    "task",
    "workflow",
    "trigger",
    "condition",
    "permission",
)

REQUIRED_PATTERNS = {
    "Which ... should I use?": re.compile(r"^which .+ should i use\?$", re.IGNORECASE),
    "Please explain ...": re.compile(r"^please explain\b", re.IGNORECASE),
    "Make it ...": re.compile(r"^make (?:it|the )", re.IGNORECASE),
    "Do not include ...": re.compile(r"^do not include\b", re.IGNORECASE),
    "Keep only ...": re.compile(r"^keep only\b", re.IGNORECASE),
    "What is the difference between ...?": re.compile(r"^what is the difference between\b", re.IGNORECASE),
    "The request failed because ...": re.compile(r"^the request failed because\b", re.IGNORECASE),
    "If ..., then ...": re.compile(r"^if\b", re.IGNORECASE),
    "Before ..., ...": re.compile(r"^before\b", re.IGNORECASE),
    "The agent should ...": re.compile(r"^the agent should\b", re.IGNORECASE),
}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", text))


def _normalized(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _required_activity_types(lesson: dict[str, Any]) -> set[str]:
    return {
        activity["activity_type"]
        for activity in lesson["activities"]
        if activity["required"]
    }


def _coverage_corpus(sentences: list[dict[str, Any]]) -> str:
    values: list[str] = []
    for sentence in sentences:
        values.append(sentence["english"])
        values.extend(sentence["core_words"])
        values.extend(sentence["core_patterns"])
        values.extend(item["english"] for item in sentence["alternative_expressions"])
    return "\n".join(values).lower()


def collect_errors() -> tuple[list[str], list[str]]:
    errors: list[str] = []
    summaries: list[str] = []

    try:
        CourseValidator(COURSES_ROOT).validate_tree()
    except CourseLoadError as exc:
        return [f"shared course validation failed: {exc}"], summaries

    catalog = _read_json(COURSES_ROOT / "catalog.json")
    course = _read_json(COURSE_ROOT / "course.json")
    levels = course["levels"]
    unit_entries = [unit for level in levels for unit in level["units"]]

    if len(levels) != 5:
        errors.append(f"expected 5 levels, found {len(levels)}")
    if len(unit_entries) != 8:
        errors.append(f"expected 8 units, found {len(unit_entries)}")
    if course["version"] != "1.0.0" or course["content_version"] != "1.0.0":
        errors.append("course and content versions must both be 1.0.0")
    if course["status"] != "reviewed":
        errors.append("course status must be reviewed")
    if course["estimated_days"] != 56 or course["estimated_sentences"] != 176:
        errors.append("course estimates must match 56 Days and 176 sentences")
    if catalog["catalog_version"] != "1.1.0":
        errors.append("catalog version must be 1.1.0")
    catalog_entry = next((item for item in catalog["courses"] if item["course_id"] == course["course_id"]), None)
    if catalog_entry is None:
        errors.append("catalog is missing ai-large-models")
    elif catalog_entry["version"] != course["version"] or catalog_entry["content_status"] != course["status"]:
        errors.append("catalog version/status do not match the course")

    all_sentences: list[dict[str, Any]] = []
    all_lessons: list[dict[str, Any]] = []
    level_counts: dict[str, list[int]] = {level["level_id"]: [] for level in levels}

    for entry in unit_entries:
        content_path = entry["content_path"]
        if content_path is None:
            errors.append(f"{entry['unit_id']} is not materialized")
            continue
        unit = _read_json(COURSE_ROOT / content_path)
        lessons = sorted(unit["lessons"], key=lambda item: item["day"])
        sentences = unit["sentences"]
        all_lessons.extend(lessons)
        all_sentences.extend(sentences)
        level_counts[unit["level_id"]].extend(_word_count(item["english"]) for item in sentences)

        if entry["status"] != "reviewed" or unit["status"] != "reviewed":
            errors.append(f"{unit['unit_id']} status is not reviewed")
        if unit["content_version"] != "1.0.0":
            errors.append(f"{unit['unit_id']} content_version is not 1.0.0")
        if len(lessons) != 7 or [item["day"] for item in lessons] != list(range(1, 8)):
            errors.append(f"{unit['unit_id']} must contain Days 1-7")
            continue
        if not 21 <= len(sentences) <= 24:
            errors.append(f"{unit['unit_id']} has {len(sentences)} sentences; expected 21-24")

        owned_new_ids: list[str] = []
        for lesson in lessons:
            required = _required_activity_types(lesson)
            if lesson["status"] != "reviewed" or lesson["content_version"] != "1.0.0":
                errors.append(f"{lesson['lesson_id']} is not reviewed at content version 1.0.0")
            if lesson["day"] <= 4:
                if lesson["lesson_type"] != "new_content" or not 4 <= len(lesson["new_sentence_ids"]) <= 7:
                    errors.append(f"{lesson['lesson_id']} must be a 4-7 sentence new-content Day")
                if "typing" not in required:
                    errors.append(f"{lesson['lesson_id']} must require typing")
                owned_new_ids.extend(lesson["new_sentence_ids"])
            elif lesson["new_sentence_ids"]:
                errors.append(f"{lesson['lesson_id']} must not introduce new core sentences")

        if set(owned_new_ids) != {item["sentence_id"] for item in sentences}:
            errors.append(f"{unit['unit_id']} Days 1-4 do not own exactly the unit sentences")
        if lessons[4]["lesson_type"] not in {"scenario", "reading"} or not lessons[4]["review_sentence_ids"]:
            errors.append(f"{unit['unit_id']} Day 5 must be a review-based scenario or reading")
        if not {"dictation", "speaking"}.issubset(_required_activity_types(lessons[5])):
            errors.append(f"{unit['unit_id']} Day 6 must require dictation and speaking")
        day7_types = _required_activity_types(lessons[6])
        if "self_test" not in day7_types or lessons[6]["assessment"] is None:
            errors.append(f"{unit['unit_id']} Day 7 must require self_test and define an assessment")
        fsrs_activities = [item for item in lessons[6]["activities"] if item["activity_type"] == "fsrs"]
        if not fsrs_activities or any(item["required"] for item in fsrs_activities):
            errors.append(f"{unit['unit_id']} Day 7 must offer optional FSRS review")

        word_limit = LEVEL_WORD_LIMITS[unit["level_id"]]
        for sentence in sentences:
            words = _word_count(sentence["english"])
            if words > word_limit or words > 25:
                errors.append(f"{sentence['sentence_id']} has {words} words; limit is {word_limit}")
            if sentence["status"] != "reviewed" or sentence["content_version"] != "1.0.0":
                errors.append(f"{sentence['sentence_id']} is not reviewed at content version 1.0.0")
            if not sentence["core_words"] or not sentence["core_patterns"]:
                errors.append(f"{sentence['sentence_id']} is missing vocabulary or pattern metadata")
            if not re.search(r"[.!?]$", sentence["english"]):
                errors.append(f"{sentence['sentence_id']} is missing final English punctuation")

        summaries.append(f"{unit['unit_id']}: {len(lessons)} Days, {len(sentences)} sentences")

    if len(all_lessons) != 56:
        errors.append(f"expected 56 Days, found {len(all_lessons)}")
    if not 168 <= len(all_sentences) <= 192 or len(all_sentences) != 176:
        errors.append(f"expected the 176-sentence candidate, found {len(all_sentences)}")
    if sum(len(_read_json(COURSE_ROOT / item["content_path"])["sentences"]) for item in unit_entries[:4]) != 88:
        errors.append("Units 1-4 must contain 88 general-use sentences")
    if sum(len(_read_json(COURSE_ROOT / item["content_path"])["sentences"]) for item in unit_entries[4:]) != 88:
        errors.append("Units 5-8 must contain 88 technical-use sentences")

    normalized: dict[str, str] = {}
    for sentence in all_sentences:
        value = _normalized(sentence["english"])
        previous = normalized.get(value)
        if previous is not None:
            errors.append(f"exact duplicate English: {previous} and {sentence['sentence_id']}")
        normalized[value] = sentence["sentence_id"]
    for index, left in enumerate(all_sentences):
        left_value = _normalized(left["english"])
        for right in all_sentences[index + 1 :]:
            right_value = _normalized(right["english"])
            if SequenceMatcher(None, left_value, right_value).ratio() >= 0.92:
                errors.append(f"near-duplicate English: {left['sentence_id']} and {right['sentence_id']}")

    corpus = _coverage_corpus(all_sentences)
    missing_terms = [term for term in REQUIRED_COVERAGE if term not in corpus]
    if missing_terms:
        errors.append(f"missing required vocabulary coverage: {missing_terms}")
    english_values = [item["english"] for item in all_sentences]
    missing_patterns = [name for name, pattern in REQUIRED_PATTERNS.items() if not any(pattern.search(text) for text in english_values)]
    if missing_patterns:
        errors.append(f"missing required pattern coverage: {missing_patterns}")

    expected_original_keys = {f"ai-large-models-sentence-{number:04d}" for number in range(1, 13)}
    expected_all_keys = {f"ai-large-models-sentence-{number:04d}" for number in range(1, 177)}
    expected_all_ids = {f"ai-s{number:04d}" for number in range(1, 177)}
    actual_keys = {item["stable_key"] for item in all_sentences}
    actual_ids = {item["sentence_id"] for item in all_sentences}
    if not expected_original_keys.issubset(actual_keys):
        errors.append("one or more original Unit 1 stable keys were not preserved")
    if actual_keys != expected_all_keys:
        errors.append("sentence stable keys must form the unique sequence 0001-0176")
    if actual_ids != expected_all_ids:
        errors.append("sentence IDs must form the unique sequence ai-s0001-ai-s0176")

    for level_id, counts in level_counts.items():
        if counts:
            recommended_count = sum(value >= LEVEL_WORD_MINIMUMS[level_id] for value in counts)
            if recommended_count / len(counts) < 0.5:
                errors.append(
                    f"{level_id} has only {recommended_count}/{len(counts)} sentences at or above the recommended minimum length"
                )
            summaries.append(
                f"{level_id}: {len(counts)} sentences, word range {min(counts)}-{max(counts)}, "
                f"average {sum(counts) / len(counts):.1f}, recommended-length {recommended_count}/{len(counts)}"
            )
    return errors, summaries


def main() -> int:
    errors, summaries = collect_errors()
    if errors:
        print("Course content QA failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("Course content QA passed: 5 levels, 8 units, 56 Days, 176 reviewed sentences; general/technical split is 88/88.")
    for summary in summaries:
        print(f"- {summary}")
    print("- exact and near-duplicate English: 0")
    print(f"- required vocabulary: {len(REQUIRED_COVERAGE)}/{len(REQUIRED_COVERAGE)}; required patterns: {len(REQUIRED_PATTERNS)}/{len(REQUIRED_PATTERNS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
