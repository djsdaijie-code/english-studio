from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class CourseLoadError(RuntimeError):
    """Base error for course resources that cannot be loaded safely."""

    def __init__(self, reason: str, *, path: Path, course_id: str | None = None) -> None:
        self.reason = reason
        self.path = path
        self.course_id = course_id
        identity = course_id or "<catalog>"
        super().__init__(f"course_id={identity} path={path}: {reason}")


class CourseValidationError(CourseLoadError):
    """A course resource is readable but violates its data contract."""


class UnsupportedCourseVersionError(CourseLoadError):
    """The loader does not support a course specification version."""


@dataclass(frozen=True, slots=True)
class CourseLoadFailure:
    course_id: str | None
    path: Path
    error_type: str
    reason: str

    @classmethod
    def from_error(cls, error: CourseLoadError) -> CourseLoadFailure:
        return cls(error.course_id, error.path, type(error).__name__, error.reason)
