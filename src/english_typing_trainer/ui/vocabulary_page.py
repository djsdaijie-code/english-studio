from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


def _local_text(value: str | None) -> str:
    if not value:
        return "暂无"
    try:
        return datetime.fromisoformat(value).strftime("%m-%d %H:%M")
    except ValueError:
        return value


class VocabularyEditorDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("编辑生词")
        self.resize(520, 320)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.meaning_edit = QLineEdit()
        self.note_edit = QTextEdit()
        self.note_edit.setFixedHeight(120)
        form.addRow("中文释义", self.meaning_edit)
        form.addRow("备注", self.note_edit)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        self.save_button = QPushButton("保存")
        self.save_button.setProperty("variant", "primary")
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)
        buttons.addStretch(1)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.save_button)
        layout.addLayout(buttons)


class VocabularyPage(QWidget):
    refresh_requested = Signal()
    add_requested = Signal(str)
    save_requested = Signal(int, str, str)
    archive_requested = Signal(int, bool)
    mastery_requested = Signal(int, bool)
    review_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []
        self._editor = VocabularyEditorDialog(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("生词本")
        title.setProperty("role", "page-title")
        subtitle = QLabel("把常错单词和重点词汇集中起来，逐步复习直到真正掌握。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        filter_card = QFrame()
        filter_card.setObjectName("Card")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 16, 16, 16)
        top_filters = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索单词、释义或备注")
        self.status_combo = QComboBox()
        self.status_combo.addItem("全部状态", "all")
        self.status_combo.addItem("新加入", "new")
        self.status_combo.addItem("学习中", "learning")
        self.status_combo.addItem("复习中", "reviewing")
        self.status_combo.addItem("已掌握", "mastered")
        self.archived_checkbox = QCheckBox("显示已归档")
        self.due_only_checkbox = QCheckBox("只看待复习")
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setProperty("variant", "ghost")
        for widget in (
            self.search_input,
            self.status_combo,
            self.archived_checkbox,
            self.due_only_checkbox,
            self.refresh_button,
        ):
            top_filters.addWidget(widget)
        filter_layout.addLayout(top_filters)

        add_row = QHBoxLayout()
        self.manual_word_input = QLineEdit()
        self.manual_word_input.setPlaceholderText("手动添加一个单词")
        self.add_button = QPushButton("添加生词")
        self.add_button.setProperty("variant", "primary")
        add_row.addWidget(self.manual_word_input)
        add_row.addWidget(self.add_button)
        filter_layout.addLayout(add_row)
        layout.addWidget(filter_card)

        self.table = QTableWidget(0, 6)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["单词", "中文释义", "熟练度", "状态", "下次复习", "最近复习"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        footer = QHBoxLayout()
        self.empty_label = QLabel("生词本还是空的")
        self.empty_label.setProperty("role", "muted")
        self.edit_button = QPushButton("编辑释义")
        self.archive_button = QPushButton("归档")
        self.restore_button = QPushButton("恢复")
        self.mastered_button = QPushButton("标记掌握")
        self.learning_button = QPushButton("重新设为学习中")
        self.review_button = QPushButton("立即复习")
        self.review_button.setProperty("variant", "primary")
        footer.addWidget(self.empty_label)
        footer.addStretch(1)
        footer.addWidget(self.edit_button)
        footer.addWidget(self.archive_button)
        footer.addWidget(self.restore_button)
        footer.addWidget(self.mastered_button)
        footer.addWidget(self.learning_button)
        footer.addWidget(self.review_button)
        layout.addLayout(footer)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "subtitle")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.table.itemSelectionChanged.connect(self._update_action_state)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.add_button.clicked.connect(self._emit_add)
        self.edit_button.clicked.connect(self._open_editor)
        self.archive_button.clicked.connect(lambda: self._emit_archive(True))
        self.restore_button.clicked.connect(lambda: self._emit_archive(False))
        self.mastered_button.clicked.connect(lambda: self._emit_mastery(True))
        self.learning_button.clicked.connect(lambda: self._emit_mastery(False))
        self.review_button.clicked.connect(self._emit_review)
        self._update_action_state()

    def populate_items(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.table.setRowCount(len(rows))
        self.empty_label.setVisible(len(rows) == 0)
        for row_index, row in enumerate(rows):
            values = [
                row["display_word"],
                row["meaning"] or "未填写",
                row["mastery_level"],
                self._status_label(str(row["status"])),
                _local_text(row["next_review_at"] or None),
                _local_text(row["last_reviewed_at"] or None),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 0:
                    item.setData(32, row["id"])
                self.table.setItem(row_index, column, item)
        if rows:
            self.table.setCurrentCell(0, 0)
        self._update_action_state()

    def selected_item_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(32) if item else None

    def set_status_message(self, text: str) -> None:
        self.status_label.setText(text)

    def _selected_row(self) -> dict[str, object] | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def _update_action_state(self) -> None:
        selected = self._selected_row()
        has_selection = selected is not None
        archived = bool(selected.get("is_archived")) if selected else False
        self.edit_button.setEnabled(has_selection)
        self.review_button.setEnabled(has_selection)
        self.mastered_button.setEnabled(has_selection)
        self.learning_button.setEnabled(has_selection)
        self.archive_button.setVisible(has_selection and not archived)
        self.restore_button.setVisible(has_selection and archived)

    def _emit_add(self) -> None:
        if self.manual_word_input.text().strip():
            self.add_requested.emit(self.manual_word_input.text().strip())
            self.manual_word_input.clear()

    def _open_editor(self) -> None:
        item = self._selected_row()
        if item is None:
            return
        self._editor.meaning_edit.setText(str(item["meaning"]))
        self._editor.note_edit.setPlainText(str(item["note"]))
        if self._editor.exec():
            item_id = self.selected_item_id()
            if item_id is not None:
                self.save_requested.emit(
                    item_id,
                    self._editor.meaning_edit.text().strip(),
                    self._editor.note_edit.toPlainText().strip(),
                )

    def _emit_archive(self, archived: bool) -> None:
        item_id = self.selected_item_id()
        if item_id is not None:
            self.archive_requested.emit(item_id, archived)

    def _emit_mastery(self, mastered: bool) -> None:
        item_id = self.selected_item_id()
        if item_id is not None:
            self.mastery_requested.emit(item_id, mastered)

    def _emit_review(self) -> None:
        item_id = self.selected_item_id()
        if item_id is not None:
            self.review_requested.emit(item_id)

    def _status_label(self, status: str) -> str:
        mapping = {
            "new": "新加入",
            "learning": "学习中",
            "reviewing": "复习中",
            "mastered": "已掌握",
        }
        return mapping.get(status, status)
