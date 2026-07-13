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
    open_learning_requested = Signal(int)
    play_requested = Signal(int)
    delete_requested = Signal(int)
    row_learning_requested = Signal(object)
    scope_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rows: list[dict[str, object]] = []
        self._editor = VocabularyEditorDialog(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("单词本")
        title.setProperty("role", "page-title")
        subtitle = QLabel("收藏文章中的单词，用词典、语境讲解和输入练习逐步掌握。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        filter_card = QFrame()
        filter_card.setObjectName("Card")
        filter_layout = QVBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 16, 16, 16)
        top_filters = QHBoxLayout()
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("待学习", "learning")
        self.scope_combo.addItem("当前文章", "article")
        self.scope_combo.addItem("全部", "all")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索单词、释义或备注")
        self.status_combo = QComboBox()
        self.status_combo.addItem("全部状态", "all")
        self.status_combo.addItem("新加入", "new")
        self.status_combo.addItem("学习中", "learning")
        self.status_combo.addItem("复习中", "reviewing")
        self.status_combo.addItem("已掌握", "mastered")
        self.sort_combo=QComboBox(); self.sort_combo.addItem("首次出现","first"); self.sort_combo.addItem("出现次数","frequency"); self.sort_combo.addItem("字母顺序","alpha")
        self.hide_mastered_checkbox=QCheckBox("隐藏已掌握")
        self.archived_checkbox = QCheckBox("显示已归档")
        self.due_only_checkbox = QCheckBox("只看待复习")
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setProperty("variant", "ghost")
        for widget in (
            self.scope_combo,
            self.search_input,
            self.status_combo,
            self.sort_combo,
            self.hide_mastered_checkbox,
            self.archived_checkbox,
            self.due_only_checkbox,
            self.refresh_button,
        ):
            top_filters.addWidget(widget)
        filter_layout.addLayout(top_filters)

        add_row = QHBoxLayout()
        self.manual_word_input = QLineEdit()
        self.manual_word_input.setPlaceholderText("手动添加一个单词")
        self.add_button = QPushButton("添加单词")
        self.add_button.setProperty("variant", "primary")
        add_row.addWidget(self.manual_word_input)
        add_row.addWidget(self.add_button)
        filter_layout.addLayout(add_row)
        layout.addWidget(filter_card)

        self.table = QTableWidget(0, 8)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["单词", "出现次数", "音标", "中文意思", "词性", "来源文章", "状态", "最近练习"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        footer = QHBoxLayout()
        self.empty_label = QLabel("单词本还是空的")
        self.empty_label.setProperty("role", "muted")
        self.edit_button = QPushButton("编辑释义")
        self.archive_button = QPushButton("归档")
        self.restore_button = QPushButton("恢复")
        self.mastered_button = QPushButton("标记掌握")
        self.learning_button = QPushButton("重新设为学习中")
        self.review_button = QPushButton("立即复习")
        self.review_button.setProperty("variant", "primary")
        self.open_button = QPushButton("打开学习"); self.open_button.setProperty("variant", "primary")
        self.play_button = QPushButton("播放单词")
        self.delete_button = QPushButton("删除"); self.delete_button.setProperty("variant", "danger")
        footer.addWidget(self.empty_label)
        footer.addStretch(1)
        footer.addWidget(self.edit_button)
        footer.addWidget(self.archive_button)
        footer.addWidget(self.restore_button)
        footer.addWidget(self.mastered_button)
        footer.addWidget(self.learning_button)
        footer.addWidget(self.play_button); footer.addWidget(self.delete_button); footer.addWidget(self.review_button); footer.addWidget(self.open_button)
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
        self.open_button.clicked.connect(self._emit_learning)
        self.play_button.clicked.connect(lambda: self._emit_id(self.play_requested))
        self.delete_button.clicked.connect(lambda: self._emit_id(self.delete_requested))
        self.table.cellDoubleClicked.connect(lambda _row,_column:self._emit_learning())
        self.search_input.textChanged.connect(lambda _text:self.refresh_requested.emit())
        self.status_combo.currentIndexChanged.connect(lambda _index:self.refresh_requested.emit())
        self.scope_combo.currentIndexChanged.connect(lambda _index:self.scope_changed.emit(str(self.scope_combo.currentData())))
        self.sort_combo.currentIndexChanged.connect(lambda _index:self.refresh_requested.emit())
        self.hide_mastered_checkbox.toggled.connect(lambda _checked:self.refresh_requested.emit())
        self._update_action_state()
        for obsolete in (self.edit_button,self.archive_button,self.restore_button,self.review_button,self.archived_checkbox,self.due_only_checkbox):
            obsolete.hide()

    def populate_items(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows
        self.table.setRowCount(len(rows))
        self.empty_label.setVisible(len(rows) == 0)
        for row_index, row in enumerate(rows):
            values = [
                row["display_word"],
                row.get("occurrence_count") or "-",
                row.get("phonetic") or "暂无",
                row.get("meaning_zh") or row.get("meaning") or "待获取",
                row.get("primary_part_of_speech") or "暂无",
                row.get("article_title") or "手动添加",
                self._status_label(str(row["status"])),
                _local_text(row.get("last_practiced_at") or row.get("last_reviewed_at") or None),
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
        self.edit_button.setEnabled(has_selection)
        self.review_button.setEnabled(has_selection)
        self.mastered_button.setEnabled(has_selection)
        self.learning_button.setEnabled(has_selection)
        self.open_button.setEnabled(has_selection); self.play_button.setEnabled(has_selection); self.delete_button.setEnabled(has_selection)
        mastered = bool(selected and selected.get("status") == "mastered")
        self.mastered_button.setVisible(has_selection and not mastered)
        self.learning_button.setVisible(has_selection and mastered)
        self.edit_button.hide(); self.archive_button.hide(); self.restore_button.hide(); self.review_button.hide()

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

    def _emit_id(self, signal) -> None:
        item_id=self.selected_item_id()
        if item_id is not None: signal.emit(item_id)

    def _emit_learning(self) -> None:
        row=self._selected_row()
        if row:self.row_learning_requested.emit(row)

    def set_article_available(self,available:bool) -> None:
        index=self.scope_combo.findData("article")
        self.scope_combo.model().item(index).setEnabled(available)

    def _status_label(self, status: str) -> str:
        mapping = {
            "new": "新加入",
            "learning": "学习中",
            "reviewing": "复习中",
            "mastered": "已掌握",
        }
        return mapping.get(status, status)
