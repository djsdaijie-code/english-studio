from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class PracticeGeneratorDialog(QDialog):
    def __init__(self, mode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = mode
        self.setWindowTitle("生成专项练习")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.range_combo = QComboBox()
        self.range_combo.addItem("最近 7 天", "7d")
        self.range_combo.addItem("最近 30 天", "30d")
        self.range_combo.addItem("最近 90 天", "90d")
        self.range_combo.addItem("全部", "all")
        self.count_combo = QComboBox()
        for label, value in (("5", 5), ("10", 10), ("20", 20), ("30", 30), ("50", 50)):
            self.count_combo.addItem(label, value)
        self.repeat_combo = QComboBox()
        for label, value in (("1", 1), ("3", 3), ("5", 5)):
            self.repeat_combo.addItem(label, value)
        self.arrangement_combo = QComboBox()
        self.arrangement_combo.addItem("重复排列", "repeat")
        self.arrangement_combo.addItem("轮转混合", "mixed")
        self.arrangement_combo.addItem("单词加原句", "with_context")
        form.addRow("时间范围", self.range_combo)
        form.addRow("数量", self.count_combo)
        if mode in {"error_words", "mixed_review"}:
            form.addRow("重复次数", self.repeat_combo)
            form.addRow("生成方式", self.arrangement_combo)
        layout.addLayout(form)

        button_row = QHBoxLayout()
        self.cancel_button = QPushButton("取消")
        self.confirm_button = QPushButton("生成预览")
        self.confirm_button.setProperty("variant", "primary")
        self.cancel_button.clicked.connect(self.reject)
        self.confirm_button.clicked.connect(self.accept)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.confirm_button)
        layout.addLayout(button_row)

    def payload(self) -> dict[str, object]:
        return {
            "mode": self._mode,
            "range_key": self.range_combo.currentData(),
            "count": int(self.count_combo.currentData()),
            "repeat_count": int(self.repeat_combo.currentData()),
            "arrangement": self.arrangement_combo.currentData(),
        }


class SpecialPracticePage(QWidget):
    generate_requested = Signal(dict)
    start_preview_requested = Signal()
    start_saved_requested = Signal(int)
    refresh_requested = Signal()
    start_today_review_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dialogs: dict[str, PracticeGeneratorDialog] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("专项练习")
        title.setProperty("role", "page-title")
        subtitle = QLabel("围绕错词、错字和生词，生成更聚焦的练习。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self.summary_card = QFrame()
        self.summary_card.setObjectName("CardAccent")
        summary_layout = QVBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(18, 16, 18, 16)
        summary_title = QLabel("今日复习")
        summary_title.setProperty("role", "page-title")
        summary_title.setStyleSheet("font-size: 18px;")
        self.summary_label = QLabel("今天还没有复习概览。")
        self.summary_label.setWordWrap(True)
        self.summary_label.setProperty("role", "subtitle")
        self.today_review_button = QPushButton("开始今日复习")
        self.today_review_button.setProperty("variant", "primary")
        summary_layout.addWidget(summary_title)
        summary_layout.addWidget(self.summary_label)
        summary_layout.addWidget(self.today_review_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.summary_card)

        cards_layout = QGridLayout()
        cards_layout.setSpacing(12)
        self.entry_cards: dict[str, QLabel] = {}
        entries = [
            ("error_words", "错词练习", "根据历史中反复输入错误的单词生成练习。"),
            ("error_characters", "错误字符", "针对经常出错的字符和混淆组合反复练习。"),
            ("context_sentences", "原句复习", "回到原文语境，重新练习错误单词所在句子。"),
            ("vocabulary_review", "生词复习", "按到期时间和熟练度安排重点单词复习。"),
        ]
        for index, (key, title_text, body_text) in enumerate(entries):
            card = QFrame()
            card.setObjectName("Card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(16, 16, 16, 16)
            title_label = QLabel(title_text)
            title_label.setProperty("role", "page-title")
            title_label.setStyleSheet("font-size: 18px;")
            body_label = QLabel(body_text)
            body_label.setWordWrap(True)
            body_label.setProperty("role", "subtitle")
            count_label = QLabel("可练数量：-")
            count_label.setProperty("role", "metric-title")
            start_button = QPushButton("开始")
            start_button.setProperty("variant", "primary")
            start_button.clicked.connect(lambda checked=False, mode=key: self._open_generator(mode))
            card_layout.addWidget(title_label)
            card_layout.addWidget(body_label)
            card_layout.addStretch(1)
            card_layout.addWidget(count_label)
            card_layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignLeft)
            cards_layout.addWidget(card, index // 2, index % 2)
            self.entry_cards[key] = count_label
        layout.addLayout(cards_layout)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "subtitle")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(16, 16, 16, 16)
        preview_title = QLabel("练习预览")
        preview_title.setProperty("role", "page-title")
        preview_title.setStyleSheet("font-size: 18px;")
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("选择一种专项练习后，再生成预览。")
        preview_actions = QHBoxLayout()
        self.start_preview_button = QPushButton("开始当前预览")
        self.refresh_button = QPushButton("刷新已保存练习")
        preview_actions.addWidget(self.start_preview_button)
        preview_actions.addWidget(self.refresh_button)
        preview_actions.addStretch(1)
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.preview)
        preview_layout.addLayout(preview_actions)
        layout.addWidget(preview_card, stretch=1)

        saved_card = QFrame()
        saved_card.setObjectName("Card")
        saved_layout = QVBoxLayout(saved_card)
        saved_layout.setContentsMargins(16, 16, 16, 16)
        saved_title = QLabel("已保存练习")
        saved_title.setProperty("role", "page-title")
        saved_title.setStyleSheet("font-size: 18px;")
        self.saved_sets = QListWidget()
        self.start_saved_button = QPushButton("开始所选练习")
        saved_layout.addWidget(saved_title)
        saved_layout.addWidget(self.saved_sets)
        saved_layout.addWidget(self.start_saved_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(saved_card, stretch=1)

        self.start_preview_button.clicked.connect(self.start_preview_requested.emit)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.today_review_button.clicked.connect(self.start_today_review_requested.emit)
        self.start_saved_button.clicked.connect(self._emit_start_saved)

    def set_summary(self, summary: dict[str, int]) -> None:
        self.summary_label.setText(
            f"待复习 {summary['due_count']} 个，逾期 {summary['overdue_count']} 个，"
            f"新增 {summary['new_count']} 个，学习中 {summary['learning_count']} 个，"
            f"已掌握 {summary['mastered_count']} 个。"
        )
        self.entry_cards["vocabulary_review"].setText(f"可练数量：{summary['due_count']} 个")

    def set_preview(self, text: str, message: str) -> None:
        self.preview.setPlainText(text)
        self.status_label.setText(message)

    def populate_saved_sets(self, sets) -> None:
        self.saved_sets.clear()
        counts = {
            "error_words": 0,
            "error_characters": 0,
            "context_sentences": 0,
            "vocabulary_review": 0,
        }
        for practice_set in sets:
            item = QListWidgetItem(
                f"{practice_set.title}\n{self._mode_label(practice_set.practice_mode)} · {practice_set.item_count} 项"
            )
            item.setData(Qt.ItemDataRole.UserRole, practice_set.id)
            self.saved_sets.addItem(item)
            if practice_set.practice_mode in counts:
                counts[practice_set.practice_mode] += practice_set.item_count
        self.entry_cards["error_words"].setText(f"可练数量：约 {counts['error_words']} 个错词")
        self.entry_cards["error_characters"].setText(f"可练数量：约 {counts['error_characters']} 个字符")
        self.entry_cards["context_sentences"].setText(f"可练数量：约 {counts['context_sentences']} 个原句")
        if counts["vocabulary_review"]:
            self.entry_cards["vocabulary_review"].setText(f"可练数量：约 {counts['vocabulary_review']} 个生词")

    def selected_saved_set_id(self) -> int | None:
        item = self.saved_sets.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _open_generator(self, mode: str) -> None:
        dialog = self._dialogs.get(mode)
        if dialog is None:
            dialog = PracticeGeneratorDialog(mode, self)
            self._dialogs[mode] = dialog
        if dialog.exec():
            self.generate_requested.emit(dialog.payload())

    def _emit_start_saved(self) -> None:
        practice_set_id = self.selected_saved_set_id()
        if practice_set_id is not None:
            self.start_saved_requested.emit(practice_set_id)

    def _mode_label(self, practice_mode: str) -> str:
        mapping = {
            "error_words": "错词练习",
            "error_characters": "错误字符",
            "context_sentences": "原句复习",
            "vocabulary_review": "生词复习",
            "mixed_review": "混合复习",
        }
        return mapping.get(practice_mode, practice_mode)
