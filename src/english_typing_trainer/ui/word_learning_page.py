from __future__ import annotations

from time import monotonic

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QSplitter, QVBoxLayout, QWidget

from english_typing_trainer.models.vocabulary import VocabularyAttempt, VocabularyContext, VocabularyEntry, VocabularyLearningState
from english_typing_trainer.ui.practice_view import PracticeInputEdit
from english_typing_trainer.ui.theme import resource_root


class WordLearningPage(QWidget):
    back_requested=Signal(); play_word_requested=Signal(object, object); play_sentence_requested=Signal(str)
    attempt_completed=Signal(object); context_changed=Signal(int)

    def __init__(self,parent=None) -> None:
        super().__init__(parent); self.entry=None; self.contexts=[]; self.state=None; self.typed=""; self.errors=0; self.repeat_index=0; self.started=None; self.mode="typing"
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(32,24,32,24); root.setSpacing(16)
        top=QHBoxLayout(); self.back_button=QPushButton("返回单词本"); self.back_button.setProperty("variant","ghost"); self.back_button.clicked.connect(self.back_requested.emit)
        self.title=QLabel("单词学习"); self.title.setProperty("role","page-title")
        self.mode_combo=QComboBox(); self.mode_combo.addItem("单词打字","typing"); self.mode_combo.addItem("原句填空","sentence_cloze"); self.mode_combo.addItem("看英文回忆中文","meaning_recall"); self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        top.addWidget(self.back_button); top.addWidget(self.title,1); top.addWidget(self.mode_combo); root.addLayout(top)
        split=QSplitter(Qt.Orientation.Horizontal); split.setChildrenCollapsible(False)
        left=QFrame(); left.setObjectName("Card"); ll=QVBoxLayout(left); ll.setContentsMargins(24,24,24,24); ll.setSpacing(16)
        self.prompt=QLabel(""); self.prompt.setWordWrap(True); self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter); self.prompt.setStyleSheet("font-size: 30px; font-weight: 600;")
        self.progress=QLabel(""); self.progress.setProperty("role","subtitle"); self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input=PracticeInputEdit(); self.input.setMinimumHeight(140); self.input.key_received.connect(self._key)
        self.reveal=QPushButton("显示意思"); self.reveal.clicked.connect(self._reveal); self.reveal.hide()
        ratings=QHBoxLayout(); self.rating_buttons=[]
        for text,value in (("不认识","unknown"),("模糊","fuzzy"),("认识","known"),("很熟","familiar")):
            button=QPushButton(text); button.clicked.connect(lambda checked=False,v=value:self._rate(v)); button.hide(); ratings.addWidget(button); self.rating_buttons.append(button)
        ll.addStretch(1); ll.addWidget(self.prompt); ll.addWidget(self.progress); ll.addWidget(self.input); ll.addWidget(self.reveal,alignment=Qt.AlignmentFlag.AlignCenter); ll.addLayout(ratings); ll.addStretch(1)
        right=QFrame(); right.setObjectName("Card"); rl=QVBoxLayout(right); rl.setContentsMargins(24,24,24,24); rl.setSpacing(12)
        head=QHBoxLayout(); self.word=QLabel(""); self.word.setProperty("role","page-title"); self.play_word=QPushButton("播放单词"); self.play_word.clicked.connect(lambda:self.play_word_requested.emit(self.entry,self.current_context))
        self.play_word.setIcon(QIcon(str(resource_root()/"icons"/"speaker.svg")))
        head.addWidget(self.word,1); head.addWidget(self.play_word); rl.addLayout(head)
        self.phonetic=QLabel(""); self.phonetic.setProperty("role","subtitle"); rl.addWidget(self.phonetic)
        self.meaning=QLabel("等待获取中文讲解"); self.meaning.setWordWrap(True); self.meaning.setStyleSheet("font-size: 20px; font-weight: 600;"); rl.addWidget(self.meaning)
        self.explanation=QLabel(""); self.explanation.setWordWrap(True); rl.addWidget(self.explanation)
        self.collocation=QLabel(""); self.collocation.setWordWrap(True); rl.addWidget(self.collocation)
        self.context_combo=QComboBox(); self.context_combo.currentIndexChanged.connect(self._context_index_changed); rl.addWidget(self.context_combo)
        self.sentence=QLabel(""); self.sentence.setWordWrap(True); rl.addWidget(self.sentence)
        self.play_sentence=QPushButton("播放来源句"); self.play_sentence.clicked.connect(lambda:self.play_sentence_requested.emit(self.current_context.source_sentence if self.current_context else "")); rl.addWidget(self.play_sentence,alignment=Qt.AlignmentFlag.AlignLeft); rl.addStretch(1)
        self.play_sentence.setIcon(QIcon(str(resource_root()/"icons"/"speaker.svg")))
        split.addWidget(left); split.addWidget(right); split.setSizes([850,450]); root.addWidget(split,1)

    @property
    def current_context(self):
        index=self.context_combo.currentIndex(); return self.contexts[index] if 0<=index<len(self.contexts) else None

    def load(self,entry:VocabularyEntry,contexts:list[VocabularyContext],state:VocabularyLearningState):
        self.entry=entry; self.contexts=contexts; self.state=state; self.repeat_index=0
        self.word.setText(entry.display_word); self.phonetic.setText(entry.phonetic or "暂无音标")
        self.context_combo.clear()
        for i,c in enumerate(contexts): self.context_combo.addItem(f"来源 {i+1}：{c.source_sentence[:36] or '手动添加'}",i)
        if not contexts:
            self.meaning.setText("等待获取中文讲解"); self.explanation.setText("该旧词条暂无来源句，可以继续打字学习并在联网后补充词典信息。")
            self.collocation.clear(); self.sentence.setText("暂无来源句"); self.play_sentence.setEnabled(False)
        else:
            self.play_sentence.setEnabled(True)
        self._context_index_changed(); self._reset_round(); QTimer.singleShot(0,self.input.setFocus)

    def _context_index_changed(self):
        c=self.current_context
        if not c: return
        self.meaning.setText(c.contextual_meaning_zh or "等待获取中文讲解")
        self.explanation.setText(c.explanation_zh or "已有收藏可离线学习；联网后可补充讲解。")
        self.collocation.setText(f"常见搭配：{c.common_collocation}" if c.common_collocation else "")
        self.sentence.setText(c.source_sentence or "暂无来源句")
        if c.id: self.context_changed.emit(c.id)
        self._update_prompt()

    def _mode_changed(self): self.mode=str(self.mode_combo.currentData()); self.repeat_index=0; self._reset_round()

    def _update_prompt(self):
        if not self.entry:return
        c=self.current_context
        if self.mode=="typing": self.prompt.setText(self.entry.display_word); self.progress.setText(f"当前进度 {self.repeat_index} / {self.state.typing_target_count if self.state else 5}")
        elif self.mode=="sentence_cloze":
            sentence=c.source_sentence if c else ""; word=c.source_word if c else self.entry.display_word
            if c and 0<=c.start_offset<c.end_offset<=len(sentence) and sentence[c.start_offset:c.end_offset]==word:
                sentence=sentence[:c.start_offset]+"___"+sentence[c.end_offset:]
            else: sentence=sentence.replace(word,"___",1)
            self.prompt.setText(sentence); self.progress.setText("输入原句中的正确词形")
        else: self.prompt.setText(f"{self.entry.display_word}\n{c.source_sentence if c else ''}"); self.progress.setText("先回忆中文意思，再点击显示")

    def _reset_round(self):
        self.typed=""; self.errors=0; self.started=None; self.input.clear(); self.input.setEnabled(self.mode!="meaning_recall")
        self.reveal.setVisible(self.mode=="meaning_recall"); [b.hide() for b in self.rating_buttons]; self._update_prompt(); QTimer.singleShot(0,self.input.setFocus)

    def _key(self,event:QKeyEvent):
        if event.key()==Qt.Key.Key_Backspace: self.typed=self.typed[:-1]; self._render(); return
        text="\n" if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) else event.text()
        if not text or len(text)!=1:return
        if self.started is None:self.started=monotonic()
        self.typed+=text; expected=self._expected()
        if len(self.typed)<=len(expected) and self.typed[-1]!=expected[len(self.typed)-1]:self.errors+=1
        self._render()
        if len(self.typed)>=len(expected): self._finish(expected)

    def _render(self):
        self.input.clear(); cursor=QTextCursor(self.input.document()); expected=self._expected()
        for i,ch in enumerate(self.typed):
            fmt=QTextCharFormat()
            if i>=len(expected) or ch!=expected[i]: fmt.setForeground(QColor("#c74444")); fmt.setBackground(QColor("#fee2e2"))
            cursor.insertText(ch,fmt)
        cursor.movePosition(QTextCursor.MoveOperation.End); self.input.setTextCursor(cursor); self.input.ensureCursorVisible()

    def _expected(self) -> str:
        if self.mode=="sentence_cloze" and self.current_context:return self.current_context.source_word
        return self.entry.normalized_word if self.entry else ""

    def _finish(self,expected):
        correct=self.typed==expected; duration=int(((monotonic()-(self.started or monotonic())))*1000); accuracy=max(0,(len(expected)-self.errors)/max(len(expected),1)*100)
        self.attempt_completed.emit(VocabularyAttempt(self.entry.id,self.mode,expected,self.typed,correct,accuracy,duration,vocabulary_context_id=self.current_context.id if self.current_context else None))
        if self.mode=="typing" and correct:
            self.repeat_index+=1
            if self.state and self.repeat_index>=self.state.typing_target_count:
                self.progress.setText(f"已完成 {self.state.typing_target_count} 次单词打字"); self.input.setEnabled(False); return
        QTimer.singleShot(250,self._reset_round)

    def _reveal(self):
        self.meaning.setText(self.current_context.contextual_meaning_zh or "暂无中文讲解"); self.reveal.hide(); [b.show() for b in self.rating_buttons]

    def _rate(self,rating):
        self.attempt_completed.emit(VocabularyAttempt(self.entry.id,"meaning_recall",self.current_context.contextual_meaning_zh if self.current_context else "","",None,0,0,rating,self.current_context.id if self.current_context else None)); self._reset_round()
