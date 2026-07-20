import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent, QTextCursor, QTextOption
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame

from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.typing_engine.session import TypingSession
from english_typing_trainer.ui.practice_view import PracticeView


def test_typing_session_advances_after_correct_and_wrong_characters() -> None:
    session = TypingSession("ab")

    assert session.handle_character("x") is False
    assert session.position == 1
    assert session.error_keystrokes == 1
    assert session.typed_characters[0].actual_char == "x"
    assert session.typed_characters[0].is_correct is False

    assert session.handle_character("b") is True
    assert session.position == 2
    assert session.correct_keystrokes == 1
    assert session.is_complete


def test_typing_session_tracks_completion_and_snapshot_with_error() -> None:
    session = TypingSession("hi")
    session.handle_character("x")
    session.handle_character("i")

    snapshot = session.snapshot()

    assert snapshot.is_complete is True
    assert snapshot.correct_characters == 1
    assert snapshot.total_keystrokes == 2
    assert snapshot.error_keystrokes == 1
    assert snapshot.accuracy == 50.0


def test_backspace_removes_visible_character_but_keeps_historical_counts() -> None:
    session = TypingSession("ab")
    session.handle_character("x")

    assert session.handle_backspace() is True
    assert session.position == 0
    assert session.typed_characters == []
    assert session.total_keystrokes == 1
    assert session.error_keystrokes == 1
    assert len(session.errors) == 1

    assert session.handle_character("a") is True
    assert session.position == 1
    assert session.total_keystrokes == 2
    assert session.correct_keystrokes == 1
    assert session.error_keystrokes == 1


def test_paused_session_does_not_accept_input_or_backspace() -> None:
    session = TypingSession("ab")
    session.handle_character("a")
    session.pause()

    assert session.handle_character("x") is False
    assert session.handle_backspace() is False
    assert session.position == 1
    assert session.total_keystrokes == 1


def test_case_space_punctuation_and_newline_errors_advance() -> None:
    session = TypingSession("A .\n")
    for actual in ("a", "x", ",", "\t"):
        session.handle_character(actual)

    assert session.is_complete
    assert [error.error_type for error in session.errors] == [
        "case_error",
        "space_error",
        "punctuation_error",
        "newline_error",
    ]
    assert [typed.actual_char for typed in session.typed_characters] == ["a", "x", ",", "\t"]


def test_practice_view_maps_enter_and_tab_independent_of_expected_character() -> None:
    view = _start_view("ab")

    enter = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r")
    tab = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier, "\t")

    assert view._map_input_text(enter) == "\n"
    assert view._map_input_text(tab) == "\t"


def _start_view(text: str, *, practice_type: str = "article_section", size: tuple[int, int] = (1280, 720)) -> PracticeView:
    app = QApplication.instance() or QApplication([])
    view = PracticeView()
    view.resize(*size)
    view.show()
    view.start_practice(
        PracticeMaterial(
            article_id=1,
            article_title="测试文章",
            section_id=1,
            section_index=0,
            section_count=1,
            section_text=text,
            practice_type=practice_type,
        ),
        AppSettings(),
    )
    app.processEvents()
    return view


def _key(key: Qt.Key, text: str = "", modifiers=Qt.NoModifier) -> QKeyEvent:
    return QKeyEvent(QKeyEvent.KeyPress, key, modifiers, text)


def _format_at(view: PracticeView, position: int):
    cursor = QTextCursor(view.input_edit.document())
    cursor.setPosition(position)
    cursor.setPosition(position + 1, QTextCursor.MoveMode.KeepAnchor)
    return cursor.charFormat()


def test_practice_input_keeps_wrong_character_and_continues_at_next_position() -> None:
    view = _start_view("AbC")

    view._handle_input_event(_key(Qt.Key_X, "x"))
    assert view.session is not None
    assert view.session.position == 1
    assert view.session.error_keystrokes == 1
    assert view.input_edit.toPlainText() == "x"
    assert "输入错误" in view.input_feedback_label.text()

    view._handle_input_event(_key(Qt.Key_B, "b"))
    assert view.session.position == 2
    assert view.input_edit.toPlainText() == "xb"
    assert view.session.correct_keystrokes == 1


def test_input_render_uses_distinct_correct_and_error_formats() -> None:
    view = _start_view("ab")
    view._handle_input_event(_key(Qt.Key_A, "a"))
    view._handle_input_event(_key(Qt.Key_X, "x"))

    correct_format = _format_at(view, 0)
    error_format = _format_at(view, 1)
    assert correct_format.foreground().color() != error_format.foreground().color()
    assert error_format.fontUnderline() is True
    assert error_format.background().style() != Qt.BrushStyle.NoBrush


def test_practice_input_backspace_retreats_and_allows_retyping() -> None:
    view = _start_view("ab")
    view._handle_input_event(_key(Qt.Key_X, "x"))
    view._handle_input_event(_key(Qt.Key_Backspace))

    assert view.session is not None
    assert view.session.position == 0
    assert view.input_edit.toPlainText() == ""
    assert view.session.error_keystrokes == 1

    view._handle_input_event(_key(Qt.Key_A, "a"))
    assert view.session.position == 1
    assert view.input_edit.toPlainText() == "a"
    assert view.session.total_keystrokes == 2


def test_practice_completes_at_text_length_even_with_errors() -> None:
    view = _start_view("ab")
    view._handle_input_event(_key(Qt.Key_X, "x"))
    view._handle_input_event(_key(Qt.Key_Y, "y"))

    assert view.session is not None
    assert view.session.is_complete
    assert view.session.position == 2
    assert view.session.error_keystrokes == 2
    assert view.input_edit.toPlainText() == "xy"


def test_practice_input_handles_correct_space_punctuation_and_newline() -> None:
    view = _start_view("a, \nB")
    for event in (
        _key(Qt.Key_A, "a"),
        _key(Qt.Key_Comma, ","),
        _key(Qt.Key_Space, " "),
        _key(Qt.Key_Return, "\r"),
        _key(Qt.Key_B, "B"),
    ):
        view._handle_input_event(event)

    assert view.session is not None
    assert view.session.is_complete
    assert view.input_edit.toPlainText() == "a, \nB"


def test_continuous_practice_keeps_source_and_input_in_sync_after_sentence_boundary() -> None:
    content = "First you must listen every day. listening is very important."
    prefix = "First you must listen every day."
    view = _start_view(content)

    for character in prefix:
        view._handle_input_event(_key(Qt.Key_unknown, character))

    assert view.session is not None
    assert view.session.position == len(prefix)
    assert view.input_edit.toPlainText() == prefix
    assert view.progress_label.text() == f"进度 {len(prefix)} / {len(content)}"
    assert view.target_hint.text() == "当前目标：空格"
    selection = view.text_browser.extraSelections()[-1]
    current_selection = QTextCursor(selection.cursor)
    assert current_selection.selectionStart() == len(prefix)
    assert current_selection.selectionEnd() == len(prefix) + 1

    for character in " listening":
        view._handle_input_event(_key(Qt.Key_unknown, character))

    assert view.session.position == len(prefix) + len(" listening")
    assert view.input_edit.toPlainText().endswith(" listening")
    selection = view.text_browser.extraSelections()[-1]
    current_selection = QTextCursor(selection.cursor)
    assert current_selection.selectionStart() == view.session.position


def test_practice_input_blocks_paste_and_uses_same_view_for_special_practice() -> None:
    view = _start_view("word", practice_type="error_word")
    view._handle_input_event(_key(Qt.Key_V, "v", Qt.ControlModifier))

    assert view.session is not None
    assert view.session.position == 0
    assert view.input_edit.toPlainText() == ""
    assert view.title_label.text() == "专项练习"
    assert view.input_edit.hasFocus()
    assert view.findChildren(QFrame, "PracticeSourceCard")
    assert view.findChildren(QFrame, "PracticeInputCard")


def test_practice_layout_expands_and_uses_natural_word_wrap() -> None:
    app = QApplication.instance() or QApplication([])
    text = "A responsive practice area should keep complete English phrases readable without adding manual line breaks. " * 4
    expected_minimums = {1280: 1000, 1500: 1200, 1920: 1300}

    for width, height in ((1280, 720), (1500, 1000), (1920, 1080)):
        view = _start_view(text, size=(width, height))
        app.processEvents()
        source_card = view.findChild(QFrame, "PracticeSourceCard")
        input_card = view.findChild(QFrame, "PracticeInputCard")
        assert source_card is not None and input_card is not None
        assert view.content_host.width() >= expected_minimums[width]
        assert view.content_host.width() <= 1400
        assert abs(source_card.width() - input_card.width()) <= 2
        assert view.text_browser.toPlainText() == text
        assert view.text_browser.document().defaultTextOption().wrapMode() == QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
        assert view.input_edit.document().defaultTextOption().wrapMode() == QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere
        view.close()

def test_clicking_source_or_input_restores_focus_and_keeps_cursor_at_end() -> None:
    app = QApplication.instance() or QApplication([])
    view = _start_view("abc")
    view._handle_input_event(_key(Qt.Key_A, "a"))

    view.text_browser.setFocus()
    QTest.mouseClick(view.input_edit.viewport(), Qt.MouseButton.LeftButton)
    app.processEvents()
    assert view.input_edit.hasFocus()
    assert view.input_edit.textCursor().position() == len(view.input_edit.toPlainText())

    view.text_browser.setFocus()
    QTest.mouseClick(view.text_browser.viewport(), Qt.MouseButton.LeftButton)
    app.processEvents()
    assert view.input_edit.hasFocus()
    assert view.input_edit.textCursor().position() == len(view.input_edit.toPlainText())
