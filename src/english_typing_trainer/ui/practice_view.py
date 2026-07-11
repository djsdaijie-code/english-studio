from __future__ import annotations

from html import escape

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.typing_engine.session import TypingSession


class FocusTextBrowser(QTextBrowser):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        super().mousePressEvent(event)
        self.clicked.emit()


class PracticeView(QWidget):
    session_completed = Signal(object)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.material: PracticeMaterial | None = None
        self.session: TypingSession | None = None
        self._error_flash_remaining = 0
        self._current_font_size = 26

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

        self.hint_label = QLabel("直接输入即可。按 Esc 可暂停或继续，点击正文会自动恢复输入焦点。")
        self.hint_label.setProperty("role", "subtitle")
        layout.addWidget(self.hint_label)

        text_shell = QHBoxLayout()
        text_shell.addStretch(1)
        text_card = QFrame()
        text_card.setObjectName("PanelCard")
        text_card.setMaximumWidth(940)
        text_layout = QVBoxLayout(text_card)
        text_layout.setContentsMargins(28, 24, 28, 24)
        self.text_browser = FocusTextBrowser()
        self.text_browser.setReadOnly(True)
        self.text_browser.setOpenLinks(False)
        self.text_browser.setMinimumHeight(420)
        self.text_browser.viewport().installEventFilter(self)
        self.text_browser.clicked.connect(self._restore_focus)
        text_layout.addWidget(self.text_browser)
        text_shell.addWidget(text_card, stretch=1)
        text_shell.addStretch(1)
        layout.addLayout(text_shell, stretch=1)

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
        self._current_font_size = min(28, max(24, settings.font_size + 8))
        self.stats_frame.setVisible(settings.show_live_stats)
        self._render_text()

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
        self._error_flash_remaining = 0
        self._refresh_ui()
        self._render_text()
        self._timer.start()
        self._restore_focus()

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched is self.text_browser.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            self._restore_focus()
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.session is None:
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self._toggle_pause()
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta}:
            event.ignore()
            return

        text = self._map_input_text(event)
        if not text:
            event.ignore()
            return

        if not self.session.handle_character(text):
            self._error_flash_remaining = 3
        self._refresh_ui()
        self._render_text()

        if self.session.is_complete:
            self._timer.stop()
            self.session_completed.emit(self.session.snapshot())
        event.accept()

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        if self.session and not self.session.is_complete:
            self.session.pause()
            self.pause_button.setText("继续")
        super().focusOutEvent(event)

    def _map_input_text(self, event: QKeyEvent) -> str:
        if self.session is None or self.session.is_complete:
            return ""
        expected_char = self.session.content[self.session.position]
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and expected_char == "\n":
            return "\n"
        if event.key() == Qt.Key.Key_Tab and expected_char == "\t":
            return "\t"
        return event.text()

    def _toggle_pause(self) -> None:
        if self.session is None or self.session.is_complete:
            return
        if self.session.started_at is None and self.session.elapsed_active_seconds <= 0:
            return
        if self.session.is_paused:
            self.session.resume()
            self.pause_button.setText("暂停")
            self._restore_focus()
        else:
            self.session.pause()
            self.pause_button.setText("继续")
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
        if self._error_flash_remaining > 0:
            self._error_flash_remaining -= 1

    def _render_text(self) -> None:
        if self.session is None:
            self.text_browser.clear()
            return

        foreground = self.palette().text().color().name()
        muted = "#8b9bb0" if self.palette().window().color().lightness() < 128 else "#94a3b8"
        current_line = "#8aa4c5" if self.palette().window().color().lightness() < 128 else "#7c8da3"
        error_color = "#fecaca" if self.palette().window().color().lightness() < 128 else "#fee4e2"
        error_text = "#fee2e2" if self.palette().window().color().lightness() < 128 else "#b42318"
        content = self.session.content
        position = self.session.position
        current_char = content[position] if position < len(content) else ""
        typed_part = escape(content[:position]).replace("\n", "<br>")
        remaining_part = escape(content[position + 1 :]).replace("\n", "<br>")
        current_part = escape(current_char).replace("\n", "<br>")

        typed_html = f"<span style='color:{muted};'>{typed_part}</span>"
        current_style = f"color:{foreground};border-bottom:2px solid {current_line};padding:0 1px;"
        if self._error_flash_remaining > 0 and self.session.last_error is not None:
            current_style = f"color:{error_text};background:{error_color};border-bottom:2px solid #ef4444;padding:0 1px;"
        current_html = f"<a name='current-position'></a><span style='{current_style}'>{current_part}</span>" if current_part else ""
        remaining_html = f"<span style='color:{foreground};'>{remaining_part}</span>"

        html = (
            f"<div style='font-size:{self._current_font_size}px; line-height:1.9; "
            "max-width:900px; margin:0 auto; font-family:\"Microsoft YaHei UI\", \"Microsoft YaHei\", serif;'>"
            f"{typed_html}{current_html}{remaining_html}</div>"
        )
        self.text_browser.setHtml(html)
        self.text_browser.scrollToAnchor("current-position")

    def _restore_focus(self) -> None:
        self.setFocus(Qt.FocusReason.OtherFocusReason)
