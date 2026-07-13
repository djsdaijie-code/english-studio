from __future__ import annotations

from time import monotonic

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from english_typing_trainer.models.dictation import DictationAttempt
from english_typing_trainer.models.fsrs_review import ReviewQueueItem
from english_typing_trainer.services.dictation_service import DictationService
from english_typing_trainer.ui.practice_view import PracticeInputEdit


class DictationPage(QWidget):
    back_requested = Signal()
    audio_requested = Signal(str, float)
    rating_requested = Signal(int, str)
    attempt_completed = Signal(object)
    learning_activity = Signal(str, object)

    def __init__(self, service: DictationService, parent=None) -> None:
        super().__init__(parent)
        self.service = service; self.items: list[ReviewQueueItem] = []; self.index = 0
        self.replay_count = 0; self._started = 0.0; self._submitted = False
        self._build()

    def _build(self) -> None:
        root=QVBoxLayout(self); root.setContentsMargins(32,24,32,24); root.setSpacing(16)
        top=QHBoxLayout(); back=QPushButton("返回单词本"); back.setProperty("variant","ghost"); back.clicked.connect(self.back_requested.emit)
        self.title=QLabel("听写练习"); self.title.setProperty("role","page-title"); self.position=QLabel("0 / 0"); self.position.setProperty("role","subtitle")
        top.addWidget(back); top.addWidget(self.title,1); top.addWidget(self.position); root.addLayout(top)
        card=QFrame(); card.setObjectName("Card"); layout=QVBoxLayout(card); layout.setContentsMargins(36,32,36,32); layout.setSpacing(16)
        controls=QHBoxLayout(); self.kind=QComboBox(); self.kind.addItem("单词听写","word"); self.kind.addItem("句子听写","sentence")
        self.mode=QComboBox(); self.mode.addItem("严格模式","strict"); self.mode.addItem("学习模式（忽略句首大小写和句末标点）","learning")
        self.speed=QComboBox(); [self.speed.addItem(f"{value:.1f}×",value) for value in (0.8,1.0,1.2)]
        self.play=QPushButton("播放"); self.play.clicked.connect(self._play); controls.addWidget(QLabel("类型")); controls.addWidget(self.kind); controls.addWidget(self.mode); controls.addWidget(self.speed); controls.addStretch(1); controls.addWidget(self.play)
        self.prompt=QLabel("点击播放后输入听到的内容"); self.prompt.setWordWrap(True); self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter); self.prompt.setStyleSheet("font-size: 24px; font-weight: 600;")
        self.context=QLabel(""); self.context.setWordWrap(True); self.context.setAlignment(Qt.AlignmentFlag.AlignCenter); self.context.setProperty("role","subtitle")
        self.input=PracticeInputEdit(); self.input.setMinimumHeight(130); self.input.setPlaceholderText("在这里输入听写内容"); self.input.key_received.connect(self._key); self.input.clicked.connect(self._restore_focus)
        self.submit=QPushButton("提交听写"); self.submit.setProperty("variant","primary"); self.submit.clicked.connect(self._submit)
        self.feedback=QLabel(""); self.feedback.setWordWrap(True); self.feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ratings=QHBoxLayout(); self.rating_buttons=[]
        for text,value in (("忘记了","again"),("困难","hard"),("记得","good"),("很熟","easy")):
            button=QPushButton(text); button.clicked.connect(lambda _=False,rating=value:self._rate(rating)); button.hide(); self.ratings.addWidget(button); self.rating_buttons.append(button)
        layout.addLayout(controls); layout.addStretch(1); layout.addWidget(self.prompt); layout.addWidget(self.context); layout.addWidget(self.input); layout.addWidget(self.submit, alignment=Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.feedback); layout.addLayout(self.ratings); layout.addStretch(1); root.addWidget(card,1)
        self.kind.currentIndexChanged.connect(self._load_current); self.mode.currentIndexChanged.connect(self._load_current)

    @property
    def current(self): return self.items[self.index] if 0 <= self.index < len(self.items) else None

    def load_queue(self, items: list[ReviewQueueItem]) -> None:
        self.items=list(items); self.index=0; self._load_current()

    def _expected(self) -> str:
        item=self.current
        if item is None:return ""
        return item.target_word if self.kind.currentData()=="word" else (item.context.source_sentence if item.context else item.target_word)

    def _load_current(self) -> None:
        self._submitted=False; self.replay_count=0; self._started=0.0; self.input.clear(); self.feedback.clear()
        for button in self.rating_buttons: button.hide()
        item=self.current
        if item is None:
            self.position.setText("已完成"); self.prompt.setText("本轮听写已结束"); self.context.setText(""); self.input.setEnabled(False); self.submit.setEnabled(False); self.play.setEnabled(False); return
        self.position.setText(f"第 {self.index+1} / {len(self.items)} 项"); self.prompt.setText("播放后输入你听到的内容"); self.context.setText("单词严格保留大小写、连字符和撇号。句子可选择学习模式。")
        is_word=self.kind.currentData()=="word"; self.mode.setEnabled(not is_word); self.input.setEnabled(True); self.submit.setEnabled(True); self.play.setEnabled(True); QTimer.singleShot(0,self._restore_focus)

    def _play(self) -> None:
        if self.current is None:return
        self.replay_count+=1; self.learning_activity.emit("audio_started",self.current.entry.id); self.audio_requested.emit(self._expected(),float(self.speed.currentData())); self._restore_focus()

    def _key(self,event) -> None:
        if not self.input.isEnabled():return
        if event.key()==Qt.Key.Key_Backspace:
            cursor=self.input.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End); cursor.deletePreviousChar(); self.input.setTextCursor(cursor); self.learning_activity.emit("typing_activity",self.current.entry.id if self.current else None); return
        text=event.text()
        if text and len(text)==1:
            self._started=self._started or monotonic(); cursor=self.input.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End); cursor.insertText(text); self.input.setTextCursor(cursor); self.learning_activity.emit("typing_activity",self.current.entry.id if self.current else None)
        if event.key() in {Qt.Key.Key_Return,Qt.Key.Key_Enter} and self.kind.currentData()=="sentence": self._submit()

    def _submit(self) -> None:
        item=self.current
        if item is None or self._submitted:return
        expected=self._expected(); actual=self.input.toPlainText(); kind=str(self.kind.currentData()); mode=str(self.mode.currentData()) if kind=="sentence" else "strict"; comparison=self.service.compare(expected,actual,dictation_type=kind,mode=mode)
        duration=int(max(0.0,monotonic()-self._started)*1000) if self._started else 0
        attempt=DictationAttempt(kind,mode,expected,actual,f"{comparison.normalized_expected} => {comparison.normalized_actual}",comparison.error_count,comparison.omitted_count,comparison.inserted_count,self.replay_count,float(self.speed.currentData()),duration,vocabulary_entry_id=item.entry.id,vocabulary_context_id=item.context.id if item.context else None)
        self.attempt_completed.emit(attempt); self._submitted=True; self.input.setEnabled(False); self.submit.setEnabled(False)
        self.feedback.setText("听写正确，请选择熟悉程度。" if comparison.correct else f"标准答案：{expected}\n错误 {comparison.error_count}，遗漏 {comparison.omitted_count}，多余 {comparison.inserted_count}")
        for button in self.rating_buttons:button.show()

    def _rate(self,rating:str)->None:
        item=self.current
        if item is None:return
        self.rating_requested.emit(item.entry.id or 0,rating); self.learning_activity.emit("self_rated",item.entry.id); self.index+=1; self._load_current()

    def _restore_focus(self)->None:
        if self.input.isEnabled():
            cursor=self.input.textCursor(); cursor.movePosition(QTextCursor.MoveOperation.End); self.input.setTextCursor(cursor); self.input.setFocus(); self.input.ensureCursorVisible()
