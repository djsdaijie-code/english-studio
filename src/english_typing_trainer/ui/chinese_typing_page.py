from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class ChineseTypingPage(QWidget):
    import_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("中文打字练习")
        title.setProperty("role", "page-title")
        subtitle = QLabel("粘贴标题和整篇中文正文，使用五笔或其他中文输入法练习。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 28)
        card_layout.setSpacing(14)

        heading = QLabel("开始一篇中文练习")
        heading.setProperty("role", "section-title")
        description = QLabel(
            "填写文章标题并粘贴正文。正文会作为一篇完整文章保存，不自动分段；"
            "练习速度按正确汉字数显示为“字/分钟”。"
        )
        description.setProperty("role", "subtitle")
        description.setWordWrap(True)
        self.import_button = QPushButton("粘贴中文文章")
        self.import_button.setProperty("variant", "primary")
        self.import_button.clicked.connect(self.import_requested.emit)

        card_layout.addWidget(heading)
        card_layout.addWidget(description)
        card_layout.addSpacing(8)
        card_layout.addWidget(self.import_button)
        card_layout.addStretch(1)
        layout.addWidget(card, stretch=1)
