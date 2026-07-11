from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from english_typing_trainer import __version__
from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.application.logging_config import configure_logging
from english_typing_trainer.services.app_paths import AppPathService
from english_typing_trainer.ui.main_window import MainWindow


def _install_exception_handler(log_path) -> None:
    def handle_exception(exc_type, exc_value, traceback) -> None:
        logging.getLogger(__name__).critical(
            "未处理异常",
            exc_info=(exc_type, exc_value, traceback),
        )
        QMessageBox.critical(
            QApplication.activeWindow(),
            "程序发生错误",
            f"程序遇到未处理的错误。\n\n请重新启动程序；如果问题持续出现，请查看日志：\n{log_path}",
        )

    sys.excepthook = handle_exception


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("英语打字练习")
    app.setApplicationDisplayName("英语打字练习")
    context = None
    log_path = None
    try:
        paths = AppPathService().ensure_directories()
        log_path = configure_logging(paths.logs_dir)
        _install_exception_handler(log_path)
        logging.getLogger(__name__).info(
            "应用启动 version=%s frozen=%s data_dir=%s",
            __version__,
            bool(getattr(sys, "frozen", False)),
            paths.data_dir,
        )
        context = build_app_context(data_dir=paths.data_dir)
        window = MainWindow(context)
        window.show()
        exit_code = app.exec()
        logging.getLogger(__name__).info("应用正常退出 exit_code=%s", exit_code)
        return exit_code
    except Exception:
        logging.getLogger(__name__).exception("应用启动失败")
        detail = f"\n\n错误日志：\n{log_path}" if log_path else ""
        QMessageBox.critical(None, "启动失败", f"英语打字练习无法启动。{detail}")
        return 1
    finally:
        if context is not None:
            context.database.close()