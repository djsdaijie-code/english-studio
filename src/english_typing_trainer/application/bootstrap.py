from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("英语打字练习")
    context = build_app_context()
    window = MainWindow(context)
    window.show()
    exit_code = app.exec()
    context.database.close()
    return exit_code
