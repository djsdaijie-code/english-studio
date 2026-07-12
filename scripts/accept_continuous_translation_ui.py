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
    return QKeyEvent(QKeyEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, character)


def capture(window: MainWindow, path: Path, app: QApplication) -> None:
    app.processEvents()
    if not window.grab().save(str(path)):
        raise RuntimeError(f"截图保存失败：{path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--screenshots", type=Path, required=True)
    args = parser.parse_args()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.screenshots.mkdir(parents=True, exist_ok=True)

    text = " ".join(
        [
            "Many people around the world use English to communicate with confidence.",
            "A calm translation panel can support understanding without interrupting typing rhythm.",
            "Cached meanings appear instantly and never create a network request during practice.",
            "Comfortable line spacing helps long English paragraphs remain easy to scan.",
            "The eye control hides optional Chinese guidance whenever focused recall is preferred.",
        ]
    )
    source_dir = args.data_dir / "中文路径"
    source_dir.mkdir(exist_ok=True)
    source = source_dir / "连续练习中文辅助.txt"
    source.write_text(text, encoding="utf-8")

    app = QApplication.instance() or QApplication([])
    app.setCursorFlashTime(0)
    context = build_app_context(data_dir=args.data_dir, credential_store=MemoryCredentialStore("sk-mock-only"))
    imported = context.article_library.import_txt_file(source, 500)
    material = context.practice_service.load_practice_material(imported.article.id)
    sentences = context.sentence_service.ensure_for_section(material.section_id)
    meanings = [
        "世界各地的许多人使用英语自信地交流。",
        "简洁的翻译面板可以帮助理解，同时不打断打字节奏。",
        "缓存的中文意思会立即显示，练习期间绝不会发起网络请求。",
        "舒适的行间距让较长的英文段落更容易阅读。",
        "需要专注回忆时，可以用眼睛按钮隐藏中文提示。",
    ]
    for sentence, meaning in zip(sentences, meanings, strict=True):
        context.translation_service.prepare(sentence, provider="mock", model="mock-v1")
        context.translation_service.complete(
            sentence.sentence_hash,
            TranslationResult(meaning, []),
            provider="mock",
            model="mock-v1",
        )
    settings = context.settings_service.get_settings()
    settings.sentence_learning_enabled = False
    context.settings_service.save_settings(settings)

    window = MainWindow(context)
    window.show()
    try:
        window._begin_practice(material)
        view = window.practice_view
        for character in sentences[0].text[:20]:
            view._handle_input_event(key_event(character))
        if view.translation_text.text() != meanings[0]:
            raise RuntimeError("连续练习未显示当前句缓存翻译")

        apply_theme(window, "light")
        window.resize(1280, 720)
        capture(window, args.screenshots / "01-continuous-chinese-light-1280x720.png", app)
        view.translation_toggle.click()
        capture(window, args.screenshots / "02-continuous-hidden-light-1280x720.png", app)
        view.translation_toggle.click()
        window.resize(1500, 1000)
        capture(window, args.screenshots / "03-continuous-chinese-light-1500x1000.png", app)

        apply_theme(window, "dark")
        window.resize(1920, 1080)
        capture(window, args.screenshots / "04-continuous-chinese-dark-1920x1080.png", app)
        view.translation_toggle.click()
        capture(window, args.screenshots / "05-continuous-hidden-dark-1920x1080.png", app)

        window.current_practice_saved = True
        window._show_library()
        window.practice_mode_control.button("sentence").click()
        window.continue_button.click()
        apply_theme(window, "light")
        window.resize(1500, 1000)
        capture(window, args.screenshots / "06-sentence-learning-unaffected-light.png", app)
        apply_theme(window, "dark")
        window.resize(1920, 1080)
        capture(window, args.screenshots / "07-sentence-learning-unaffected-dark.png", app)
        window.current_practice_saved = True
        window.close()
    finally:
        context.database.close()

    print("CONTINUOUS_TRANSLATION_ACCEPTANCE_OK")
    print(f"DATA_DIR={args.data_dir.resolve()}")
    print(f"SCREENSHOTS={args.screenshots.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
