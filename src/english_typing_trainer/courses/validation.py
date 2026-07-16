from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any

from english_typing_trainer.courses.errors import (
    CourseLoadError,
    CourseValidationError,
    UnsupportedCourseVersionError,
)
from english_typing_trainer.courses.paths import resolve_safe_relative


SUPPORTED_SPECIFICATION_VERSIONS = frozenset({"1.0"})
SCHEMA_NAMES = (
    "course.schema.json",
    "lesson.schema.json",
    "sentence.schema.json",
    "unit.schema.json",
)


@dataclass(frozen=True, slots=True)
class ValidationSummary:
    schema_count: int
    template_count: int
    course_count: int
    unit_count: int
    sentence_count: int


@dataclass(slots=True)
class LoadedCourseData:
    catalog_entry: dict[str, Any]
    course: dict[str, Any]
    units: dict[str, dict[str, Any]]
    course_path: Path


class SchemaValidationFailure(ValueError):
    pass


def read_json_utf8(path: Path) -> Any:
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except FileNotFoundError:
        raise
    except UnicodeDecodeError as exc:
        raise SchemaValidationFailure("file is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise SchemaValidationFailure(f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}") from exc


def _type_matches(value: Any, expected: str) -> bool:
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
    raise SchemaValidationFailure(f"unsupported schema type: {expected}")


def _resolve_pointer(document: Any, pointer: str) -> Any:
    current = document
    for raw_part in pointer.removeprefix("#/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, dict) or part not in current:
            raise SchemaValidationFailure(f"unresolved JSON pointer: {pointer}")
        current = current[part]
    return current


def validate_schema_value(
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
            target = _resolve_pointer(root_schema, reference)
            validate_schema_value(value, target, root_schema=root_schema, registry=registry, location=location)
            return
        target_root = registry.get(reference)
        if target_root is None:
            raise SchemaValidationFailure(f"{location}: unresolved schema reference {reference!r}")
        validate_schema_value(value, target_root, root_schema=target_root, registry=registry, location=location)
        return

    if "oneOf" in schema:
        matches = 0
        messages: list[str] = []
        for option in schema["oneOf"]:
            try:
                validate_schema_value(value, option, root_schema=root_schema, registry=registry, location=location)
            except SchemaValidationFailure as exc:
                messages.append(str(exc))
            else:
                matches += 1
        if matches != 1:
            detail = " | ".join(messages)
            raise SchemaValidationFailure(f"{location}: expected one oneOf match, got {matches}; {detail}")
        return

    if "const" in schema and value != schema["const"]:
        raise SchemaValidationFailure(f"{location}: expected constant {schema['const']!r}, got {value!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaValidationFailure(f"{location}: {value!r} is not in {schema['enum']!r}")

    expected_type = schema.get("type")
    if expected_type and not _type_matches(value, expected_type):
        raise SchemaValidationFailure(f"{location}: expected {expected_type}, got {type(value).__name__}")

    if isinstance(value, dict):
        missing = [key for key in schema.get("required", []) if key not in value]
        if missing:
            raise SchemaValidationFailure(f"{location}: missing required fields {missing!r}")
        if len(value) < schema.get("minProperties", 0):
            raise SchemaValidationFailure(f"{location}: too few properties")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            unexpected = sorted(set(value) - set(properties))
            if unexpected:
                raise SchemaValidationFailure(f"{location}: unexpected fields {unexpected!r}")
        for key, child in value.items():
            if key in properties:
                validate_schema_value(
                    child,
                    properties[key],
                    root_schema=root_schema,
                    registry=registry,
                    location=f"{location}.{key}",
                )

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise SchemaValidationFailure(f"{location}: too few items")
        if schema.get("uniqueItems"):
            normalized = [json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value]
            if len(normalized) != len(set(normalized)):
                raise SchemaValidationFailure(f"{location}: duplicate array items")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_schema_value(
                    item,
                    item_schema,
                    root_schema=root_schema,
                    registry=registry,
                    location=f"{location}[{index}]",
                )

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise SchemaValidationFailure(f"{location}: string is too short")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            raise SchemaValidationFailure(f"{location}: {value!r} does not match {pattern!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaValidationFailure(f"{location}: {value} is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaValidationFailure(f"{location}: {value} is above maximum {schema['maximum']}")


class CourseValidator:
    """Shared runtime and command-line validation for a course resource root."""

    def __init__(
        self,
        courses_root: Path,
        *,
        supported_specification_versions: frozenset[str] = SUPPORTED_SPECIFICATION_VERSIONS,
    ) -> None:
        self.courses_root = courses_root.resolve()
        self.schema_root = self.courses_root / "schema"
        self.supported_specification_versions = supported_specification_versions
        self._registry: dict[str, dict[str, Any]] | None = None

    def load_schema_registry(self) -> dict[str, dict[str, Any]]:
        if self._registry is not None:
            return self._registry
        registry: dict[str, dict[str, Any]] = {}
        for name in SCHEMA_NAMES:
            path = self.schema_root / name
            try:
                schema = read_json_utf8(path)
            except FileNotFoundError as exc:
                raise CourseLoadError("required schema file is missing", path=path) from exc
            except SchemaValidationFailure as exc:
                raise CourseValidationError(str(exc), path=path) from exc
            if not isinstance(schema, dict):
                raise CourseValidationError("schema root must be an object", path=path)
            if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
                raise CourseValidationError("unsupported or missing $schema", path=path)
            if not isinstance(schema.get("$id"), str) or not schema["$id"]:
                raise CourseValidationError("missing $id", path=path)
            if schema.get("type") != "object":
                raise CourseValidationError("root schema must describe an object", path=path)
            registry[name] = schema
            registry[schema["$id"]] = schema
        self._registry = registry
        return registry

    def load_catalog_document(self) -> dict[str, Any]:
        path = self.courses_root / "catalog.json"
        try:
            catalog = read_json_utf8(path)
        except FileNotFoundError as exc:
            raise CourseLoadError("catalog file is missing", path=path) from exc
        except SchemaValidationFailure as exc:
            raise CourseValidationError(str(exc), path=path) from exc
        if not isinstance(catalog, dict) or set(catalog) != {"catalog_version", "courses"}:
            raise CourseValidationError("invalid catalog fields", path=path)
        if not isinstance(catalog["catalog_version"], str) or not catalog["catalog_version"]:
            raise CourseValidationError("catalog_version must be a non-empty string", path=path)
        if not isinstance(catalog["courses"], list) or not catalog["courses"]:
            raise CourseValidationError("courses must be a non-empty array", path=path)
        required = {
            "course_id",
            "title",
            "path",
            "version",
            "content_status",
            "default_order",
            "built_in",
            "read_only",
        }
        course_ids: list[str] = []
        orders: list[int] = []
        for index, entry in enumerate(catalog["courses"]):
            if not isinstance(entry, dict) or set(entry) != required:
                raise CourseValidationError(f"invalid course entry fields at index {index}", path=path)
            for field in ("course_id", "title", "path", "version", "content_status"):
                if not isinstance(entry[field], str) or not entry[field]:
                    raise CourseValidationError(f"invalid {field} at index {index}", path=path)
            if re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", entry["course_id"]) is None:
                raise CourseValidationError(f"invalid course_id at index {index}", path=path)
            if re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?", entry["version"]) is None:
                raise CourseValidationError(f"invalid version at index {index}", path=path)
            if entry["content_status"] not in {"draft", "reviewed", "published", "deprecated"}:
                raise CourseValidationError(f"invalid content_status at index {index}", path=path)
            if not isinstance(entry["default_order"], int) or isinstance(entry["default_order"], bool) or entry["default_order"] < 1:
                raise CourseValidationError(f"invalid default_order at index {index}", path=path)
            if not isinstance(entry["built_in"], bool) or not isinstance(entry["read_only"], bool):
                raise CourseValidationError(f"invalid access flags at index {index}", path=path)
            course_ids.append(entry["course_id"])
            orders.append(entry["default_order"])
        self._assert_unique(course_ids, "catalog course_id", path=path)
        self._assert_unique(orders, "catalog default_order", path=path)
        return catalog

    def load_course_data(self, entry: dict[str, Any]) -> LoadedCourseData:
        course_id = entry["course_id"]
        try:
            course_path = resolve_safe_relative(self.courses_root, entry["path"])
        except ValueError as exc:
            raise CourseValidationError(str(exc), path=self.courses_root / entry["path"], course_id=course_id) from exc
        course = self._read_document(course_path, course_id)
        self._check_specification_version(course, course_path, course_id)
        self._validate_document(course, "course.schema.json", course_path, course_id)

        if course["course_id"] != course_id or course["version"] != entry["version"]:
            raise CourseValidationError("catalog identity or version does not match course", path=course_path, course_id=course_id)
        if course["status"] != entry["content_status"]:
            raise CourseValidationError("catalog status does not match course", path=course_path, course_id=course_id)
        if course["built_in"] != entry["built_in"] or course["read_only"] != entry["read_only"]:
            raise CourseValidationError("catalog access flags do not match course", path=course_path, course_id=course_id)

        units: dict[str, dict[str, Any]] = {}
        stable_keys: dict[tuple[str, str], str] = {("course", course_id): course["stable_key"]}
        level_ids = [level["level_id"] for level in course["levels"]]
        self._assert_unique(level_ids, "level_id", path=course_path, course_id=course_id)
        self._assert_unique([level["order"] for level in course["levels"]], "level order", path=course_path, course_id=course_id)
        unit_ids: list[str] = []
        unit_orders: list[int] = []

        for level in course["levels"]:
            stable_keys[("level", level["level_id"])] = level["stable_key"]
            for unit_entry in level["units"]:
                unit_id = unit_entry["unit_id"]
                unit_ids.append(unit_id)
                unit_orders.append(unit_entry["order"])
                stable_keys[("unit", unit_id)] = unit_entry["stable_key"]
                relative = unit_entry["content_path"]
                if relative is None:
                    if unit_entry["status"] != "planned":
                        raise CourseValidationError(
                            f"unit {unit_id} without content_path must have planned status",
                            path=course_path,
                            course_id=course_id,
                        )
                    continue
                try:
                    unit_path = resolve_safe_relative(course_path.parent, relative)
                except ValueError as exc:
                    raise CourseValidationError(str(exc), path=course_path.parent / relative, course_id=course_id) from exc
                unit = self._read_document(unit_path, course_id)
                self._check_specification_version(unit, unit_path, course_id)
                self._validate_document(unit, "unit.schema.json", unit_path, course_id)
                if unit["course_id"] != course_id or unit["level_id"] != level["level_id"]:
                    raise CourseValidationError("unit course/level identity mismatch", path=unit_path, course_id=course_id)
                if unit["unit_id"] != unit_id or unit["stable_key"] != unit_entry["stable_key"]:
                    raise CourseValidationError("unit manifest identity mismatch", path=unit_path, course_id=course_id)
                if unit["order"] != unit_entry["order"] or unit["title"] != unit_entry["title"]:
                    raise CourseValidationError("unit manifest order or title mismatch", path=unit_path, course_id=course_id)
                if unit["status"] != unit_entry["status"]:
                    raise CourseValidationError("unit manifest status mismatch", path=unit_path, course_id=course_id)
                self._validate_unit_graph(unit, unit_path, course_id, stable_keys)
                units[unit_id] = unit

        self._assert_unique(unit_ids, "unit_id", path=course_path, course_id=course_id)
        self._assert_unique(unit_orders, "unit order", path=course_path, course_id=course_id)
        self._assert_unique(list(stable_keys.values()), "stable_key", path=course_path, course_id=course_id)
        return LoadedCourseData(entry, course, units, course_path)

    def validate_templates(self) -> None:
        mapping = {
            "course.template.json": "course.schema.json",
            "unit.template.json": "unit.schema.json",
            "lesson.template.json": "lesson.schema.json",
            "sentence.template.json": "sentence.schema.json",
        }
        for template_name, schema_name in mapping.items():
            path = self.courses_root / "templates" / template_name
            document = self._read_document(path, None)
            self._validate_document(document, schema_name, path, None)

    def validate_tree(self) -> ValidationSummary:
        self.load_schema_registry()
        self.validate_templates()
        catalog = self.load_catalog_document()
        unit_count = sentence_count = 0
        global_stable_keys: list[str] = []
        for entry in catalog["courses"]:
            data = self.load_course_data(entry)
            unit_count += len(data.units)
            sentence_count += sum(len(unit["sentences"]) for unit in data.units.values())
            global_stable_keys.extend(self._stable_keys_for_data(data))
        self._assert_unique(global_stable_keys, "global stable_key", path=self.courses_root / "catalog.json")
        return ValidationSummary(len(SCHEMA_NAMES), 4, len(catalog["courses"]), unit_count, sentence_count)

    def _read_document(self, path: Path, course_id: str | None) -> dict[str, Any]:
        try:
            document = read_json_utf8(path)
        except FileNotFoundError as exc:
            raise CourseLoadError("required course file is missing", path=path, course_id=course_id) from exc
        except SchemaValidationFailure as exc:
            raise CourseValidationError(str(exc), path=path, course_id=course_id) from exc
        if not isinstance(document, dict):
            raise CourseValidationError("JSON root must be an object", path=path, course_id=course_id)
        return document

    def _validate_document(self, value: Any, schema_name: str, path: Path, course_id: str | None) -> None:
        registry = self.load_schema_registry()
        schema = registry[schema_name]
        try:
            validate_schema_value(value, schema, root_schema=schema, registry=registry, location=path.name)
        except SchemaValidationFailure as exc:
            raise CourseValidationError(str(exc), path=path, course_id=course_id) from exc

    def _check_specification_version(self, document: dict[str, Any], path: Path, course_id: str | None) -> None:
        version = document.get("specification_version")
        if isinstance(version, str) and version not in self.supported_specification_versions:
            supported = ", ".join(sorted(self.supported_specification_versions))
            raise UnsupportedCourseVersionError(
                f"unsupported specification_version {version!r}; supported: {supported}",
                path=path,
                course_id=course_id,
            )

    def _validate_unit_graph(
        self,
        unit: dict[str, Any],
        path: Path,
        course_id: str,
        stable_keys: dict[tuple[str, str], str],
    ) -> None:
        lesson_ids = [lesson["lesson_id"] for lesson in unit["lessons"]]
        sentence_ids = [sentence["sentence_id"] for sentence in unit["sentences"]]
        self._assert_unique(lesson_ids, "lesson_id", path=path, course_id=course_id)
        self._assert_unique(sentence_ids, "sentence_id", path=path, course_id=course_id)
        self._assert_unique([lesson["day"] for lesson in unit["lessons"]], "lesson day", path=path, course_id=course_id)
        self._assert_unique([lesson["order"] for lesson in unit["lessons"]], "lesson order", path=path, course_id=course_id)
        lessons = {lesson["lesson_id"]: lesson for lesson in unit["lessons"]}
        sentence_id_set = set(sentence_ids)

        for lesson in unit["lessons"]:
            stable_keys[("lesson", lesson["lesson_id"])] = lesson["stable_key"]
            if lesson["unit_id"] != unit["unit_id"]:
                raise CourseValidationError(
                    f"lesson {lesson['lesson_id']} has wrong unit_id",
                    path=path,
                    course_id=course_id,
                )
            referenced = lesson["new_sentence_ids"] + lesson["review_sentence_ids"]
            for activity in lesson["activities"]:
                referenced.extend(activity["sentence_ids"])
            if lesson["assessment"] is not None:
                referenced.extend(lesson["assessment"]["sentence_ids"])
            missing = sorted(set(referenced) - sentence_id_set)
            if missing:
                raise CourseValidationError(
                    f"lesson {lesson['lesson_id']} references missing sentences {missing!r}",
                    path=path,
                    course_id=course_id,
                )

        orders_by_lesson: dict[str, list[int]] = {}
        for sentence in unit["sentences"]:
            stable_keys[("sentence", sentence["sentence_id"])] = sentence["stable_key"]
            lesson = lessons.get(sentence["lesson_id"])
            if lesson is None:
                raise CourseValidationError(
                    f"sentence {sentence['sentence_id']} has missing lesson",
                    path=path,
                    course_id=course_id,
                )
            if sentence["unit_id"] != unit["unit_id"] or sentence["day"] != lesson["day"]:
                raise CourseValidationError(
                    f"sentence {sentence['sentence_id']} has inconsistent unit/day",
                    path=path,
                    course_id=course_id,
                )
            if sentence["sentence_id"] not in lesson["new_sentence_ids"]:
                raise CourseValidationError(
                    f"sentence {sentence['sentence_id']} is not owned by its lesson",
                    path=path,
                    course_id=course_id,
                )
            orders_by_lesson.setdefault(sentence["lesson_id"], []).append(sentence["order"])
            self._check_fixed_casing(sentence["english"], path, course_id, sentence["sentence_id"])
            for word in sentence["core_words"]:
                self._check_fixed_casing(word, path, course_id, sentence["sentence_id"])
        for lesson_id, orders in orders_by_lesson.items():
            self._assert_unique(orders, f"sentence order in {lesson_id}", path=path, course_id=course_id)

    @staticmethod
    def _stable_keys_for_data(data: LoadedCourseData) -> list[str]:
        values = [data.course["stable_key"]]
        for level in data.course["levels"]:
            values.append(level["stable_key"])
            for unit_entry in level["units"]:
                values.append(unit_entry["stable_key"])
                unit = data.units.get(unit_entry["unit_id"])
                if unit is None:
                    continue
                values.extend(lesson["stable_key"] for lesson in unit["lessons"])
                values.extend(sentence["stable_key"] for sentence in unit["sentences"])
        return values

    @staticmethod
    def _check_fixed_casing(text: str, path: Path, course_id: str, sentence_id: str) -> None:
        for form in ("Github", "Api", "Json", "english studio"):
            if re.search(rf"(?<![A-Za-z]){re.escape(form)}(?![A-Za-z])", text):
                raise CourseValidationError(
                    f"sentence {sentence_id} uses invalid fixed casing {form!r}",
                    path=path,
                    course_id=course_id,
                )
        if re.search(r"(?<![A-Za-z])python(?![A-Za-z])", text):
            raise CourseValidationError(
                f"sentence {sentence_id} must use 'Python'",
                path=path,
                course_id=course_id,
            )

    @staticmethod
    def _assert_unique(
        values: list[Any],
        label: str,
        *,
        path: Path,
        course_id: str | None = None,
    ) -> None:
        seen: set[Any] = set()
        duplicates: set[Any] = set()
        for value in values:
            if value in seen:
                duplicates.add(value)
            seen.add(value)
        if duplicates:
            raise CourseValidationError(
                f"duplicate {label}: {sorted(duplicates)!r}",
                path=path,
                course_id=course_id,
            )
