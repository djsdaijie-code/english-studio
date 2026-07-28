from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QSize, QTimer, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFrame, QHBoxLayout, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from english_typing_trainer.ui.theme import resource_root


class VocabularyQuickAccess(QFrame):
    open_requested = Signal()
    geometry_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("VocabularyQuickAccess")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._shortcut_visible = True
        self._drag_press_global: QPoint | None = None
        self._drag_start_position = QPoint()
        self._drag_active = False
        self._manual_anchor: tuple[float, float] | None = None

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
        self.book_button.setToolTip("拖动调整位置，点击打开单词本")
        self.book_button.setCursor(Qt.CursorShape.SizeAllCursor)
        self.book_button.installEventFilter(self)
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

    @property
    def has_custom_position(self) -> bool:
        return self._manual_anchor is not None

    def position_in_parent(self, margin: int = 24) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        if self._manual_anchor is None:
            proposed = QPoint(parent.width() - self.width() - margin, parent.height() - self.height() - margin)
        else:
            target = QPoint(
                round(self._manual_anchor[0] * parent.width()),
                round(self._manual_anchor[1] * parent.height()),
            )
            button_center = self.book_button.mapTo(self, self.book_button.rect().center())
            proposed = target - button_center
        self.move(self._clamp_position(proposed, margin=8))
        self.raise_()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.book_button:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self._drag_press_global = event.globalPosition().toPoint()
                self._drag_start_position = self.pos()
                self._drag_active = False
            elif (
                event.type() == QEvent.Type.MouseMove
                and self._drag_press_global is not None
                and event.buttons() & Qt.MouseButton.LeftButton
            ):
                delta = event.globalPosition().toPoint() - self._drag_press_global
                if not self._drag_active and delta.manhattanLength() >= QApplication.startDragDistance():
                    self._drag_active = True
                    self.book_button.setCursor(Qt.CursorShape.ClosedHandCursor)
                if self._drag_active:
                    self.move(self._clamp_position(self._drag_start_position + delta, margin=8))
                    self.raise_()
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                was_dragged = self._drag_active
                if was_dragged:
                    self._remember_anchor()
                    self.book_button.setDown(False)
                    self.book_button.setCursor(Qt.CursorShape.SizeAllCursor)
                self._drag_press_global = None
                self._drag_active = False
                if was_dragged:
                    event.accept()
                    return True
        return super().eventFilter(watched, event)

    def _clamp_position(self, proposed: QPoint, *, margin: int) -> QPoint:
        parent = self.parentWidget()
        if parent is None:
            return proposed
        maximum_x = max(margin, parent.width() - self.width() - margin)
        maximum_y = max(margin, parent.height() - self.height() - margin)
        return QPoint(
            min(maximum_x, max(margin, proposed.x())),
            min(maximum_y, max(margin, proposed.y())),
        )

    def _remember_anchor(self) -> None:
        parent = self.parentWidget()
        if parent is None or parent.width() <= 0 or parent.height() <= 0:
            return
        button_center = self.book_button.mapTo(parent, self.book_button.rect().center())
        self._manual_anchor = (
            button_center.x() / parent.width(),
            button_center.y() / parent.height(),
        )


__all__ = ["VocabularyQuickAccess"]
