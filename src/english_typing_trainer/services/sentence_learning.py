from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from time import monotonic
from typing import Callable

from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.statistics.metrics import calculate_accuracy, calculate_cpm, calculate_wpm
from english_typing_trainer.typing_engine.session import TypingSession


class SentenceLearningState(StrEnum):
    WAITING_FIRST_INPUT = "waiting_first_input"
    TYPING = "typing"
    IDLE_PAUSED = "idle_paused"
    LEARNING_PAUSED = "learning_paused"
    MANUAL_PAUSED = "manual_paused"
    TRANSLATION_LOADING = "translation_loading"
    COMPLETED = "completed"


@dataclass(slots=True)
class SentenceAttemptResult:
    article_sentence_id: int | None
    sentence_hash: str
    started_at: datetime | None
    completed_at: datetime | None
    active_seconds: float
    total_elapsed_seconds: float
    correct_characters: int
    total_characters: int
    error_count: int
    cpm: float
    wpm: float
    accuracy: float
    completed: bool


@dataclass(slots=True)
class LearningTimingSnapshot:
    active_seconds: float
    total_elapsed_seconds: float
    learning_seconds: float
    idle_seconds: float
    manual_paused_seconds: float


class SentenceLearningSession:
    def __init__(
        self,
        sentences: list[ArticleSentence],
        *,
        case_sensitive: bool = True,
        idle_pause_seconds: int = 3,
        clock: Callable[[], float] = monotonic,
        start_sentence_index: int = 0,
        start_character_index: int = 0,
    ) -> None:
        if not sentences:
            raise ValueError("逐句练习至少需要一个句子。")
        self.sentences = sentences
        self.case_sensitive = case_sensitive
        self.idle_pause_seconds = max(0, idle_pause_seconds)
        self._clock = clock
        self.current_index = max(0, min(start_sentence_index, len(sentences) - 1))
        self.state = SentenceLearningState.WAITING_FIRST_INPUT
        self.current_session = self._new_typing_session(start_character_index)
        self.attempts: list[SentenceAttemptResult] = []
        self._total_started: float | None = None
        self._sentence_total_started: float | None = None
        self._active_started: float | None = None
        self._last_input_at: float | None = None
        self._learning_started: float | None = None
        self._idle_started: float | None = None
        self._manual_started: float | None = None
        self._resume_state = SentenceLearningState.WAITING_FIRST_INPUT
        self._active = 0.0
        self._learning = 0.0
        self._idle = 0.0
        self._manual = 0.0
        self._sentence_active_start = 0.0

    @property
    def current_sentence(self) -> ArticleSentence:
        return self.sentences[self.current_index]

    def handle_character(self, character: str) -> bool | None:
        if self.state in {SentenceLearningState.MANUAL_PAUSED, SentenceLearningState.LEARNING_PAUSED, SentenceLearningState.COMPLETED}:
            return None
        if len(character) != 1:
            return None
        now = self._clock()
        self._resume_for_input(now)
        result = self.current_session.handle_character(character)
        self._last_input_at = now
        if self.current_session.is_complete:
            self._finish_sentence(now)
        return result

    def handle_backspace(self) -> bool:
        if self.state in {SentenceLearningState.MANUAL_PAUSED, SentenceLearningState.LEARNING_PAUSED, SentenceLearningState.COMPLETED}:
            return False
        return self.current_session.handle_backspace()

    def check_idle(self) -> bool:
        if self.idle_pause_seconds <= 0 or self.state != SentenceLearningState.TYPING or self._last_input_at is None:
            return False
        now = self._clock()
        deadline = self._last_input_at + self.idle_pause_seconds
        if now < deadline:
            return False
        self._stop_active(deadline)
        self._idle_started = deadline
        self.state = SentenceLearningState.IDLE_PAUSED
        return True

    def toggle_manual_pause(self) -> None:
        now = self._clock()
        if self.state == SentenceLearningState.MANUAL_PAUSED:
            if self._manual_started is not None:
                self._manual += now - self._manual_started
            self._manual_started = None
            self.state = self._resume_state
            if self.state == SentenceLearningState.TYPING:
                self._active_started = now
                self._last_input_at = now
            elif self.state == SentenceLearningState.IDLE_PAUSED:
                self._idle_started = now
            elif self.state == SentenceLearningState.LEARNING_PAUSED:
                self._learning_started = now
            return
        if self.state == SentenceLearningState.COMPLETED:
            return
        self._resume_state = self.state
        self._stop_current_interval(now)
        self._manual_started = now
        self.state = SentenceLearningState.MANUAL_PAUSED

    def focus_lost(self) -> None:
        if self.state != SentenceLearningState.MANUAL_PAUSED:
            self.toggle_manual_pause()

    def next_sentence(self) -> bool:
        if self.state != SentenceLearningState.LEARNING_PAUSED:
            return False
        now = self._clock()
        if self._learning_started is not None:
            self._learning += now - self._learning_started
        self._learning_started = None
        if self.current_index + 1 >= len(self.sentences):
            self.state = SentenceLearningState.COMPLETED
            return False
        self.current_index += 1
        self.current_session = self._new_typing_session()
        self._sentence_total_started = now
        self._sentence_active_start = self._active
        self.state = SentenceLearningState.WAITING_FIRST_INPUT
        return True

    def timing_snapshot(self) -> LearningTimingSnapshot:
        now = self._clock()
        active = self._active + ((now - self._active_started) if self._active_started is not None else 0.0)
        learning = self._learning + ((now - self._learning_started) if self._learning_started is not None else 0.0)
        idle = self._idle + ((now - self._idle_started) if self._idle_started is not None else 0.0)
        manual = self._manual + ((now - self._manual_started) if self._manual_started is not None else 0.0)
        total = (now - self._total_started) if self._total_started is not None else 0.0
        return LearningTimingSnapshot(max(active, 0.0), max(total, 0.0), max(learning, 0.0), max(idle, 0.0), max(manual, 0.0))

    def _resume_for_input(self, now: float) -> None:
        if self._total_started is None:
            self._total_started = now
            self._sentence_total_started = now
        if self.state == SentenceLearningState.IDLE_PAUSED:
            if self._idle_started is not None:
                self._idle += now - self._idle_started
            self._idle_started = None
        if self.state in {SentenceLearningState.WAITING_FIRST_INPUT, SentenceLearningState.IDLE_PAUSED}:
            self._active_started = now
            self.state = SentenceLearningState.TYPING

    def _finish_sentence(self, now: float) -> None:
        self._stop_active(now)
        snapshot = self.current_session.snapshot()
        active = self._active - self._sentence_active_start
        total = now - (self._sentence_total_started if self._sentence_total_started is not None else now)
        self.attempts.append(
            SentenceAttemptResult(
                article_sentence_id=self.current_sentence.id,
                sentence_hash=self.current_sentence.sentence_hash,
                started_at=self.current_session.started_at,
                completed_at=self.current_session.completed_at,
                active_seconds=active,
                total_elapsed_seconds=max(total, 0.0),
                correct_characters=snapshot.correct_characters,
                total_characters=len(self.current_sentence.text),
                error_count=snapshot.error_keystrokes,
                cpm=calculate_cpm(snapshot.correct_characters, active),
                wpm=calculate_wpm(snapshot.correct_characters, active),
                accuracy=calculate_accuracy(snapshot.correct_keystrokes, snapshot.total_keystrokes),
                completed=True,
            )
        )
        self._learning_started = now
        self.state = SentenceLearningState.LEARNING_PAUSED

    def _stop_current_interval(self, now: float) -> None:
        if self.state == SentenceLearningState.TYPING:
            self._stop_active(now)
        elif self.state == SentenceLearningState.IDLE_PAUSED and self._idle_started is not None:
            self._idle += now - self._idle_started
            self._idle_started = None
        elif self.state == SentenceLearningState.LEARNING_PAUSED and self._learning_started is not None:
            self._learning += now - self._learning_started
            self._learning_started = None

    def _stop_active(self, now: float) -> None:
        if self._active_started is not None:
            self._active += max(now - self._active_started, 0.0)
        self._active_started = None

    def _new_typing_session(self, start_position: int = 0) -> TypingSession:
        return TypingSession(self.sentences[self.current_index].text, case_sensitive=self.case_sensitive, start_position=start_position)