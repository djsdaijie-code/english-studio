from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from time import monotonic

from english_typing_trainer.statistics.metrics import (
    calculate_accuracy,
    calculate_cpm,
    calculate_wpm,
)
from english_typing_trainer.typing_engine.text_analysis import classify_error, extract_target_word


@dataclass(slots=True)
class TypingErrorRecord:
    target_char: str
    actual_char: str
    position: int
    word: str
    error_type: str
    timestamp: datetime


@dataclass(slots=True)
class SessionSnapshot:
    position: int
    total_keystrokes: int
    correct_keystrokes: int
    error_keystrokes: int
    correct_characters: int
    current_streak: int
    best_streak: int
    elapsed_active_seconds: float
    paused_seconds: float
    wpm: float
    cpm: float
    accuracy: float
    is_complete: bool
    last_error: TypingErrorRecord | None


class TypingSession:
    def __init__(self, content: str, *, case_sensitive: bool = True, start_position: int = 0) -> None:
        self.content = content
        self.case_sensitive = case_sensitive
        self.start_position = max(0, min(start_position, len(content)))
        self.position = self.start_position
        self.total_keystrokes = 0
        self.correct_keystrokes = 0
        self.error_keystrokes = 0
        self.correct_characters = 0
        self.current_streak = 0
        self.best_streak = 0
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None
        self._started_monotonic: float | None = None
        self._last_resumed_monotonic: float | None = None
        self._active_seconds_accumulator = 0.0
        self._paused_seconds_accumulator = 0.0
        self._paused_monotonic: float | None = None
        self._is_paused = False
        self._persisted = False
        self._persisted_session_id: int | None = None
        self.errors: list[TypingErrorRecord] = []
        self.last_error: TypingErrorRecord | None = None

    @property
    def is_complete(self) -> bool:
        return self.position >= len(self.content)

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def is_persisted(self) -> bool:
        return self._persisted

    @property
    def persisted_session_id(self) -> int | None:
        return self._persisted_session_id

    @property
    def elapsed_active_seconds(self) -> float:
        active_seconds = self._active_seconds_accumulator
        if (
            self._started_monotonic is not None
            and self._last_resumed_monotonic is not None
            and not self._is_paused
            and not self.completed_at
        ):
            active_seconds += monotonic() - self._last_resumed_monotonic
        return max(active_seconds, 0.0)

    @property
    def paused_seconds(self) -> float:
        paused_seconds = self._paused_seconds_accumulator
        if self._is_paused and self._paused_monotonic is not None:
            paused_seconds += monotonic() - self._paused_monotonic
        return max(paused_seconds, 0.0)

    def pause(self) -> None:
        if not self.started_at or self._is_paused or self.completed_at:
            return
        if self._last_resumed_monotonic is not None:
            self._active_seconds_accumulator += monotonic() - self._last_resumed_monotonic
        self._paused_monotonic = monotonic()
        self._last_resumed_monotonic = None
        self._is_paused = True

    def resume(self) -> None:
        if not self.started_at or not self._is_paused or self.completed_at:
            return
        if self._paused_monotonic is not None:
            self._paused_seconds_accumulator += monotonic() - self._paused_monotonic
        self._paused_monotonic = None
        self._last_resumed_monotonic = monotonic()
        self._is_paused = False

    def handle_character(self, actual_char: str) -> bool:
        if self.is_complete or self._is_paused or not actual_char:
            return False

        if self.started_at is None:
            now = datetime.now()
            self.started_at = now
            current_tick = monotonic()
            self._started_monotonic = current_tick
            self._last_resumed_monotonic = current_tick

        expected_char = self.content[self.position]
        self.total_keystrokes += 1

        if self._matches(actual_char, expected_char):
            self.correct_keystrokes += 1
            self.correct_characters += 1
            self.position += 1
            self.current_streak += 1
            self.best_streak = max(self.best_streak, self.current_streak)
            self.last_error = None
            if self.is_complete:
                self._finish()
            return True

        self.error_keystrokes += 1
        self.current_streak = 0
        error_record = TypingErrorRecord(
            target_char=expected_char,
            actual_char=actual_char,
            position=self.position,
            word=extract_target_word(self.content, self.position),
            error_type=classify_error(expected_char, actual_char),
            timestamp=datetime.now(),
        )
        self.errors.append(error_record)
        self.last_error = error_record
        return False

    def mark_persisted(self, session_id: int) -> None:
        self._persisted = True
        self._persisted_session_id = session_id

    def _matches(self, actual_char: str, expected_char: str) -> bool:
        if self.case_sensitive:
            return actual_char == expected_char
        return actual_char.casefold() == expected_char.casefold()

    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            position=self.position,
            total_keystrokes=self.total_keystrokes,
            correct_keystrokes=self.correct_keystrokes,
            error_keystrokes=self.error_keystrokes,
            correct_characters=self.correct_characters,
            current_streak=self.current_streak,
            best_streak=self.best_streak,
            elapsed_active_seconds=self.elapsed_active_seconds,
            paused_seconds=self.paused_seconds,
            wpm=calculate_wpm(self.correct_characters, self.elapsed_active_seconds),
            cpm=calculate_cpm(self.correct_characters, self.elapsed_active_seconds),
            accuracy=calculate_accuracy(self.correct_keystrokes, self.total_keystrokes),
            is_complete=self.is_complete,
            last_error=self.last_error,
        )

    def _finish(self) -> None:
        if self.completed_at is not None:
            return
        if self._last_resumed_monotonic is not None:
            self._active_seconds_accumulator += monotonic() - self._last_resumed_monotonic
            self._last_resumed_monotonic = None
        self.completed_at = datetime.now()
        self._is_paused = False
