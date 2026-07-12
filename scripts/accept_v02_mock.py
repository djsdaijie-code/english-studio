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
from PySide6.QtWidgets import QApplication, QProgressDialog

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.sentence_learning import SentenceLearningState
from english_typing_trainer.services.translation_provider import TranslationResult
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import apply_theme


class MockProvider:
    name = "mock"
    model = "mock-sentence-v1"

    def __init__(self) -> None:
        self.calls = 0

    def translate(self, sentence: str, **_kwargs) -> TranslationResult:
        self.calls += 1
        return TranslationResult(
            f"模拟翻译：{sentence[:28]}",
            [{"expression": "sentence learning", "meaning": "逐句学习"}],
        )


def key_event(character: str) -> QKeyEvent:
    if character == "\n":
        return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "\r")
    if character == "\t":
        return QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier, "\t")
    return QKeyEvent(QKeyEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character)


def save(widget, path: Path, app: QApplication) -> None:
    app.processEvents()
    if not widget.grab().save(str(path)):
        raise RuntimeError(f"无法保存截图：{path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.screenshots.mkdir(parents=True, exist_ok=True)

    article_text = " ".join(
        [
            "Sentence learning keeps a long article approachable for focused practice.",
            "The first valid key starts active typing time instead of opening the page.",
            "A short idle pause should stop speed timing without blocking the learner.",
            "Typing resumes immediately when the learner presses another useful key.",
            "Completed sentences can show a concise Chinese translation and expressions.",
            "Pressing Enter moves forward once and waits for the next sentence input.",
            "Cached translations remain available when the network is unavailable.",
            "An edited translation is protected until the learner requests regeneration.",
            "Sentence attempts preserve speed and accuracy data for future trend charts.",
            "The desktop layout adapts across common Windows screen sizes and themes.",
            "Bulk translation reports cached, successful, and failed sentence counts.",
            "All acceptance data stays outside the formal user data directory.",
        ]
    )
    source_dir = args.data_dir / "中文路径"
    source_dir.mkdir(exist_ok=True)
    source_path = source_dir / "逐句学习 样例.txt"
    source_path.write_text(article_text, encoding="utf-8")

    app = QApplication.instance() or QApplication([])
    store = MemoryCredentialStore("sk-mock-only")
    context = build_app_context(data_dir=args.data_dir, credential_store=store)
    provider = MockProvider()
    window = MainWindow(context)
    try:
        imported = context.article_library.import_txt_file(source_path, 1000)
        if imported.article is None:
            raise RuntimeError(imported.message)
        material = context.practice_service.load_practice_material(imported.article.id)
        sentences = context.sentence_service.ensure_for_section(material.section_id)
        if len(sentences) < 10:
            raise RuntimeError(f"句子数量不足：{len(sentences)}")

        first = sentences[0]
        decision = context.translation_service.prepare(first, provider=provider.name, model=provider.model)
        result = context.translation_service.request(provider, first, following=sentences[1].normalized_text)
        context.translation_service.complete(first.sentence_hash, result, provider=provider.name, model=provider.model)
        cached = context.translation_service.prepare(first, provider=provider.name, model=provider.model)
        if cached.should_request or provider.calls != 1:
            raise RuntimeError("翻译缓存未命中")

        window.show()
        window._begin_practice(material)
        view = window.sentence_practice_view
        for index, character in enumerate(first.text):
            view._handle_key(key_event("x" if index == 0 else character))
        app.processEvents()
        if view.learning.state != SentenceLearningState.LEARNING_PAUSED:
            raise RuntimeError("句子完成后未进入学习暂停")
        if view.learning.current_session.error_keystrokes != 1:
            raise RuntimeError("错误字符未记录")

        for width, height, name in (
            (1280, 720, "01-1280x720-light-sentence.png"),
            (1500, 1000, "02-1500x1000-light-completed.png"),
        ):
            apply_theme(window, "light")
            window.resize(width, height)
            save(window, args.screenshots / name, app)
        apply_theme(window, "dark")
        window.resize(1920, 1080)
        save(window, args.screenshots / "03-1920x1080-dark-sentence.png", app)

        view.translation_status.setText("正在翻译……")
        view.translation_text.setText("请稍候，您也可以按 Enter 继续下一句。")
        save(window, args.screenshots / "04-translation-loading.png", app)
        view.show_translation_failed("模拟网络错误，打字练习仍可继续。")
        save(window, args.screenshots / "05-translation-failed.png", app)

        progress = QProgressDialog("12 / 80 · 已缓存 25 · 成功 10 · 失败 1", "取消", 0, 80, window)
        progress.setWindowTitle("翻译整篇文章")
        progress.setValue(12)
        progress.show()
        save(progress, args.screenshots / "06-bulk-translation-progress.png", app)
        progress.close()

        window._show_settings()
        apply_theme(window, "light")
        window.resize(1500, 1000)
        save(window, args.screenshots / "07-deepseek-settings.png", app)

        window._begin_practice(material)
        view = window.sentence_practice_view
        view._handle_key(key_event(first.text[0]))
        view.learning._last_input_at -= 4
        if not view.learning.check_idle() or view.learning.state != SentenceLearningState.IDLE_PAUSED:
            raise RuntimeError("自动暂停验收失败")
        view._handle_key(key_event(first.text[1]))
        if view.learning.state != SentenceLearningState.TYPING:
            raise RuntimeError("自动暂停恢复失败")

        context.translation_service.edit(first.sentence_hash, "人工修改后的翻译", [])
        window.current_practice_saved = True
        window.close()
    finally:
        context.database.close()

    reopened = build_app_context(data_dir=args.data_dir, credential_store=store)
    try:
        persisted = reopened.translation_service.get(first.sentence_hash)
        if not persisted or persisted.chinese_translation != "人工修改后的翻译" or not persisted.is_user_edited:
            raise RuntimeError("人工翻译重启持久化失败")
    finally:
        reopened.database.close()

    print(f"MOCK_ACCEPTANCE_OK sentences={len(sentences)} provider_calls={provider.calls}")
    print(f"DATA_DIR={args.data_dir.resolve()}")
    print(f"SCREENSHOTS={args.screenshots.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
