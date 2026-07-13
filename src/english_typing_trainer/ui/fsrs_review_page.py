from __future__ import annotations

from time import monotonic

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from english_typing_trainer.models.fsrs_review import ReviewQueueItem
from english_typing_trainer.ui.practice_view import PracticeInputEdit


class FsrsReviewPage(QWidget):
    back_requested = Signal()
    rating_requested = Signal(int, str)
    defer_requested = Signal(int)
    learning_activity = Signal(str, object)
    dictation_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.items: list[ReviewQueueItem] = []
        self.index = 0
        self.typed = ""
        self.errors = 0
        self._started = 0.0
        self._revealed = False
        self._build()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 24, 32, 24)
        root.setSpacing(16)
        top = QHBoxLayout()
        back = QPushButton("返回单词本")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self.back_requested.emit)
        self.title = QLabel("今日复习")
        self.title.setProperty("role", "page-title")
        self.position = QLabel("0 / 0")
        self.position.setProperty("role", "subtitle")
        self.defer_button = QPushButton("稍后复习")
        self.defer_button.setProperty("variant", "ghost")
        self.defer_button.clicked.connect(self._defer)
        self.skip_button = QPushButton("跳过")
        self.skip_button.setProperty("variant", "ghost")
        self.skip_button.clicked.connect(self._skip)
        self.dictation_button = QPushButton("听写模式")
        self.dictation_button.setProperty("variant", "ghost")
        self.dictation_button.clicked.connect(self.dictation_requested.emit)
        top.addWidget(back)
        top.addWidget(self.title, 1)
        top.addWidget(self.position)
        top.addWidget(self.defer_button)
        top.addWidget(self.skip_button)
        top.addWidget(self.dictation_button)
        root.addLayout(top)

        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(36, 32, 36, 32)
        layout.setSpacing(18)
        self.kind = QLabel("")
        self.kind.setProperty("role", "subtitle")
        self.prompt = QLabel("")
        self.prompt.setWordWrap(True)
        self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prompt.setStyleSheet("font-size: 30px; font-weight: 600;")
        self.context = QLabel("")
        self.context.setWordWrap(True)
        self.context.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.context.setProperty("role", "subtitle")
        self.input = PracticeInputEdit()
        self.input.setMinimumHeight(120)
        self.input.key_received.connect(self._key)
        self.feedback = QLabel("")
        self.feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.feedback.setProperty("role", "subtitle")
        self.reveal = QPushButton("显示中文意思")
        self.reveal.clicked.connect(self._reveal)
        self.ratings = QHBoxLayout()
        self.rating_buttons: list[QPushButton] = []
        for text, value in (("忘记了", "again"), ("困难", "hard"), ("记得", "good"), ("很熟", "easy")):
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, rating=value: self._rate(rating))
            button.hide()
            self.ratings.addWidget(button)
            self.rating_buttons.append(button)
        layout.addWidget(self.kind)
        layout.addStretch(1)
        layout.addWidget(self.prompt)
        layout.addWidget(self.context)
        layout.addWidget(self.input)
        layout.addWidget(self.reveal, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.feedback)
        layout.addLayout(self.ratings)
        layout.addStretch(1)
        root.addWidget(card, 1)

    def load_queue(self, items: list[ReviewQueueItem]) -> None:
        self.items = list(items)
        self.index = 0
        self._load_current()

    @property
    def current(self) -> ReviewQueueItem | None:
        return self.items[self.index] if 0 <= self.index < len(self.items) else None

    def _load_current(self) -> None:
        item = self.current
        if item is None:
            self.position.setText("已完成")
            self.kind.setText("今日复习完成")
            self.prompt.setText("本轮复习已结束")
            self.context.setText("稍后到期的卡片会在合适时间再次出现。")
            self.input.clear()
            self.input.setEnabled(False)
            self.reveal.hide()
            self.defer_button.setEnabled(False)
            self.skip_button.setEnabled(False)
            for button in self.rating_buttons:
                button.hide()
            return
        self.position.setText(f"第 {self.index + 1} / {len(self.items)} 张")
        self.defer_button.setEnabled(True)
        self.skip_button.setEnabled(True)
        self.typed = ""
        self.errors = 0
        self._started = 0.0
        self._revealed = False
        self.input.clear()
        self.feedback.clear()
        for button in self.rating_buttons:
            button.hide()
        is_spelling = item.card.card_type == "spelling"
        self.kind.setText("拼写卡 · 根据中文或语境输入原词形" if is_spelling else "词义卡 · 回忆后进行自评")
        source = item.context.source_sentence if item.context else ""
        if is_spelling:
            meaning = item.context.contextual_meaning_zh if item.context else ""
            self.prompt.setText(meaning or "根据来源句输入英文单词")
            self.context.setText(source)
            self.input.setEnabled(True)
            self.input.setPlaceholderText("在这里输入英文单词")
            self.reveal.hide()
            QTimer.singleShot(0, self.input.setFocus)
        else:
            self.prompt.setText(item.target_word)
            self.context.setText(source)
            self.input.setEnabled(False)
            self.reveal.show()

    def _key(self, event: QKeyEvent) -> None:
        item = self.current
        if item is None or item.card.card_type != "spelling":
            return
        if event.key() == Qt.Key.Key_Backspace:
            if self.typed:
                self.typed = self.typed[:-1]
                self._render()
                self.learning_activity.emit("typing_activity", item.entry.id)
            return
        text = event.text()
        if not text or len(text) != 1:
            return
        self.learning_activity.emit("typing_activity", item.entry.id)
        self._started = self._started or monotonic()
        self.typed += text
        expected = item.target_word
        index = len(self.typed) - 1
        if index >= len(expected) or text != expected[index]:
            self.errors += 1
        self._render()
        if len(self.typed) >= len(expected):
            if self.typed == expected:
                self.feedback.setText("拼写正确，请选择熟悉程度。")
            else:
                self.feedback.setText(f"标准拼写：{expected}")
            self.input.setEnabled(False)
            for button in self.rating_buttons:
                button.show()

    def _render(self) -> None:
        item = self.current
        if item is None:
            return
        expected = item.target_word
        cursor = QTextCursor(self.input.document())
        self.input.clear()
        for index, character in enumerate(self.typed):
            fmt = QTextCharFormat()
            if index >= len(expected) or character != expected[index]:
                fmt.setForeground(QColor("#c74444"))
                fmt.setBackground(QColor("#fee2e2"))
            cursor.insertText(character, fmt)
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.input.setTextCursor(cursor)
        self.input.ensureCursorVisible()

    def _reveal(self) -> None:
        item = self.current
        if item is None:
            return
        self._revealed = True
        self.learning_activity.emit("meaning_revealed", item.entry.id)
        meaning = item.context.contextual_meaning_zh if item.context else ""
        self.feedback.setText(meaning or "暂无中文讲解，可根据来源句自评。")
        self.reveal.hide()
        for button in self.rating_buttons:
            button.show()

    def _rate(self, rating: str) -> None:
        item = self.current
        if item is None:
            return
        self.learning_activity.emit("self_rated", item.entry.id)
        self.rating_requested.emit(item.card.id or 0, rating)
        self.index += 1
        QTimer.singleShot(0, self._load_current)

    def _defer(self) -> None:
        item = self.current
        if item is None:
            return
        self.defer_requested.emit(item.card.id or 0)
        self.learning_activity.emit("next_item", item.entry.id)
        self.index += 1
        self._load_current()

    def _skip(self) -> None:
        item = self.current
        if item is not None:
            self.learning_activity.emit("next_item", item.entry.id)
        self.index += 1
        self._load_current()
