from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.typing_engine.session import TypingSession
from english_typing_trainer.ui.practice_view import PracticeView


def test_typing_session_advances_only_on_correct_character() -> None:
    session = TypingSession("ab")

    assert session.handle_character("x") is False
    assert session.position == 0
    assert session.error_keystrokes == 1

    assert session.handle_character("a") is True
    assert session.position == 1
    assert session.correct_keystrokes == 1


def test_typing_session_tracks_completion_and_snapshot() -> None:
    session = TypingSession("hi")
    session.handle_character("h")
    session.handle_character("i")

    snapshot = session.snapshot()

    assert snapshot.is_complete is True
    assert snapshot.correct_characters == 2
    assert snapshot.total_keystrokes == 2


def test_paused_session_does_not_accept_input() -> None:
    session = TypingSession("a")
    session.handle_character("a")
    session.pause()

    assert session.handle_character("a") is False


def test_practice_view_maps_return_to_newline() -> None:
    app = QApplication.instance() or QApplication([])
    view = PracticeView()
    view.start_practice(
        PracticeMaterial(
            article_id=1,
            article_title="t",
            section_id=1,
            section_index=0,
            section_count=1,
            section_text="a\nb",
        ),
        AppSettings(),
    )
    view.session.handle_character("a")

    event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r")

    assert view._map_input_text(event) == "\n"
