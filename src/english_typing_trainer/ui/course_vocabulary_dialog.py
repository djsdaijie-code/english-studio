from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from english_typing_trainer.models.learning_content import CourseCapabilityItem
from english_typing_trainer.services.article_word_index import ArticleWordOccurrence


class CourseVocabularyDialog(QDialog):
    """Selects a transient course occurrence; persistence remains in services."""

    def __init__(
        self,
        words: tuple[tuple[CourseCapabilityItem, ArticleWordOccurrence], ...],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.words = words
        self.action: str | None = None
        self.setWindowTitle("课程词汇")
        self.resize(720, 520)
        layout = QVBoxLayout(self)
        title = QLabel("课程词汇")
        title.setProperty("role", "page-title")
        note = QLabel("课程正文仅在当前窗口中读取；收藏记录只保存 stable key、单词和字符位置。")
        note.setWordWrap(True)
        note.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(note)
        self.list_widget = QListWidget()
        for index, (item, occurrence) in enumerate(words):
            row = QListWidgetItem(
                f"{occurrence.source_word}  ·  {item.text}\n{item.translation}"
            )
            row.setData(Qt.ItemDataRole.UserRole, index)
            self.list_widget.addItem(row)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget, stretch=1)
        buttons = QHBoxLayout()
        close = QPushButton("关闭")
        close.clicked.connect(self.reject)
        collect = QPushButton("收藏并查看词义")
        collect.clicked.connect(lambda: self._finish("collect"))
        review = QPushButton("收藏并加入 FSRS")
        review.setProperty("variant", "primary")
        review.clicked.connect(lambda: self._finish("review"))
        enabled = bool(words)
        collect.setEnabled(enabled)
        review.setEnabled(enabled)
        buttons.addWidget(close)
        buttons.addStretch(1)
        buttons.addWidget(collect)
        buttons.addWidget(review)
        layout.addLayout(buttons)

    @property
    def selected(self) -> tuple[CourseCapabilityItem, ArticleWordOccurrence] | None:
        row = self.list_widget.currentItem()
        if row is None:
            return None
        index = int(row.data(Qt.ItemDataRole.UserRole))
        return self.words[index] if 0 <= index < len(self.words) else None

    def _finish(self, action: str) -> None:
        if self.selected is None:
            return
        self.action = action
        self.accept()


__all__ = ["CourseVocabularyDialog"]
