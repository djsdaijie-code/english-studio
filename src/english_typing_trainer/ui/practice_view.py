from __future__ import annotations

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QKeySequence, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.typing_engine.session import TypingSession
from english_typing_trainer.ui.theme import resource_root


class FocusTextBrowser(QTextBrowser):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        self.clicked.emit()


class PracticeInputEdit(QPlainTextEdit):
    key_received = Signal(object)
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PracticeInput")
        # Keep the editor visually editable so Qt paints its native caret;
        # all document changes still flow through the controlled key handler.
        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setCursorWidth(2)
        self.setAcceptDrops(False)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setPlaceholderText("在这里开始输入……")
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.document().defaultTextOption().setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # type: ignore[override]
        if event.matches(QKeySequence.StandardKey.Paste):
            event.accept()
            return
        self.key_received.emit(event)
        event.accept()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        self.clicked.emit()

    def mouseDoubleClickEvent(self, event) -> None:  # type: ignore[override]
        super().mouseDoubleClickEvent(event)
        self.clicked.emit()

    def inputMethodEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()

    def insertFromMimeData(self, source) -> None:  # type: ignore[override]
        return

    def dropEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()


class PracticeView(QWidget):
    session_completed = Signal(object)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.material: PracticeMaterial | None = None
        self.session: TypingSession | None = None
        self._settings_font_size = 18
        self._current_font_size = 22
        self._translation_hints: list[tuple[int, int, str]] = []
        self._translation_visible = True

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._refresh_ui)

        self._build_ui()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(16)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)
        self.back_button = QPushButton("返回")
        self.back_button.setProperty("variant", "ghost")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.title_label = QLabel("尚未开始练习")
        self.title_label.setProperty("role", "page-title")
        self.section_label = QLabel("第 0 / 0 段")
        self.section_label.setProperty("role", "subtitle")
        self.progress_label = QLabel("进度 0 / 0")
        self.progress_label.setProperty("role", "subtitle")
        self.pause_button = QPushButton("暂停")
        self.end_button = QPushButton("结束")
        self.end_button.setProperty("variant", "danger")
        self.pause_button.clicked.connect(self._toggle_pause)
        self.end_button.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(self.back_button)
        top_bar.addWidget(self.title_label, stretch=1)
        top_bar.addWidget(self.section_label)
        top_bar.addWidget(self.progress_label)
        top_bar.addWidget(self.pause_button)
        top_bar.addWidget(self.end_button)
        layout.addLayout(top_bar)

        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("Card")
        stats_row = QHBoxLayout(self.stats_frame)
        stats_row.setContentsMargins(16, 10, 16, 10)
        stats_row.setSpacing(24)
        self.wpm_value = self._build_stat_label("WPM", stats_row)
        self.accuracy_value = self._build_stat_label("正确率", stats_row)
        self.errors_value = self._build_stat_label("错误数", stats_row)
        self.elapsed_value = self._build_stat_label("时间", stats_row)
        stats_row.addStretch(1)
        layout.addWidget(self.stats_frame)

        self.hint_label = QLabel("请在“我的输入”中打字。错误字符会标红并继续前进，Backspace 可回退一格，Esc 暂停或继续。")
        self.hint_label.setProperty("role", "subtitle")
        layout.addWidget(self.hint_label)

        content_shell = QHBoxLayout()
        content_shell.setContentsMargins(0, 0, 0, 0)
        self.content_host = QWidget()
        self.content_host.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        host_layout = QVBoxLayout(self.content_host)
        host_layout.setContentsMargins(0, 0, 0, 0)

        self.practice_splitter = QSplitter(Qt.Orientation.Vertical)
        self.practice_splitter.setChildrenCollapsible(False)
        self.practice_splitter.setHandleWidth(8)
        self.practice_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        source_card = QFrame()
        source_card.setObjectName("PracticeSourceCard")
        source_card.setMinimumHeight(200)
        source_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        source_layout = QVBoxLayout(source_card)
        source_layout.setContentsMargins(20, 16, 20, 18)
        source_layout.setSpacing(10)
        source_heading = QHBoxLayout()
        source_title = QLabel("原文")
        source_title.setProperty("role", "section-title")
        self.target_hint = QLabel("高亮位置是当前输入目标")
        self.target_hint.setProperty("role", "muted")
        source_heading.addWidget(source_title)
        source_heading.addStretch(1)
        source_heading.addWidget(self.target_hint)
        source_layout.addLayout(source_heading)
        self.text_browser = FocusTextBrowser()
        self.text_browser.setObjectName("PracticeSource")
        self.text_browser.setReadOnly(True)
        self.text_browser.setOpenLinks(False)
        self.text_browser.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.text_browser.document().defaultTextOption().setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.text_browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text_browser.viewport().installEventFilter(self)
        self.text_browser.clicked.connect(lambda: QTimer.singleShot(0, self._restore_focus))
        source_layout.addWidget(self.text_browser, stretch=1)

        input_card = QFrame()
        input_card.setObjectName("PracticeInputCard")
        input_card.setMinimumHeight(150)
        input_card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(20, 16, 20, 18)
        input_layout.setSpacing(10)
        input_heading = QHBoxLayout()
        input_title = QLabel("我的输入")
        input_title.setProperty("role", "section-title")
        self.input_feedback_label = QLabel("等待输入")
        self.input_feedback_label.setProperty("role", "muted")
        input_heading.addWidget(input_title)
        input_heading.addStretch(1)
        input_heading.addWidget(self.input_feedback_label)
        input_layout.addLayout(input_heading)
        self.input_edit = PracticeInputEdit()
        self.input_edit.key_received.connect(self._handle_input_event)
        self.input_edit.clicked.connect(lambda: QTimer.singleShot(0, self._restore_focus))
        input_layout.addWidget(self.input_edit, stretch=1)

        self.practice_splitter.addWidget(source_card)
        self.practice_splitter.addWidget(input_card)
        self.practice_splitter.setStretchFactor(0, 3)
        self.practice_splitter.setStretchFactor(1, 2)
        self.practice_splitter.setSizes([560, 360])
        host_layout.addWidget(self.practice_splitter)

        self.translation_card = QFrame()
        self.translation_card.setObjectName("ContinuousTranslationCard")
        self.translation_card.setMinimumWidth(280)
        self.translation_card.hide()
        translation_layout = QVBoxLayout(self.translation_card)
        translation_layout.setContentsMargins(20, 18, 20, 20)
        translation_layout.setSpacing(14)
        translation_header = QHBoxLayout()
        translation_title = QLabel("中文意思")
        translation_title.setProperty("role", "section-title")
        self.translation_toggle = QToolButton()
        self.translation_toggle.setObjectName("TranslationVisibilityButton")
        self.translation_toggle.setIcon(QIcon(str(resource_root() / "icons" / "eye.svg")))
        self.translation_toggle.setToolTip("隐藏中文意思")
        self.translation_toggle.clicked.connect(self._toggle_translation_visibility)
        translation_header.addWidget(translation_title)
        translation_header.addStretch(1)
        translation_header.addWidget(self.translation_toggle)
        translation_layout.addLayout(translation_header)
        self.translation_text = QLabel("暂无翻译")
        self.translation_text.setObjectName("ContinuousTranslationText")
        self.translation_text.setWordWrap(True)
        self.translation_text.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        translation_layout.addWidget(self.translation_text, stretch=1)

        self.continuous_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.continuous_splitter.setChildrenCollapsible(False)
        self.continuous_splitter.setHandleWidth(10)
        self.continuous_splitter.addWidget(self.content_host)
        self.continuous_splitter.addWidget(self.translation_card)
        self.continuous_splitter.setStretchFactor(0, 2)
        self.continuous_splitter.setStretchFactor(1, 1)
        self.continuous_splitter.setSizes([920, 440])
        content_shell.addStretch(1)
        content_shell.addWidget(self.continuous_splitter, stretch=18)
        content_shell.addStretch(1)
        layout.addLayout(content_shell, stretch=1)
        self._update_responsive_geometry()

    def _build_stat_label(self, title: str, parent_layout: QHBoxLayout) -> QLabel:
        box = QVBoxLayout()
        box.setSpacing(2)
        title_label = QLabel(title)
        title_label.setProperty("role", "metric-title")
        value_label = QLabel("-")
        value_label.setProperty("role", "metric-value")
        value_label.setStyleSheet("font-size: 22px;")
        box.addWidget(title_label)
        box.addWidget(value_label)
        parent_layout.addLayout(box)
        return value_label

    def apply_settings(self, settings: AppSettings) -> None:
        self._settings_font_size = settings.font_size
        self.stats_frame.setVisible(settings.show_live_stats)
        self._update_responsive_geometry()
        self._render_text()
        self._render_input()

    def start_practice(self, material: PracticeMaterial, settings: AppSettings) -> None:
        self.material = material
        self.session = TypingSession(
            material.section_text,
            case_sensitive=settings.case_sensitive,
            start_position=material.resume_character_index,
        )
        practice_name = "专项练习" if material.practice_type not in {"article", "article_section"} else material.article_title
        self.title_label.setText(practice_name)
        self.section_label.setText(f"第 {material.section_index + 1} / {material.section_count} 段")
        self.pause_button.setText("暂停")
        self.input_feedback_label.setText("等待输入")
        self._translation_visible = True
        self._update_translation_visibility()
        self._settings_font_size = settings.font_size
        self._refresh_ui()
        self._update_responsive_geometry()
        self._render_text()
        self._render_input()
        self._timer.start()
        self._set_input_active(True)
        QTimer.singleShot(0, self._restore_focus)

    def set_translation_hints(self, hints: list[tuple[int, int, str]], *, visible: bool) -> None:
        self._translation_hints = hints
        self.translation_card.setVisible(visible)
        self._refresh_translation()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._update_responsive_geometry()

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self.text_browser.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            QTimer.singleShot(0, self._restore_focus)
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        self._handle_input_event(event)

    def _handle_input_event(self, event: QKeyEvent) -> None:
        if self.session is None:
            event.ignore()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._toggle_pause()
            event.accept()
            return
        if event.matches(QKeySequence.StandardKey.Paste):
            event.accept()
            return
        if event.key() == Qt.Key.Key_Backspace:
            if not self.session.is_paused and self.session.handle_backspace():
                self.input_feedback_label.setText("已回退一格，可重新输入")
                self._refresh_ui()
                self._render_text()
                self._render_input()
            event.accept()
            return
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta}:
            event.ignore()
            return

        text = self._map_input_text(event)
        if not text:
            event.ignore()
            return
        if self.session.is_paused:
            self.input_feedback_label.setText("练习已暂停，按 Esc 继续")
            event.accept()
            return

        is_correct = self.session.handle_character(text)
        if not self.session.typed_characters:
            event.accept()
            return
        typed = self.session.typed_characters[-1]
        if is_correct:
            self.input_feedback_label.setText("输入正确")
        else:
            self.input_feedback_label.setText(f"输入错误：输入了 {self._describe_character(typed.actual_char)}，原文是 {self._describe_character(typed.target_char)}")

        self._refresh_ui()
        self._render_text()
        self._render_input()

        if self.session.is_complete:
            self._timer.stop()
            self._set_input_active(False)
            self.input_feedback_label.setText("本段练习已完成")
            self.session_completed.emit(self.session.snapshot())
        event.accept()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        if self.session and not self.session.is_complete and not self.isActiveWindow():
            self.session.pause()
            self.pause_button.setText("继续")
        super().focusOutEvent(event)

    def _map_input_text(self, event: QKeyEvent) -> str:
        if self.session is None or self.session.is_complete:
            return ""
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            return "\n"
        if event.key() == Qt.Key.Key_Tab:
            return "\t"
        text = event.text()
        return text if len(text) == 1 and text.isprintable() else ""

    def _toggle_pause(self) -> None:
        if self.session is None or self.session.is_complete:
            return
        if self.session.started_at is None and self.session.elapsed_active_seconds <= 0:
            return
        if self.session.is_paused:
            self.session.resume()
            self.pause_button.setText("暂停")
            self.input_feedback_label.setText("练习已继续")
            self._restore_focus()
        else:
            self.session.pause()
            self.pause_button.setText("继续")
            self.input_feedback_label.setText("练习已暂停，按 Esc 继续")
            self._set_input_active(False)
        self._refresh_ui()

    def _refresh_ui(self) -> None:
        if self.session is None:
            return
        snapshot = self.session.snapshot()
        self.progress_label.setText(f"进度 {snapshot.position} / {len(self.session.content)}")
        self.wpm_value.setText(f"{snapshot.wpm:.1f}")
        self.accuracy_value.setText(f"{snapshot.accuracy:.1f}%")
        self.errors_value.setText(str(snapshot.error_keystrokes))
        self.elapsed_value.setText(f"{snapshot.elapsed_active_seconds:.1f} 秒")
        self._refresh_translation()

    def _render_text(self) -> None:
        if self.session is None:
            self.text_browser.clear()
            return
        content = self.session.content
        if self.text_browser.toPlainText() != content:
            self.text_browser.setPlainText(content)
        dark = self.palette().window().color().lightness() < 128
        muted = QColor("#8291a5" if dark else "#94a3b8")
        error_text = QColor("#fecaca" if dark else "#b42318")
        error_bg = QColor("#4a2528" if dark else "#fee4e2")
        current_text = self.palette().text().color()
        current_bg = QColor("#263b53" if dark else "#e8f0fa")
        selections: list[QTextEdit.ExtraSelection] = []

        if self.session.position > 0:
            selections.append(self._selection(0, self.session.position, foreground=muted))
        for typed in self.session.typed_characters:
            if not typed.is_correct:
                selections.append(
                    self._selection(
                        typed.position,
                        typed.position + 1,
                        foreground=error_text,
                        background=error_bg,
                        underline=True,
                    )
                )
        if not self.session.is_complete:
            selections.append(
                self._selection(
                    self.session.position,
                    self.session.position + 1,
                    foreground=current_text,
                    background=current_bg,
                    underline=False,
                )
            )
        self.text_browser.setExtraSelections(selections)
        cursor = self.text_browser.textCursor()
        cursor.setPosition(min(self.session.position, len(content)))
        self.text_browser.setTextCursor(cursor)
        self.text_browser.ensureCursorVisible()
        self._apply_line_spacing(self.text_browser, 160)

    def _render_input(self) -> None:
        if self.session is None:
            self.input_edit.clear()
            return
        dark = self.palette().window().color().lightness() < 128
        normal = QColor("#d9f3e4" if dark else "#18392a")
        resumed = QColor("#8291a5" if dark else "#64748b")
        error_text = QColor("#fecaca" if dark else "#b42318")
        error_bg = QColor("#4a2528" if dark else "#fee4e2")
        document = self.input_edit.document()
        document.clear()
        cursor = QTextCursor(document)

        if self.session.start_position:
            prefix_format = QTextCharFormat()
            prefix_format.setForeground(resumed)
            cursor.insertText(self.session.content[: self.session.start_position], prefix_format)
        for typed in self.session.typed_characters:
            char_format = QTextCharFormat()
            if typed.is_correct:
                char_format.setForeground(normal)
            else:
                char_format.setForeground(error_text)
                char_format.setBackground(error_bg)
                char_format.setFontUnderline(True)
            cursor.insertText(typed.actual_char, char_format)

        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.input_edit.setTextCursor(cursor)
        self.input_edit.ensureCursorVisible()
        self._apply_line_spacing(self.input_edit, 160)

    def _selection(
        self,
        start: int,
        end: int,
        *,
        foreground: QColor,
        background: QColor | None = None,
        underline: bool = False,
    ) -> QTextEdit.ExtraSelection:
        selection = QTextEdit.ExtraSelection()
        cursor = QTextCursor(self.text_browser.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        selection.cursor = cursor
        char_format = QTextCharFormat()
        char_format.setForeground(foreground)
        if background is not None:
            char_format.setBackground(background)
        char_format.setFontUnderline(underline)
        selection.format = char_format
        return selection

    def _update_responsive_geometry(self) -> None:
        if not hasattr(self, "content_host"):
            return
        viewport_width = max(self.width(), 1)
        self.continuous_splitter.setMaximumWidth(min(1400, max(640, int(viewport_width * 0.90))))
        panel_enabled = not self.translation_card.isHidden()
        self.content_host.setMaximumWidth(16777215 if panel_enabled else min(1400, max(640, int(viewport_width * 0.90))))
        if panel_enabled:
            self.continuous_splitter.setOrientation(
                Qt.Orientation.Vertical if viewport_width < 1100 else Qt.Orientation.Horizontal
            )
            self.continuous_splitter.setSizes([720, 280] if viewport_width < 1100 else [920, 440])
        if viewport_width < 1400:
            responsive_size = 20
        elif viewport_width < 1800:
            responsive_size = 22
        else:
            responsive_size = 24
        self._current_font_size = min(26, max(18, responsive_size + self._settings_font_size - 18))
        for editor in (self.text_browser, self.input_edit):
            font = editor.font()
            font.setPixelSize(self._current_font_size)
            editor.setFont(font)
            editor.document().setDefaultFont(font)

    @staticmethod
    def _describe_character(character: str) -> str:
        if character == "\n":
            return "换行"
        if character == "\t":
            return "Tab"
        if character == " ":
            return "空格"
        return f"“{character}”"

    def _restore_focus(self) -> None:
        if self.session is None or self.session.is_paused or self.session.is_complete:
            self._set_input_active(False)
            return
        self._set_input_active(True)
        if not self.input_edit.hasFocus():
            self.input_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        cursor = self.input_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.input_edit.setTextCursor(cursor)
        self.input_edit.ensureCursorVisible()

    def _set_input_active(self, active: bool) -> None:
        self.input_edit.setCursorWidth(2 if active else 0)

    def _toggle_translation_visibility(self) -> None:
        self._translation_visible = not self._translation_visible
        self._update_translation_visibility()
        QTimer.singleShot(0, self._restore_focus)

    def _update_translation_visibility(self) -> None:
        icon_name = "eye.svg" if self._translation_visible else "eye-off.svg"
        self.translation_toggle.setIcon(QIcon(str(resource_root() / "icons" / icon_name)))
        self.translation_toggle.setToolTip("隐藏中文意思" if self._translation_visible else "显示中文意思")
        self._refresh_translation()

    def _refresh_translation(self) -> None:
        if not hasattr(self, "translation_text"):
            return
        if not self._translation_visible:
            self.translation_text.setText("中文意思已隐藏")
            self.translation_text.setProperty("hidden", "true")
        else:
            position = self.session.position if self.session else 0
            translation = next(
                (text for start, end, text in self._translation_hints if start <= position < end),
                self._translation_hints[-1][2] if self._translation_hints and self.session and self.session.is_complete else "",
            )
            self.translation_text.setText(translation or "暂无翻译")
            self.translation_text.setProperty("hidden", "false")
        self.translation_text.style().unpolish(self.translation_text)
        self.translation_text.style().polish(self.translation_text)

    @staticmethod
    def _apply_line_spacing(editor: QPlainTextEdit | QTextBrowser, percent: int) -> None:
        cursor = QTextCursor(editor.document())
        cursor.select(QTextCursor.SelectionType.Document)
        block_format = QTextBlockFormat()
        block_format.setLineHeight(
            float(percent), QTextBlockFormat.LineHeightTypes.ProportionalHeight.value
        )
        cursor.mergeBlockFormat(block_format)
