from __future__ import annotations

from collections import Counter

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout

from english_typing_trainer.statistics.metrics import is_effective_result
from english_typing_trainer.typing_engine.session import SessionSnapshot, TypingSession


class ResultDialog(QDialog):
    def __init__(
        self,
        session: TypingSession,
        snapshot: SessionSnapshot,
        *,
        has_next_section: bool,
        title: str = "练习完成",
        extra_lines: list[str] | None = None,
        allow_retry_errors: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.action = "library"
        self.setWindowTitle(title)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        lines = [
            f"WPM：{snapshot.wpm:.1f}",
            f"CPM：{snapshot.cpm:.1f}",
            f"正确率：{snapshot.accuracy:.1f}%",
            f"有效练习时间：{snapshot.elapsed_active_seconds:.1f} 秒",
            f"暂停时间：{snapshot.paused_seconds:.1f} 秒",
            f"错误次数：{snapshot.error_keystrokes}",
            f"正确字符数：{snapshot.correct_characters}",
            f"最长连续正确：{snapshot.best_streak}",
        ]
        for line in lines:
            label = QLabel(line)
            label.setWordWrap(True)
            layout.addWidget(label)

        if not is_effective_result(
            completed=snapshot.is_complete,
            correct_characters=snapshot.correct_characters,
            active_seconds=snapshot.elapsed_active_seconds,
        ):
            warning = QLabel("练习时间过短，暂不计算有效速度。")
            warning.setWordWrap(True)
            warning.setStyleSheet("color:#b42318;")
            layout.addWidget(warning)

        for line in extra_lines or []:
            label = QLabel(line)
            label.setWordWrap(True)
            layout.addWidget(label)

        error_chars = Counter(error.target_char for error in session.errors)
        common_error_text = "、".join(f"{char!r} × {count}" for char, count in error_chars.most_common(5))
        if not common_error_text:
            common_error_text = "本次没有明显的高频错误字符"
        common_label = QLabel(f"高频错误字符：{common_error_text}")
        common_label.setWordWrap(True)
        layout.addWidget(common_label)

        if has_next_section:
            next_button = QPushButton("继续下一段")
            next_button.setProperty("variant", "primary")
            next_button.clicked.connect(self._accept_next)
            layout.addWidget(next_button)

        if allow_retry_errors:
            retry_errors_button = QPushButton("只重练本次出错内容")
            retry_errors_button.clicked.connect(self._accept_retry_errors)
            layout.addWidget(retry_errors_button)

        restart_button = QPushButton("再练一次")
        restart_button.clicked.connect(self._accept_restart)
        library_button = QPushButton("返回")
        library_button.setProperty("variant", "ghost")
        library_button.clicked.connect(self.accept)
        layout.addWidget(restart_button)
        layout.addWidget(library_button)

    def _accept_next(self) -> None:
        self.action = "next"
        self.accept()

    def _accept_restart(self) -> None:
        self.action = "restart"
        self.accept()

    def _accept_retry_errors(self) -> None:
        self.action = "retry_errors"
        self.accept()
