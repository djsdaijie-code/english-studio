from __future__ import annotations

from datetime import date, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)


def _local_text(value: str | None) -> str:
    if not value:
        return "暂无"
    try:
        return datetime.fromisoformat(value).strftime("%Y年%m月%d日 %H:%M")
    except ValueError:
        return value


class HistoryPage(QWidget):
    view_detail_requested = Signal(int)
    delete_session_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("练习记录")
        title.setProperty("role", "page-title")
        subtitle = QLabel("查看每次练习的时间、成绩和详细错误。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        filter_card = QFrame()
        filter_card.setObjectName("Card")
        filters = QHBoxLayout(filter_card)
        filters.setContentsMargins(16, 16, 16, 16)
        filters.setSpacing(10)

        self.article_filter = QComboBox()
        self.article_filter.addItem("全部文章", None)
        self.range_filter = QComboBox()
        self.range_filter.addItem("全部时间", "all")
        self.range_filter.addItem("今天", "today")
        self.range_filter.addItem("最近 7 天", "7d")
        self.range_filter.addItem("最近 30 天", "30d")
        self.range_filter.addItem("自定义", "custom")
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(date.today())
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(date.today())
        self.completed_filter = QComboBox()
        self.completed_filter.addItem("全部状态", None)
        self.completed_filter.addItem("仅已完成", True)
        self.completed_filter.addItem("仅未完成", False)
        self.practice_type_filter = QComboBox()
        self.practice_type_filter.addItem("全部练习", None)
        self.practice_type_filter.addItem("普通文章", "article")
        self.practice_type_filter.addItem("错词练习", "error_words")
        self.practice_type_filter.addItem("错误字符", "error_characters")
        self.practice_type_filter.addItem("原句复习", "context_sentences")
        self.practice_type_filter.addItem("生词复习", "vocabulary_review")
        self.practice_type_filter.addItem("混合复习", "mixed_review")
        self.sort_filter = QComboBox()
        self.sort_filter.addItem("按时间", "created_at")
        self.sort_filter.addItem("按 WPM", "wpm")
        self.sort_filter.addItem("按正确率", "accuracy")
        self.sort_filter.addItem("按错误数", "error_keystrokes")
        self.sort_filter.addItem("按时长", "active_seconds")
        self.desc_checkbox = QCheckBox("倒序")
        self.desc_checkbox.setChecked(True)
        self.valid_only_checkbox = QCheckBox("只看有效成绩")
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.setProperty("variant", "primary")

        for widget in (
            self.article_filter,
            self.range_filter,
            self.start_date,
            self.end_date,
            self.completed_filter,
            self.practice_type_filter,
            self.sort_filter,
            self.desc_checkbox,
            self.valid_only_checkbox,
            self.refresh_button,
        ):
            filters.addWidget(widget)
        layout.addWidget(filter_card)

        self.table = QTableWidget(0, 10)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(
            ["时间", "练习类型", "文章 / 练习", "段落", "状态", "时长", "WPM", "CPM", "正确率", "错误数"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        footer = QHBoxLayout()
        self.empty_label = QLabel("暂无练习记录")
        self.empty_label.setProperty("role", "muted")
        self.detail_button = QPushButton("查看详情")
        self.delete_button = QPushButton("删除记录")
        self.delete_button.setProperty("variant", "danger")
        self.detail_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        footer.addWidget(self.empty_label)
        footer.addStretch(1)
        footer.addWidget(self.detail_button)
        footer.addWidget(self.delete_button)
        layout.addLayout(footer)

        self.table.itemSelectionChanged.connect(self._update_action_state)
        self.detail_button.clicked.connect(self._emit_detail)
        self.delete_button.clicked.connect(self._emit_delete)

    def populate_articles(self, articles) -> None:
        current = self.article_filter.currentData()
        self.article_filter.blockSignals(True)
        self.article_filter.clear()
        self.article_filter.addItem("全部文章", None)
        for article in articles:
            self.article_filter.addItem(article.title, article.id)
        index = self.article_filter.findData(current)
        self.article_filter.setCurrentIndex(index if index >= 0 else 0)
        self.article_filter.blockSignals(False)

    def populate_history(self, rows) -> None:
        self.table.setRowCount(len(rows))
        self.empty_label.setVisible(len(rows) == 0)
        for row_index, row in enumerate(rows):
            is_effective = bool(row["is_effective_result"])
            values = [
                _local_text(row["created_at"]),
                self._humanize_practice_type(row["practice_type"]),
                row["article_title"] or row["practice_set_title"] or "已删除内容",
                str((row["section_index"] or 0) + 1) if row["section_index"] is not None else "-",
                "已完成" if row["completed"] else "未完成",
                f"{row['active_seconds']:.1f} 秒",
                f"{row['wpm']:.1f}" if is_effective else "数据不足",
                f"{row['cpm']:.1f}" if is_effective else "数据不足",
                f"{row['accuracy']:.1f}%" if is_effective else "数据不足",
                str(row["error_keystrokes"]),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                if column == 4:
                    item.setData(Qt.ItemDataRole.UserRole, row["id"])
                self.table.setItem(row_index, column, item)
        self._update_action_state()

    def selected_session_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 4)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _update_action_state(self) -> None:
        has_selection = self.selected_session_id() is not None
        self.detail_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def _emit_detail(self) -> None:
        session_id = self.selected_session_id()
        if session_id is not None:
            self.view_detail_requested.emit(session_id)

    def _emit_delete(self) -> None:
        session_id = self.selected_session_id()
        if session_id is not None:
            self.delete_session_requested.emit(session_id)

    def _humanize_practice_type(self, practice_type: str) -> str:
        mapping = {
            "article": "普通文章",
            "article_section": "普通文章",
            "error_words": "错词练习",
            "error_characters": "错误字符",
            "context_sentences": "原句复习",
            "vocabulary_review": "生词复习",
            "mixed_review": "混合复习",
        }
        return mapping.get(practice_type, practice_type)
