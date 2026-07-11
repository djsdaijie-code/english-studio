from english_typing_trainer.statistics.metrics import (
    calculate_accuracy,
    calculate_cpm,
    calculate_wpm,
)


def test_calculate_wpm_uses_five_characters_per_word() -> None:
    assert calculate_wpm(correct_characters=250, elapsed_active_seconds=60) == 50.0


def test_calculate_cpm_uses_active_minutes() -> None:
    assert calculate_cpm(correct_characters=180, elapsed_active_seconds=60) == 180.0


def test_calculate_accuracy_handles_zero_keystrokes() -> None:
    assert calculate_accuracy(correct_keystrokes=0, total_keystrokes=0) == 100.0
