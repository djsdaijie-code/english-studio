from __future__ import annotations

from time import monotonic

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QIcon, QKeyEvent, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.models.vocabulary import VocabularyAttempt, VocabularyContext, VocabularyEntry, VocabularyLearningState
from english_typing_trainer.ui.practice_view import PracticeInputEdit
from english_typing_trainer.ui.segmented_control import SegmentedControl
from english_typing_trainer.ui.theme import resource_root


class WordLearningPage(QWidget):
    back_requested=Signal(); play_word_requested=Signal(object, object); play_sentence_requested=Signal(str)
    attempt_completed=Signal(object); context_changed=Signal(int)
    current_entry_changed=Signal(int); queue_finished=Signal(object)
    retry_enrichment_requested=Signal(int, object)
    learning_activity=Signal(str)

    def __init__(self,parent=None) -> None:
        super().__init__(parent); self.entry=None; self.contexts=[]; self.state=None; self.typed=""; self.errors=0; self.repeat_index=0; self.started=None; self.mode="typing"
        self.queue=[]; self.queue_index=0; self.completed_words=0; self.skipped_words=0; self.queue_correct=0; self.queue_errors=0; self.queue_started=0.0; self._switch_token=0
        self._build()

    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(32,24,32,24); root.setSpacing(16)
        top=QHBoxLayout(); self.back_button=QPushButton("返回单词本"); self.back_button.setProperty("variant","ghost"); self.back_button.clicked.connect(self.back_requested.emit)
        self.title=QLabel("单词学习"); self.title.setProperty("role","page-title")
        self.queue_position=QLabel("第 0 / 0 个"); self.queue_position.setProperty("role","subtitle")
        self.queue_progress=QProgressBar(); self.queue_progress.setObjectName("WordQueueProgress"); self.queue_progress.setRange(0,1); self.queue_progress.setValue(0); self.queue_progress.setTextVisible(False); self.queue_progress.setFixedWidth(116); self.queue_progress.setFixedHeight(7)
        self.previous_button=QPushButton("上一个"); self.skip_button=QPushButton("跳过"); self.next_button=QPushButton("下一个")
        self.previous_button.clicked.connect(self.previous_word); self.skip_button.clicked.connect(self.skip_word); self.next_button.clicked.connect(self._manual_next)
        top.addWidget(self.back_button); top.addWidget(self.title,1); top.addWidget(self.queue_position); top.addWidget(self.queue_progress); top.addWidget(self.previous_button); top.addWidget(self.skip_button); top.addWidget(self.next_button); root.addLayout(top)

        mode_row=QHBoxLayout(); mode_row.addStretch(1)
        mode_label=QLabel("练习方式"); mode_label.setProperty("role","subtitle")
        self.mode_control=SegmentedControl([("单词打字","typing"),("原句填空","sentence_cloze"),("回忆中文","meaning_recall")])
        self.mode_control.setObjectName("WordLearningModeControl"); self.mode_control.set_value("typing"); self.mode_control.value_changed.connect(self._mode_changed)
        mode_row.addWidget(mode_label); mode_row.addWidget(self.mode_control); root.addLayout(mode_row)

        split=QSplitter(Qt.Orientation.Horizontal); split.setChildrenCollapsible(False)
        left=QFrame(); left.setObjectName("WordLearningFocusCard"); ll=QVBoxLayout(left); ll.setContentsMargins(32,30,32,28); ll.setSpacing(12)
        prompt_label=QLabel("当前练习"); prompt_label.setObjectName("WordLearningEyebrow"); prompt_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.prompt=QLabel(""); self.prompt.setObjectName("WordLearningPrompt"); self.prompt.setWordWrap(True); self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress=QLabel(""); self.progress.setObjectName("WordLearningProgressText"); self.progress.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.repeat_progress=QProgressBar(); self.repeat_progress.setObjectName("WordRepeatProgress"); self.repeat_progress.setRange(0,5); self.repeat_progress.setValue(0); self.repeat_progress.setTextVisible(False); self.repeat_progress.setFixedHeight(8); self.repeat_progress.setMaximumWidth(360)

        self.input_panel=QFrame(); self.input_panel.setObjectName("WordLearningInputPanel"); self.input_panel.setMinimumWidth(480); self.input_panel.setMaximumWidth(680); self.input_panel.setMaximumHeight(150); self.input_panel.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed)
        input_layout=QVBoxLayout(self.input_panel); input_layout.setContentsMargins(18,14,18,14); input_layout.setSpacing(8)
        input_title=QLabel("输入单词"); input_title.setObjectName("WordLearningInputTitle")
        self.input=PracticeInputEdit(); self.input.setObjectName("WordLearningInput"); self.input.setFixedHeight(72); self.input.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Fixed); self.input.setLineWrapMode(PracticeInputEdit.LineWrapMode.NoWrap); self.input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff); self.input.key_received.connect(self._key)
        self.input_hint=QLabel("严格区分大小写，错误字符会标红"); self.input_hint.setObjectName("WordLearningInputHint")
        input_layout.addWidget(input_title); input_layout.addWidget(self.input); input_layout.addWidget(self.input_hint)

        self.reveal=QPushButton("显示中文意思"); self.reveal.setProperty("variant","primary"); self.reveal.clicked.connect(self._reveal); self.reveal.hide()
        result_actions=QHBoxLayout(); self.retry_queue_button=QPushButton("再练一遍"); self.retry_queue_button.clicked.connect(self.retry_queue); self.retry_queue_button.hide(); self.result_back_button=QPushButton("返回单词本"); self.result_back_button.clicked.connect(self.back_requested.emit); self.result_back_button.hide(); result_actions.addStretch(1); result_actions.addWidget(self.retry_queue_button); result_actions.addWidget(self.result_back_button); result_actions.addStretch(1)
        ratings=QHBoxLayout(); self.rating_buttons=[]
        for text,value in (("不认识","unknown"),("模糊","fuzzy"),("认识","known"),("很熟","familiar")):
            button=QPushButton(text); button.clicked.connect(lambda checked=False,v=value:self._rate(v)); button.hide(); ratings.addWidget(button); self.rating_buttons.append(button)
        ll.addWidget(prompt_label); ll.addWidget(self.prompt); ll.addWidget(self.progress); ll.addWidget(self.repeat_progress,alignment=Qt.AlignmentFlag.AlignHCenter); ll.addSpacing(10); ll.addWidget(self.input_panel,alignment=Qt.AlignmentFlag.AlignHCenter); ll.addWidget(self.reveal,alignment=Qt.AlignmentFlag.AlignCenter); ll.addLayout(ratings); ll.addLayout(result_actions); ll.addStretch(1)

        right=QFrame(); right.setObjectName("WordLearningDetailCard"); right.setMinimumWidth(360); rl=QVBoxLayout(right); rl.setContentsMargins(26,26,26,24); rl.setSpacing(10)
        head=QHBoxLayout(); self.word=QLabel(""); self.word.setProperty("role","page-title"); self.play_word=QPushButton("播放单词"); self.play_word.clicked.connect(lambda:self.play_word_requested.emit(self.entry,self.current_context)); self.play_word.clicked.connect(lambda:self.learning_activity.emit("audio_started"))
        self.play_word.setIcon(QIcon(str(resource_root()/"icons"/"speaker.svg")))
        head.addWidget(self.word,1); head.addWidget(self.play_word); rl.addLayout(head)
        self.phonetic=QLabel(""); self.phonetic.setProperty("role","subtitle"); rl.addWidget(self.phonetic)
        enrichment_row=QHBoxLayout(); self.enrichment_status=QLabel(""); self.enrichment_status.setProperty("role","subtitle")
        self.retry_enrichment_button=QPushButton("重试"); self.retry_enrichment_button.hide()
        self.retry_enrichment_button.clicked.connect(self._retry_enrichment)
        enrichment_row.addWidget(self.enrichment_status,1); enrichment_row.addWidget(self.retry_enrichment_button); rl.addLayout(enrichment_row)

        meaning_card=QFrame(); meaning_card.setObjectName("WordMeaningCard"); meaning_layout=QVBoxLayout(meaning_card); meaning_layout.setContentsMargins(16,14,16,14); meaning_layout.setSpacing(6)
        meaning_title=QLabel("中文意思"); meaning_title.setObjectName("WordDetailSectionTitle")
        self.meaning=QLabel("等待获取中文讲解"); self.meaning.setObjectName("WordMeaningText"); self.meaning.setWordWrap(True)
        self.explanation=QLabel(""); self.explanation.setObjectName("WordExplanationText"); self.explanation.setWordWrap(True)
        meaning_layout.addWidget(meaning_title); meaning_layout.addWidget(self.meaning); meaning_layout.addWidget(self.explanation); rl.addWidget(meaning_card)

        collocation_title=QLabel("常见搭配"); collocation_title.setObjectName("WordDetailSectionTitle"); rl.addWidget(collocation_title)
        self.collocation=QLabel(""); self.collocation.setObjectName("WordCollocationText"); self.collocation.setWordWrap(True); rl.addWidget(self.collocation)

        source_title=QLabel("来源原句"); source_title.setObjectName("WordDetailSectionTitle"); rl.addWidget(source_title)
        self.context_combo=QComboBox(); self.context_combo.currentIndexChanged.connect(self._context_index_changed)
        self.context_combo.activated.connect(lambda _index: self.learning_activity.emit("source_changed")); rl.addWidget(self.context_combo)
        self.sentence=QLabel(""); self.sentence.setObjectName("WordSourceSentence"); self.sentence.setWordWrap(True); rl.addWidget(self.sentence)
        self.play_sentence=QPushButton("播放来源句"); self.play_sentence.clicked.connect(lambda:self.play_sentence_requested.emit(self.current_context.source_sentence if self.current_context else "")); self.play_sentence.clicked.connect(lambda:self.learning_activity.emit("audio_started")); rl.addWidget(self.play_sentence,alignment=Qt.AlignmentFlag.AlignLeft); rl.addStretch(1)
        self.play_sentence.setIcon(QIcon(str(resource_root()/"icons"/"speaker.svg")))
        split.addWidget(left); split.addWidget(right); split.setStretchFactor(0,3); split.setStretchFactor(1,2); split.setSizes([760,480]); root.addWidget(split,1)

    @property
    def current_context(self):
        index=self.context_combo.currentIndex(); return self.contexts[index] if 0<=index<len(self.contexts) else None

    @property
    def current_target_word(self) -> str:
        context=self.current_context
        if context and context.source_word:
            return context.source_word
        if self.entry and self.entry.display_word:
            return self.entry.display_word
        return self.entry.normalized_word if self.entry else ""

    def load(self,entry:VocabularyEntry,contexts:list[VocabularyContext],state:VocabularyLearningState):
        self.load_queue([(entry,contexts,state)])

    def load_queue(self,items):
        self.queue=list(items); self.queue_index=0; self.completed_words=0; self.skipped_words=0; self.queue_correct=0; self.queue_errors=0; self.queue_started=monotonic(); self.retry_queue_button.hide(); self.result_back_button.hide(); self._load_current()

    def _load_current(self):
        if not self.queue:
            self._show_results(); return
        self.entry,self.contexts,self.state=self.queue[self.queue_index]; self.repeat_index=0; self._switch_token+=1
        self.queue_position.setText(f"第 {self.queue_index+1} / {len(self.queue)} 个")
        self.queue_progress.setRange(0,max(1,len(self.queue))); self.queue_progress.setValue(self.queue_index+1)
        self.previous_button.setEnabled(self.queue_index>0); self.next_button.setEnabled(self.queue_index<len(self.queue)-1)
        self._render_entry(); self._reset_round(); self.current_entry_changed.emit(self.entry.id)

    def _render_entry(self,preserve_context_id:int|None=None):
        entry=self.entry; contexts=self.contexts
        self.word.setText(entry.display_word); self.phonetic.setText(entry.phonetic or "暂无音标")
        self.context_combo.clear()
        for i,c in enumerate(contexts): self.context_combo.addItem(f"来源 {i+1}：{c.source_sentence[:36] or '手动添加'}",i)
        if preserve_context_id is not None:
            preserved=next((i for i,c in enumerate(contexts) if c.id==preserve_context_id),-1)
            if preserved>=0:self.context_combo.setCurrentIndex(preserved)
        if not contexts:
            self.meaning.setText("等待获取中文讲解"); self.explanation.setText("该旧词条暂无来源句，可以继续打字学习并在联网后补充词典信息。")
            self.collocation.clear(); self.sentence.setText("暂无来源句"); self.play_sentence.setEnabled(False)
        else:
            self.play_sentence.setEnabled(True)
        self._context_index_changed(); QTimer.singleShot(0,self.input.setFocus)

    def update_details(self,entry:VocabularyEntry,contexts:list[VocabularyContext],state:VocabularyLearningState):
        if not self.entry or entry.id!=self.entry.id:return False
        typed=self.typed; repeat=self.repeat_index; cursor=self.input.textCursor().position(); context=self.current_context
        preserve_context_id=context.id if context else None
        self.entry=entry; self.contexts=contexts; self.state=state; self.queue[self.queue_index]=(entry,contexts,state); self._render_entry(preserve_context_id)
        self.typed=typed; self.repeat_index=repeat; self._render(); self._update_prompt(); self.input.setFocus(); return self.input.textCursor().position()>=min(cursor,len(typed))

    def set_enrichment_status(self,text:str,retry:bool=False) -> None:
        self.enrichment_status.setText(text)
        self.retry_enrichment_button.setVisible(retry)

    def _retry_enrichment(self) -> None:
        if self.entry:self.retry_enrichment_requested.emit(self.entry.id,self.current_context.id if self.current_context else None)

    def _context_index_changed(self):
        c=self.current_context
        if not c: return
        self.meaning.setText(c.contextual_meaning_zh or "等待获取中文讲解")
        self.explanation.setText(c.explanation_zh or "已有收藏可离线学习；联网后可补充讲解。")
        self.collocation.setText(c.common_collocation or "暂无常见搭配")
        self.sentence.setText(c.source_sentence or "暂无来源句")
        if c.id: self.context_changed.emit(c.id)
        self._update_prompt()
        if self.typed:self._render()

    def _mode_changed(self,mode:str): self.mode=mode; self.repeat_index=0; self._reset_round()

    def _update_prompt(self):
        if not self.entry:return
        c=self.current_context
        if self.mode=="typing":
            target=self.state.typing_target_count if self.state else 5
            self.prompt.setText(self.current_target_word); self.progress.setText(f"已完成 {self.repeat_index} 次 · 共 {target} 次")
            self.repeat_progress.setRange(0,max(1,target)); self.repeat_progress.setValue(self.repeat_index); self.repeat_progress.show()
        elif self.mode=="sentence_cloze":
            sentence=c.source_sentence if c else ""; word=self.current_target_word
            if c and 0<=c.start_offset<c.end_offset<=len(sentence) and sentence[c.start_offset:c.end_offset]==word:
                sentence=sentence[:c.start_offset]+"___"+sentence[c.end_offset:]
            else: sentence=sentence.replace(word,"___",1)
            self.prompt.setText(sentence); self.progress.setText("输入原句中的正确词形"); self.repeat_progress.hide()
        else: self.prompt.setText(f"{self.entry.display_word}\n{c.source_sentence if c else ''}"); self.progress.setText("先回忆中文意思，再点击显示"); self.repeat_progress.hide()

    def _reset_round(self):
        self.typed=""; self.errors=0; self.started=None; self.input.clear(); self.input.setEnabled(self.mode!="meaning_recall")
        self.input_panel.setVisible(self.mode!="meaning_recall"); self.reveal.setVisible(self.mode=="meaning_recall"); [b.hide() for b in self.rating_buttons]; self._update_prompt(); QTimer.singleShot(0,self.input.setFocus)

    def _key(self,event:QKeyEvent):
        if event.key()==Qt.Key.Key_Backspace:
            if self.typed:self.typed=self.typed[:-1]; self._render(); self.learning_activity.emit("typing_activity")
            return
        text="\n" if event.key() in (Qt.Key.Key_Return,Qt.Key.Key_Enter) else event.text()
        if not text or len(text)!=1:return
        self.learning_activity.emit("typing_activity")
        if self.started is None:self.started=monotonic()
        self.typed+=text; expected=self._expected()
        if len(self.typed)<=len(expected) and self.typed[-1]!=expected[len(self.typed)-1]:self.errors+=1
        self._render()
        if len(self.typed)>=len(expected): self._finish(expected)

    def _render(self):
        cursor=QTextCursor(self.input.document()); expected=self._expected(); existing=self.input.toPlainText()
        if self.typed==existing[:-1]:
            cursor.movePosition(QTextCursor.MoveOperation.End); cursor.deletePreviousChar()
        elif self.typed.startswith(existing) and len(self.typed)==len(existing)+1:
            index=len(existing); cursor.movePosition(QTextCursor.MoveOperation.End); cursor.insertText(self.typed[-1],self._character_format(index,expected))
        elif self.typed!=existing:
            self.input.clear(); cursor=QTextCursor(self.input.document())
            for i,ch in enumerate(self.typed):cursor.insertText(ch,self._character_format(i,expected))
        cursor.movePosition(QTextCursor.MoveOperation.End); self.input.setTextCursor(cursor); self.input.ensureCursorVisible()

    def _character_format(self,index:int,expected:str) -> QTextCharFormat:
        fmt=QTextCharFormat()
        if index>=len(expected) or self.typed[index]!=expected[index]:fmt.setForeground(QColor("#c74444"));fmt.setBackground(QColor("#fee2e2"))
        return fmt

    def _expected(self) -> str:
        return self.current_target_word

    def _finish(self,expected):
        correct=self.typed==expected; duration=int(((monotonic()-(self.started or monotonic())))*1000); accuracy=max(0,(len(expected)-self.errors)/max(len(expected),1)*100)
        self.queue_correct+=int(correct); self.queue_errors+=self.errors
        self.attempt_completed.emit(VocabularyAttempt(self.entry.id,self.mode,expected,self.typed,correct,accuracy,duration,vocabulary_context_id=self.current_context.id if self.current_context else None))
        if self.mode=="typing" and correct:
            self.repeat_index+=1
            if self.state and self.repeat_index>=self.state.typing_target_count:
                self.progress.setText(f"已完成 {self.state.typing_target_count} 次单词打字"); self.repeat_progress.setValue(self.state.typing_target_count); self.input.setEnabled(False); self.completed_words+=1; QTimer.singleShot(450,self.next_word); return
        elif self.mode=="sentence_cloze" and correct:
            self.completed_words+=1; QTimer.singleShot(450,self.next_word); return
        QTimer.singleShot(250,self._reset_round)

    def _reveal(self):
        self.learning_activity.emit("meaning_revealed")
        self.meaning.setText(self.current_context.contextual_meaning_zh or "暂无中文讲解"); self.reveal.hide(); [b.show() for b in self.rating_buttons]

    def _rate(self,rating):
        self.learning_activity.emit("self_rated")
        self.attempt_completed.emit(VocabularyAttempt(self.entry.id,"meaning_recall",self.current_context.contextual_meaning_zh if self.current_context else "","",None,0,0,rating,self.current_context.id if self.current_context else None)); self.completed_words+=1; QTimer.singleShot(450,self.next_word)

    def previous_word(self):
        self.learning_activity.emit("next_item")
        if self.queue_index>0:self._save_incomplete(); self.queue_index-=1; self._load_current()

    def skip_word(self):
        if not self.queue:return
        self.skipped_words+=1; self.next_word()

    def next_word(self):
        self.learning_activity.emit("next_item")
        if self.queue_index+1<len(self.queue):self.queue_index+=1; self._load_current()
        else:self._show_results()

    def _manual_next(self):
        self._save_incomplete(); self.next_word()

    def _save_incomplete(self):
        if self.entry and self.typed:
            self.attempt_completed.emit(VocabularyAttempt(self.entry.id,self.mode,self._expected(),self.typed,None,0,int((monotonic()-(self.started or monotonic()))*1000),vocabulary_context_id=self.current_context.id if self.current_context else None))

    def _show_results(self):
        total=len(self.queue); elapsed=int(monotonic()-self.queue_started) if self.queue_started else 0
        self.entry=None; self.input.clear(); self.input.setEnabled(False); self.input_panel.hide(); self.reveal.hide(); self.repeat_progress.hide(); [b.hide() for b in self.rating_buttons]
        self.queue_progress.setRange(0,max(1,total)); self.queue_progress.setValue(total)
        self.prompt.setText("本轮学习完成"); self.progress.setText(f"单词 {total} · 完成 {self.completed_words} · 跳过 {self.skipped_words} · 正确 {self.queue_correct} · 错误 {self.queue_errors} · 用时 {elapsed} 秒")
        self.word.setText("学习结果"); self.meaning.setText("可以返回单词本，或重新开始本轮队列。")
        self.retry_queue_button.show(); self.result_back_button.show(); result={"total":total,"completed":self.completed_words,"skipped":self.skipped_words,"correct":self.queue_correct,"errors":self.queue_errors,"elapsed_seconds":elapsed}; self.learning_activity.emit("word_queue_completed"); self.queue_finished.emit(result)

    def retry_queue(self):
        if self.queue:self.load_queue(self.queue)
