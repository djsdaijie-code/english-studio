from __future__ import annotations

from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.services.sentence_learning import SentenceLearningSession, SentenceLearningState


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def _sentences(*texts: str) -> list[ArticleSentence]:
    return [ArticleSentence(id=index + 1, article_id=1, section_id=1, sentence_index=index, text=text, normalized_text=text.strip(), sentence_hash=f"hash-{index}", start_offset=sum(len(item) for item in texts[:index]), end_offset=sum(len(item) for item in texts[:index + 1])) for index, text in enumerate(texts)]


def test_first_input_starts_active_time_and_idle_pause_resumes_on_input() -> None:
    clock = FakeClock()
    session = SentenceLearningSession(_sentences("ab", "cd"), idle_pause_seconds=3, clock=clock)
    assert session.state == SentenceLearningState.WAITING_FIRST_INPUT
    clock.advance(10)
    assert session.timing_snapshot().active_seconds == 0

    session.handle_character("a")
    assert session.state == SentenceLearningState.TYPING
    clock.advance(4)
    assert session.check_idle() is True
    assert session.state == SentenceLearningState.IDLE_PAUSED
    assert session.timing_snapshot().active_seconds == 3
    assert session.timing_snapshot().idle_seconds == 1

    clock.advance(1)
    session.handle_character("b")
    assert session.state == SentenceLearningState.LEARNING_PAUSED
    timing = session.timing_snapshot()
    assert timing.active_seconds == 3
    assert timing.idle_seconds == 2
    assert session.attempts[0].active_seconds == 3


def test_learning_time_and_enter_next_sentence_do_not_start_active_time() -> None:
    clock = FakeClock()
    session = SentenceLearningSession(_sentences("a", "b"), clock=clock)
    session.handle_character("a")
    assert session.state == SentenceLearningState.LEARNING_PAUSED
    clock.advance(5)
    assert session.next_sentence() is True
    assert session.state == SentenceLearningState.WAITING_FIRST_INPUT
    assert session.timing_snapshot().learning_seconds == 5
    clock.advance(7)
    assert session.timing_snapshot().active_seconds == 0
    session.handle_character("b")
    assert session.state == SentenceLearningState.LEARNING_PAUSED


def test_manual_pause_and_focus_pause_exclude_time_and_block_input() -> None:
    clock = FakeClock()
    session = SentenceLearningSession(_sentences("abc"), clock=clock)
    session.handle_character("a")
    clock.advance(1)
    session.toggle_manual_pause()
    assert session.state == SentenceLearningState.MANUAL_PAUSED
    clock.advance(4)
    assert session.handle_character("b") is None
    assert session.current_session.position == 1
    session.toggle_manual_pause()
    clock.advance(1)
    session.handle_character("b")
    timing = session.timing_snapshot()
    assert timing.active_seconds == 2
    assert timing.manual_paused_seconds == 4

    session.focus_lost()
    clock.advance(2)
    assert session.state == SentenceLearningState.MANUAL_PAUSED
    assert session.timing_snapshot().manual_paused_seconds == 6


def test_sentence_completion_stops_active_and_records_error_attempt() -> None:
    clock = FakeClock()
    session = SentenceLearningSession(_sentences("ab"), clock=clock)
    session.handle_character("x")
    clock.advance(2)
    session.handle_character("b")
    assert session.state == SentenceLearningState.LEARNING_PAUSED
    clock.advance(20)
    attempt = session.attempts[0]
    assert attempt.completed is True
    assert attempt.error_count == 1
    assert attempt.correct_characters == 1
    assert attempt.accuracy == 50.0
    assert attempt.active_seconds == 2
    assert session.timing_snapshot().active_seconds == 2
    assert session.timing_snapshot().learning_seconds == 20
    assert session.next_sentence() is False
    assert session.state == SentenceLearningState.COMPLETED


def test_idle_pause_can_be_disabled() -> None:
    clock = FakeClock()
    session = SentenceLearningSession(_sentences("ab"), idle_pause_seconds=0, clock=clock)
    session.handle_character("a")
    clock.advance(20)
    assert session.check_idle() is False
    assert session.state == SentenceLearningState.TYPING
    assert session.timing_snapshot().active_seconds == 20