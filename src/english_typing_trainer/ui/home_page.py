from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from english_typing_trainer.ui.daily_learning_card import DailyLearningCard


class HomeActionCard(QFrame):
    """A compact shortcut that keeps the home page focused on starting study."""

    def __init__(self, title: str, description: str, action_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setMinimumHeight(150)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(8)
        title_label = QLabel(title)
        title_label.setProperty("role", "section-title")
        description_label = QLabel(description)
        description_label.setProperty("role", "subtitle")
        description_label.setWordWrap(True)
        self.action_button = QPushButton(action_text)
        self.action_button.setProperty("variant", "ghost")
        layout.addWidget(title_label)
        layout.addWidget(description_label, stretch=1)
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignLeft)


class HomePage(QWidget):
    article_library_requested = Signal()
    courses_requested = Signal()
    special_practice_requested = Signal()
    vocabulary_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(18)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("首页")
        title.setProperty("role", "page-title")
        subtitle = QLabel("从今天的学习开始，也可以快速回到你的文章和课程。")
        subtitle.setProperty("role", "subtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading)
        header.addStretch(1)
        layout.addLayout(header)

        self.daily_learning_card = DailyLearningCard()
        layout.addWidget(self.daily_learning_card)

        section_title = QLabel("继续学习")
        section_title.setProperty("role", "section-title")
        layout.addWidget(section_title)

        shortcuts = QGridLayout()
        shortcuts.setHorizontalSpacing(16)
        shortcuts.setVerticalSpacing(16)
        self.article_card = HomeActionCard(
            "文章库",
            "导入文章、继续上次练习，或从头开始一段新的阅读。",
            "打开文章库",
        )
        self.course_card = HomeActionCard(
            "内置课程",
            "按推荐 Day 学习，也可以自由打开任意课程内容。",
            "查看课程",
        )
        self.special_card = HomeActionCard(
            "专项练习",
            "针对错词、错误字符和原句安排一次练习。",
            "开始专项练习",
        )
        self.vocabulary_card = HomeActionCard(
            "单词本",
            "复习已收藏的单词、听写和间隔复习任务。",
            "打开单词本",
        )
        shortcuts.addWidget(self.article_card, 0, 0)
        shortcuts.addWidget(self.course_card, 0, 1)
        shortcuts.addWidget(self.special_card, 1, 0)
        shortcuts.addWidget(self.vocabulary_card, 1, 1)
        shortcuts.setColumnStretch(0, 1)
        shortcuts.setColumnStretch(1, 1)
        layout.addLayout(shortcuts)
        layout.addStretch(1)

        self.article_card.action_button.clicked.connect(self.article_library_requested.emit)
        self.course_card.action_button.clicked.connect(self.courses_requested.emit)
        self.special_card.action_button.clicked.connect(self.special_practice_requested.emit)
        self.vocabulary_card.action_button.clicked.connect(self.vocabulary_requested.emit)
