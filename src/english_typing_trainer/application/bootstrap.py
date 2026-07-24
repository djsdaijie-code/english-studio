from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from english_typing_trainer import __version__
from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.application.logging_config import configure_logging
from english_typing_trainer.services.app_paths import AppPathService
from english_typing_trainer.ui.main_window import MainWindow
from english_typing_trainer.ui.theme import resource_root


def run_acceptance_smoke(context, window: MainWindow, report_path: Path, action: str) -> bool:
    """Exercise bundled resources and course UI without exposing course body text."""
    if action not in {"seed", "verify"}:
        raise ValueError("Unknown acceptance smoke action.")
    catalog = context.course_repository.load_catalog()
    if not catalog.courses:
        raise RuntimeError("No bundled course is available.")
    course = catalog.courses[0]
    location = next(
        (
            (unit, lesson, sentence)
            for level in course.levels
            for unit in level.units
            for lesson in unit.lessons
            for sentence in unit.sentences
            if sentence.lesson_id == lesson.lesson_id
        ),
        None,
    )
    if location is None:
        raise RuntimeError("The bundled course has no materialized lesson.")
    _unit, lesson, sentence = location
    if action == "seed":
        context.course_progress_service.start_item(
            course.course_id, sentence.stable_key
        )

    window._show_courses()
    window.course_page.show_course(course.course_id)
    window.course_page.show_lesson(course.course_id, lesson.lesson_id)
    QApplication.processEvents()
    enrollment = context.course_progress_service.get_enrollment(course.course_id)
    item_progress = context.course_progress_service.get_item_progress(
        course.course_id, sentence.stable_key
    )
    connection = context.database.connect()
    report = {
        "action": action,
        "schema_version": context.database.get_schema_version(),
        "catalog_course_count": len(catalog.courses),
        "catalog_failure_count": len(catalog.failures),
        "course_id": course.course_id,
        "level_count": len(course.levels),
        "unit_count": sum(len(level.units) for level in course.levels),
        "sentence_count": sum(
            len(unit.sentences)
            for level in course.levels
            for unit in level.units
        ),
        "course_page_opened": (
            window.stack.currentWidget() is window.learning_content_page
            and window.learning_content_page.current_section() == "courses"
        ),
        "day_page_opened": (
            window.course_page.view_stack.currentWidget()
            is window.course_page.lesson_view
        ),
        "enrollment_status": enrollment.status if enrollment else None,
        "current_lesson_stable_key": (
            enrollment.current_lesson_stable_key if enrollment else None
        ),
        "first_item_status": item_progress.status,
        "article_count": int(
            connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        ),
    }
    report["passed"] = bool(
        report["schema_version"] == 13
        and report["catalog_failure_count"] == 0
        and report["course_page_opened"]
        and report["day_page_opened"]
        and report["article_count"] == 0
        and report["first_item_status"] == "in_progress"
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return bool(report["passed"])


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
    app.setApplicationName("English Studio")
    app.setApplicationDisplayName("English Studio")
    app.setWindowIcon(QIcon(str(resource_root() / "icons" / "english-studio.svg")))
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
        smoke_report = os.environ.get("ENGLISH_STUDIO_ACCEPTANCE_REPORT")
        if smoke_report:
            action = os.environ.get("ENGLISH_STUDIO_ACCEPTANCE_ACTION", "verify")
            try:
                passed = run_acceptance_smoke(
                    context, window, Path(smoke_report), action
                )
                exit_code = 0 if passed else 2
            except Exception as exc:
                logging.getLogger(__name__).exception(
                    "packaged acceptance smoke failed error_type=%s",
                    type(exc).__name__,
                )
                Path(smoke_report).parent.mkdir(parents=True, exist_ok=True)
                Path(smoke_report).write_text(
                    json.dumps(
                        {
                            "action": action,
                            "passed": False,
                            "error_type": type(exc).__name__,
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
                exit_code = 2
            QTimer.singleShot(0, lambda code=exit_code: app.exit(code))
        exit_code = app.exec()
        logging.getLogger(__name__).info("应用正常退出 exit_code=%s", exit_code)
        return exit_code
    except Exception:
        logging.getLogger(__name__).exception("应用启动失败")
        detail = f"\n\n错误日志：\n{log_path}" if log_path else ""
        QMessageBox.critical(None, "English Studio 启动失败", f"English Studio 无法启动。{detail}")
        return 1
    finally:
        if context is not None:
            context.database.close()
