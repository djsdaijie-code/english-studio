from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from english_typing_trainer import __version__
from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.translation_provider import TranslationResult
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.reading_import_dialog import ReadingImportDialog
from english_typing_trainer.ui.theme import apply_theme


TEXT = (
    "Learning English works best when you read something that matters to you. "
    "A short article can introduce useful expressions in a meaningful context. "
    "Read each sentence slowly, and try to understand the idea before checking the translation.\n\n"
    "When you meet an unfamiliar word, save it together with its original sentence. "
    "Review these words regularly and listen to the sentence when pronunciation is unclear. "
    "Small steps repeated over time can make a real difference."
)
TRANSLATIONS = [
    "阅读自己感兴趣的内容，是学习英语的一种有效方法。",
    "一篇短文章可以在有意义的语境中介绍实用表达。",
    "慢慢阅读每个句子，先尝试理解意思，再查看翻译。",
    "遇到不熟悉的单词时，把它与原句一起收藏。",
    "定期复习这些单词，发音不清楚时可以听一听原句。",
    "长期重复的小步骤，会带来真正的改变。",
]


def _hash(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an isolated automated reading UI smoke test.")
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    output = options.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    formal = Path(os.environ["LOCALAPPDATA"]) / "EnglishStudio" / "typing_trainer.db"
    before = _hash(formal)
    app = QApplication([])
    context = build_app_context(
        data_dir=output / "runtime", credential_store=MemoryCredentialStore(),
        tts_credential_store=MemoryCredentialStore(),
    )
    window = MainWindow(context)
    window.show()
    result = {}

    def verify():
        try:
            service = window.reading_controller.service
            article = service.import_article("Learning English through reading", TEXT, "https://example.com/reading")
            material = service.load(article.id, restart=True)
            assert len(material.sentences) == len(TRANSLATIONS)
            for sentence, chinese in zip(material.sentences, TRANSLATIONS):
                context.translation_service.prepare(sentence, provider="qa-fixture", model="offline")
                context.translation_service.complete(
                    sentence.sentence_hash,
                    TranslationResult(chinese, [{"expression": "meaningful context", "meaning": "有意义的语境"}]),
                    provider="qa-fixture", model="offline",
                )
            for theme, size in (("light", (1280, 720)), ("light", (1500, 1000)), ("dark", (1920, 1080))):
                window.resize(*size)
                apply_theme(window, theme)
                window._open_reading_article(article.id)
                app.processEvents()
                page = window.reading_page
                assert page.translation_label.text() == TRANSLATIONS[material.index]
                assert page.source_text.horizontalScrollBar().maximum() == 0
                window.grab().save(str(output / f"reading-{size[0]}-{theme}.png"))
            window._show_reading()
            apply_theme(window, "light")
            window.resize(1280, 720)
            app.processEvents()
            window.grab().save(str(output / "reading-library-light.png"))
            window._switch_page(window.PAGE_HOME)
            app.processEvents()
            window.grab().save(str(output / "home-light.png"))
            dialog = ReadingImportDialog(window)
            dialog.title_input.setText("Learning English through reading")
            dialog.text_input.setPlainText(TEXT)
            dialog._advance()
            dialog.show()
            app.processEvents()
            dialog.grab().save(str(output / "reading-import-preview.png"))
            dialog.reject()
            window._open_reading_article(article.id)
            window.reading_page.move(1)
            assert window.reading_page.translation_label.text() == TRANSLATIONS[1]
            window.close()
            context.database.close()
            restarted = build_app_context(
                data_dir=output / "runtime", credential_store=MemoryCredentialStore(),
                tts_credential_store=MemoryCredentialStore(),
            )
            try:
                from english_typing_trainer.services.reading_service import ReadingService
                assert ReadingService(restarted).load(article.id).index == 1
            finally:
                restarted.database.close()
            result.update(passed=True, version=__version__, schema=13, sentence_count=6, restored_index=1)
        except Exception as exc:
            result.update(passed=False, error=repr(exc))
            window.close()
            context.database.close()
        finally:
            result["formal_database_sha256_before"] = before
            result["formal_database_sha256_after"] = _hash(formal)
            result["formal_database_unchanged"] = before == result["formal_database_sha256_after"]
            result["manual_input_verified"] = False
            (output / "report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(result, ensure_ascii=True))
            app.exit(0 if result.get("passed") else 1)

    QTimer.singleShot(300, verify)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
