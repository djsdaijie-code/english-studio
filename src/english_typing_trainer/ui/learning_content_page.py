from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStackedWidget, QVBoxLayout, QWidget

from english_typing_trainer.ui.segmented_control import SegmentedControl


class LearningContentPage(QWidget):
    """Groups user-owned articles and the built-in course catalog in one place."""

    section_changed = Signal(str)

    def __init__(
        self,
        article_page: QWidget,
        course_page: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setContentsMargins(32, 18, 32, 8)
        heading = QLabel("学习内容")
        heading.setProperty("role", "section-title")
        self.section_control = SegmentedControl(
            [("文章库", "articles"), ("内置课程", "courses")]
        )
        self.section_control.set_value("articles")
        header.addWidget(heading)
        header.addStretch(1)
        header.addWidget(self.section_control)
        layout.addLayout(header)

        self.content_stack = QStackedWidget()
        self.content_stack.addWidget(article_page)
        self.content_stack.addWidget(course_page)
        layout.addWidget(self.content_stack, stretch=1)

        self.section_control.value_changed.connect(self._change_section)

    def current_section(self) -> str:
        return self.section_control.value()

    def set_section(self, section: str) -> None:
        self.section_control.set_value(section)
        self.content_stack.setCurrentIndex(0 if section == "articles" else 1)

    def _change_section(self, section: str) -> None:
        self.content_stack.setCurrentIndex(0 if section == "articles" else 1)
        self.section_changed.emit(section)
