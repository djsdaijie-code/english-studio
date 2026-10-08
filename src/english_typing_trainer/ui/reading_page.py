from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QProgressBar,
    QPushButton, QScrollArea, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from english_typing_trainer.services.reading_service import ReadingMaterial
from english_typing_trainer.ui.practice_view import FocusTextBrowser
from english_typing_trainer.ui.speech_controls import SpeechControls


class ReadingPage(QWidget):
    import_requested = Signal()
    article_requested = Signal(int)
    sentence_requested = Signal()
    translation_requested = Signal(bool)
    speech_requested = Signal(str, float, object)
    typing_requested = Signal(int)
    word_collection_requested = Signal(str, int, int)
    learning_activity = Signal(str)
    library_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.material: ReadingMaterial | None = None
        self.pages = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 24)
        root.addWidget(self.pages)
        self.library = QWidget()
        library_layout = QVBoxLayout(self.library)
        library_layout.setContentsMargins(0, 0, 0, 0)
        library_layout.setSpacing(16)
        title = QLabel("英文精读")
        title.setProperty("role", "page-title")
        subtitle = QLabel("粘贴一篇英文文章，逐句理解意思，并积累自己的单词。")
        subtitle.setProperty("role", "subtitle")
        subtitle.setWordWrap(True)
        self.import_button = QPushButton("粘贴英文文章")
        self.import_button.setProperty("variant", "primary")
        self.import_button.clicked.connect(self.import_requested.emit)
        library_layout.addWidget(title)
        library_layout.addWidget(subtitle)
        library_layout.addWidget(self.import_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.empty_label = QLabel("还没有精读文章。复制网页正文后，点击上方按钮开始。")
        self.empty_label.setProperty("role", "muted")
        library_layout.addWidget(self.empty_label)
        self.article_list = QListWidget()
        self.article_list.itemDoubleClicked.connect(lambda _item: self._open_selected())
        library_layout.addWidget(self.article_list, stretch=1)
        self.resume_button = QPushButton("继续精读")
        self.resume_button.setProperty("variant", "primary")
        self.resume_button.clicked.connect(self._open_selected)
        self.article_list.currentRowChanged.connect(lambda row: self.resume_button.setEnabled(row >= 0))
        self.resume_button.setEnabled(False)
        library_layout.addWidget(self.resume_button, alignment=Qt.AlignmentFlag.AlignRight)
        self.pages.addWidget(self.library)

        self.reader = QWidget()
        layout = QVBoxLayout(self.reader)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        top = QHBoxLayout()
        back = QPushButton("返回精读列表")
        back.clicked.connect(self.library_requested.emit)
        self.title_label = QLabel()
        self.title_label.setProperty("role", "page-title")
        self.title_label.setWordWrap(True)
        self.typing_button = QPushButton("打字练习")
        self.typing_button.clicked.connect(self._request_typing)
        top.addWidget(back)
        top.addWidget(self.title_label, stretch=1)
        top.addWidget(self.typing_button)
        layout.addLayout(top)
        progress_row = QHBoxLayout()
        self.position_label = QLabel()
        self.position_label.setProperty("role", "subtitle")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        self.progress.setStyleSheet(
            "QProgressBar { border:0; border-radius:4px; background:#dbe4f0; }"
            "QProgressBar::chunk { border-radius:4px; background:#537bbb; }"
        )
        progress_row.addWidget(self.position_label)
        progress_row.addWidget(self.progress, stretch=1)
        layout.addLayout(progress_row)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        source = QFrame()
        source.setObjectName("Card")
        source_layout = QVBoxLayout(source)
        source_layout.setContentsMargins(24, 24, 24, 24)
        heading = QHBoxLayout()
        source_title = QLabel("英文原句")
        source_title.setProperty("role", "section-title")
        self.speech_controls = SpeechControls()
        self.speech_controls.play_requested.connect(self._play_sentence)
        heading.addWidget(source_title)
        heading.addStretch()
        heading.addWidget(self.speech_controls)
        source_layout.addLayout(heading)
        self.source_text = FocusTextBrowser()
        self.source_text.setReadOnly(True)
        self.source_text.setOpenLinks(False)
        self.source_text.word_selected.connect(self.word_collection_requested.emit)
        font = self.source_text.font()
        font.setPixelSize(24)
        self.source_text.setFont(font)
        self.source_text.setStyleSheet("font-size:24px;")
        source_layout.addWidget(self.source_text, stretch=1)
        hint = QLabel("选中或双击单词可加入单词本。")
        hint.setProperty("role", "muted")
        source_layout.addWidget(hint)
        self.splitter.addWidget(source)

        explanation = QFrame()
        explanation.setObjectName("Card")
        explanation_layout = QVBoxLayout(explanation)
        explanation_layout.setContentsMargins(24, 24, 24, 24)
        explanation_layout.setSpacing(16)
        translation_heading = QLabel("中文意思")
        translation_heading.setProperty("role", "section-title")
        self.status_label = QLabel()
        self.status_label.setProperty("role", "subtitle")
        self.status_label.setWordWrap(True)
        explanation_layout.addWidget(translation_heading)
        explanation_layout.addWidget(self.status_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setStyleSheet("background:transparent;")
        details = QVBoxLayout(content)
        details.setContentsMargins(0, 0, 8, 0)
        details.setSpacing(24)
        self.translation_label = QLabel("正在准备讲解……")
        self.translation_label.setWordWrap(True)
        self.translation_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.translation_label.setTextFormat(Qt.TextFormat.PlainText)
        translation_font = self.translation_label.font()
        translation_font.setPixelSize(24)
        translation_font.setBold(True)
        self.translation_label.setFont(translation_font)
        self.translation_label.setStyleSheet("font-size:24px; font-weight:600; background:transparent;")
        expressions_title = QLabel("重点表达")
        expressions_title.setProperty("role", "section-title")
        self.expressions_label = QLabel()
        self.expressions_label.setWordWrap(True)
        self.expressions_label.setTextFormat(Qt.TextFormat.PlainText)
        expressions_font = self.expressions_label.font()
        expressions_font.setPixelSize(18)
        self.expressions_label.setFont(expressions_font)
        self.expressions_label.setStyleSheet("font-size:18px; background:transparent;")
        details.addWidget(self.translation_label)
        details.addWidget(expressions_title)
        details.addWidget(self.expressions_label)
        details.addStretch()
        scroll.setWidget(content)
        explanation_layout.addWidget(scroll, stretch=1)
        self.retry_button = QPushButton("重新翻译")
        self.retry_button.clicked.connect(lambda: self.translation_requested.emit(True))
        explanation_layout.addWidget(self.retry_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.splitter.addWidget(explanation)
        self.splitter.setSizes([600, 480])
        layout.addWidget(self.splitter, stretch=1)
        navigation = QHBoxLayout()
        self.previous_button = QPushButton("上一句")
        self.previous_button.clicked.connect(lambda: self.move(-1))
        self.next_button = QPushButton("下一句（Enter）")
        self.next_button.setProperty("variant", "primary")
        self.next_button.clicked.connect(lambda: self.move(1))
        navigation.addWidget(self.previous_button)
        navigation.addStretch()
        navigation.addWidget(self.next_button)
        layout.addLayout(navigation)
        self.pages.addWidget(self.reader)
        self.shortcuts = []
        for key, action in (("Return", lambda: self.move(1)), ("Right", lambda: self.move(1)), ("Left", lambda: self.move(-1)), ("Space", lambda: self._play_sentence(float(self.speech_controls.speed_combo.currentData())))):
            shortcut = QShortcut(QKeySequence(key), self.reader)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(action)
            self.shortcuts.append(shortcut)

    @property
    def current_sentence(self):
        return self.material.sentences[self.material.index] if self.material else None

    def populate_articles(self, rows) -> None:
        self.article_list.clear()
        self.empty_label.setVisible(not rows)
        for article, bookmark in rows:
            total = int(bookmark.get("total", 0) or 0)
            position = int(bookmark.get("index", 0) or 0) + 1
            state = "已读完" if bookmark.get("completed") else (f"第 {position}/{total} 句" if total else "尚未开始")
            item = QListWidgetItem(f"{article.title}\n{state}")
            item.setData(Qt.ItemDataRole.UserRole, article.id)
            self.article_list.addItem(item)
        if rows:
            self.article_list.setCurrentRow(0)

    def _open_selected(self) -> None:
        item = self.article_list.currentItem()
        if item:
            self.article_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def load(self, material: ReadingMaterial) -> None:
        self.material = material
        self.pages.setCurrentWidget(self.reader)
        self.title_label.setText(material.article.title)
        self._show_sentence()

    def _show_sentence(self) -> None:
        if self.material is None:
            return
        index = self.material.index
        count = len(self.material.sentences)
        self.position_label.setText(f"第 {index + 1} / {count} 句" + (" · 已读完" if self.material.completed else ""))
        self.progress.setRange(0, count)
        self.progress.setValue(count if self.material.completed else index)
        self.source_text.setPlainText(self.current_sentence.normalized_text)
        self.show_status("正在准备讲解……", loading=True)
        self.speech_controls.set_state("stopped")
        self.previous_button.setEnabled(index > 0)
        self.next_button.setText("完成精读" if index == count - 1 else "下一句（Enter）")
        self.next_button.setEnabled(not self.material.completed)
        if self.material.completed:
            self.next_button.setText("已完成")
        self.sentence_requested.emit()

    def move(self, step: int) -> None:
        if self.material is None or self.pages.currentWidget() is not self.reader:
            return
        index = self.material.index + step
        if index < 0:
            return
        if index >= len(self.material.sentences):
            self.material.completed = True
            self.sentence_requested.emit()
            self.position_label.setText(f"共 {len(self.material.sentences)} 句 · 已读完")
            self.progress.setValue(len(self.material.sentences))
            self.next_button.setText("已完成")
            self.next_button.setEnabled(False)
            self.learning_activity.emit("next_item")
            return
        self.material.index = index
        self.material.completed = False
        self.next_button.setEnabled(True)
        self.learning_activity.emit("next_item")
        self._show_sentence()

    def show_translation(self, cached) -> None:
        self.status_label.setText("已缓存 · 可离线阅读" if not cached.is_user_edited else "人工编辑的翻译")
        self.translation_label.setText(cached.chinese_translation)
        self.expressions_label.setText("\n\n".join(f"{item['expression']}\n{item['meaning']}" for item in cached.key_expressions) or "本句暂无重点表达。")
        self.retry_button.setEnabled(True)
        self.retry_button.setText("重新翻译")

    def show_status(self, message: str, *, loading: bool = False) -> None:
        self.status_label.setText("正在获取" if loading else "暂未获取讲解")
        self.translation_label.setText(message)
        self.expressions_label.setText("讲解完成后会显示本句重点表达。")
        self.retry_button.setEnabled(not loading)
        self.retry_button.setText("重试")

    def _play_sentence(self, speed: float) -> None:
        if self.current_sentence:
            self.learning_activity.emit("audio_started")
            self.speech_requested.emit(self.current_sentence.normalized_text, speed, self.speech_controls)

    def _request_typing(self) -> None:
        if self.material:
            self.typing_requested.emit(self.material.article.id)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.splitter.setOrientation(Qt.Orientation.Vertical if self.width() < 900 else Qt.Orientation.Horizontal)
