from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.translation_provider import TranslationResult
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme


def key_event(character: str) -> QKeyEvent:
    if character == "\n":
        return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r")
    return QKeyEvent(QKeyEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character)


def capture(widget, path: Path, app: QApplication) -> None:
    app.processEvents()
    if not widget.grab().save(str(path)):
        raise RuntimeError(f"截图保存失败：{path}")


def assert_caret_at_end(editor) -> None:
    if editor.isReadOnly() or not editor.hasFocus() or editor.cursorWidth() <= 0:
        raise RuntimeError("输入区未显示真实活动光标")
    if editor.textCursor().position() != len(editor.toPlainText()):
        raise RuntimeError("输入光标未位于输入内容末尾")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.screenshots.mkdir(parents=True, exist_ok=True)

    text = " ".join(
        [
            "A visible caret makes controlled typing feel natural and predictable.",
            "Sentence learning pauses after each sentence so the learner can review translation.",
            "Continuous practice keeps the full paragraph moving without sentence pauses.",
            "The selected practice mode is saved locally and takes effect immediately.",
            "Soft background highlighting marks the current character without an underline.",
            "Both light and dark themes keep the article controls calm and readable.",
        ]
    )
    source_dir = args.data_dir / "中文路径"
    source_dir.mkdir(exist_ok=True)
    source = source_dir / "光标与模式 样例.txt"
    source.write_text(text, encoding="utf-8")

    app = QApplication.instance() or QApplication([])
    app.setCursorFlashTime(0)
    store = MemoryCredentialStore("sk-mock-only")
    context = build_app_context(data_dir=args.data_dir, credential_store=store)
    imported = context.article_library.import_txt_file(source, 500)
    if imported.article is None:
        raise RuntimeError(imported.message)

    window = MainWindow(context)
    window.resize(1500, 1000)
    window.show()
    try:
        apply_theme(window, "light")
        window.practice_mode_control.set_value("sentence")
        capture(window, args.screenshots / "01-article-detail-sentence-light.png", app)

        window.practice_mode_control.button("continuous").click()
        capture(window, args.screenshots / "02-article-detail-continuous-light.png", app)
        window.practice_mode_control.button("sentence").click()

        window.continue_button.click()
        app.processEvents()
        sentence_view = window.sentence_practice_view
        first = sentence_view.current_sentence
        context.translation_service.prepare(first, provider="mock", model="mock-v1")
        context.translation_service.complete(
            first.sentence_hash,
            TranslationResult("清晰的光标让受控输入自然且可预测。", [{"expression": "visible caret", "meaning": "可见光标"}]),
            provider="mock",
            model="mock-v1",
        )
        for character in first.text[:18]:
            sentence_view._handle_key(key_event(character))
        sentence_view._restore_focus()
        assert_caret_at_end(sentence_view.input_edit)
        capture(window, args.screenshots / "03-sentence-native-caret-light.png", app)
        capture(window, args.screenshots / "04-sentence-bulk-entry-light.png", app)

        while sentence_view.learning.current_session.position < len(first.text):
            position = sentence_view.learning.current_session.position
            sentence_view._handle_key(key_event(first.text[position]))
        if sentence_view.input_edit.cursorWidth() != 0:
            raise RuntimeError("句后学习状态未隐藏输入光标")
        sentence_view._handle_key(key_event("\n"))
        app.processEvents()
        assert_caret_at_end(sentence_view.input_edit)

        window.current_practice_saved = True
        window._show_library()
        window.practice_mode_control.button("continuous").click()
        window.continue_button.click()
        app.processEvents()
        continuous_view = window.practice_view
        for character in continuous_view.session.content[:24]:
            continuous_view._handle_input_event(key_event(character))
        continuous_view._restore_focus()
        assert_caret_at_end(continuous_view.input_edit)
        capture(window, args.screenshots / "05-continuous-native-caret-light.png", app)

        window.current_practice_saved = True
        window._show_library()
        window.practice_mode_control.button("sentence").click()
        window.continue_button.click()
        apply_theme(window, "dark")
        sentence_view = window.sentence_practice_view
        sentence_view._restore_focus()
        assert_caret_at_end(sentence_view.input_edit)
        capture(window, args.screenshots / "06-sentence-native-caret-dark.png", app)
        window.current_practice_saved = True
        window.close()
    finally:
        context.database.close()

    reopened = build_app_context(data_dir=args.data_dir, credential_store=store)
    second_window = MainWindow(reopened)
    second_window.resize(1500, 1000)
    second_window.show()
    try:
        app.processEvents()
        if second_window.practice_mode_control.value() != "sentence":
            raise RuntimeError("练习模式重启后未保留")
        apply_theme(second_window, "dark")
        capture(second_window, args.screenshots / "07-article-detail-sentence-dark.png", app)
        second_window.current_practice_saved = True
        second_window.close()
    finally:
        reopened.database.close()

    print("UI_REFINEMENT_ACCEPTANCE_OK")
    print(f"DATA_DIR={args.data_dir.resolve()}")
    print(f"SCREENSHOTS={args.screenshots.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
