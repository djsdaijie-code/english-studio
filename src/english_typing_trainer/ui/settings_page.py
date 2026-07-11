from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.models.settings import AppSettings


class SettingsPage(QWidget):
    def __init__(self, data_dir: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        title = QLabel("设置")
        title.setProperty("role", "page-title")
        subtitle = QLabel("调整练习规则、界面外观和本地数据相关选项。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        content_row = QHBoxLayout()
        content_row.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(960)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        practice_card = self._build_practice_card()
        appearance_card = self._build_appearance_card()
        data_card = self._build_data_card(data_dir)
        content_layout.addWidget(practice_card)
        content_layout.addWidget(appearance_card)
        content_layout.addWidget(data_card)

        footer = QHBoxLayout()
        self.status_label = QLabel("所有设置均已保存。")
        self.status_label.setProperty("role", "subtitle")
        self.save_button = QPushButton("保存设置")
        self.save_button.setProperty("variant", "primary")
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        footer.addWidget(self.save_button)
        content_layout.addLayout(footer)

        content_row.addWidget(content, stretch=1)
        content_row.addStretch(1)
        layout.addLayout(content_row)

        self.section_target_combo.currentIndexChanged.connect(self._mark_dirty)
        self.case_sensitive_checkbox.toggled.connect(self._mark_dirty)
        self.live_stats_checkbox.toggled.connect(self._mark_dirty)
        self.target_wpm_spin.valueChanged.connect(self._mark_dirty)
        self.target_accuracy_spin.valueChanged.connect(self._mark_dirty)
        self.theme_combo.currentIndexChanged.connect(self._mark_dirty)
        self.font_size_spin.valueChanged.connect(self._mark_dirty)

    def _build_practice_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("练习")
        title.setProperty("role", "page-title")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.section_target_combo = QComboBox()
        for value in (300, 500, 800, 1000):
            self.section_target_combo.addItem(str(value), value)
        self.case_sensitive_checkbox = QCheckBox("区分大小写")
        self.live_stats_checkbox = QCheckBox("显示实时统计")
        self.target_wpm_spin = QSpinBox()
        self.target_wpm_spin.setRange(10, 300)
        self.target_accuracy_spin = QDoubleSpinBox()
        self.target_accuracy_spin.setRange(50.0, 100.0)
        self.target_accuracy_spin.setDecimals(1)
        self.target_accuracy_spin.setSingleStep(0.5)
        form.addRow("默认分段字数", self.section_target_combo)
        form.addRow("输入规则", self.case_sensitive_checkbox)
        form.addRow("实时统计", self.live_stats_checkbox)
        form.addRow("目标 WPM", self.target_wpm_spin)
        form.addRow("目标正确率", self.target_accuracy_spin)
        layout.addLayout(form)
        return card

    def _build_appearance_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("外观")
        title.setProperty("role", "page-title")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.addItem("跟随系统", "system")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 36)
        form.addRow("主题", self.theme_combo)
        form.addRow("字体大小", self.font_size_spin)
        layout.addLayout(form)
        return card

    def _build_data_card(self, data_dir: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("数据")
        title.setProperty("role", "page-title")
        title.setStyleSheet("font-size: 18px;")
        self.data_dir_label = QLabel(data_dir)
        self.data_dir_label.setWordWrap(True)
        self.data_dir_label.setProperty("role", "subtitle")
        self.open_data_dir_button = QPushButton("打开数据目录")
        self.backup_hint = QLabel("数据库、日志和备份都会保存在这个目录中。")
        self.backup_hint.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(self.data_dir_label)
        layout.addWidget(self.open_data_dir_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.backup_hint)
        return card

    def load_settings(self, settings: AppSettings) -> None:
        index = self.section_target_combo.findData(settings.section_target_characters)
        if index >= 0:
            self.section_target_combo.setCurrentIndex(index)
        self.case_sensitive_checkbox.setChecked(settings.case_sensitive)
        self.live_stats_checkbox.setChecked(settings.show_live_stats)
        self.target_wpm_spin.setValue(settings.target_wpm)
        self.target_accuracy_spin.setValue(settings.target_accuracy)
        self.font_size_spin.setValue(settings.font_size)
        theme_index = self.theme_combo.findData(settings.theme)
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self.status_label.setText("所有设置均已保存。")

    def build_settings(self) -> AppSettings:
        return AppSettings(
            section_target_characters=int(self.section_target_combo.currentData()),
            case_sensitive=self.case_sensitive_checkbox.isChecked(),
            show_live_stats=self.live_stats_checkbox.isChecked(),
            target_wpm=self.target_wpm_spin.value(),
            target_accuracy=self.target_accuracy_spin.value(),
            theme=str(self.theme_combo.currentData()),
            font_size=self.font_size_spin.value(),
        )

    def _mark_dirty(self, *_args) -> None:
        self.status_label.setText("设置已修改，尚未保存。")
