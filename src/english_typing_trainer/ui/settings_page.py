from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.models.settings import AppSettings


class SettingsPage(QWidget):
    def __init__(self, data_dir: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(24)

        title = QLabel("设置")
        title.setProperty("role", "page-title")
        subtitle = QLabel("调整练习规则、界面外观和本地数据相关选项。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        content_row = QHBoxLayout()
        content_row.addStretch(1)
        content = QWidget()
        content.setMaximumWidth(960)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(16)

        practice_card = self._build_practice_card()
        appearance_card = self._build_appearance_card()
        translation_card = self._build_translation_card()
        speech_card = self._build_speech_card()
        pronunciation_card = self._build_pronunciation_card()
        vocabulary_card = self._build_vocabulary_card()
        daily_learning_card = self._build_daily_learning_card()
        data_card = self._build_data_card(data_dir)
        content_layout.addWidget(practice_card)
        content_layout.addWidget(appearance_card)
        content_layout.addWidget(translation_card)
        content_layout.addWidget(speech_card)
        content_layout.addWidget(pronunciation_card)
        content_layout.addWidget(vocabulary_card)
        content_layout.addWidget(daily_learning_card)
        content_layout.addWidget(data_card)

        footer = QHBoxLayout()
        self.status_label = QLabel("所有设置均已保存。")
        self.status_label.setProperty("role", "subtitle")
        self.save_button = QPushButton("保存设置")
        self.save_button.setProperty("variant", "primary")
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        footer.addWidget(self.save_button)
        content_layout.addLayout(footer)

        content_row.addWidget(content, stretch=1)
        content_row.addStretch(1)
        scroll_host = QWidget()
        scroll_host.setLayout(content_row)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(scroll_host)
        self.scroll_area = scroll
        layout.addWidget(scroll, stretch=1)

        self.section_target_combo.currentIndexChanged.connect(self._mark_dirty)
        self.case_sensitive_checkbox.toggled.connect(self._mark_dirty)
        self.live_stats_checkbox.toggled.connect(self._mark_dirty)
        self.target_wpm_spin.valueChanged.connect(self._mark_dirty)
        self.target_accuracy_spin.valueChanged.connect(self._mark_dirty)
        self.theme_combo.currentIndexChanged.connect(self._mark_dirty)
        self.font_size_spin.valueChanged.connect(self._mark_dirty)
        self.show_translation_checkbox.toggled.connect(self._mark_dirty)
        self.idle_pause_combo.currentIndexChanged.connect(self._mark_dirty)
        self.translation_auto_checkbox.toggled.connect(self._mark_dirty)
        self.translation_model_combo.currentIndexChanged.connect(self._mark_dirty)
        self.tts_model_combo.currentIndexChanged.connect(self._mark_dirty)
        self.tts_voice_combo.currentIndexChanged.connect(self._mark_dirty)
        self.tts_speed_combo.currentIndexChanged.connect(self._mark_dirty)
        self.pronunciation_region_input.textChanged.connect(self._mark_dirty)
        self.pronunciation_keep_checkbox.toggled.connect(self._mark_dirty)
        self.vocabulary_typing_combo.currentIndexChanged.connect(self._mark_dirty)
        self.vocabulary_auto_checkbox.toggled.connect(self._mark_dirty)
        self.daily_goal_combo.currentIndexChanged.connect(self._mark_dirty)
        self.learning_idle_combo.currentIndexChanged.connect(self._mark_dirty)
        self.checkin_animation_checkbox.toggled.connect(self._mark_dirty)
        self.health_reminders_checkbox.toggled.connect(self._mark_dirty)
        self.reduce_motion_checkbox.toggled.connect(self._mark_dirty)
        self.fsrs_retention_combo.currentIndexChanged.connect(self._mark_dirty)
        self.fsrs_new_cards_combo.currentIndexChanged.connect(self._mark_dirty)
        self._sentence_learning_enabled = True

    def _build_practice_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("练习")
        title.setProperty("role", "page-title")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.section_target_combo = QComboBox()
        for value in (300, 500, 800, 1000):
            self.section_target_combo.addItem(str(value), value)
        self.case_sensitive_checkbox = QCheckBox("区分大小写")
        self.live_stats_checkbox = QCheckBox("显示实时统计")
        self.target_wpm_spin = QSpinBox()
        self.target_wpm_spin.setRange(10, 300)
        self.target_accuracy_spin = QDoubleSpinBox()
        self.target_accuracy_spin.setRange(50.0, 100.0)
        self.target_accuracy_spin.setDecimals(1)
        self.target_accuracy_spin.setSingleStep(0.5)
        form.addRow("默认分段字数", self.section_target_combo)
        form.addRow("输入规则", self.case_sensitive_checkbox)
        form.addRow("实时统计", self.live_stats_checkbox)
        form.addRow("目标 WPM", self.target_wpm_spin)
        form.addRow("目标正确率", self.target_accuracy_spin)
        self.show_translation_checkbox = QCheckBox("完成句子后显示翻译")
        self.idle_pause_combo = QComboBox()
        for label, value in (("关闭", 0), ("2 秒", 2), ("3 秒", 3), ("5 秒", 5), ("10 秒", 10)):
            self.idle_pause_combo.addItem(label, value)
        form.addRow("句后翻译", self.show_translation_checkbox)
        form.addRow("无输入自动暂停", self.idle_pause_combo)
        layout.addLayout(form)
        return card

    def _build_appearance_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("外观")
        title.setProperty("role", "page-title")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)

        form = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.addItem("跟随系统", "system")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 36)
        form.addRow("主题", self.theme_combo)
        form.addRow("字体大小", self.font_size_spin)
        layout.addLayout(form)
        return card

    def _build_translation_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("翻译服务")
        title.setProperty("role", "page-title")
        title.setStyleSheet("font-size: 18px;")
        layout.addWidget(title)
        form = QFormLayout()
        provider = QLabel("DeepSeek")
        self.translation_model_combo = QComboBox()
        self.translation_model_combo.addItem("DeepSeek V4 Flash", "deepseek-v4-flash")
        self.translation_model_combo.addItem("DeepSeek V4 Pro", "deepseek-v4-pro")
        self.translation_auto_checkbox = QCheckBox("按需自动翻译当前句")
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("输入 API Key（不会保存到数据库）")
        self.api_key_status = QLabel("凭据状态：尚未读取")
        self.api_key_status.setProperty("role", "muted")
        form.addRow("服务商", provider)
        form.addRow("模型", self.translation_model_combo)
        form.addRow("自动翻译", self.translation_auto_checkbox)
        form.addRow("API Key", self.api_key_input)
        layout.addLayout(form)
        layout.addWidget(self.api_key_status)
        actions = QHBoxLayout()
        self.save_api_key_button = QPushButton("保存 Key")
        self.delete_api_key_button = QPushButton("删除 Key")
        self.test_api_button = QPushButton("测试连接")
        actions.addWidget(self.save_api_key_button)
        actions.addWidget(self.delete_api_key_button)
        actions.addWidget(self.test_api_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        return card

    def set_api_key_status(self, masked_value: str) -> None:
        self.api_key_status.setText(f"凭据状态：{masked_value}")

    def _build_speech_card(self) -> QFrame:
        card = QFrame(); card.setObjectName("Card")
        layout = QVBoxLayout(card); layout.setContentsMargins(20,20,20,20); layout.setSpacing(12)
        title = QLabel("语音服务"); title.setProperty("role","page-title"); title.setStyleSheet("font-size: 18px;"); layout.addWidget(title)
        form = QFormLayout()
        form.addRow("服务商", QLabel("MiniMax"))
        self.tts_model_combo = QComboBox()
        self.tts_model_combo.addItem("Speech-2.8-HD", "speech-2.8-hd")
        self.tts_model_combo.addItem("Speech-2.8-Turbo", "speech-2.8-turbo")
        self.tts_voice_combo = QComboBox()
        for label, value in (("英语 · 表现力旁白","English_expressive_narrator"),("英语 · 磁性男声","English_magnetic_voiced_man"),("英语 · 明亮女声","English_radiant_girl")):
            self.tts_voice_combo.addItem(label, value)
        self.tts_speed_combo = QComboBox()
        for label,value in (("0.8×",0.8),("1.0×",1.0),("1.2×",1.2)): self.tts_speed_combo.addItem(label,value)
        self.tts_api_key_input = QLineEdit(); self.tts_api_key_input.setEchoMode(QLineEdit.EchoMode.Password); self.tts_api_key_input.setPlaceholderText("输入 MiniMax API Key（不会写入数据库）")
        form.addRow("模型", self.tts_model_combo); form.addRow("音色",self.tts_voice_combo); form.addRow("默认语速",self.tts_speed_combo); form.addRow("API Key",self.tts_api_key_input)
        layout.addLayout(form)
        self.tts_api_key_status=QLabel("凭据状态：尚未读取"); self.tts_api_key_status.setProperty("role","muted"); layout.addWidget(self.tts_api_key_status)
        actions=QHBoxLayout(); self.save_tts_key_button=QPushButton("保存 Key"); self.delete_tts_key_button=QPushButton("删除 Key"); self.test_tts_button=QPushButton("测试连接")
        actions.addWidget(self.save_tts_key_button); actions.addWidget(self.delete_tts_key_button); actions.addWidget(self.test_tts_button); actions.addStretch(1); layout.addLayout(actions)
        self.tts_cache_label=QLabel("语音缓存：0 个文件 · 0 B"); self.tts_cache_label.setProperty("role","subtitle")
        self.clear_tts_cache_button=QPushButton("清理缓存")
        cache_row=QHBoxLayout(); cache_row.addWidget(self.tts_cache_label); cache_row.addStretch(1); cache_row.addWidget(self.clear_tts_cache_button); layout.addLayout(cache_row)
        cost=QLabel("音频生成由 MiniMax 按字符计费；已缓存音频重复播放不会再次收费。"); cost.setWordWrap(True); cost.setProperty("role","muted"); layout.addWidget(cost)
        return card

    def set_tts_api_key_status(self, masked_value: str) -> None:
        self.tts_api_key_status.setText(f"凭据状态：{masked_value}")

    def set_tts_cache_stats(self, file_count: int, size_bytes: int) -> None:
        size = f"{size_bytes / (1024*1024):.1f} MB" if size_bytes >= 1024*1024 else f"{size_bytes / 1024:.1f} KB" if size_bytes >= 1024 else f"{size_bytes} B"
        self.tts_cache_label.setText(f"语音缓存：{file_count} 个文件 · {size}")

    def _build_pronunciation_card(self) -> QFrame:
        card=QFrame(); card.setObjectName("Card")
        layout=QVBoxLayout(card); layout.setContentsMargins(20,20,20,20); layout.setSpacing(10)
        title=QLabel("跟读评分 Beta"); title.setProperty("role","page-title"); title.setStyleSheet("font-size: 18px;"); layout.addWidget(title)
        notice=QLabel("录音会在用户点击评分时发送至 Azure Speech。未配置时仍可录音、回放并对照标准发音，不会显示模拟分数。")
        notice.setWordWrap(True); notice.setProperty("role","muted"); layout.addWidget(notice)
        form=QFormLayout(); self.pronunciation_region_input=QLineEdit(); self.pronunciation_region_input.setPlaceholderText("例如 eastus")
        self.pronunciation_key_input=QLineEdit(); self.pronunciation_key_input.setEchoMode(QLineEdit.EchoMode.Password); self.pronunciation_key_input.setPlaceholderText("Azure Speech Key（不会写入数据库）")
        self.pronunciation_keep_checkbox=QCheckBox("保留评分后的本地录音")
        form.addRow("服务商",QLabel("Azure Speech（可选 Beta）")); form.addRow("区域",self.pronunciation_region_input); form.addRow("Speech Key",self.pronunciation_key_input); form.addRow("录音保存",self.pronunciation_keep_checkbox); layout.addLayout(form)
        self.pronunciation_key_status=QLabel("凭据状态：尚未读取"); self.pronunciation_key_status.setProperty("role","muted"); layout.addWidget(self.pronunciation_key_status)
        actions=QHBoxLayout(); self.save_pronunciation_key_button=QPushButton("保存 Key"); self.delete_pronunciation_key_button=QPushButton("删除 Key"); actions.addWidget(self.save_pronunciation_key_button); actions.addWidget(self.delete_pronunciation_key_button); actions.addStretch(1); layout.addLayout(actions)
        return card

    def set_pronunciation_key_status(self, masked_value: str) -> None:
        self.pronunciation_key_status.setText(f"凭据状态：{masked_value}")

    def _build_vocabulary_card(self) -> QFrame:
        card=QFrame(); card.setObjectName("Card"); layout=QVBoxLayout(card); layout.setContentsMargins(20,20,20,20)
        title=QLabel("单词学习"); title.setProperty("role","page-title"); title.setStyleSheet("font-size: 18px;"); layout.addWidget(title)
        form=QFormLayout(); self.vocabulary_typing_combo=QComboBox()
        for value in (3,5,10): self.vocabulary_typing_combo.addItem(f"{value} 次",value)
        self.vocabulary_auto_checkbox=QCheckBox("收藏后自动获取词典和中文讲解")
        self.vocabulary_audio_label=QLabel("优先词典音频，无音频时使用 MiniMax")
        form.addRow("每个单词打字次数",self.vocabulary_typing_combo); form.addRow("自动获取讲解",self.vocabulary_auto_checkbox); form.addRow("发音优先级",self.vocabulary_audio_label)
        layout.addLayout(form); return card

    def _build_daily_learning_card(self) -> QFrame:
        card=QFrame(); card.setObjectName("Card")
        layout=QVBoxLayout(card); layout.setContentsMargins(20,20,20,20)
        title=QLabel("每日学习"); title.setProperty("role","page-title"); title.setStyleSheet("font-size: 18px;"); layout.addWidget(title)
        form=QFormLayout(); self.daily_goal_combo=QComboBox()
        for value in (15,30,45,60):self.daily_goal_combo.addItem(f"{value} 分钟",value)
        self.learning_idle_combo=QComboBox()
        for value in (60,90,120):self.learning_idle_combo.addItem(f"{value} 秒",value)
        self.checkin_animation_checkbox=QCheckBox("达到目标时播放轻量动画")
        self.health_reminders_checkbox=QCheckBox("显示 120 / 180 / 240 分钟健康提醒")
        self.reduce_motion_checkbox=QCheckBox("减少动画")
        form.addRow("每日目标",self.daily_goal_combo); form.addRow("空闲截止",self.learning_idle_combo)
        form.addRow("打卡动画",self.checkin_animation_checkbox); form.addRow("健康提醒",self.health_reminders_checkbox); form.addRow("辅助选项",self.reduce_motion_checkbox)
        self.fsrs_retention_combo=QComboBox()
        for label,value in (("85%",0.85),("90%（推荐）",0.90),("93%",0.93)): self.fsrs_retention_combo.addItem(label,value)
        self.fsrs_new_cards_combo=QComboBox()
        for value in (10,20,30): self.fsrs_new_cards_combo.addItem(f"{value} 个",value)
        form.addRow("FSRS 期望保持率",self.fsrs_retention_combo); form.addRow("每日新词上限",self.fsrs_new_cards_combo)
        layout.addLayout(form); return card
    def _build_data_card(self, data_dir: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 20, 20, 20)
        title = QLabel("数据")
        title.setProperty("role", "page-title")
        title.setStyleSheet("font-size: 18px;")
        self.data_dir_label = QLabel(data_dir)
        self.data_dir_label.setWordWrap(True)
        self.data_dir_label.setProperty("role", "subtitle")
        self.open_data_dir_button = QPushButton("打开数据目录")
        self.backup_database_button = QPushButton("备份数据库")
        self.restore_database_button = QPushButton("恢复数据库")
        self.export_diagnostics_button = QPushButton("导出诊断日志")
        self.about_button = QPushButton("关于 English Studio")
        self.backup_hint = QLabel("备份、恢复和诊断文件均不会包含 Windows 凭据管理器中的 API Key。")
        self.backup_hint.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(self.data_dir_label)
        actions = QHBoxLayout()
        actions.addWidget(self.open_data_dir_button)
        actions.addWidget(self.backup_database_button)
        actions.addWidget(self.restore_database_button)
        actions.addWidget(self.export_diagnostics_button)
        actions.addStretch(1)
        layout.addLayout(actions)
        layout.addWidget(self.backup_hint)
        layout.addWidget(self.about_button, alignment=Qt.AlignmentFlag.AlignLeft)
        return card

    def load_settings(self, settings: AppSettings) -> None:
        index = self.section_target_combo.findData(settings.section_target_characters)
        if index >= 0:
            self.section_target_combo.setCurrentIndex(index)
        self.case_sensitive_checkbox.setChecked(settings.case_sensitive)
        self.live_stats_checkbox.setChecked(settings.show_live_stats)
        self.target_wpm_spin.setValue(settings.target_wpm)
        self.target_accuracy_spin.setValue(settings.target_accuracy)
        self.font_size_spin.setValue(settings.font_size)
        theme_index = self.theme_combo.findData(settings.theme)
        self.theme_combo.setCurrentIndex(theme_index if theme_index >= 0 else 0)
        self._sentence_learning_enabled = settings.sentence_learning_enabled
        self.show_translation_checkbox.setChecked(settings.show_translation_after_sentence)
        idle_index = self.idle_pause_combo.findData(settings.idle_pause_seconds)
        self.idle_pause_combo.setCurrentIndex(idle_index if idle_index >= 0 else 2)
        self.translation_auto_checkbox.setChecked(settings.translation_auto_on_demand)
        model_index = self.translation_model_combo.findData(settings.translation_model)
        self.translation_model_combo.setCurrentIndex(model_index if model_index >= 0 else 0)
        for combo, value, fallback in ((self.tts_model_combo,settings.tts_model,0),(self.tts_voice_combo,settings.tts_voice_id,0),(self.tts_speed_combo,settings.tts_speed,1)):
            index=combo.findData(value); combo.setCurrentIndex(index if index >= 0 else fallback)
        index=self.vocabulary_typing_combo.findData(settings.vocabulary_typing_count); self.vocabulary_typing_combo.setCurrentIndex(index if index>=0 else 1)
        self.vocabulary_auto_checkbox.setChecked(settings.vocabulary_auto_enrich)
        for combo,value,fallback in ((self.daily_goal_combo,settings.daily_learning_goal_minutes,0),(self.learning_idle_combo,settings.learning_idle_timeout_seconds,1)):
            index=combo.findData(value); combo.setCurrentIndex(index if index>=0 else fallback)
        self.checkin_animation_checkbox.setChecked(settings.checkin_animation_enabled)
        self.health_reminders_checkbox.setChecked(settings.health_reminders_enabled)
        self.reduce_motion_checkbox.setChecked(settings.reduce_motion)
        for combo,value in ((self.fsrs_retention_combo,settings.fsrs_desired_retention),(self.fsrs_new_cards_combo,settings.fsrs_new_cards_per_day)):
            index=combo.findData(value); combo.setCurrentIndex(index if index>=0 else 0)
        self.status_label.setText("所有设置均已保存。")
        self.pronunciation_region_input.setText(settings.pronunciation_region)
        self.pronunciation_keep_checkbox.setChecked(settings.pronunciation_keep_recordings)

    def build_settings(self) -> AppSettings:
        return AppSettings(
            section_target_characters=int(self.section_target_combo.currentData()),
            case_sensitive=self.case_sensitive_checkbox.isChecked(),
            show_live_stats=self.live_stats_checkbox.isChecked(),
            target_wpm=self.target_wpm_spin.value(),
            target_accuracy=self.target_accuracy_spin.value(),
            theme=str(self.theme_combo.currentData()),
            font_size=self.font_size_spin.value(),
            sentence_learning_enabled=self._sentence_learning_enabled,
            show_translation_after_sentence=self.show_translation_checkbox.isChecked(),
            idle_pause_seconds=int(self.idle_pause_combo.currentData()),
            translation_auto_on_demand=self.translation_auto_checkbox.isChecked(),
            translation_provider="deepseek",
            translation_model=str(self.translation_model_combo.currentData()),
            translation_prompt_version="sentence-v1",
            tts_provider="minimax",
            tts_model=str(self.tts_model_combo.currentData()),
            tts_voice_id=str(self.tts_voice_combo.currentData()),
            tts_speed=float(self.tts_speed_combo.currentData()),
            tts_auto_play=False,
            vocabulary_typing_count=int(self.vocabulary_typing_combo.currentData()),
            vocabulary_auto_enrich=self.vocabulary_auto_checkbox.isChecked(),
            vocabulary_audio_preference="dictionary",
            daily_learning_goal_minutes=int(self.daily_goal_combo.currentData()),
            learning_idle_timeout_seconds=int(self.learning_idle_combo.currentData()),
            checkin_animation_enabled=self.checkin_animation_checkbox.isChecked(),
            health_reminders_enabled=self.health_reminders_checkbox.isChecked(),
            reduce_motion=self.reduce_motion_checkbox.isChecked(),
            fsrs_desired_retention=float(self.fsrs_retention_combo.currentData()),
            fsrs_new_cards_per_day=int(self.fsrs_new_cards_combo.currentData()),
            fsrs_review_soft_limit=100,
            pronunciation_provider="azure",
            pronunciation_region=self.pronunciation_region_input.text().strip(),
            pronunciation_locale="en-US",
            pronunciation_keep_recordings=self.pronunciation_keep_checkbox.isChecked(),
        )

    def _mark_dirty(self, *_args) -> None:
        self.status_label.setText("设置已修改，尚未保存。")
