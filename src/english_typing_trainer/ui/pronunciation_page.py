from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from english_typing_trainer.models.pronunciation import PronunciationAttempt, PronunciationResult
from english_typing_trainer.models.learning_content import CourseCapabilityItem
from english_typing_trainer.models.vocabulary import VocabularyContext, VocabularyEntry


class PronunciationPage(QWidget):
    back_requested=Signal(); standard_audio_requested=Signal(str,float); record_requested=Signal(); stop_requested=Signal(); cancel_requested=Signal(); playback_requested=Signal(object); assess_requested=Signal(str,object,bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent); self.entry=None; self.context=None; self.course_item:CourseCapabilityItem|None=None; self.audio_path:Path|None=None; self._build()

    def _build(self) -> None:
        root=QVBoxLayout(self); root.setContentsMargins(32,24,32,24); root.setSpacing(16)
        top=QHBoxLayout(); self.back_button=QPushButton("返回单词本"); self.back_button.setProperty("variant","ghost"); self.back_button.clicked.connect(self.back_requested.emit); self.title=QLabel("跟读评分 Beta"); self.title.setProperty("role","page-title"); top.addWidget(self.back_button); top.addWidget(self.title,1); root.addLayout(top)
        card=QFrame(); card.setObjectName("Card"); layout=QVBoxLayout(card); layout.setContentsMargins(32,28,32,28); layout.setSpacing(16)
        notice=QLabel("Beta：评分需配置 Azure Speech。未配置时可以录音、回放和对照标准发音，绝不会显示模拟分数。"); notice.setWordWrap(True); notice.setProperty("role","subtitle"); layout.addWidget(notice)
        controls=QHBoxLayout(); self.target_type=QComboBox(); self.target_type.addItem("单词跟读","word"); self.target_type.addItem("句子跟读","sentence"); self.speed=QComboBox(); [self.speed.addItem(f"{value:.1f}×",value) for value in (0.8,1.0,1.2)]
        self.standard_button=QPushButton("听标准发音"); self.standard_button.clicked.connect(lambda:self.standard_audio_requested.emit(self.reference_text(),float(self.speed.currentData())))
        controls.addWidget(QLabel("练习类型")); controls.addWidget(self.target_type); controls.addWidget(self.speed); controls.addStretch(1); controls.addWidget(self.standard_button); layout.addLayout(controls)
        self.reference=QLabel(""); self.reference.setAlignment(Qt.AlignmentFlag.AlignCenter); self.reference.setWordWrap(True); self.reference.setStyleSheet("font-size: 26px; font-weight: 600;"); layout.addWidget(self.reference)
        recordings=QHBoxLayout(); self.record_button=QPushButton("开始跟读"); self.stop_button=QPushButton("停止录音"); self.cancel_button=QPushButton("取消录音"); self.playback_button=QPushButton("播放我的录音"); self.assess_button=QPushButton("开始评分"); self.assess_button.setProperty("variant","primary")
        self.record_button.clicked.connect(self.record_requested.emit); self.stop_button.clicked.connect(self.stop_requested.emit); self.cancel_button.clicked.connect(self.cancel_requested.emit); self.playback_button.clicked.connect(lambda:self.playback_requested.emit(self.audio_path)); self.assess_button.clicked.connect(lambda:self.assess_requested.emit(str(self.target_type.currentData()),self.audio_path,False))
        for button in (self.record_button,self.stop_button,self.cancel_button,self.playback_button,self.assess_button): recordings.addWidget(button)
        layout.addLayout(recordings)
        self.status=QLabel("准备开始跟读。"); self.status.setProperty("role","subtitle"); self.status.setWordWrap(True); layout.addWidget(self.status)
        self.scores=QLabel("完成 Azure 评分后将在这里显示准确度、流利度、完整度和韵律反馈。"); self.scores.setWordWrap(True); self.scores.setProperty("role","muted"); layout.addWidget(self.scores)
        self.feedback=QLabel(""); self.feedback.setWordWrap(True); layout.addWidget(self.feedback); layout.addStretch(1); root.addWidget(card,1)
        self.target_type.currentIndexChanged.connect(self._refresh_reference); self._set_recording_state("idle")

    def load_target(self, entry: VocabularyEntry, context: VocabularyContext | None) -> None:
        self.course_item=None; self.entry=entry; self.context=context; self.audio_path=None; self.back_button.setText("返回单词本"); self.target_type.setEnabled(True); self.status.setText("准备开始跟读。"); self.scores.setText("完成 Azure 评分后将在这里显示准确度、流利度、完整度和韵律反馈。"); self.feedback.clear(); self._refresh_reference()
        self._set_recording_state("idle")

    def load_course_target(self, item: CourseCapabilityItem) -> None:
        self.course_item=item; self.entry=None; self.context=None; self.audio_path=None
        self.back_button.setText("返回 Day"); self.target_type.setCurrentIndex(self.target_type.findData("sentence")); self.target_type.setEnabled(False)
        self.status.setText("准备开始课程跟读。评分历史只关联课程 stable key。")
        self.scores.setText("完成 Azure 评分后将在这里显示各项分数。"); self.feedback.clear(); self._refresh_reference(); self._set_recording_state("idle")

    def reference_text(self) -> str:
        if self.course_item is not None:return self.course_item.text
        if self.target_type.currentData()=="sentence" and self.context and self.context.source_sentence:return self.context.source_sentence
        return self.context.source_word if self.context and self.context.source_word else (self.entry.display_word if self.entry else "")

    def _refresh_reference(self) -> None:
        self.reference.setText(self.reference_text())

    def set_recorded(self, path: Path | None) -> None:
        self.audio_path=path; self.status.setText("录音已完成，可回放或开始评分。" if path else "未生成可用录音。"); self._set_recording_state("recorded" if path else "idle")

    def set_recording_state(self, state:str) -> None:
        self._set_recording_state(state)

    def _set_recording_state(self,state:str)->None:
        active=state=="recording"; recorded=state=="recorded"
        self.record_button.setEnabled(not active); self.stop_button.setEnabled(active); self.cancel_button.setEnabled(active); self.playback_button.setEnabled(recorded); self.assess_button.setEnabled(recorded)

    def show_attempt(self, attempt: PronunciationAttempt) -> None:
        if attempt.status=="not_configured": self.status.setText("跟读评分目前为 Beta，需要在设置中配置 Azure Speech 才能启用云端发音评分。未配置时仍可录音、回放并对照标准发音练习。"); self.scores.setText("未配置 Azure Speech，未生成评分。\n录音不会因未评分而保留，除非设置中启用“保留本地录音”。"); return
        if attempt.status!="completed": self.status.setText("评分未完成："+(attempt.error_code or "网络或服务暂时不可用。")); self.scores.setText("未显示评分结果，请检查 Azure 配置或稍后重试。 "); return
        self.status.setText("评分完成。分数仅用于帮助发现可练习的部分，不代表语言能力结论。")
        self.scores.setText(f"总分 {attempt.overall_score:.1f} · 准确度 {attempt.accuracy_score:.1f} · 流利度 {attempt.fluency_score:.1f} · 完整度 {attempt.completeness_score:.1f}" + (f" · 韵律 {attempt.prosody_score:.1f}" if attempt.prosody_score is not None else ""))

    def show_result(self, result: PronunciationResult) -> None:
        if result.status=="not_configured": self.status.setText("跟读评分目前为 Beta，需要在设置中配置 Azure Speech。未配置时仍可录音、回放并对照标准发音。"); self.scores.setText("未配置 Azure Speech，未生成评分。"); return
        if result.status!="completed": self.status.setText("评分未完成："+(result.error_code or "网络或服务暂时不可用。")); self.scores.setText("未显示评分结果，请检查 Azure 配置或稍后重试。"); return
        self.status.setText("评分完成。本次课程跟读活动已完成，不设置最低分门槛。")
        self.scores.setText(f"总分 {result.overall_score:.1f} · 准确度 {result.accuracy_score:.1f} · 流利度 {result.fluency_score:.1f} · 完整度 {result.completeness_score:.1f}" + (f" · 韵律 {result.prosody_score:.1f}" if result.prosody_score is not None else ""))
