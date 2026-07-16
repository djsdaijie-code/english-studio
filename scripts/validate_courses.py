from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from english_typing_trainer.courses.errors import CourseLoadError  # noqa: E402
from english_typing_trainer.courses.validation import CourseValidator  # noqa: E402


def main() -> int:
    try:
        summary = CourseValidator(PROJECT_ROOT / "courses").validate_tree()
    except CourseLoadError as exc:
        print(f"Course validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        "Course validation passed: "
        f"{summary.schema_count} schemas, {summary.template_count} templates, "
        f"{summary.course_count} course, {summary.unit_count} materialized unit, "
        f"{summary.sentence_count} sentences; references, IDs, stable keys, casing, and UTF-8 are valid."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
