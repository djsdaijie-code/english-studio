from __future__ import annotations

from PySide6.QtCore import QSize, QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from english_typing_trainer.ui.theme import resource_root


class VocabularyQuickAccess(QFrame):
    open_requested = Signal()
    geometry_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VocabularyQuickAccess")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._shortcut_visible = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.added_popup = QFrame()
        self.added_popup.setObjectName("VocabularyAddedPopup")
        popup_layout = QVBoxLayout(self.added_popup)
        popup_layout.setContentsMargins(16, 14, 16, 14)
        popup_layout.setSpacing(5)

        heading = QHBoxLayout()
        title = QLabel("已加入单词本")
        title.setProperty("role", "vocabulary-popup-title")
        self.open_button = QPushButton("打开单词本")
        self.open_button.setProperty("variant", "ghost")
        heading.addWidget(title)
        heading.addStretch(1)
        heading.addWidget(self.open_button)
        popup_layout.addLayout(heading)

        self.word_label = QLabel("")
        self.word_label.setProperty("role", "vocabulary-popup-word")
        self.message_label = QLabel("")
        self.message_label.setProperty("role", "vocabulary-popup-message")
        self.message_label.setWordWrap(True)
        popup_layout.addWidget(self.word_label)
        popup_layout.addWidget(self.message_label)
        self.added_popup.hide()
        layout.addWidget(self.added_popup)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.book_button = QToolButton()
        self.book_button.setObjectName("VocabularyQuickButton")
        self.book_button.setIcon(QIcon(str(resource_root() / "icons" / "vocabulary-book.svg")))
        self.book_button.setIconSize(QSize(24, 24))
        self.book_button.setToolTip("打开单词本")
        self.book_button.setCursor(Qt.CursorShape.PointingHandCursor)
        button_row.addWidget(self.book_button)
        layout.addLayout(button_row)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(4200)
        self._hide_timer.timeout.connect(self.hide_added)
        self.book_button.clicked.connect(self._open)
        self.open_button.clicked.connect(self._open)

    def set_shortcut_visible(self, visible: bool) -> None:
        self._shortcut_visible = visible
        self.book_button.setVisible(visible)
        self.open_button.setVisible(visible)
        self._sync_visibility()

    def show_added(self, word: str, message: str) -> None:
        self.word_label.setText(word)
        self.message_label.setText(message)
        self.added_popup.show()
        self.show()
        self.adjustSize()
        self.raise_()
        self._hide_timer.start()
        self.geometry_changed.emit()

    def hide_added(self) -> None:
        self._hide_timer.stop()
        self.added_popup.hide()
        self.adjustSize()
        self._sync_visibility()
        self.geometry_changed.emit()

    def _open(self) -> None:
        self.hide_added()
        self.open_requested.emit()

    def _sync_visibility(self) -> None:
        self.setVisible(self._shortcut_visible or self.added_popup.isVisible())


__all__ = ["VocabularyQuickAccess"]
