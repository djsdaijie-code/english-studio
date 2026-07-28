from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton, QWidget

from english_typing_trainer.ui.theme import resource_root


def format_learning_duration(seconds: float) -> str:
    total_seconds = max(0, int(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class TodayLearningTimeBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("TodayLearningTimeBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._seconds = 0.0
        self._time_hidden = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 5, 24, 5)
        layout.setSpacing(8)
        layout.addStretch(1)

        self.title_label = QLabel("今日学习")
        self.title_label.setObjectName("TodayLearningTimeTitle")
        self.value_label = QLabel(format_learning_duration(0))
        self.value_label.setObjectName("TodayLearningTimeValue")
        self.value_label.setMinimumWidth(70)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

        self.visibility_button = QToolButton()
        self.visibility_button.setObjectName("TodayLearningTimeToggle")
        self.visibility_button.setIconSize(QSize(18, 18))
        self.visibility_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.visibility_button.clicked.connect(self.toggle_time_visibility)
        layout.addWidget(self.visibility_button)
        self.set_hide_control_visible(False)
        self._refresh_display()

    @property
    def time_hidden(self) -> bool:
        return self._time_hidden

    def set_seconds(self, seconds: float) -> None:
        self._seconds = max(0.0, float(seconds))
        self._refresh_display()

    def set_hide_control_visible(self, visible: bool) -> None:
        self.visibility_button.setVisible(visible)
        self.setProperty("typingPage", "true" if visible else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def toggle_time_visibility(self) -> None:
        self._time_hidden = not self._time_hidden
        self._refresh_display()

    def _refresh_display(self) -> None:
        icon_name = "eye-off.svg" if self._time_hidden else "eye.svg"
        self.visibility_button.setIcon(QIcon(str(resource_root() / "icons" / icon_name)))
        self.visibility_button.setToolTip("显示今日学习时间" if self._time_hidden else "隐藏今日学习时间")
        self.value_label.setText("已隐藏" if self._time_hidden else format_learning_duration(self._seconds))


__all__ = ["TodayLearningTimeBar", "format_learning_duration"]
