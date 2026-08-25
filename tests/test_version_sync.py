from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from english_typing_trainer import __version__


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_application_and_packaging_versions_are_synchronized() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_script = (PROJECT_ROOT / "scripts" / "package.ps1").read_text(encoding="utf-8")
    version_info = (PROJECT_ROOT / "packaging" / "version_info.txt").read_text(encoding="utf-8")
    installer = (PROJECT_ROOT / "packaging" / "EnglishStudio.iss").read_text(encoding="utf-8")

    assert __version__ == "2.0.0"
    assert project["project"]["version"] == "2.0.0"
    assert re.search(r'^\$Version = "2\.0\.0"$', package_script, re.MULTILINE)
    assert re.search(r'^\$VersionNumeric = "2\.0\.0\.0"$', package_script, re.MULTILINE)
    assert "filevers=(2, 0, 0, 0)" in version_info
    assert "ProductVersion', u'2.0.0'" in version_info
    assert "VersionInfoVersion={#MyAppVersionNumeric}" in installer


def test_course_versions_remain_independent_from_application_version() -> None:
    project = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    course = json.loads(
        (PROJECT_ROOT / "courses" / "ai-large-models" / "course.json").read_text(encoding="utf-8")
    )

    assert project["project"]["version"] != course["version"]
    assert course["version"] == "1.0.0"
    assert course["content_version"] == "1.0.0"
