from __future__ import annotations

MIN_SPEED_SECONDS = 1.0
MIN_EFFECTIVE_SECONDS = 30.0
MIN_EFFECTIVE_CHARACTERS = 100
AUTOMATED_APP_VERSION_MARKERS = (
    "acceptance",
    "runtime",
    "phase",
    "qa",
    "test",
    "automation",
)


def calculate_wpm(correct_characters: int, elapsed_active_seconds: float) -> float:
    minutes = elapsed_active_seconds / 60
    if elapsed_active_seconds < MIN_SPEED_SECONDS or minutes <= 0:
        return 0.0
    return (correct_characters / 5) / minutes


def calculate_cpm(correct_characters: int, elapsed_active_seconds: float) -> float:
    minutes = elapsed_active_seconds / 60
    if elapsed_active_seconds < MIN_SPEED_SECONDS or minutes <= 0:
        return 0.0
    return correct_characters / minutes


def calculate_accuracy(correct_keystrokes: int, total_keystrokes: int) -> float:
    if total_keystrokes <= 0:
        return 100.0
    return (correct_keystrokes / total_keystrokes) * 100


def is_effective_result(
    *,
    completed: bool,
    correct_characters: int,
    active_seconds: float,
) -> bool:
    return (
        completed
        and correct_characters >= MIN_EFFECTIVE_CHARACTERS
        and active_seconds >= MIN_EFFECTIVE_SECONDS
    )


def has_sufficient_speed_data(
    *,
    correct_characters: int,
    active_seconds: float,
) -> bool:
    return correct_characters > 0 and active_seconds >= MIN_SPEED_SECONDS


def is_automated_app_version(app_version: str | None) -> bool:
    normalized = (app_version or "").strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in AUTOMATED_APP_VERSION_MARKERS)
