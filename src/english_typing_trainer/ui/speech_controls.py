from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QToolButton, QWidget

from english_typing_trainer.ui.theme import resource_root


class SpeechControls(QWidget):
    play_requested = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(6)
        self.status_label = QLabel(""); self.status_label.setProperty("role", "muted")
        self.speed_combo = QComboBox()
        self.speed_combo.setMinimumWidth(72)
        for label, value in (("0.8×", 0.8), ("1.0×", 1.0), ("1.2×", 1.2)):
            self.speed_combo.addItem(label, value)
        self.play_button = QToolButton(); self.play_button.setObjectName("SpeechButton")
        self.play_button.setIcon(QIcon(str(resource_root() / "icons" / "speaker.svg")))
        self.play_button.setToolTip("朗读当前句")
        self.play_button.clicked.connect(lambda: self.play_requested.emit(float(self.speed_combo.currentData())))
        layout.addWidget(self.status_label); layout.addWidget(self.speed_combo); layout.addWidget(self.play_button)

    def set_speed(self, speed: float) -> None:
        index = self.speed_combo.findData(speed)
        self.speed_combo.setCurrentIndex(index if index >= 0 else 1)

    def set_state(self, state: str, message: str = "") -> None:
        self.status_label.setText(message)
        self.play_button.setEnabled(state != "loading")
        icon = "pause.svg" if state == "playing" else "speaker.svg"
        self.play_button.setIcon(QIcon(str(resource_root() / "icons" / icon)))
        self.play_button.setToolTip({"loading":"正在生成语音","playing":"暂停","paused":"继续"}.get(state, "朗读当前句"))
