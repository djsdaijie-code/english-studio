from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COURSES_ROOT = PROJECT_ROOT / "courses"
SCHEMA_ROOT = COURSES_ROOT / "schema"


class ValidationError(ValueError):
    pass


def load_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        return json.loads(text)
    except UnicodeDecodeError as exc:
        raise ValidationError(f"{path}: not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}:{exc.lineno}:{exc.colno}: {exc.msg}") from exc


def type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    raise ValidationError(f"unsupported schema type: {expected}")


def resolve_pointer(document: Any, pointer: str) -> Any:
    current = document
    for raw_part in pointer.removeprefix("#/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise ValidationError(f"unresolved JSON pointer: {pointer}")
        current = current[part]
    return current


def validate(
    value: Any,
    schema: dict[str, Any],
    *,
    root_schema: dict[str, Any],
    registry: dict[str, dict[str, Any]],
    location: str,
) -> None:
    if "$ref" in schema:
        reference = schema["$ref"]
        if reference.startswith("#/"):
            target = resolve_pointer(root_schema, reference)
            validate(value, target, root_schema=root_schema, registry=registry, location=location)
            return
        target_root = registry.get(reference)
        if target_root is None:
            raise ValidationError(f"{location}: unresolved schema reference {reference!r}")
        validate(value, target_root, root_schema=target_root, registry=registry, location=location)
        return

    if "oneOf" in schema:
        matches = 0
        messages: list[str] = []
        for option in schema["oneOf"]:
            try:
                validate(value, option, root_schema=root_schema, registry=registry, location=location)
            except ValidationError as exc:
                messages.append(str(exc))
            else:
                matches += 1
        if matches != 1:
            raise ValidationError(f"{location}: expected exactly one oneOf match, got {matches}; {' | '.join(messages)}")
        return

    if "const" in schema and value != schema["const"]:
        raise ValidationError(f"{location}: expected constant {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{location}: {value!r} is not in {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type and not type_matches(value, expected_type):
        raise ValidationError(f"{location}: expected {expected_type}, got {type(value).__name__}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ValidationError(f"{location}: missing required fields {missing!r}")
        if len(value) < schema.get("minProperties", 0):
            raise ValidationError(f"{location}: too few properties")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                raise ValidationError(f"{location}: unexpected fields {unexpected!r}")
        for key, child in value.items():
            if key in properties:
                validate(child, properties[key], root_schema=root_schema, registry=registry, location=f"{location}.{key}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ValidationError(f"{location}: too few items")
        if schema.get("uniqueItems"):
            normalized = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(normalized) != len(set(normalized)):
                raise ValidationError(f"{location}: duplicate array items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate(item, item_schema, root_schema=root_schema, registry=registry, location=f"{location}[{index}]")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ValidationError(f"{location}: string is too short")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            raise ValidationError(f"{location}: {value!r} does not match {pattern!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError(f"{location}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError(f"{location}: {value} is above maximum {schema['maximum']}")


def load_schema_registry() -> tuple[dict[str, dict[str, Any]], dict[str, Path]]:
    registry: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    schema_files = sorted(SCHEMA_ROOT.glob("*.schema.json"))
    if len(schema_files) != 4:
        raise ValidationError(f"expected 4 schema files, found {len(schema_files)}")
    for path in schema_files:
        schema = load_json(path)
        if not isinstance(schema, dict):
            raise ValidationError(f"{path}: schema root must be an object")
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise ValidationError(f"{path}: unsupported or missing $schema")
        if not isinstance(schema.get("$id"), str) or not schema["$id"]:
            raise ValidationError(f"{path}: missing $id")
        if schema.get("type") != "object":
            raise ValidationError(f"{path}: root schema must describe an object")
        registry[path.name] = schema
        registry[schema["$id"]] = schema
        paths[path.name] = path
    return registry, paths


def validate_document(path: Path, schema_name: str, registry: dict[str, dict[str, Any]]) -> Any:
    value = load_json(path)
    schema = registry[schema_name]
    validate(value, schema, root_schema=schema, registry=registry, location=str(path.relative_to(PROJECT_ROOT)))
    return value


def assert_unique(values: list[str], label: str) -> None:
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValidationError(f"duplicate {label}: {duplicates!r}")


def validate_course_graph(registry: dict[str, dict[str, Any]]) -> tuple[int, int, int]:
    catalog_path = COURSES_ROOT / "catalog.json"
    catalog = load_json(catalog_path)
    if not isinstance(catalog, dict) or set(catalog) != {"catalog_version", "courses"}:
        raise ValidationError("courses/catalog.json: invalid catalog fields")
    if not isinstance(catalog["courses"], list) or not catalog["courses"]:
        raise ValidationError("courses/catalog.json: courses must be a non-empty array")

    catalog_ids: list[str] = []
    entity_stable_keys: dict[tuple[str, str], str] = {}
    course_count = unit_count = sentence_count = 0

    for course_entry in catalog["courses"]:
        required = {"course_id", "title", "path", "version", "content_status", "default_order", "built_in", "read_only"}
        if not isinstance(course_entry, dict) or set(course_entry) != required:
            raise ValidationError("courses/catalog.json: invalid course entry fields")
        catalog_ids.append(course_entry["course_id"])
        course_path = (COURSES_ROOT / course_entry["path"]).resolve()
        if COURSES_ROOT.resolve() not in course_path.parents or not course_path.is_file():
            raise ValidationError(f"catalog path is missing or unsafe: {course_entry['path']!r}")
        course = validate_document(course_path, "course.schema.json", registry)
        course_count += 1
        if course["course_id"] != course_entry["course_id"] or course["version"] != course_entry["version"]:
            raise ValidationError(f"{course_path}: catalog identity/version mismatch")
        if course["status"] != course_entry["content_status"]:
            raise ValidationError(f"{course_path}: catalog status mismatch")
        if course["built_in"] != course_entry["built_in"] or course["read_only"] != course_entry["read_only"]:
            raise ValidationError(f"{course_path}: catalog access flags mismatch")

        level_ids = [level["level_id"] for level in course["levels"]]
        assert_unique(level_ids, f"level_id in {course['course_id']}")
        assert_unique([level["order"] for level in course["levels"]], f"level order in {course['course_id']}")
        unit_ids_in_course: list[str] = []
        for level in course["levels"]:
            entity_stable_keys[("level", level["level_id"])] = level["stable_key"]
            assert_unique([entry["order"] for entry in level["units"]], f"unit order in {level['level_id']}")
            for unit_entry in level["units"]:
                unit_ids_in_course.append(unit_entry["unit_id"])
                entity_stable_keys[("unit", unit_entry["unit_id"])] = unit_entry["stable_key"]
                relative = unit_entry["content_path"]
                if relative is None:
                    if unit_entry["status"] != "planned":
                        raise ValidationError(f"{unit_entry['unit_id']}: missing content_path requires planned status")
                    continue
                unit_path = (course_path.parent / relative).resolve()
                if course_path.parent.resolve() not in unit_path.parents or not unit_path.is_file():
                    raise ValidationError(f"{course_path}: missing or unsafe unit path {relative!r}")
                unit = validate_document(unit_path, "unit.schema.json", registry)
                unit_count += 1
                if unit["course_id"] != course["course_id"] or unit["level_id"] != level["level_id"]:
                    raise ValidationError(f"{unit_path}: course/level identity mismatch")
                if unit["unit_id"] != unit_entry["unit_id"] or unit["stable_key"] != unit_entry["stable_key"]:
                    raise ValidationError(f"{unit_path}: unit manifest identity mismatch")
                if unit["status"] != unit_entry["status"]:
                    raise ValidationError(f"{unit_path}: unit manifest status mismatch")
                validate_unit_graph(unit, unit_path, entity_stable_keys)
                sentence_count += len(unit["sentences"])
        assert_unique(unit_ids_in_course, f"unit_id in {course['course_id']}")
        entity_stable_keys[("course", course["course_id"])] = course["stable_key"]

    assert_unique(catalog_ids, "catalog course_id")
    assert_unique(list(entity_stable_keys.values()), "entity stable_key")
    return course_count, unit_count, sentence_count


def validate_unit_graph(unit: dict[str, Any], path: Path, stable_keys: dict[tuple[str, str], str]) -> None:
    lesson_ids = [lesson["lesson_id"] for lesson in unit["lessons"]]
    sentence_ids = [sentence["sentence_id"] for sentence in unit["sentences"]]
    assert_unique(lesson_ids, f"lesson_id in {path.name}")
    assert_unique(sentence_ids, f"sentence_id in {path.name}")
    assert_unique([lesson["day"] for lesson in unit["lessons"]], f"lesson day in {path.name}")

    lessons = {lesson["lesson_id"]: lesson for lesson in unit["lessons"]}
    sentence_id_set = set(sentence_ids)
    for lesson in unit["lessons"]:
        stable_keys[("lesson", lesson["lesson_id"])] = lesson["stable_key"]
        if lesson["unit_id"] != unit["unit_id"]:
            raise ValidationError(f"{path}: lesson {lesson['lesson_id']} has wrong unit_id")
        referenced = lesson["new_sentence_ids"] + lesson["review_sentence_ids"]
        for activity in lesson["activities"]:
            referenced.extend(activity["sentence_ids"])
        if lesson["assessment"] is not None:
            referenced.extend(lesson["assessment"]["sentence_ids"])
        missing = sorted(set(referenced) - sentence_id_set)
        if missing:
            raise ValidationError(f"{path}: lesson {lesson['lesson_id']} references missing sentences {missing!r}")

    orders_by_lesson: dict[str, list[int]] = {}
    for sentence in unit["sentences"]:
        stable_keys[("sentence", sentence["sentence_id"])] = sentence["stable_key"]
        lesson = lessons.get(sentence["lesson_id"])
        if lesson is None:
            raise ValidationError(f"{path}: sentence {sentence['sentence_id']} has missing lesson")
        if sentence["unit_id"] != unit["unit_id"] or sentence["day"] != lesson["day"]:
            raise ValidationError(f"{path}: sentence {sentence['sentence_id']} has inconsistent unit/day")
        if sentence["sentence_id"] not in lesson["new_sentence_ids"]:
            raise ValidationError(f"{path}: sentence {sentence['sentence_id']} is not owned by its lesson")
        orders_by_lesson.setdefault(sentence["lesson_id"], []).append(sentence["order"])
        check_fixed_casing(sentence["english"], f"{path.name}:{sentence['sentence_id']}.english")
        for word in sentence["core_words"]:
            check_fixed_casing(word, f"{path.name}:{sentence['sentence_id']}.core_words")
    for lesson_id, orders in orders_by_lesson.items():
        assert_unique(orders, f"sentence order in {lesson_id}")


def check_fixed_casing(text: str, location: str) -> None:
    forbidden = ["Github", "Api", "Json", "english studio"]
    for form in forbidden:
        if re.search(rf"(?<![A-Za-z]){re.escape(form)}(?![A-Za-z])", text):
            raise ValidationError(f"{location}: use fixed casing instead of {form!r}")
    if re.search(r"(?<![A-Za-z])python(?![A-Za-z])", text):
        raise ValidationError(f"{location}: use 'Python'")


def validate_templates(registry: dict[str, dict[str, Any]]) -> None:
    mapping = {
        "course.template.json": "course.schema.json",
        "unit.template.json": "unit.schema.json",
        "lesson.template.json": "lesson.schema.json",
        "sentence.template.json": "sentence.schema.json",
    }
    for template_name, schema_name in mapping.items():
        validate_document(COURSES_ROOT / "templates" / template_name, schema_name, registry)


def main() -> int:
    try:
        registry, schema_paths = load_schema_registry()
        for schema_name, schema_path in schema_paths.items():
            schema = registry[schema_name]
            validate({}, {"type": "object"}, root_schema=schema, registry=registry, location=str(schema_path))
        validate_templates(registry)
        course_count, unit_count, sentence_count = validate_course_graph(registry)
    except ValidationError as exc:
        print(f"Course validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        "Course validation passed: "
        f"4 schemas, 4 templates, {course_count} course, {unit_count} materialized unit, "
        f"{sentence_count} sentences; references, IDs, stable keys, casing, and UTF-8 are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
