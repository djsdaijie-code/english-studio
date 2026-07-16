from __future__ import annotations

from pathlib import Path
import sys


def default_courses_root() -> Path:
    """Locate bundled courses without consulting the process working directory."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / "courses"
    return Path(__file__).resolve().parents[3] / "courses"


def resolve_courses_root(courses_root: Path | None = None) -> Path:
    return (courses_root if courses_root is not None else default_courses_root()).resolve()


def resolve_safe_relative(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute():
        raise ValueError("absolute paths are not allowed")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise ValueError("path escapes the course resource root")
    return candidate
