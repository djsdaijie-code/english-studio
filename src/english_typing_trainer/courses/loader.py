from __future__ import annotations

from pathlib import Path
from typing import Any

from english_typing_trainer.courses.models import (
    Course,
    CourseActivity,
    CourseAlternative,
    CourseAssessment,
    CourseAudioHint,
    CourseLearningPlan,
    CourseLesson,
    CourseLevel,
    CourseMistake,
    CourseSentence,
    CourseUnit,
    CourseVisualPrompt,
)
from english_typing_trainer.courses.paths import resolve_safe_relative
from english_typing_trainer.courses.validation import LoadedCourseData


def build_course(data: LoadedCourseData) -> Course:
    raw = data.course
    levels = tuple(
        _build_level(level, data.units, data.course_path.parent)
        for level in sorted(raw["levels"], key=lambda item: item["order"])
    )
    return Course(
        specification_version=raw["specification_version"],
        course_id=raw["course_id"],
        stable_key=raw["stable_key"],
        version=raw["version"],
        content_version=raw["content_version"],
        title=raw["title"],
        subtitle=raw["subtitle"],
        description=raw["description"],
        language=raw["language"],
        target_level=raw["target_level"],
        topics=tuple(raw["topics"]),
        estimated_days=raw["estimated_days"],
        estimated_sentences=raw["estimated_sentences"],
        prerequisites=tuple(raw["prerequisites"]),
        learning_goals=tuple(raw["learning_goals"]),
        default_learning_plan=_build_learning_plan(raw["default_learning_plan"]),
        levels=levels,
        status=raw["status"],
        built_in=raw["built_in"],
        read_only=raw["read_only"],
        default_order=data.catalog_entry["default_order"],
        source_path=data.catalog_entry["path"],
    )


def _build_level(
    raw: dict[str, Any],
    units: dict[str, dict[str, Any]],
    course_root: Path,
) -> CourseLevel:
    return CourseLevel(
        level_id=raw["level_id"],
        stable_key=raw["stable_key"],
        order=raw["order"],
        title=raw["title"],
        description=raw["description"],
        difficulty=raw["difficulty"],
        learning_goals=tuple(raw["learning_goals"]),
        units=tuple(
            _build_unit(entry, units.get(entry["unit_id"]), course_root)
            for entry in sorted(raw["units"], key=lambda item: item["order"])
        ),
    )


def _build_unit(
    entry: dict[str, Any],
    raw: dict[str, Any] | None,
    course_root: Path,
) -> CourseUnit:
    if raw is None:
        return CourseUnit(
            unit_id=entry["unit_id"],
            stable_key=entry["stable_key"],
            order=entry["order"],
            title=entry["title"],
            status=entry["status"],
            content_path=entry["content_path"],
        )
    return CourseUnit(
        unit_id=raw["unit_id"],
        stable_key=raw["stable_key"],
        order=entry["order"],
        title=raw["title"],
        status=raw["status"],
        content_path=entry["content_path"],
        specification_version=raw["specification_version"],
        content_version=raw["content_version"],
        course_id=raw["course_id"],
        level_id=raw["level_id"],
        description=raw["description"],
        difficulty=raw["difficulty"],
        estimated_days=raw["estimated_days"],
        learning_goals=tuple(raw["learning_goals"]),
        core_vocabulary=tuple(raw["core_vocabulary"]),
        core_patterns=tuple(raw["core_patterns"]),
        learning_plan_override=(
            _build_learning_plan(raw["learning_plan_override"])
            if raw["learning_plan_override"] is not None
            else None
        ),
        lessons=tuple(_build_lesson(item) for item in sorted(raw["lessons"], key=lambda item: item["order"])),
        sentences=tuple(
            _build_sentence(item, course_root)
            for item in sorted(raw["sentences"], key=lambda item: (item["day"], item["order"]))
        ),
    )


def _build_learning_plan(raw: dict[str, Any]) -> CourseLearningPlan:
    return CourseLearningPlan(
        new_sentences_per_day=raw.get("new_sentences_per_day"),
        unit_days=raw.get("unit_days"),
        review_day=raw.get("review_day"),
        assessment_day=raw.get("assessment_day"),
    )


def _build_lesson(raw: dict[str, Any]) -> CourseLesson:
    assessment = raw["assessment"]
    return CourseLesson(
        lesson_id=raw["lesson_id"],
        stable_key=raw["stable_key"],
        unit_id=raw["unit_id"],
        day=raw["day"],
        order=raw["order"],
        title=raw["title"],
        lesson_type=raw["lesson_type"],
        description=raw["description"],
        learning_goals=tuple(raw["learning_goals"]),
        new_sentence_ids=tuple(raw["new_sentence_ids"]),
        review_sentence_ids=tuple(raw["review_sentence_ids"]),
        activities=tuple(
            CourseActivity(item["activity_type"], tuple(item["sentence_ids"]), item["required"])
            for item in raw["activities"]
        ),
        assessment=(
            CourseAssessment(
                assessment["assessment_type"],
                tuple(assessment["sentence_ids"]),
                assessment["passing_score"],
            )
            if assessment is not None
            else None
        ),
        content_version=raw["content_version"],
        status=raw["status"],
    )


def _build_sentence(raw: dict[str, Any], course_root: Path) -> CourseSentence:
    audio = raw["audio_hint"]
    visual = raw.get("visual_prompt")
    return CourseSentence(
        sentence_id=raw["sentence_id"],
        stable_key=raw["stable_key"],
        unit_id=raw["unit_id"],
        lesson_id=raw["lesson_id"],
        day=raw["day"],
        order=raw["order"],
        english=raw["english"],
        chinese=raw["chinese"],
        scene=raw["scene"],
        difficulty=raw["difficulty"],
        core_words=tuple(raw["core_words"]),
        core_patterns=tuple(raw["core_patterns"]),
        common_mistakes=tuple(
            CourseMistake(item["incorrect"], item["explanation_zh"])
            for item in raw["common_mistakes"]
        ),
        alternative_expressions=tuple(
            CourseAlternative(item["english"], item["chinese"])
            for item in raw["alternative_expressions"]
        ),
        skill_tags=tuple(raw["skill_tags"]),
        source_type=raw["source_type"],
        audio_hint=(
            CourseAudioHint(
                tuple(audio.get("stress_words", [])),
                tuple(audio.get("pause_after", [])),
                audio.get("note_zh", ""),
            )
            if audio is not None
            else None
        ),
        review_group=raw["review_group"],
        content_version=raw["content_version"],
        status=raw["status"],
        replacement_stable_keys=tuple(raw.get("replacement_stable_keys", [])),
        visual_prompt=(
            CourseVisualPrompt(
                prompt_type=visual["prompt_type"],
                asset_path=visual["asset_path"],
                resolved_asset_path=resolve_safe_relative(
                    course_root, visual["asset_path"]
                ),
                alt_text=visual["alt_text"],
                instruction_zh=visual["instruction_zh"],
                source_url=visual["source_url"],
                rights_note=visual["rights_note"],
                hide_answer=visual["hide_answer"],
            )
            if visual is not None
            else None
        ),
    )
