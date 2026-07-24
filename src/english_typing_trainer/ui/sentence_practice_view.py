from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QKeySequence, QTextCharFormat, QTextCursor, QTextOption
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
    QSizePolicy, QSplitter, QTextBrowser, QTextEdit, QVBoxLayout, QWidget,
)

from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.sentence import ArticleSentence, SentenceTranslation
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.services.sentence_learning import SentenceLearningSession, SentenceLearningState
from english_typing_trainer.statistics.metrics import calculate_cpm, calculate_wpm
from english_typing_trainer.typing_engine.session import TypingSession
from english_typing_trainer.ui.practice_view import FocusTextBrowser, PracticeInputEdit


class SentencePracticeView(QWidget):
    back_requested = Signal()
    session_completed = Signal(object)
    attempt_completed = Signal(object)
    translation_requested = Signal(object, bool)
    edit_translation_requested = Signal(object)
    translate_article_requested = Signal()
    speech_requested = Signal(str, float, object)
    speech_sentence_changed = Signal(str)
    word_collection_requested = Signal(str, int, int)
    learning_activity = Signal(str)
    course_dictation_requested = Signal()
    course_pronunciation_requested = Signal()
    course_words_requested = Signal()
    course_review_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.material: PracticeMaterial | None = None
        self.sentences: list[ArticleSentence] = []
        self.learning: SentenceLearningSession | None = None
        self.session: TypingSession | None = None
        self._font_size = 22
        self._emitted_attempts = 0
        self._course_mode = False
        self._course_translations: tuple[str, ...] = ()
        self._course_activity_types: tuple[tuple[str, ...], ...] = ()
        self._auto_read_sentence_index = -1
        self._section_start_offset = 0
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._tick)
        self._build_ui()
        self.installEventFilter(self)
        for widget in self.findChildren(QWidget):
            widget.installEventFilter(self)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(14)
        top = QHBoxLayout()
        self.back_button = QPushButton("返回"); self.back_button.setProperty("variant", "ghost")
        self.back_button.clicked.connect(self.back_requested.emit)
        self.title_label = QLabel("逐句学习"); self.title_label.setProperty("role", "page-title")
        self.sentence_label = QLabel("第 0 / 0 句"); self.sentence_label.setProperty("role", "subtitle")
        self.progress_label = QLabel("进度 0 / 0"); self.progress_label.setProperty("role", "subtitle")
        self.pause_button = QPushButton("暂停"); self.pause_button.clicked.connect(self._toggle_pause)
        self.end_button = QPushButton("结束"); self.end_button.setProperty("variant", "danger"); self.end_button.clicked.connect(self.back_requested.emit)
        for widget, stretch in ((self.back_button, 0), (self.title_label, 1), (self.sentence_label, 0), (self.progress_label, 0), (self.pause_button, 0), (self.end_button, 0)):
            top.addWidget(widget, stretch=stretch)
        layout.addLayout(top)

        stats = QFrame(); stats.setObjectName("Card")
        row = QHBoxLayout(stats); row.setContentsMargins(16, 8, 16, 8); row.setSpacing(28)
        self.wpm_value = self._stat(row, "WPM")
        self.cpm_value = self._stat(row, "CPM")
        self.accuracy_value = self._stat(row, "正确率")
        self.errors_value = self._stat(row, "错误数")
        self.active_value = self._stat(row, "有效输入")
        row.addStretch(1); layout.addWidget(stats)
        self.state_label = QLabel("输入第一个字符后开始计时"); self.state_label.setProperty("role", "subtitle"); layout.addWidget(self.state_label)

        self.course_actions = QWidget()
        course_actions_layout = QHBoxLayout(self.course_actions)
        course_actions_layout.setContentsMargins(0, 0, 0, 0)
        self.course_dictation_button = QPushButton("听写")
        self.course_dictation_button.clicked.connect(self.course_dictation_requested.emit)
        self.course_speaking_button = QPushButton("跟读")
        self.course_speaking_button.clicked.connect(self.course_pronunciation_requested.emit)
        self.course_words_button = QPushButton("查看单词")
        self.course_words_button.clicked.connect(self.course_words_requested.emit)
        self.course_review_button = QPushButton("加入课程复习")
        self.course_review_button.clicked.connect(self.course_review_requested.emit)
        for button in (
            self.course_dictation_button,
            self.course_speaking_button,
            self.course_words_button,
            self.course_review_button,
        ):
            course_actions_layout.addWidget(button)
        course_actions_layout.addStretch(1)
        self.course_actions.hide()
        layout.addWidget(self.course_actions)

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setChildrenCollapsible(False); self.main_splitter.setHandleWidth(10)
        self.main_splitter.addWidget(self._build_practice_panel())
        self.main_splitter.addWidget(self._build_translation_panel())
        self.main_splitter.setStretchFactor(0, 65); self.main_splitter.setStretchFactor(1, 35)
        self.main_splitter.setSizes([900, 480])
        layout.addWidget(self.main_splitter, stretch=1)

    def _build_practice_panel(self) -> QWidget:
        panel = QWidget(); panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(12)
        source = QFrame(); source.setObjectName("PracticeSourceCard"); source.setMinimumHeight(180)
        source_layout = QVBoxLayout(source); source_layout.setContentsMargins(20, 16, 20, 18)
        source_heading = QHBoxLayout(); source_title = QLabel("当前句原文"); source_title.setProperty("role", "section-title")
        from english_typing_trainer.ui.speech_controls import SpeechControls
        self.speech_controls = SpeechControls(); self.speech_controls.play_requested.connect(self._request_speech)
        source_heading.addWidget(source_title); source_heading.addStretch(1); source_heading.addWidget(self.speech_controls); source_layout.addLayout(source_heading)
        self.text_browser = FocusTextBrowser(); self.text_browser.setObjectName("PracticeSource"); self.text_browser.setReadOnly(True)
        self.text_browser.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth); self.text_browser.document().defaultTextOption().setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.text_browser.clicked.connect(lambda: QTimer.singleShot(0, self._restore_focus)); source_layout.addWidget(self.text_browser, stretch=1)
        self.text_browser.word_selected.connect(self.word_collection_requested.emit)
        input_card = QFrame(); input_card.setObjectName("PracticeInputCard"); input_card.setMinimumHeight(140)
        input_layout = QVBoxLayout(input_card); input_layout.setContentsMargins(20, 16, 20, 18)
        heading = QHBoxLayout(); title = QLabel("我的输入"); title.setProperty("role", "section-title"); self.input_feedback = QLabel("等待输入"); self.input_feedback.setProperty("role", "muted")
        heading.addWidget(title); heading.addStretch(1); heading.addWidget(self.input_feedback); input_layout.addLayout(heading)
        self.input_edit = PracticeInputEdit(); self.input_edit.key_received.connect(self._handle_key); self.input_edit.clicked.connect(lambda: QTimer.singleShot(0, self._restore_focus)); input_layout.addWidget(self.input_edit, stretch=1)
        vertical = QSplitter(Qt.Orientation.Vertical); vertical.setChildrenCollapsible(False); vertical.addWidget(source); vertical.addWidget(input_card); vertical.setStretchFactor(0, 3); vertical.setStretchFactor(1, 2); vertical.setSizes([430, 270])
        layout.addWidget(vertical)
        return panel

    def _build_translation_panel(self) -> QWidget:
        panel = QFrame(); panel.setObjectName("TranslationCard"); panel.setMinimumWidth(300); panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel); layout.setContentsMargins(20, 20, 20, 20); layout.setSpacing(14)
        heading = QHBoxLayout()
        title = QLabel("中文译文"); title.setObjectName("SentenceTranslationHeading")
        heading.addWidget(title); heading.addStretch(1)
        self.translate_article_button = QPushButton("翻译整篇文章")
        self.translate_article_button.setProperty("variant", "ghost")
        self.translate_article_button.clicked.connect(self.translate_article_requested.emit)
        heading.addWidget(self.translate_article_button)
        layout.addLayout(heading)
        self.translation_status = QLabel("完成当前句后显示翻译"); self.translation_status.setObjectName("SentenceTranslationStatus")
        layout.addWidget(self.translation_status, alignment=Qt.AlignmentFlag.AlignLeft)

        self.translation_body = QFrame(); self.translation_body.setObjectName("SentenceTranslationBody")
        translation_layout = QVBoxLayout(self.translation_body); translation_layout.setContentsMargins(16, 16, 16, 16)
        self.translation_text = QLabel("翻译尚未显示"); self.translation_text.setObjectName("SentenceTranslationText")
        self.translation_text.setWordWrap(True); self.translation_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        translation_layout.addWidget(self.translation_text)
        layout.addWidget(self.translation_body)

        source_title = QLabel("英文原句"); source_title.setObjectName("SentenceSourceTitle"); layout.addWidget(source_title)
        self.translation_source = QLabel(""); self.translation_source.setObjectName("SentenceTranslationSource")
        self.translation_source.setWordWrap(True); layout.addWidget(self.translation_source)

        expression_title = QLabel("重点表达"); expression_title.setObjectName("SentenceExpressionsTitle"); layout.addWidget(expression_title)
        self.expressions_label = QLabel("暂无"); self.expressions_label.setObjectName("SentenceExpressionsText")
        self.expressions_label.setWordWrap(True); self.expressions_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); layout.addWidget(self.expressions_label)
        layout.addStretch(1)
        actions = QHBoxLayout()
        self.retry_button = QPushButton("重新生成 AI 翻译"); self.retry_button.clicked.connect(lambda: self._request_translation(True))
        self.edit_button = QPushButton("编辑翻译"); self.edit_button.clicked.connect(lambda: self.edit_translation_requested.emit(self.current_sentence))
        self.copy_button = QPushButton("复制中文"); self.copy_button.clicked.connect(self._copy_translation)
        actions.addWidget(self.retry_button); actions.addWidget(self.edit_button); actions.addWidget(self.copy_button); layout.addLayout(actions)
        self.next_button = QPushButton("下一句（Enter）"); self.next_button.setProperty("variant", "primary"); self.next_button.clicked.connect(self._next_sentence); layout.addWidget(self.next_button)
        self._set_translation_actions(False)
        return panel

    @property
    def current_sentence(self) -> ArticleSentence | None:
        return self.learning.current_sentence if self.learning else None

    def start_practice(self, material: PracticeMaterial, sentences: list[ArticleSentence], settings: AppSettings) -> None:
        self._course_mode = False
        self._course_translations = ()
        self._course_activity_types = ()
        self.course_actions.hide()
        self.translate_article_button.setVisible(True)
        self.speech_controls.setVisible(True)
        self.text_browser.set_word_collection_enabled(True)
        self._start_session(material, sentences, settings)

    def start_course_practice(
        self,
        material: PracticeMaterial,
        sentences: list[ArticleSentence],
        translations: tuple[str, ...],
        activity_types: tuple[tuple[str, ...], ...],
        settings: AppSettings,
    ) -> None:
        self._course_mode = True
        self._course_translations = translations
        self._course_activity_types = activity_types
        self.translate_article_button.setVisible(False)
        self.speech_controls.setVisible(True)
        self.text_browser.set_word_collection_enabled(True)
        self.course_actions.show()
        self._start_session(material, sentences, settings)

    def _start_session(self, material: PracticeMaterial, sentences: list[ArticleSentence], settings: AppSettings) -> None:
        self.material = material; self.sentences = sentences; self._emitted_attempts = 0; self._auto_read_sentence_index = -1
        leading_whitespace = len(material.section_text) - len(material.section_text.lstrip())
        self._section_start_offset = sentences[0].start_offset - leading_whitespace
        absolute = self._section_start_offset + material.resume_character_index
        sentence_index = len(sentences) - 1; local_position = len(sentences[-1].text)
        for index, sentence in enumerate(sentences):
            if absolute < sentence.start_offset:
                sentence_index = index; local_position = 0; break
            if sentence.start_offset <= absolute < sentence.end_offset:
                sentence_index = index; local_position = max(0, min(absolute - sentence.start_offset, len(sentence.text))); break
        self.learning = SentenceLearningSession(sentences, case_sensitive=settings.case_sensitive, idle_pause_seconds=settings.idle_pause_seconds, start_sentence_index=sentence_index, start_character_index=local_position)
        self.session = TypingSession(material.section_text, case_sensitive=settings.case_sensitive, start_position=material.resume_character_index)
        self.title_label.setText(material.article_title); self.pause_button.setText("暂停")
        self._show_translation = settings.show_translation_after_sentence
        self._auto_translate = settings.translation_auto_on_demand
        self.speech_controls.set_speed(settings.tts_speed)
        self._font_size = max(18, min(26, settings.font_size + 4)); self._apply_font(); self._show_sentence(); self._timer.start(); QTimer.singleShot(0, self._restore_focus)

    def _handle_key(self, event: QKeyEvent) -> None:
        if not self.learning or not self.session: return
        if event.key() == Qt.Key.Key_Escape: self._toggle_pause(); return
        if self.learning.state == SentenceLearningState.LEARNING_PAUSED:
            self._set_input_active(False)
            if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter} and not event.isAutoRepeat(): self._next_sentence()
            return
        if event.matches(QKeySequence.StandardKey.Paste): return
        if event.key() == Qt.Key.Key_Backspace:
            if self.learning.handle_backspace() and self.session.handle_backspace(): self.input_feedback.setText("已回退一格"); self.learning_activity.emit("typing_activity")
            self._refresh(); return
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier): return
        character = self._event_text(event)
        if not character: return
        result = self.learning.handle_character(character)
        if result is None: return
        self.session.handle_character(character)
        self.learning_activity.emit("typing_activity")
        self.input_feedback.setText("输入正确" if result else "输入错误，已继续前进")
        self._emit_new_attempts(); self._refresh()
        if self.learning.state == SentenceLearningState.LEARNING_PAUSED:
            self.learning_activity.emit("sentence_completed")
            self._set_input_active(False)
            self.state_label.setText("有效计时已暂停，请阅读翻译；按 Space 重听，按 Enter 进入下一句")
            if self._course_mode:
                self._show_course_translation()
            elif self._show_translation and self._auto_translate:
                self._request_translation(False)
            else:
                self.translation_status.setText("翻译已关闭" if not self._show_translation else "可按重试按钮翻译")
                self.next_button.setVisible(True)
            self._auto_read_completed_sentence()

    def _event_text(self, event: QKeyEvent) -> str:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}: return "\n"
        if event.key() == Qt.Key.Key_Tab: return "\t"
        text = event.text(); return text if len(text) == 1 and text.isprintable() else ""

    def _tick(self) -> None:
        if not self.learning: return
        if self.learning.check_idle(): self.state_label.setText("计时已暂停，继续输入即可恢复")
        self._update_stats()

    def _toggle_pause(self) -> None:
        if not self.learning: return
        self.learning.toggle_manual_pause()
        paused = self.learning.state == SentenceLearningState.MANUAL_PAUSED
        self.pause_button.setText("继续" if paused else "暂停")
        self.state_label.setText("练习已手动暂停" if paused else "练习已继续")
        self._set_input_active(not paused)
        if not paused: self._restore_focus()

    def _next_sentence(self) -> None:
        if not self.learning or self.learning.state != SentenceLearningState.LEARNING_PAUSED: return
        self.learning_activity.emit("next_item")
        if self.learning.next_sentence():
            self._show_sentence(); self.state_label.setText("输入第一个字符后开始计时"); self._set_input_active(True); self._restore_focus()
        else:
            self.session.skip_whitespace_to(len(self.session.content))
            self._timer.stop(); self._prepare_aggregate_snapshot(); self.session_completed.emit(self._aggregate_snapshot())

    def _show_sentence(self) -> None:
        sentence = self.current_sentence
        if not sentence or not self.learning: return
        if self.session:
            local_start = sentence.start_offset - self._section_start_offset
            self.session.skip_whitespace_to(local_start)
        self.sentence_label.setText(f"第 {self.learning.current_index + 1} / {len(self.sentences)} 句")
        self.translation_source.setText(sentence.normalized_text); self.translation_status.setText("完成当前句后显示课程译文" if self._course_mode else "完成当前句后显示翻译")
        self.translation_text.setText("翻译尚未显示"); self.expressions_label.setText("暂无"); self._set_translation_actions(False); self._refresh()
        if self._course_mode:
            activity_types = (
                self._course_activity_types[self.learning.current_index]
                if self.learning.current_index < len(self._course_activity_types)
                else ()
            )
            self.course_dictation_button.setVisible("dictation" in activity_types)
            self.course_speaking_button.setVisible("speaking" in activity_types)
            self.course_words_button.setVisible(True)
            self.course_review_button.setVisible("review" in activity_types)
        self.speech_sentence_changed.emit(sentence.normalized_text)

    def _request_translation(self, retry: bool) -> None:
        if self._course_mode:
            self._show_course_translation()
            return
        if self.current_sentence:
            self.translation_status.setText("正在翻译……"); self.translation_text.setText("请稍候，您也可以按 Enter 继续下一句。")
            self.next_button.setVisible(True)
            self.translation_requested.emit(self.current_sentence, retry)

    def show_translation(self, translation: SentenceTranslation, *, cached: bool = False) -> None:
        label = "人工修改" if translation.is_user_edited else ("已缓存" if cached else "AI 翻译")
        self.translation_status.setText(label); self.translation_text.setText(translation.chinese_translation or "暂无翻译")
        self.expressions_label.setText("\n".join(f"• {item.get('expression', '')}：{item.get('meaning', '')}" for item in translation.key_expressions) or "暂无")
        self.learning_activity.emit("meaning_revealed")
        self._set_translation_actions(True)

    def show_translation_failed(self, message: str) -> None:
        self.translation_status.setText("翻译失败"); self.translation_text.setText(message)
        self.retry_button.setText("重试翻译"); self._set_translation_actions(True)

    def _set_translation_actions(self, visible: bool) -> None:
        if self._course_mode:
            self.retry_button.setVisible(False)
            self.edit_button.setVisible(False)
            self.copy_button.setVisible(visible)
            self.next_button.setVisible(bool(self.learning and self.learning.state == SentenceLearningState.LEARNING_PAUSED))
            return
        if visible and self.translation_status.text() != "翻译失败":
            self.retry_button.setText("重新生成 AI 翻译")
        self.retry_button.setVisible(visible); self.edit_button.setVisible(visible); self.copy_button.setVisible(visible)
        self.next_button.setVisible(bool(self.learning and self.learning.state == SentenceLearningState.LEARNING_PAUSED))

    def _show_course_translation(self) -> None:
        if not self.learning:
            return
        index = self.learning.current_index
        translation = self._course_translations[index] if index < len(self._course_translations) else ""
        self.translation_status.setText("课程译文")
        self.translation_text.setText(translation or "本句暂无中文译文。")
        self.expressions_label.setText("本阶段未接入课程词汇能力。")
        self.learning_activity.emit("meaning_revealed")
        self._set_translation_actions(True)

    def _copy_translation(self) -> None:
        QApplication.clipboard().setText(self.translation_text.text())

    def _request_speech(self, speed: float) -> None:
        if self._course_mode:
            QTimer.singleShot(0, self._restore_focus)
            return
        if self.current_sentence:
            self.learning_activity.emit("audio_started")
            self.speech_requested.emit(self.current_sentence.normalized_text, speed, self.speech_controls)
        QTimer.singleShot(0, self._restore_focus)

    def _repeat_current_sentence(self) -> None:
        if not self.learning or self.learning.state != SentenceLearningState.LEARNING_PAUSED:
            return
        self._request_speech(float(self.speech_controls.speed_combo.currentData()))

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        in_this_view = isinstance(watched, QWidget) and (watched is self or self.isAncestorOf(watched))
        should_repeat = (
            in_this_view
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Space
            and not event.isAutoRepeat()
            and bool(self.learning)
            and self.learning.state == SentenceLearningState.LEARNING_PAUSED
            and not self._course_mode
        )
        if should_repeat:
            self._repeat_current_sentence()
            return True
        return super().eventFilter(watched, event)

    def _auto_read_completed_sentence(self) -> None:
        if not self.learning or self._course_mode:
            return
        sentence_index = self.learning.current_index
        if sentence_index == self._auto_read_sentence_index:
            return
        self._auto_read_sentence_index = sentence_index
        self._request_speech(float(self.speech_controls.speed_combo.currentData()))

    def _emit_new_attempts(self) -> None:
        if not self.learning: return
        while self._emitted_attempts < len(self.learning.attempts):
            self.attempt_completed.emit(self.learning.attempts[self._emitted_attempts]); self._emitted_attempts += 1

    def _refresh(self) -> None:
        if not self.learning or not self.session: return
        current = self.learning.current_session; sentence = self.learning.current_sentence
        self.progress_label.setText(f"进度 {self.session.position} / {len(self.session.content)}")
        self.text_browser.setPlainText(sentence.text); self._render_source(current); self._render_input(current); self._update_stats()

    def _render_source(self, current: TypingSession) -> None:
        dark = self.palette().window().color().lightness() < 128
        selections=[]
        if current.position: selections.append(self._selection(0,current.position,QColor("#8291a5" if dark else "#94a3b8")))
        for typed in current.typed_characters:
            if not typed.is_correct: selections.append(self._selection(typed.position,typed.position+1,QColor("#fecaca" if dark else "#b42318"),QColor("#4a2528" if dark else "#fee4e2"),True))
        if not current.is_complete: selections.append(self._selection(current.position,current.position+1,self.palette().text().color(),QColor("#263b53" if dark else "#e8f0fa"),False))
        self.text_browser.setExtraSelections(selections); cursor=self.text_browser.textCursor(); cursor.setPosition(min(current.position,len(current.content))); self.text_browser.setTextCursor(cursor); self.text_browser.ensureCursorVisible()

    def _render_input(self, current: TypingSession) -> None:
        dark=self.palette().window().color().lightness()<128; doc=self.input_edit.document(); doc.clear(); cursor=QTextCursor(doc)
        if current.start_position:
            fmt=QTextCharFormat(); fmt.setForeground(QColor("#8291a5" if dark else "#64748b")); cursor.insertText(current.content[:current.start_position],fmt)
        for typed in current.typed_characters:
            fmt=QTextCharFormat(); fmt.setForeground(QColor("#d9f3e4" if dark else "#18392a") if typed.is_correct else QColor("#fecaca" if dark else "#b42318"))
            if not typed.is_correct: fmt.setBackground(QColor("#4a2528" if dark else "#fee4e2")); fmt.setFontUnderline(True)
            cursor.insertText(typed.actual_char,fmt)
        cursor.movePosition(QTextCursor.MoveOperation.End); self.input_edit.setTextCursor(cursor); self.input_edit.ensureCursorVisible()

    def _selection(self,start,end,foreground,background=None,underline=False):
        selection=QTextEdit.ExtraSelection(); cursor=QTextCursor(self.text_browser.document()); cursor.setPosition(start); cursor.setPosition(end,QTextCursor.MoveMode.KeepAnchor); selection.cursor=cursor
        fmt=QTextCharFormat(); fmt.setForeground(foreground); fmt.setFontUnderline(underline)
        if background: fmt.setBackground(background)
        selection.format=fmt; return selection

    def _update_stats(self) -> None:
        if not self.learning or not self.session: return
        timing=self.learning.timing_snapshot(); snap=self.session.snapshot(); self.wpm_value.setText(f"{calculate_wpm(snap.correct_characters,timing.active_seconds):.1f}"); self.cpm_value.setText(f"{calculate_cpm(snap.correct_characters,timing.active_seconds):.1f}")
        self.accuracy_value.setText(f"{snap.accuracy:.1f}%"); self.errors_value.setText(str(snap.error_keystrokes)); self.active_value.setText(f"{timing.active_seconds:.1f} 秒")

    def _aggregate_snapshot(self):
        snap=self.session.snapshot(); timing=self.learning.timing_snapshot(); return replace(snap,elapsed_active_seconds=timing.active_seconds,paused_seconds=timing.learning_seconds+timing.idle_seconds+timing.manual_paused_seconds,wpm=calculate_wpm(snap.correct_characters,timing.active_seconds),cpm=calculate_cpm(snap.correct_characters,timing.active_seconds))

    def current_snapshot(self):
        self._prepare_aggregate_snapshot(); return self._aggregate_snapshot()

    def _prepare_aggregate_snapshot(self) -> None:
        timing=self.learning.timing_snapshot(); self.session.timing_breakdown={"total_elapsed_seconds":timing.total_elapsed_seconds,"learning_seconds":timing.learning_seconds,"idle_seconds":timing.idle_seconds,"manual_paused_seconds":timing.manual_paused_seconds}

    def _stat(self,row,title):
        box=QVBoxLayout(); label=QLabel(title); label.setProperty("role","metric-title"); value=QLabel("-"); value.setProperty("role","metric-value"); box.addWidget(label); box.addWidget(value); row.addLayout(box); return value

    def _apply_font(self) -> None:
        for editor in (self.text_browser,self.input_edit): font=editor.font(); font.setPixelSize(self._font_size); editor.setFont(font); editor.document().setDefaultFont(font)

    def resizeEvent(self,event) -> None:
        super().resizeEvent(event); self.main_splitter.setOrientation(Qt.Orientation.Vertical if self.width()<1100 else Qt.Orientation.Horizontal)

    def focusOutEvent(self,event) -> None:
        if self.learning and not self.isActiveWindow(): self.learning.focus_lost(); self.pause_button.setText("继续"); self.state_label.setText("窗口失去焦点，练习已暂停")
        super().focusOutEvent(event)

    def _restore_focus(self) -> None:
        if not self.learning or self.learning.state in {SentenceLearningState.LEARNING_PAUSED, SentenceLearningState.MANUAL_PAUSED, SentenceLearningState.COMPLETED}:
            self._set_input_active(False); return
        self._set_input_active(True); self.input_edit.setFocus(Qt.FocusReason.OtherFocusReason); cursor=self.input_edit.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End); self.input_edit.setTextCursor(cursor); self.input_edit.ensureCursorVisible()

    def _set_input_active(self, active: bool) -> None:
        self.input_edit.setCursorWidth(2 if active else 0)
