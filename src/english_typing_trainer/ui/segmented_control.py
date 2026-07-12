from __future__ import annotations

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QPushButton, QWidget


class SegmentedControl(QFrame):
    value_changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SegmentedControl")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for index, (label, value) in enumerate(options):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("segment", "true")
            button.setMinimumWidth(104)
            self._group.addButton(button, index)
            self._buttons[value] = button
            layout.addWidget(button)
        self._group.idClicked.connect(self._emit_value)

    def value(self) -> str:
        for value, button in self._buttons.items():
            if button.isChecked():
                return value
        return next(iter(self._buttons))

    def set_value(self, value: str) -> None:
        button = self._buttons.get(value)
        if button is None:
            return
        with QSignalBlocker(self._group):
            button.setChecked(True)

    def button(self, value: str) -> QPushButton:
        return self._buttons[value]

    def _emit_value(self, _button_id: int) -> None:
        self.value_changed.emit(self.value())
