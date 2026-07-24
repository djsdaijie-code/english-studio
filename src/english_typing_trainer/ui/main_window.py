from __future__ import annotations

from collections import Counter
from datetime import datetime
from dataclasses import replace
from pathlib import Path
import logging
import re

from PySide6.QtCore import QEvent, Qt, QTimer, QUrl, QThreadPool
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QProgressDialog,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
    QComboBox,
    QDialog,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from english_typing_trainer.application.context import AppContext
from english_typing_trainer import __version__
from english_typing_trainer.models.article import Article
from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.services.credential_store import mask_api_key, mask_secret
from english_typing_trainer.database.sentence_repositories import SentenceAttemptRepository
from english_typing_trainer.services.translation_provider import DeepSeekTranslationProvider, TranslationProviderError
from english_typing_trainer.models.tts import TTSRequest
from english_typing_trainer.services.audio_playback import AudioPlaybackService
from english_typing_trainer.services.tts_provider import MiniMaxTTSProvider, TTSProviderError
from english_typing_trainer.ui.history_page import HistoryPage
from english_typing_trainer.ui.practice_view import PracticeView
from english_typing_trainer.ui.result_dialog import ResultDialog
from english_typing_trainer.ui.segmented_control import SegmentedControl
from english_typing_trainer.ui.session_detail_dialog import SessionDetailDialog
from english_typing_trainer.ui.sentence_practice_view import SentencePracticeView
from english_typing_trainer.ui.translation_tasks import TranslationWorker
from english_typing_trainer.ui.tts_tasks import TTSWorker
from english_typing_trainer.ui.settings_page import SettingsPage as SettingsScreen
from english_typing_trainer.ui.special_practice_page import SpecialPracticePage
from english_typing_trainer.ui.statistics_page import StatisticsPage
from english_typing_trainer.ui.theme import apply_theme
from english_typing_trainer.ui.vocabulary_page import VocabularyPage
from english_typing_trainer.ui.word_learning_page import WordLearningPage
from english_typing_trainer.ui.fsrs_review_page import FsrsReviewPage
from english_typing_trainer.ui.dictation_page import DictationPage
from english_typing_trainer.ui.pronunciation_page import PronunciationPage
from english_typing_trainer.ui.course_page import CoursePage
from english_typing_trainer.ui.course_vocabulary_dialog import CourseVocabularyDialog
from english_typing_trainer.ui.home_page import HomePage
from english_typing_trainer.ui.learning_content_page import LearningContentPage
from english_typing_trainer.ui.vocabulary_tasks import VocabularyTask
from english_typing_trainer.services.dictionary_provider import FreeDictionaryProvider
from english_typing_trainer.services.word_explanation_provider import DeepSeekWordExplanationProvider
from english_typing_trainer.models.vocabulary import VocabularyAttempt
from english_typing_trainer.models.pronunciation import PronunciationRequest
from english_typing_trainer.models.pronunciation import PronunciationResult
from english_typing_trainer.models.learning_content import (
    CourseCapabilityItem,
    LearningContentRef,
)
from english_typing_trainer.services.pronunciation_provider import AzurePronunciationAssessmentProvider
from english_typing_trainer.services.course_learning import CourseLearningSession
from english_typing_trainer.services.article_proofreading import (
    ArticleProofreadingError,
    DeepSeekArticleProofreadingProvider,
)
from english_typing_trainer.ui.article_proofreading_dialog import ArticleProofreadingDialog
from english_typing_trainer.ui.article_proofreading_tasks import ArticleProofreadingWorker


class MetricCard(QFrame):
    def __init__(self, title: str, value: str = "-", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "metric-title")
        self.value_label = QLabel(value)
        self.value_label.setProperty("role", "metric-value")
        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class EmptyStateCard(QFrame):
    def __init__(self, title: str, body: str, button_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EmptyCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(12)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "page-title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 24px;")
        self.body_label = QLabel(body)
        self.body_label.setWordWrap(True)
        self.body_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body_label.setProperty("role", "subtitle")
        self.action_button = QPushButton(button_text)
        self.action_button.setProperty("variant", "primary")
        self.action_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addStretch(1)
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addWidget(self.action_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch(1)


class SettingsPage(QWidget):
    def __init__(self, data_dir: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        title = QLabel("设置")
        title.setProperty("role", "page-title")
        subtitle = QLabel("在不影响历史数据的前提下，调整练习规则和界面外观。")
        subtitle.setProperty("role", "subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        practice_card = QFrame()
        practice_card.setObjectName("Card")
        practice_layout = QVBoxLayout(practice_card)
        practice_layout.setContentsMargins(16, 16, 16, 16)
        practice_title = QLabel("练习设置")
        practice_title.setProperty("role", "page-title")
        practice_title.setStyleSheet("font-size: 18px;")
        practice_layout.addWidget(practice_title)
        practice_form = QFormLayout()
        self.section_target_combo = QComboBox()
        for value in (300, 500, 800, 1000):
            self.section_target_combo.addItem(str(value), value)
        self.case_sensitive_checkbox = QCheckBox("区分大小写")
        self.live_stats_checkbox = QCheckBox("显示实时速度")
        self.target_wpm_spin = QSpinBox()
        self.target_wpm_spin.setRange(10, 300)
        self.target_accuracy_spin = QDoubleSpinBox()
        self.target_accuracy_spin.setRange(50.0, 100.0)
        self.target_accuracy_spin.setDecimals(1)
        self.target_accuracy_spin.setSingleStep(0.5)
        practice_form.addRow("默认分段字数", self.section_target_combo)
        practice_form.addRow("输入规则", self.case_sensitive_checkbox)
        practice_form.addRow("实时统计", self.live_stats_checkbox)
        practice_form.addRow("目标速度", self.target_wpm_spin)
        practice_form.addRow("目标正确率", self.target_accuracy_spin)
        practice_layout.addLayout(practice_form)
        layout.addWidget(practice_card)

        appearance_card = QFrame()
        appearance_card.setObjectName("Card")
        appearance_layout = QVBoxLayout(appearance_card)
        appearance_layout.setContentsMargins(16, 16, 16, 16)
        appearance_title = QLabel("外观")
        appearance_title.setProperty("role", "page-title")
        appearance_title.setStyleSheet("font-size: 18px;")
        appearance_layout.addWidget(appearance_title)
        appearance_form = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("浅色", "light")
        self.theme_combo.addItem("深色", "dark")
        self.theme_combo.addItem("跟随系统", "system")
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(12, 36)
        appearance_form.addRow("主题", self.theme_combo)
        appearance_form.addRow("字体大小", self.font_size_spin)
        appearance_layout.addLayout(appearance_form)
        layout.addWidget(appearance_card)

        data_card = QFrame()
        data_card.setObjectName("Card")
        data_layout = QVBoxLayout(data_card)
        data_layout.setContentsMargins(16, 16, 16, 16)
        data_title = QLabel("数据")
        data_title.setProperty("role", "page-title")
        data_title.setStyleSheet("font-size: 18px;")
        self.data_dir_label = QLabel(data_dir)
        self.data_dir_label.setWordWrap(True)
        self.data_dir_label.setProperty("role", "subtitle")
        self.open_data_dir_button = QPushButton("打开数据目录")
        self.backup_hint = QLabel("数据库备份入口将在后续阶段完善。")
        self.backup_hint.setProperty("role", "subtitle")
        data_layout.addWidget(data_title)
        data_layout.addWidget(self.data_dir_label)
        data_layout.addWidget(self.open_data_dir_button, alignment=Qt.AlignmentFlag.AlignLeft)
        data_layout.addWidget(self.backup_hint)
        layout.addWidget(data_card)

        footer = QHBoxLayout()
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "subtitle")
        self.save_button = QPushButton("保存设置")
        self.save_button.setProperty("variant", "primary")
        footer.addWidget(self.status_label)
        footer.addStretch(1)
        footer.addWidget(self.save_button)
        layout.addLayout(footer)

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
        self.status_label.setText("")

    def build_settings(self) -> AppSettings:
        return AppSettings(
            section_target_characters=int(self.section_target_combo.currentData()),
            case_sensitive=self.case_sensitive_checkbox.isChecked(),
            show_live_stats=self.live_stats_checkbox.isChecked(),
            target_wpm=self.target_wpm_spin.value(),
            target_accuracy=self.target_accuracy_spin.value(),
            theme=str(self.theme_combo.currentData()),
            font_size=self.font_size_spin.value(),
        )


class MainWindow(QMainWindow):
    PAGE_HOME = 0
    PAGE_LEARNING_CONTENT = 1
    PAGE_SPECIAL_PRACTICE = 2
    PAGE_VOCABULARY = 3
    PAGE_HISTORY = 4
    PAGE_STATISTICS = 5
    PAGE_SETTINGS = 6

    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.settings = self.context.settings_service.get_settings()
        self.articles: list[Article] = []
        self.current_material: PracticeMaterial | None = None
        self.current_course_session: CourseLearningSession | None = None
        self.current_course_capability_item: CourseCapabilityItem | None = None
        self.current_course_return: tuple[str, str] | None = None
        self.course_review_queue_active = False
        self.current_practice_saved = True
        self.preview_special_material: PracticeMaterial | None = None
        self._logger = logging.getLogger(__name__)

        self.setWindowTitle("English Studio")
        self.setMinimumSize(1280, 720)
        self.resize(1500, 1000)

        self.practice_view = PracticeView()
        self.practice_view.session_completed.connect(self._handle_session_completed)
        self.practice_view.back_requested.connect(self._leave_practice_view)
        self.practice_view.speech_requested.connect(self._request_speech)
        self.practice_view.speech_sentence_changed.connect(self._speech_sentence_changed)
        self.practice_view.word_collection_requested.connect(self._collect_selected_word)
        self.practice_view.learning_activity.connect(self._track_learning_activity)
        self.sentence_practice_view = SentencePracticeView()
        self.sentence_practice_view.session_completed.connect(self._handle_session_completed)
        self.sentence_practice_view.back_requested.connect(self._leave_practice_view)
        self.sentence_practice_view.attempt_completed.connect(self._save_sentence_attempt)
        self.sentence_practice_view.translation_requested.connect(self._request_sentence_translation)
        self.sentence_practice_view.edit_translation_requested.connect(self._edit_sentence_translation)
        self.sentence_practice_view.translate_article_requested.connect(self._translate_current_article)
        self.sentence_practice_view.speech_requested.connect(self._request_speech)
        self.sentence_practice_view.speech_sentence_changed.connect(self._speech_sentence_changed)
        self.sentence_practice_view.word_collection_requested.connect(self._collect_selected_word)
        self.sentence_practice_view.learning_activity.connect(self._track_learning_activity)
        self._sentence_attempts = SentenceAttemptRepository(self.context.database.connect)
        self._sentence_attempt_ids: list[int] = []
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(3)
        self._translation_workers: set[TranslationWorker] = set()
        self._proofreading_workers: set[ArticleProofreadingWorker] = set()
        self._proofreading_article_ids: set[int] = set()
        self._proofreading_missing_key_notified = False
        self._tts_workers: set[TTSWorker] = set()
        self._active_speech_control = None
        self._active_speech_text = ""
        self._active_speech_ref: LearningContentRef | None = None
        self._active_course_activity_ref: LearningContentRef | None = None
        self.audio_playback = AudioPlaybackService(self)
        self.audio_playback.state_changed.connect(self._speech_playback_state_changed)
        self.audio_playback.playback_failed.connect(self._speech_playback_failed)

        self.settings_page = SettingsScreen(str(self.context.paths.data_dir.resolve()))
        self.settings_page.save_button.clicked.connect(self._save_settings)
        self.settings_page.open_data_dir_button.clicked.connect(self._open_data_dir)
        self.settings_page.backup_database_button.clicked.connect(self._backup_database)
        self.settings_page.restore_database_button.clicked.connect(self._restore_database)
        self.settings_page.export_diagnostics_button.clicked.connect(self._export_diagnostics)
        self.settings_page.about_button.clicked.connect(self._show_about)
        self.settings_page.save_api_key_button.clicked.connect(self._save_api_key)
        self.settings_page.delete_api_key_button.clicked.connect(self._delete_api_key)
        self.settings_page.test_api_button.clicked.connect(self._test_api_connection)
        self.settings_page.save_tts_key_button.clicked.connect(self._save_tts_key)
        self.settings_page.delete_tts_key_button.clicked.connect(self._delete_tts_key)
        self.settings_page.test_tts_button.clicked.connect(self._test_tts_connection)
        self.settings_page.clear_tts_cache_button.clicked.connect(self._clear_tts_cache)
        self.settings_page.save_pronunciation_key_button.clicked.connect(self._save_pronunciation_key)
        self.settings_page.delete_pronunciation_key_button.clicked.connect(self._delete_pronunciation_key)
        self.history_page = HistoryPage()
        self.history_page.view_detail_requested.connect(self._show_session_detail)
        self.history_page.delete_session_requested.connect(self._delete_session)
        self.statistics_page = StatisticsPage()
        self.course_page = CoursePage(
            self.context.course_repository,
            self.context.course_progress_service,
        )
        self.course_page.lesson_start_requested.connect(self._start_course_lesson)
        self.course_page.capability_requested.connect(self._start_course_capability)
        self.course_page.due_review_requested.connect(self._start_course_due_review)
        self.special_practice_page = SpecialPracticePage()
        self.special_practice_page.generate_requested.connect(self._generate_special_preview)
        self.special_practice_page.start_preview_requested.connect(self._start_preview_special_practice)
        self.special_practice_page.start_saved_requested.connect(self._start_saved_special_practice)
        self.special_practice_page.refresh_requested.connect(self._refresh_special_practice_page)
        self.special_practice_page.start_today_review_requested.connect(self._start_fsrs_review)
        self.vocabulary_page = VocabularyPage()
        self.vocabulary_page.refresh_requested.connect(self._refresh_vocabulary_page)
        self.vocabulary_page.add_requested.connect(self._add_vocabulary_word)
        self.vocabulary_page.save_requested.connect(self._save_vocabulary_item)
        self.vocabulary_page.archive_requested.connect(self._set_vocabulary_archived)
        self.vocabulary_page.mastery_requested.connect(self._set_vocabulary_mastery)
        self.vocabulary_page.review_requested.connect(self._open_word_learning)
        self.vocabulary_page.open_learning_requested.connect(self._open_word_learning)
        self.vocabulary_page.play_requested.connect(self._play_vocabulary_word)
        self.vocabulary_page.pronunciation_requested.connect(self._start_pronunciation)
        self.vocabulary_page.delete_requested.connect(self._delete_vocabulary_entry)
        self.vocabulary_page.row_learning_requested.connect(self._start_vocabulary_row)
        self.vocabulary_page.scope_changed.connect(lambda _scope:self._refresh_vocabulary_page())
        self.vocabulary_page.today_review_requested.connect(self._start_fsrs_review)
        self.vocabulary_page.dictation_requested.connect(self._start_dictation)
        self.current_vocabulary_article_id = None
        self.word_learning_page = WordLearningPage()
        self.word_learning_page.back_requested.connect(self._leave_word_learning)
        self.word_learning_page.attempt_completed.connect(self._record_vocabulary_attempt)
        self.word_learning_page.play_word_requested.connect(self._play_word_from_learning)
        self.word_learning_page.play_sentence_requested.connect(lambda text:self._request_speech(text,self.settings.tts_speed,self.practice_view.speech_controls) if text else None)
        self.word_learning_page.current_entry_changed.connect(self._ensure_current_word_enrichment)
        self.word_learning_page.context_changed.connect(self._ensure_current_context_enrichment)
        self.word_learning_page.retry_enrichment_requested.connect(self._retry_current_word_enrichment)
        self.word_learning_page.learning_activity.connect(self._track_learning_activity)
        self.fsrs_review_page = FsrsReviewPage()
        self.fsrs_review_page.back_requested.connect(self._show_vocabulary)
        self.fsrs_review_page.rating_requested.connect(self._rate_fsrs_card)
        self.fsrs_review_page.defer_requested.connect(self._defer_fsrs_card)
        self.fsrs_review_page.learning_activity.connect(self._track_fsrs_learning_activity)
        self.fsrs_review_page.dictation_requested.connect(self._start_dictation)
        self.dictation_page = DictationPage(self.context.dictation_service)
        self.dictation_page.back_requested.connect(self._leave_dictation)
        self.dictation_page.audio_requested.connect(self._play_dictation_audio)
        self.dictation_page.attempt_completed.connect(self._save_dictation_attempt)
        self.dictation_page.rating_requested.connect(self._rate_dictation_card)
        self.dictation_page.learning_activity.connect(self._track_dictation_learning_activity)
        self.dictation_page.course_audio_requested.connect(self._play_course_dictation_audio)
        self.dictation_page.course_attempt_completed.connect(self._save_course_dictation_attempt)
        self.dictation_page.course_rating_requested.connect(self._rate_course_dictation_card)
        self.dictation_page.course_review_rating_requested.connect(self._rate_course_review_card)
        self.pronunciation_page = PronunciationPage()
        self.pronunciation_page.back_requested.connect(self._leave_pronunciation)
        self.pronunciation_page.standard_audio_requested.connect(self._play_pronunciation_reference)
        self.pronunciation_page.record_requested.connect(self._start_pronunciation_recording)
        self.pronunciation_page.stop_requested.connect(self._stop_pronunciation_recording)
        self.pronunciation_page.cancel_requested.connect(self._cancel_pronunciation_recording)
        self.pronunciation_page.playback_requested.connect(self._play_pronunciation_recording)
        self.pronunciation_page.assess_requested.connect(self._assess_pronunciation)
        self.sentence_practice_view.course_dictation_requested.connect(self._start_current_course_dictation)
        self.sentence_practice_view.course_pronunciation_requested.connect(self._start_current_course_pronunciation)
        self.sentence_practice_view.course_words_requested.connect(self._show_current_course_words)
        self.sentence_practice_view.course_review_requested.connect(self._add_current_course_review)
        self.context.recording_service.state_changed.connect(self._pronunciation_recording_state)
        self.context.recording_service.failed.connect(lambda message: self.pronunciation_page.status.setText(message))
        self._vocabulary_workers: set[VocabularyTask] = set()
        self._enrichment_loading: set[tuple[int,str]] = set()
        self._enrichment_errors: dict[tuple[int,str],str] = {}

        self._build_ui()
        self.stack.currentChanged.connect(self._learning_page_changed)
        self._learning_timer=QTimer(self); self._learning_timer.setInterval(1000); self._learning_timer.timeout.connect(self._tick_learning_time); self._learning_timer.start()
        self._apply_settings()
        self._reload_articles()
        self._refresh_history()
        self._refresh_statistics()
        self._refresh_special_practice_page()
        self._refresh_vocabulary_page()
        self._refresh_daily_learning()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("RootShell")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setFixedWidth(228)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(18, 18, 18, 18)
        sidebar_layout.setSpacing(10)

        app_title = QLabel("English Studio")
        app_title.setProperty("role", "app-title")
        app_subtitle = QLabel("通过阅读、打字、听写和复习学习英语")
        app_subtitle.setProperty("role", "subtitle")
        sidebar_layout.addWidget(app_title)
        sidebar_layout.addWidget(app_subtitle)
        sidebar_layout.addSpacing(8)

        self.stack = QStackedWidget()
        self.home_page = HomePage()
        self.home_page.article_library_requested.connect(self._show_library)
        self.home_page.courses_requested.connect(self._show_courses)
        self.home_page.special_practice_requested.connect(self._show_special_practice)
        self.home_page.vocabulary_requested.connect(self._show_vocabulary)
        self.daily_learning_card = self.home_page.daily_learning_card
        self.daily_learning_card.review_requested.connect(self._start_fsrs_review)
        self.library_page = self._build_library_page()
        self.learning_content_page = LearningContentPage(self.library_page, self.course_page)
        self.learning_content_page.section_changed.connect(self._learning_content_section_changed)
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.learning_content_page)
        self.stack.addWidget(self.special_practice_page)
        self.stack.addWidget(self.vocabulary_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.statistics_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.practice_view)
        self.stack.addWidget(self.sentence_practice_view)
        self.stack.addWidget(self.word_learning_page)
        self.stack.addWidget(self.fsrs_review_page)
        self.stack.addWidget(self.dictation_page)
        self.stack.addWidget(self.pronunciation_page)

        self.nav_buttons: dict[int, QPushButton] = {}
        nav_specs = [
            (self.PAGE_HOME, "首页", QStyle.StandardPixmap.SP_ComputerIcon),
            (self.PAGE_LEARNING_CONTENT, "学习内容", QStyle.StandardPixmap.SP_DirHomeIcon),
            (self.PAGE_SPECIAL_PRACTICE, "专项练习", QStyle.StandardPixmap.SP_MediaPlay),
            (self.PAGE_VOCABULARY, "单词本", QStyle.StandardPixmap.SP_FileDialogDetailedView),
            (self.PAGE_HISTORY, "练习记录", QStyle.StandardPixmap.SP_FileDialogListView),
            (self.PAGE_STATISTICS, "学习统计", QStyle.StandardPixmap.SP_ComputerIcon),
            (self.PAGE_SETTINGS, "设置", QStyle.StandardPixmap.SP_FileDialogContentsView),
        ]
        for index, text, icon_type in nav_specs:
            button = QPushButton(text)
            button.setIcon(self.style().standardIcon(icon_type))
            button.setProperty("nav", "true")
            button.clicked.connect(lambda checked=False, idx=index: self._switch_page(idx))
            sidebar_layout.addWidget(button)
            self.nav_buttons[index] = button
        sidebar_layout.addStretch(1)

        version_label = QLabel(f"版本 {__version__}")
        version_label.setProperty("role", "subtitle")
        sidebar_layout.addWidget(version_label)

        content = QFrame()
        content.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self.stack)

        shell.addWidget(self.sidebar)
        shell.addWidget(content, stretch=1)
        self.setCentralWidget(root)

        self._switch_page(self.PAGE_HOME)
        self.history_page.refresh_button.clicked.connect(self._refresh_history)
        self.statistics_page.trend_range.currentIndexChanged.connect(self._refresh_statistics)
        self.statistics_page.error_range.currentIndexChanged.connect(self._refresh_statistics)

    def _build_library_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        top_row = QHBoxLayout()
        header_box = QVBoxLayout()
        title = QLabel("文章库")
        title.setProperty("role", "page-title")
        subtitle = QLabel("导入英文文章，按段练习并记录进步")
        subtitle.setProperty("role", "subtitle")
        header_box.addWidget(title)
        header_box.addWidget(subtitle)
        top_row.addLayout(header_box, stretch=1)
        self.import_button = QPushButton("导入文章")
        self.import_button.setProperty("variant", "primary")
        self.import_button.clicked.connect(self._import_articles)
        top_row.addWidget(self.import_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(top_row)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        self.metric_article_count = MetricCard("文章数量")
        self.metric_completed_count = MetricCard("已完成")
        self.metric_due_words = MetricCard("今日待复习")
        self.metric_last_practice = MetricCard("最近练习")
        for idx, card in enumerate(
            [
                self.metric_article_count,
                self.metric_completed_count,
                self.metric_due_words,
                self.metric_last_practice,
            ]
        ):
            metrics.addWidget(card, 0, idx)
        layout.addLayout(metrics)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索文章")
        self.search_input.textChanged.connect(self._reload_articles)
        refresh_button = QPushButton("刷新")
        refresh_button.setProperty("variant", "ghost")
        refresh_button.clicked.connect(self._reload_articles)
        search_row.addWidget(self.search_input)
        search_row.addWidget(refresh_button)
        layout.addLayout(search_row)

        self.empty_state = EmptyStateCard(
            "还没有导入文章",
            "1. 导入一篇英文 TXT。2. 选择逐句学习或连续练习。3. 翻译、语音和跟读服务均可稍后在设置中按需配置。",
            "导入第一篇文章",
        )
        self.empty_state.action_button.clicked.connect(self._import_articles)
        layout.addWidget(self.empty_state, stretch=1)

        self.content_split = QHBoxLayout()
        self.content_split.setSpacing(16)
        list_card = QFrame()
        list_card.setObjectName("Card")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(16, 16, 16, 16)
        list_layout.addWidget(QLabel("文章列表"))
        self.article_list = QListWidget()
        self.article_list.currentRowChanged.connect(self._update_preview)
        list_layout.addWidget(self.article_list)
        self.content_split.addWidget(list_card, stretch=1)

        detail_card = QFrame()
        detail_card.setObjectName("Card")
        detail_layout = QVBoxLayout(detail_card)
        detail_layout.setContentsMargins(18, 18, 18, 18)
        self.preview_title = QLabel("暂未选择文章")
        self.preview_title.setProperty("role", "page-title")
        self.preview_title.setStyleSheet("font-size: 22px;")
        self.preview_meta = QLabel("从左侧选择一篇文章，查看详情并开始练习。")
        self.preview_meta.setProperty("role", "subtitle")
        self.preview_meta.setWordWrap(True)
        detail_layout.addWidget(self.preview_title)
        detail_layout.addWidget(self.preview_meta)

        action_row = QHBoxLayout()
        self.continue_button = QPushButton("继续练习")
        self.continue_button.setProperty("variant", "primary")
        self.continue_button.clicked.connect(lambda: self._start_selected_article("resume"))
        self.restart_button = QPushButton("从头练习")
        self.restart_button.clicked.connect(lambda: self._start_selected_article("start_over"))
        self.more_button = QToolButton()
        self.more_button.setText("更多")
        self.more_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.more_menu = QMenu(self)
        self.rename_action = QAction("重命名", self)
        self.rename_action.triggered.connect(self._rename_selected_article)
        self.resegment_action = QAction("重新分段", self)
        self.resegment_action.triggered.connect(self._resegment_selected_article)
        self.delete_action = QAction("删除", self)
        self.delete_action.triggered.connect(self._delete_selected_article)
        self.more_menu.addAction(self.rename_action)
        self.more_menu.addAction(self.resegment_action)
        self.more_menu.addSeparator()
        self.more_menu.addAction(self.delete_action)
        self.more_button.setMenu(self.more_menu)
        action_row.addWidget(self.continue_button)
        action_row.addWidget(self.restart_button)
        action_row.addWidget(self.more_button)
        self.proofread_button = QPushButton("重新检测")
        self.proofread_button.setToolTip("使用 DeepSeek 检查文章格式、拼写和单词错误")
        self.proofread_button.clicked.connect(self._proofread_selected_article)
        action_row.addWidget(self.proofread_button)
        action_row.addStretch(1)
        detail_layout.addLayout(action_row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(12)
        mode_label = QLabel("练习模式")
        mode_label.setProperty("role", "subtitle")
        self.practice_mode_control = SegmentedControl(
            [("逐句学习", "sentence"), ("连续练习", "continuous")]
        )
        self.practice_mode_control.value_changed.connect(self._set_practice_mode)
        mode_row.addWidget(mode_label)
        mode_row.addWidget(self.practice_mode_control)
        mode_row.addStretch(1)
        detail_layout.addLayout(mode_row)

        self.preview_content = QTextEdit()
        self.preview_content.setReadOnly(True)
        self.preview_content.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preview_content.viewport().installEventFilter(self)
        detail_layout.addWidget(self.preview_content, stretch=1)
        self.content_split.addWidget(detail_card, stretch=2)
        layout.addLayout(self.content_split, stretch=1)
        return page

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.setVisible(self.stack.currentWidget() not in {self.practice_view, self.sentence_practice_view})
        if (
            self.stack.currentWidget() is self.learning_content_page
            and self.learning_content_page.current_section() == "courses"
        ):
            self.course_page.reload()
            self._refresh_course_review_count()
        for button_index, button in self.nav_buttons.items():
            button.setProperty("active", "true" if button_index == index else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _learning_page_changed(self, _index:int) -> None:
        if self.stack.currentWidget() not in {self.practice_view,self.sentence_practice_view,self.word_learning_page,self.fsrs_review_page,self.dictation_page}:
            self._handle_learning_update(self.context.learning_time_tracker.stop())
            self._refresh_daily_learning()

    def _track_learning_activity(self,event_type:str) -> None:
        if self.current_course_session is not None and self.stack.currentWidget() is self.sentence_practice_view:
            if self.sentence_practice_view.learning is not None:
                self.current_course_session.sync_index(self.sentence_practice_view.learning.current_index)
            if event_type == "typing_activity":
                item_stable_key = self.current_course_session.current_item_stable_key
                if item_stable_key and self.current_course_session.mark_item_started(item_stable_key):
                    try:
                        self.context.course_progress_service.start_item(
                            self.current_course_session.course_id,
                            item_stable_key,
                        )
                    except Exception as exc:
                        self._handle_course_state_error("开始课程句子失败", item_stable_key, exc)
            update=self.context.learning_time_tracker.activity(f"course_{event_type}")
            self._handle_learning_update(update); self._refresh_daily_learning()
            return
        if self.stack.currentWidget() is self.word_learning_page and self.word_learning_page.current_context:
            article_id=self.word_learning_page.current_context.article_id
        else:
            article_id=self.current_material.article_id if self.current_material else None
        sentence_id=self.sentence_practice_view.current_sentence.id if self.stack.currentWidget() is self.sentence_practice_view and self.sentence_practice_view.current_sentence else None
        vocabulary_id=self.word_learning_page.entry.id if self.stack.currentWidget() is self.word_learning_page and self.word_learning_page.entry else None
        update=self.context.learning_time_tracker.activity(event_type,related_article_id=article_id,related_sentence_id=sentence_id,related_vocabulary_id=vocabulary_id)
        self._handle_learning_update(update); self._refresh_daily_learning()

    def _track_fsrs_learning_activity(self, event_type: str, vocabulary_id: object) -> None:
        item = self.fsrs_review_page.current
        article_id = item.context.article_id if item and item.context else None
        update = self.context.learning_time_tracker.activity(event_type, related_article_id=article_id, related_vocabulary_id=int(vocabulary_id) if vocabulary_id else None)
        self._handle_learning_update(update)
        self._refresh_daily_learning()

    def _track_dictation_learning_activity(self, event_type: str, vocabulary_id: object) -> None:
        item = self.dictation_page.current
        if getattr(self.dictation_page, "_course_mode", False):
            update = self.context.learning_time_tracker.activity(
                f"course_dictation_{event_type}"
            )
            self._handle_learning_update(update)
            self._refresh_daily_learning()
            return
        article_id = item.context.article_id if item and item.context else None
        update = self.context.learning_time_tracker.activity(event_type, related_article_id=article_id, related_vocabulary_id=int(vocabulary_id) if vocabulary_id else None)
        self._handle_learning_update(update)
        self._refresh_daily_learning()

    def _tick_learning_time(self) -> None:
        self._handle_learning_update(self.context.learning_time_tracker.tick())
        self._refresh_daily_learning()

    def _handle_learning_update(self,update) -> None:
        if not update:return
        for minutes in update.milestones:
            if self.settings.checkin_animation_enabled:self.daily_learning_card.play_milestone(minutes,self.settings.reduce_motion)
        for achievement in update.achievements:
            self.daily_learning_card.play_achievement(achievement,self.settings.reduce_motion)
        if self.settings.health_reminders_enabled and update.reminders:
            minutes=update.reminders[-1]
            message={120:"已连续学习两小时，建议起身活动并让眼睛休息。",180:"今天已经学习三小时，建议安排较长休息。",240:"今天的学习量已经很充足，建议结束学习并充分休息。"}[minutes]
            QMessageBox.information(self,"学习健康提醒",message)

    def _refresh_daily_learning(self) -> None:
        if not hasattr(self,"daily_learning_card"):return
        dashboard=self.context.learning_repository.dashboard()
        self.daily_learning_card.update_dashboard(dashboard,self.settings.daily_learning_goal_minutes,reduce_motion=self.settings.reduce_motion)

    def eventFilter(self, watched, event) -> bool:
        if watched is self.preview_content.viewport() and event.type()==QEvent.Type.ContextMenu:
            self._show_article_preview_menu(event.pos())
            return True
        return super().eventFilter(watched,event)

    def _apply_settings(self) -> None:
        apply_theme(self, self.settings.theme, font_size=14)
        self.practice_view.apply_settings(self.settings)
        self.settings_page.load_settings(self.settings)
        self.preview_content.setStyleSheet(f"font-size: {max(14, self.settings.font_size - 1)}px;")
        self.practice_mode_control.set_value("sentence" if self.settings.sentence_learning_enabled else "continuous")
        self.context.learning_time_tracker.configure(self.settings.learning_idle_timeout_seconds,self.settings.health_reminders_enabled)
        if hasattr(self,"daily_learning_card"):self._refresh_daily_learning()

    def _set_practice_mode(self, mode: str) -> None:
        enabled = mode == "sentence"
        if enabled == self.settings.sentence_learning_enabled:
            return
        self.settings = self.context.settings_service.save_settings(
            replace(self.settings, sentence_learning_enabled=enabled)
        )
        self.settings_page.load_settings(self.settings)

    def _show_library(self) -> None:
        self.learning_content_page.set_section("articles")
        self._switch_page(self.PAGE_LEARNING_CONTENT)
        self._reload_articles()

    def _show_special_practice(self) -> None:
        self._switch_page(self.PAGE_SPECIAL_PRACTICE)
        self._refresh_special_practice_page()

    def _show_courses(self) -> None:
        self.learning_content_page.set_section("courses")
        self._switch_page(self.PAGE_LEARNING_CONTENT)

    def _learning_content_section_changed(self, section: str) -> None:
        if section == "courses":
            self.course_page.reload()
            self._refresh_course_review_count()
        else:
            self._reload_articles()

    def _refresh_course_review_count(self) -> None:
        try:
            count = len(self.context.course_capability_service.due_sentence_reviews())
        except Exception as exc:
            self._logger.error("course review count failed reason=%s", exc)
            count = 0
        self.course_page.set_due_review_count(count)

    def _start_course_due_review(self) -> None:
        try:
            reviews = self.context.course_capability_service.due_sentence_reviews()
        except Exception as exc:
            self._logger.error("course due review queue failed reason=%s", exc)
            QMessageBox.warning(self, "课程复习不可用", f"暂时无法读取课程复习队列：{exc}")
            return
        if not reviews:
            QMessageBox.information(self, "课程复习", "当前没有已到期的课程复习卡。")
            return
        self.course_review_queue_active = True
        self.current_course_return = None
        self.current_course_capability_item = reviews[0].item
        self.dictation_page.load_course_reviews(list(reviews))
        self.stack.setCurrentWidget(self.dictation_page)
        self.sidebar.hide()

    def _show_vocabulary(self) -> None:
        self._switch_page(self.PAGE_VOCABULARY)
        self._refresh_vocabulary_page()

    def _leave_word_learning(self) -> None:
        if self.current_course_session is not None:
            self.stack.setCurrentWidget(self.sentence_practice_view)
            self.sidebar.hide()
            return
        if self.current_course_return is not None:
            course_id, lesson_id = self.current_course_return
            self.current_course_return = None
            self._show_courses()
            self.course_page.show_lesson(course_id, lesson_id)
            return
        self._show_vocabulary()

    def _start_fsrs_review(self) -> None:
        queue = self.context.fsrs_review_service.build_today_queue(
            new_limit=self.settings.fsrs_new_cards_per_day,
            soft_limit=self.settings.fsrs_review_soft_limit,
        )
        if not queue.items:
            QMessageBox.information(self, "今日复习", "当前没有到期或可加入的新复习卡。")
            return
        self.fsrs_review_page.load_queue(queue.items)
        self.stack.setCurrentWidget(self.fsrs_review_page)
        self.sidebar.hide()

    def _start_dictation(self) -> None:
        queue = self.context.fsrs_review_service.build_today_queue(
            new_limit=self.settings.fsrs_new_cards_per_day,
            soft_limit=self.settings.fsrs_review_soft_limit,
        )
        items = []
        seen: set[int] = set()
        for item in queue.items:
            if item.entry.id and item.entry.id not in seen:
                seen.add(item.entry.id)
                items.append(item)
        if not items:
            QMessageBox.information(self, "听写练习", "请先在单词本添加单词，或等待今日复习队列生成。")
            return
        self.dictation_page.load_queue(items)
        self.stack.setCurrentWidget(self.dictation_page)
        self.sidebar.hide()

    def _start_pronunciation(self, entry_id: int) -> None:
        entry, contexts, _state = self.context.vocabulary_learning_service.detail(entry_id)
        if entry is None:
            QMessageBox.information(self, "跟读练习", "该单词已不存在或无法读取。")
            return
        self.pronunciation_page.load_target(entry, contexts[0] if contexts else None)
        self.stack.setCurrentWidget(self.pronunciation_page)
        self.sidebar.hide()

    def _leave_pronunciation(self) -> None:
        self._cancel_pronunciation_recording()
        if self.pronunciation_page.course_item is not None:
            self.pronunciation_page.course_item = None
            self.current_course_capability_item = None
            if self.current_course_session is not None:
                self.stack.setCurrentWidget(self.sentence_practice_view)
                self.sidebar.hide()
                return
            if self.current_course_return is not None:
                course_id, lesson_id = self.current_course_return
                self.current_course_return = None
                self._show_courses()
                self.course_page.show_lesson(course_id, lesson_id)
                return
        self._show_vocabulary()

    def _play_pronunciation_reference(self, text: str, speed: float) -> None:
        item = self.pronunciation_page
        if item.course_item is not None:
            self._request_course_speech(text, speed, item.course_item.ref)
            return
        if item.target_type.currentData() == "word" and item.entry is not None:
            self._play_word_from_learning(item.entry, item.context, focus_widget=self.pronunciation_page)
        else:
            self._request_speech(text, speed)

    def _start_pronunciation_recording(self) -> None:
        path = self.context.recording_service.start()
        if path:
            self.pronunciation_page.status.setText("正在录音。完成后点击“停止录音”。")

    def _stop_pronunciation_recording(self) -> None:
        self.pronunciation_page.set_recorded(self.context.recording_service.stop())

    def _cancel_pronunciation_recording(self) -> None:
        self.context.recording_service.cancel()
        self.pronunciation_page.audio_path = None

    def _pronunciation_recording_state(self, state: str) -> None:
        self.pronunciation_page.set_recording_state(state)

    def _play_pronunciation_recording(self, path) -> None:
        if path is None or not path.exists():
            self.pronunciation_page.status.setText("录音文件尚未准备完成或已被清理。")
            return
        self.audio_playback.toggle(path)

    def _assess_pronunciation(self, target_type: str, path, _unused_keep: bool) -> None:
        page = self.pronunciation_page
        if path is None or not path.exists():
            page.status.setText("请先完成一段录音后再评分。")
            return
        key = self.context.pronunciation_credential_store.get() or ""
        provider = AzurePronunciationAssessmentProvider(key, self.settings.pronunciation_region)
        request = PronunciationRequest(page.reference_text(), self.settings.pronunciation_locale, path)
        entry_id = page.entry.id if page.entry else None
        context_id = page.context.id if page.context else None
        course_item = page.course_item
        if not key or not self.settings.pronunciation_region:
            if course_item is not None:
                result = provider.assess(request)
                self._course_pronunciation_result_ready(
                    result, None, request, course_item
                )
            else:
                attempt = self.context.pronunciation_assessment_service.assess(
                    request, provider, target_type=target_type, entry_id=entry_id, context_id=context_id,
                    keep_audio=self.settings.pronunciation_keep_recordings,
                )
                self._pronunciation_assessed(attempt, None)
            return
        page.status.setText("正在准备评分请求……")
        task = VocabularyTask(lambda: provider.assess(request))
        self._vocabulary_workers.add(task)
        if course_item is not None:
            task.signals.completed.connect(lambda result, worker=task, req=request, item=course_item: self._course_pronunciation_result_ready(result, worker, req, item))
            task.signals.failed.connect(lambda error, worker=task, req=request, item=course_item: self._course_pronunciation_failed(str(error), worker, req, item))
        else:
            task.signals.completed.connect(lambda result, worker=task, req=request, target=target_type, entry=entry_id, context=context_id: self._pronunciation_result_ready(result, worker, req, target, entry, context))
            task.signals.failed.connect(lambda error, worker=task: self._pronunciation_assessment_failed(str(error), worker))
        self._thread_pool.start(task)

    def _pronunciation_assessed(self, attempt, worker) -> None:
        if worker is not None:
            self._vocabulary_workers.discard(worker)
        self.pronunciation_page.show_attempt(attempt)
        if not self.settings.pronunciation_keep_recordings:
            self.pronunciation_page.audio_path = None

    def _pronunciation_result_ready(self, result, worker, request, target_type: str, entry_id: int | None, context_id: int | None) -> None:
        attempt = self.context.pronunciation_assessment_service.save_result(
            request, result, target_type=target_type, entry_id=entry_id, context_id=context_id,
            keep_audio=self.settings.pronunciation_keep_recordings,
        )
        self._pronunciation_assessed(attempt, worker)

    def _course_pronunciation_result_ready(
        self, result, worker, request, item: CourseCapabilityItem
    ) -> None:
        if worker is not None:
            self._vocabulary_workers.discard(worker)
        try:
            self.context.course_capability_service.record_speaking(item.ref, result)
            self.pronunciation_page.show_result(result)
            if self.current_course_return:
                self.course_page.show_lesson(*self.current_course_return)
        except Exception as exc:
            self._logger.error(
                "course speaking save failed item_stable_key=%s reason=%s",
                item.ref.item_stable_key,
                exc,
            )
            self.pronunciation_page.status.setText(f"评分结果暂时无法保存：{exc}")
        finally:
            if not self.settings.pronunciation_keep_recordings:
                request.audio_path.unlink(missing_ok=True)
                self.pronunciation_page.audio_path = None

    def _course_pronunciation_failed(
        self, message: str, worker, request, item: CourseCapabilityItem
    ) -> None:
        result = PronunciationResult(
            status="failed",
            provider="azure",
            error_code="request_failed",
            message=message,
        )
        self._course_pronunciation_result_ready(result, worker, request, item)

    def _pronunciation_assessment_failed(self, message: str, worker) -> None:
        self._vocabulary_workers.discard(worker)
        self.pronunciation_page.status.setText(f"评分失败：{message}")

    def _save_dictation_attempt(self, attempt) -> None:
        self.context.dictation_service.save(attempt)

    def _save_course_dictation_attempt(self, item, payload) -> None:
        try:
            self.context.course_capability_service.record_dictation(
                item.ref,
                score=payload.get("score"),
                error_count=int(payload.get("error_count", 0)),
                omitted_count=int(payload.get("omitted_count", 0)),
                inserted_count=int(payload.get("inserted_count", 0)),
                replay_count=int(payload.get("replay_count", 0)),
                duration_ms=int(payload.get("duration_ms", 0)),
            )
            if self.current_course_return:
                self.course_page.show_lesson(*self.current_course_return)
        except Exception as exc:
            self._logger.error(
                "course dictation save failed item_stable_key=%s reason=%s",
                item.ref.item_stable_key,
                exc,
            )
            self.dictation_page.feedback.setText(f"课程听写结果暂时无法保存：{exc}")

    def _rate_course_dictation_card(self, content_ref, rating: str) -> None:
        try:
            self.context.course_capability_service.rate_existing_sentence_review(
                content_ref,
                rating,
            )
        except Exception as exc:
            self._logger.error(
                "course dictation rating failed item_stable_key=%s reason=%s",
                content_ref.item_stable_key,
                exc,
            )

    def _rate_course_review_card(self, card_id: int, rating: str) -> None:
        try:
            self.context.course_capability_service.rate_sentence_review(
                card_id, rating
            )
            self._refresh_course_review_count()
            self.dictation_page.accept_course_review_rating()
        except Exception as exc:
            self._logger.error(
                "course review rating failed card_id=%s reason=%s",
                card_id,
                exc,
            )
            self.dictation_page.show_course_review_rating_error(
                f"课程复习评分暂时无法保存：{exc}"
            )

    def _leave_dictation(self) -> None:
        self.audio_playback.stop()
        self.current_course_capability_item = None
        if self.course_review_queue_active:
            self.course_review_queue_active = False
            self._show_courses()
            return
        if self.current_course_session is not None:
            self.stack.setCurrentWidget(self.sentence_practice_view)
            self.sidebar.hide()
            return
        if self.current_course_return is not None:
            course_id, lesson_id = self.current_course_return
            self.current_course_return = None
            self._show_courses()
            self.course_page.show_lesson(course_id, lesson_id)
            return
        self._show_vocabulary()

    def _rate_dictation_card(self, entry_id: int, rating: str) -> None:
        card = self.context.fsrs_review_service.ensure_listening_card(entry_id)
        self.context.fsrs_review_service.rate(card.id or 0, rating)
        self._refresh_overview()

    def _rate_fsrs_card(self, card_id: int, rating: str) -> None:
        self.context.fsrs_review_service.rate(card_id, rating)
        self._refresh_overview()

    def _defer_fsrs_card(self, card_id: int) -> None:
        self.context.fsrs_review_service.defer(card_id)

    def _show_history(self) -> None:
        self._switch_page(self.PAGE_HISTORY)
        self._refresh_history()

    def _show_statistics(self) -> None:
        self._switch_page(self.PAGE_STATISTICS)
        self._refresh_statistics()

    def _show_settings(self) -> None:
        self.settings_page.load_settings(self.settings)
        try:
            self.settings_page.set_api_key_status(mask_api_key(self.context.credential_store.get()))
        except Exception:
            self.settings_page.set_api_key_status("读取失败")
        try:
            self.settings_page.set_tts_api_key_status(mask_secret(self.context.tts_credential_store.get()))
        except Exception:
            self.settings_page.set_tts_api_key_status("读取失败")
        try:
            self.settings_page.set_pronunciation_key_status(mask_secret(self.context.pronunciation_credential_store.get()))
        except Exception:
            self.settings_page.set_pronunciation_key_status("读取失败")
        stats=self.context.tts_service.stats(); self.settings_page.set_tts_cache_stats(stats.file_count,stats.total_size_bytes)
        self._switch_page(self.PAGE_SETTINGS)

    def _reload_articles(self, preferred_article_id: int | None = None) -> None:
        self.articles = self.context.article_library.list_articles(self.search_input.text())
        self.article_list.clear()
        for article in self.articles:
            recent = article.last_practiced_at.strftime("%Y-%m-%d %H:%M") if article.last_practiced_at else "暂无"
            item = QListWidgetItem(
                f"{article.title}\n{article.character_count} 字 · {article.section_count} 段 · "
                f"进度 {article.completed_section_count}/{article.section_count} · 最近练习 {recent}"
            )
            item.setData(Qt.ItemDataRole.UserRole, article.id)
            self.article_list.addItem(item)
        has_articles = self.article_list.count() > 0
        self.empty_state.setVisible(not has_articles)
        self._set_content_layout_visible(has_articles)
        if has_articles:
            selected_row = 0
            if preferred_article_id is not None:
                for row in range(self.article_list.count()):
                    if self.article_list.item(row).data(Qt.ItemDataRole.UserRole) == preferred_article_id:
                        selected_row = row
                        break
            self.article_list.setCurrentRow(selected_row)
        else:
            self._update_preview(-1)
        self.history_page.populate_articles(self.articles)
        self._refresh_overview()

    def _set_content_layout_visible(self, visible: bool) -> None:
        for index in range(self.content_split.count()):
            item = self.content_split.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.setVisible(visible)

    def _refresh_overview(self) -> None:
        article_count = len(self.articles)
        completed = sum(
            1
            for article in self.articles
            if article.completed_section_count >= article.section_count and article.section_count > 0
        )
        recent_practice = max(
            (article.last_practiced_at for article in self.articles if article.last_practiced_at),
            default=None,
        )
        recent_text = recent_practice.strftime("%m-%d %H:%M") if recent_practice else "暂无"
        summary = self.context.special_practice_service.due_summary()
        self.metric_article_count.set_value(str(article_count))
        self.metric_completed_count.set_value(str(completed))
        self.metric_due_words.set_value(str(summary["due_count"]))
        self.metric_last_practice.set_value(recent_text)

    def _refresh_history(self) -> None:
        completed_filter = self.history_page.completed_filter.currentData()
        rows = self.context.history_service.list_history(
            article_id=self.history_page.article_filter.currentData(),
            practice_type=self.history_page.practice_type_filter.currentData(),
            date_range=self.history_page.range_filter.currentData(),
            date_from=self.history_page.start_date.date().toPython(),
            date_to=self.history_page.end_date.date().toPython(),
            completed=completed_filter,
            order_by=self.history_page.sort_filter.currentData(),
            descending=self.history_page.desc_checkbox.isChecked(),
            valid_only=self.history_page.valid_only_checkbox.isChecked(),
        )
        self.history_page.populate_history(rows)

    def _refresh_statistics(self) -> None:
        overview = self.context.statistics_service.overview()
        self.statistics_page.populate_overview(overview)
        trends = self.context.statistics_service.trend_data(self.statistics_page.trend_range.currentData())
        self.statistics_page.populate_trends(trends)
        analysis = self.context.statistics_service.error_analysis(self.statistics_page.error_range.currentData())
        self.statistics_page.populate_error_analysis(analysis)

    def _refresh_special_practice_page(self) -> None:
        self.special_practice_page.set_summary(self.context.special_practice_service.due_summary())
        self.special_practice_page.populate_saved_sets(self.context.special_practice_service.list_saved_sets())

    def _refresh_vocabulary_page(self) -> None:
        scope=str(self.vocabulary_page.scope_combo.currentData())
        if scope in {"article","all"}:
            article_id=self.current_vocabulary_article_id if scope=="article" else None
            if scope=="article" and article_id is None:
                self.vocabulary_page.populate_items([]); self.vocabulary_page.set_status_message("请先在文章库选择一篇文章。"); return
            if article_id is not None:self.context.article_word_index_service.ensure(article_id)
            items=self.context.article_word_index_service.list_words(article_id,search=self.vocabulary_page.search_input.text(),sort=str(self.vocabulary_page.sort_combo.currentData()),hide_mastered=self.vocabulary_page.hide_mastered_checkbox.isChecked())
            rows=[]
            for item in items:
                row=dict(item); row["id"]=row.pop("vocabulary_entry_id"); row.update({"phonetic":"","meaning_zh":"","primary_part_of_speech":"","article_title":self.preview_title.text() if article_id else f"{row['article_count']} 篇文章","last_practiced_at":"","is_archived":False,"meaning":"","note":"","mastery_level":0})
                if row["id"]:
                    entry,contexts,state=self.context.vocabulary_learning_service.detail(row["id"]); row.update({"phonetic":entry.phonetic,"primary_part_of_speech":entry.primary_part_of_speech,"meaning_zh":contexts[0].contextual_meaning_zh if contexts else "","status":state.status})
                rows.append(row)
        else:
            items=self.context.vocabulary_learning_service.list_entries(search=self.vocabulary_page.search_input.text(),status=str(self.vocabulary_page.status_combo.currentData()))
            rows=[dict(item) | {"occurrence_count":"-","is_archived":False,"meaning":"","note":"","mastery_level":0} for item in items if item["status"]!="mastered"]
        self.vocabulary_page.set_status_message("")
        self.vocabulary_page.populate_items(rows)

    def _selected_article_id(self) -> int | None:
        item = self.article_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _update_preview(self, row: int) -> None:
        if row < 0 or row >= len(self.articles):
            self.preview_title.setText("暂未选择文章")
            self.preview_meta.setText("从左侧选择一篇文章，查看详情并开始练习。")
            self.preview_content.setPlainText("导入一篇英文 TXT，开始第一次练习")
            self.current_vocabulary_article_id=None; self.vocabulary_page.set_article_available(False)
            self.proofread_button.setText("重新检测")
            self.proofread_button.setEnabled(False)
            return
        article = self.articles[row]
        imported = article.imported_at.strftime("%Y-%m-%d %H:%M") if article.imported_at else "暂无"
        last_practiced = article.last_practiced_at.strftime("%Y-%m-%d %H:%M") if article.last_practiced_at else "暂无"
        self.preview_title.setText(article.title)
        self.preview_meta.setText(
            f"导入时间：{imported}\n"
            f"最近练习：{last_practiced}\n"
            f"总字数：{article.character_count} · 单词数：{article.word_count} · 分段数：{article.section_count}\n"
            f"完成进度：{article.completed_section_count}/{article.section_count} 段\n"
            f"原始文件名：{article.original_filename}"
        )
        self.preview_meta.setToolTip(article.source_path)
        self.preview_content.setPlainText(article.full_text[:3500])
        self.current_vocabulary_article_id=article.id; self.vocabulary_page.set_article_available(True)
        proofreading = article.id in self._proofreading_article_ids
        self.proofread_button.setText("检测中…" if proofreading else "重新检测")
        self.proofread_button.setEnabled(not proofreading)
        if article.id is not None:self.context.article_word_index_service.ensure(article.id)

    def _show_article_preview_menu(self,position) -> None:
        if self.current_vocabulary_article_id is None:return
        menu,view_action,rebuild_action=self._build_article_preview_menu()
        selected=menu.exec(self.preview_content.viewport().mapToGlobal(position))
        if selected is view_action:
            self._show_current_article_words()
        elif selected is rebuild_action:
            self._rebuild_current_article_words()

    def _build_article_preview_menu(self):
        menu=self.preview_content.createStandardContextMenu()
        if menu.actions():menu.addSeparator()
        view_action=menu.addAction("查看当前文章单词")
        rebuild_action=menu.addAction("重新提取文章单词")
        return menu,view_action,rebuild_action

    def _show_current_article_words(self) -> None:
        if self.current_vocabulary_article_id is None:return
        self.context.article_word_index_service.ensure(self.current_vocabulary_article_id)
        index=self.vocabulary_page.scope_combo.findData("article")
        self.vocabulary_page.scope_combo.setCurrentIndex(index)
        self._show_vocabulary()

    def _rebuild_current_article_words(self) -> None:
        article_id=self.current_vocabulary_article_id
        if article_id is None:return
        if QMessageBox.question(self,"重新提取文章单词","将重新分析当前文章中的单词，不会删除已收藏单词、来源语境或学习记录。") != QMessageBox.StandardButton.Yes:return
        try:
            count=self.context.article_word_index_service.rebuild(article_id)
        except Exception as exc:
            QMessageBox.warning(self,"提取失败",f"无法重新提取文章单词：{exc}")
            return
        if str(self.vocabulary_page.scope_combo.currentData())=="article":self._refresh_vocabulary_page()
        QMessageBox.information(self,"提取完成",f"已记录 {count} 个单词位置。")

    def _start_vocabulary_row(self,row) -> None:
        entry_id=row.get("id")
        if not entry_id:
            source=row.get("source_sentence","") or ""; local=max(source.find(row["display_word"]),0)
            collected=self.context.vocabulary_learning_service.collect(row["display_word"],sentence=source,article_id=self.current_vocabulary_article_id,start_offset=local,end_offset=local+len(row["display_word"]),typing_target_count=self.settings.vocabulary_typing_count)
            entry_id=collected.entry.id; self._refresh_vocabulary_page()
        if entry_id:self._open_word_learning(int(entry_id))

    def _import_articles(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(self, "导入 TXT 文章", "", "文本文件 (*.txt)")
        if not file_paths:
            return
        messages: list[str] = []
        proofreading_ids: list[int] = []
        for file_path in file_paths:
            result = self.context.article_library.import_txt_file(
                file_path,
                self.settings.section_target_characters,
            )
            name = result.article.title if result.article else file_path
            messages.append(f"{result.status}：{name} - {result.message}")
            if result.status in {"imported", "restored"} and result.article and result.article.id is not None:
                proofreading_ids.append(result.article.id)
        self._reload_articles()
        QMessageBox.information(self, "导入结果", "\n".join(messages))
        for article_id in proofreading_ids:
            self._start_article_proofreading(article_id, automatic=True)

    def _proofread_selected_article(self) -> None:
        article_id = self._selected_article_id()
        if article_id is not None:
            self._start_article_proofreading(article_id, automatic=False)

    def _start_article_proofreading(self, article_id: int, *, automatic: bool) -> None:
        if article_id in self._proofreading_article_ids:
            if not automatic:
                QMessageBox.information(self, "文章检测", "这篇文章正在检测中，请稍候。")
            return
        article = self.context.article_library.get_article(article_id)
        if article is None:
            return
        try:
            provider = DeepSeekArticleProofreadingProvider(
                self.context.credential_store.get() or "",
                model=self.settings.translation_model,
                timeout=30.0,
            )
        except Exception as exc:
            message = str(exc) if isinstance(exc, ArticleProofreadingError) else "无法读取 DeepSeek API Key。"
            if not automatic or not self._proofreading_missing_key_notified:
                QMessageBox.information(self, "未执行文章检测", f"{message}\n文章已经正常保存，可在配置 Key 后点击“重新检测”。")
                self._proofreading_missing_key_notified = True
            return

        worker = ArticleProofreadingWorker(
            article_id,
            self.context.article_proofreading_service,
            provider,
            article.full_text,
        )
        self._proofreading_workers.add(worker)
        self._proofreading_article_ids.add(article_id)
        if self._selected_article_id() == article_id:
            self.proofread_button.setText("检测中…")
            self.proofread_button.setEnabled(False)
        worker.signals.completed.connect(
            lambda completed_id, result, current=worker: self._article_proofreading_completed(
                completed_id, result, current
            )
        )
        worker.signals.failed.connect(
            lambda failed_id, error, current=worker: self._article_proofreading_failed(
                failed_id, error, current
            )
        )
        self._thread_pool.start(worker)

    def _article_proofreading_completed(self, article_id: int, result, worker: ArticleProofreadingWorker) -> None:
        self._finish_article_proofreading(article_id, worker)
        article = self.context.article_library.get_article(article_id)
        if article is None:
            return
        if article.full_text != worker.text:
            QMessageBox.information(self, "检测结果已过期", "检测期间文章内容已经变化，请重新检测。")
            return
        if not result.issues and not result.differs_from(article.full_text):
            QMessageBox.information(self, "文章检测完成", f"《{article.title}》未发现明显的格式、拼写或单词错误。")
            return

        dialog = ArticleProofreadingDialog(article.title, article.full_text, result, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.context.article_library.replace_article_content(
                article_id,
                result.corrected_text,
                self.settings.section_target_characters,
            )
        except Exception as exc:
            QMessageBox.warning(self, "应用建议失败", str(exc))
            return
        self._reload_articles(preferred_article_id=article_id)
        QMessageBox.information(self, "文章已更新", "已应用建议并重新分段；本文进度已重置，历史练习记录仍然保留。")

    def _article_proofreading_failed(self, article_id: int, error: Exception, worker: ArticleProofreadingWorker) -> None:
        self._finish_article_proofreading(article_id, worker)
        if isinstance(error, ArticleProofreadingError) and error.category == "cancelled":
            return
        QMessageBox.warning(self, "文章检测失败", f"{error}\n文章内容没有发生更改，稍后可点击“重新检测”。")

    def _finish_article_proofreading(self, article_id: int, worker: ArticleProofreadingWorker) -> None:
        self._proofreading_workers.discard(worker)
        self._proofreading_article_ids.discard(article_id)
        if self._selected_article_id() == article_id:
            self.proofread_button.setText("重新检测")
            self.proofread_button.setEnabled(True)

    def _start_selected_article(self, mode: str) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            QMessageBox.information(self, "未选择文章", "请先选择一篇文章。")
            return
        self._persist_current_practice()
        material = self.context.practice_service.load_practice_material(article_id, mode=mode)
        self._begin_practice(material)

    def _begin_practice(self, material: PracticeMaterial) -> None:
        self.current_course_session = None
        self.current_material = material
        self.current_practice_saved = False
        self._sentence_attempt_ids = []
        use_sentence_mode = (
            self.settings.sentence_learning_enabled
            and material.practice_type in {"article", "article_section"}
            and material.section_id is not None
        )
        if use_sentence_mode:
            sentences = self.context.sentence_service.ensure_for_section(material.section_id)
            self.sentence_practice_view.start_practice(material, sentences, self.settings)
            self.stack.setCurrentWidget(self.sentence_practice_view)
        else:
            hints: list[tuple[int, int, str]] = []
            speech_segments: list[tuple[int, int, str]] = []
            show_translation_panel = material.practice_type in {"article", "article_section"} and material.section_id is not None
            if show_translation_panel:
                sentences = self.context.sentence_service.ensure_for_section(material.section_id)
                leading_whitespace = len(material.section_text) - len(material.section_text.lstrip())
                section_start = sentences[0].start_offset - leading_whitespace if sentences else 0
                for sentence in sentences:
                    cached = self.context.translation_service.get(sentence.sentence_hash)
                    translation = cached.chinese_translation if cached and cached.status == "completed" else ""
                    hints.append((sentence.start_offset - section_start, sentence.end_offset - section_start, translation))
                    speech_segments.append((sentence.start_offset - section_start, sentence.end_offset - section_start, sentence.normalized_text))
            self.practice_view.set_translation_hints(hints, visible=show_translation_panel)
            self.practice_view.set_speech_segments(speech_segments, visible=show_translation_panel, speed=self.settings.tts_speed)
            self.practice_view.start_practice(material, self.settings)
            self.stack.setCurrentWidget(self.practice_view)
        self.sidebar.hide()
        for button in self.nav_buttons.values():
            button.setProperty("active", "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _start_course_lesson(self, course_id: str, lesson_id: str, session_mode: str) -> None:
        self._persist_current_practice()
        self.current_course_capability_item = None
        self.current_course_return = (course_id, lesson_id)
        try:
            if self.context.course_progress_service.get_enrollment(course_id) is None:
                self.context.course_progress_service.enroll(course_id)
            course_session = self.context.course_learning_service.build_session(
                course_id,
                lesson_id,
                session_mode=session_mode,  # type: ignore[arg-type]
            )
        except Exception as exc:
            try:
                course = self.context.course_repository.get_course(course_id)
            except Exception:
                course = None
            self._logger.error(
                "course learning session failed course_id=%s course_stable_key=%s lesson_id=%s reason=%s",
                course_id,
                course.stable_key if course else None,
                lesson_id,
                exc,
            )
            QMessageBox.warning(
                self,
                "无法开始课程",
                f"这个 Day 暂时无法开始：{exc}\n请返回课程页面重新加载后再试。",
            )
            self._show_courses()
            return

        self.current_course_session = course_session
        self.current_material = PracticeMaterial(
            article_id=None,
            article_title=f"{course_session.course_title} · {course_session.lesson_title}",
            section_id=None,
            section_index=0,
            section_count=1,
            section_text=course_session.section_text,
            practice_type="course_lesson",
        )
        self.current_practice_saved = False
        self._sentence_attempt_ids = []
        self.sentence_practice_view.start_course_practice(
            self.current_material,
            list(course_session.typing_sentences),
            course_session.chinese_translations,
            course_session.activity_types_by_item,
            self.settings,
        )
        self.stack.setCurrentWidget(self.sentence_practice_view)
        self.sidebar.hide()
        for button in self.nav_buttons.values():
            button.setProperty("active", "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _start_course_capability(
        self, course_id: str, lesson_id: str, capability: str
    ) -> None:
        try:
            items = self.context.course_capability_service.lesson_items(
                course_id,
                lesson_id,
                capability if capability in {"dictation", "speaking"} else None,
            )
            if not items:
                raise ValueError("本 Day 没有可用的课程句子。")
            self.current_course_return = (course_id, lesson_id)
            if capability == "tts":
                listening = self.context.course_capability_service.lesson_items(
                    course_id, lesson_id, "review"
                )
                item = (listening or items)[0]
                self._request_course_speech(
                    item.text,
                    self.settings.tts_speed,
                    item.ref,
                    mark_listening=True,
                )
                return
            if capability == "dictation":
                self._open_course_dictation(items)
                return
            if capability == "speaking":
                self._open_course_pronunciation(items[0])
                return
            if capability == "vocabulary":
                words = self.context.course_capability_service.lesson_words(
                    course_id, lesson_id
                )
                self._open_course_vocabulary(words)
                return
            if capability == "review":
                for item in items:
                    self.context.course_capability_service.ensure_sentence_review(
                        item.ref, "sentence_listening"
                    )
                self._open_course_dictation(items)
                return
            raise ValueError(f"不支持的课程能力：{capability}")
        except Exception as exc:
            self._logger.error(
                "course capability start failed course_id=%s lesson_id=%s capability=%s reason=%s",
                course_id,
                lesson_id,
                capability,
                exc,
            )
            QMessageBox.warning(self, "课程能力不可用", str(exc))

    def _current_course_capability_item(self) -> CourseCapabilityItem | None:
        session = self.current_course_session
        if session is None:
            return self.current_course_capability_item
        if self.sentence_practice_view.learning is not None:
            session.sync_index(self.sentence_practice_view.learning.current_index)
        stable_key = session.current_item_stable_key
        if stable_key is None:
            return None
        try:
            return self.context.course_capability_service.item(
                session.course_id, stable_key
            )
        except Exception as exc:
            self._handle_course_state_error("课程内容已刷新", stable_key, exc)
            return None

    def _start_current_course_dictation(self) -> None:
        item = self._current_course_capability_item()
        if item is not None:
            self.current_course_return = (
                self.current_course_session.course_id,
                self.current_course_session.lesson_id,
            ) if self.current_course_session else self.current_course_return
            self._open_course_dictation((item,))

    def _start_current_course_pronunciation(self) -> None:
        item = self._current_course_capability_item()
        if item is not None:
            self.current_course_return = (
                self.current_course_session.course_id,
                self.current_course_session.lesson_id,
            ) if self.current_course_session else self.current_course_return
            self._open_course_pronunciation(item)

    def _show_current_course_words(self) -> None:
        item = self._current_course_capability_item()
        if item is not None:
            words = tuple(
                (item, occurrence)
                for occurrence in self.context.course_capability_service.extract_words(
                    item.ref
                )
            )
            self._open_course_vocabulary(words)

    def _add_current_course_review(self) -> None:
        item = self._current_course_capability_item()
        if item is None:
            return
        try:
            self.context.course_capability_service.ensure_sentence_review(item.ref)
            QMessageBox.information(self, "课程复习", "该句已加入课程 FSRS 复习。")
        except Exception as exc:
            QMessageBox.warning(self, "无法加入复习", str(exc))

    def _open_course_dictation(
        self, items: tuple[CourseCapabilityItem, ...]
    ) -> None:
        self.course_review_queue_active = False
        self.current_course_capability_item = items[0] if items else None
        self.dictation_page.load_course_items(list(items))
        self.stack.setCurrentWidget(self.dictation_page)
        self.sidebar.hide()

    def _open_course_pronunciation(self, item: CourseCapabilityItem) -> None:
        self.current_course_capability_item = item
        self.pronunciation_page.load_course_target(item)
        self.stack.setCurrentWidget(self.pronunciation_page)
        self.sidebar.hide()

    def _open_course_vocabulary(self, words) -> None:
        dialog = CourseVocabularyDialog(tuple(words), self)
        if not dialog.exec() or dialog.selected is None:
            return
        item, occurrence = dialog.selected
        try:
            result = self.context.course_capability_service.collect_word(
                item.ref,
                occurrence.source_word,
                start_offset=occurrence.start_offset,
                end_offset=occurrence.end_offset,
                typing_target_count=self.settings.vocabulary_typing_count,
            )
            if dialog.action == "review" and result.entry.id is not None:
                self.context.course_capability_service.ensure_vocabulary_review(
                    item.ref, result.entry.id, result.context.id
                )
            self._refresh_vocabulary_page()
            if result.entry.id is not None:
                self._start_vocabulary_enrichment(result.entry.id, result.context.id)
                self._open_word_learning(result.entry.id)
        except Exception as exc:
            QMessageBox.warning(self, "课程词汇不可用", str(exc))

    def _active_practice_view(self):
        return self.sentence_practice_view if self.stack.currentWidget() is self.sentence_practice_view else self.practice_view

    def _request_speech(self, text: str, speed: float, controls=None) -> None:
        content_ref = None
        mark_listening = False
        if (
            self.current_course_session is not None
            and self.stack.currentWidget() is self.sentence_practice_view
        ):
            item = self._current_course_capability_item()
            content_ref = item.ref if item is not None else None
            mark_listening = bool(
                item is not None and "review" in item.activity_types
            )
        self._request_speech_internal(
            text,
            speed,
            controls,
            content_ref,
            mark_listening=mark_listening,
        )

    def _request_course_speech(
        self,
        text: str,
        speed: float,
        content_ref: LearningContentRef,
        controls=None,
        *,
        mark_listening: bool = False,
    ) -> None:
        self._request_speech_internal(
            text,
            speed,
            controls,
            content_ref,
            mark_listening=mark_listening,
        )

    def _request_speech_internal(
        self,
        text: str,
        speed: float,
        controls,
        content_ref: LearningContentRef | None,
        *,
        mark_listening: bool = False,
    ) -> None:
        request = TTSRequest(
            text=text, content_type="sentence", model=self.settings.tts_model,
            voice_id=self.settings.tts_voice_id, speed=speed,
        )
        self._active_speech_control = controls
        self._active_speech_text = text
        self._active_speech_ref = content_ref
        self._active_course_activity_ref = (
            content_ref if mark_listening else None
        )
        if self._active_course_activity_ref is not None:
            try:
                self.context.course_capability_service.start_listening(
                    self._active_course_activity_ref
                )
            except Exception as exc:
                self._logger.error(
                    "course listening start failed item_stable_key=%s reason=%s",
                    self._active_course_activity_ref.item_stable_key,
                    exc,
                )
                self._active_course_activity_ref = None
        try:
            cached = (
                self.context.tts_service.get_cached_course(content_ref, request)
                if content_ref is not None
                else self.context.tts_service.get_cached(request)
            )
        except Exception as exc:
            self._logger.error(
                "tts cache read failed item_stable_key=%s reason=%s",
                content_ref.item_stable_key if content_ref is not None else None,
                exc,
            )
            message = "音频缓存暂时无法读取，请稍后重试。"
            if controls:
                controls.set_state("error", message)
            else:
                QMessageBox.warning(self, "语音不可用", message)
            if self._active_course_activity_ref is not None:
                failed_ref = self._active_course_activity_ref
                self._active_course_activity_ref = None
                try:
                    self.context.course_capability_service.fail_listening(failed_ref)
                except Exception as save_exc:
                    self._logger.error(
                        "course listening cache failure save failed item_stable_key=%s reason=%s",
                        failed_ref.item_stable_key,
                        save_exc,
                    )
            return
        if cached:
            self.context.tts_service.mark_played(cached.cache_key)
            self.audio_playback.toggle(cached.file_path)
            return
        try:
            key = self.context.tts_credential_store.get()
            provider = MiniMaxTTSProvider(key or "", timeout=15.0)
        except Exception as exc:
            message = (
                str(exc)
                if isinstance(exc, TTSProviderError)
                else "无法读取 MiniMax 凭据，请在设置中重新配置。"
            )
            if controls:
                controls.set_state("error", message)
            else:
                QMessageBox.information(self, "语音不可用", message)
            if self._active_course_activity_ref is not None:
                failed_ref = self._active_course_activity_ref
                self._active_course_activity_ref = None
                try:
                    self.context.course_capability_service.fail_listening(failed_ref)
                except Exception as save_exc:
                    self._logger.error(
                        "course listening credential failure save failed item_stable_key=%s reason=%s",
                        failed_ref.item_stable_key,
                        save_exc,
                    )
            return
        if controls: controls.set_state("loading", "生成中")
        worker = TTSWorker(
            self.context.tts_service, provider, request, content_ref=content_ref
        )
        self._tts_workers.add(worker)
        worker.signals.completed.connect(lambda item, audio, w=worker, ref=content_ref: self._speech_generated(item, audio, w, ref))
        worker.signals.failed.connect(lambda item, error, w=worker, ref=content_ref: self._speech_generation_failed(item, error, w, ref))
        self._thread_pool.start(worker)

    def _speech_generated(self, request, audio, worker, content_ref=None) -> None:
        self._tts_workers.discard(worker)
        if request.text != self._active_speech_text or content_ref != self._active_speech_ref:
            return
        self.context.tts_service.mark_played(audio.cache_key)
        self.audio_playback.toggle(audio.file_path)
        if self.audio_playback.is_playing() and self._active_speech_control:
            self._active_speech_control.set_state("playing")

    def _speech_generation_failed(self, request, error, worker, content_ref=None) -> None:
        self._tts_workers.discard(worker)
        if request.text == self._active_speech_text and content_ref == self._active_speech_ref:
            if self._active_speech_control:
                self._active_speech_control.set_state("error", str(error))
            elif content_ref is not None:
                QMessageBox.warning(self, "语音生成失败", str(error))
        if (
            request.text == self._active_speech_text
            and content_ref == self._active_course_activity_ref
            and content_ref is not None
        ):
            self._active_course_activity_ref = None
            try:
                self.context.course_capability_service.fail_listening(content_ref)
            except Exception as exc:
                self._logger.error(
                    "course listening generation failure save failed item_stable_key=%s reason=%s",
                    content_ref.item_stable_key,
                    exc,
                )

    def _speech_sentence_changed(self, text: str) -> None:
        if text != self._active_speech_text:
            self.audio_playback.stop()
            if self._active_speech_control:
                self._active_speech_control.set_state("ready")
            self._active_speech_text = text

    def _speech_playback_state_changed(self, state: str) -> None:
        if self._active_speech_control:
            self._active_speech_control.set_state(state)
        if state == "playing" and self._active_course_activity_ref is not None:
            content_ref = self._active_course_activity_ref
            self._active_course_activity_ref = None
            try:
                self.context.course_capability_service.complete_listening(content_ref)
                if self.current_course_return:
                    self.course_page.show_lesson(*self.current_course_return)
            except Exception as exc:
                self._logger.error(
                    "course listening completion failed item_stable_key=%s reason=%s",
                    content_ref.item_stable_key,
                    exc,
                )
        if state in {"stopped","finished"} and self.stack.currentWidget() in {self.practice_view,self.sentence_practice_view,self.word_learning_page}:
            self._track_learning_activity("audio_finished")

    def _speech_playback_failed(self, message: str) -> None:
        if self._active_speech_control:
            self._active_speech_control.set_state("error", message or "音频播放失败。")
        elif self._active_speech_ref is not None:
            QMessageBox.warning(
                self,
                "音频播放失败",
                message or "音频播放失败，请检查播放设备。",
            )
        if self._active_course_activity_ref is not None:
            content_ref = self._active_course_activity_ref
            self._active_course_activity_ref = None
            try:
                self.context.course_capability_service.fail_listening(content_ref)
            except Exception as exc:
                self._logger.error(
                    "course listening failure save failed item_stable_key=%s reason=%s",
                    content_ref.item_stable_key,
                    exc,
                )

    def _active_snapshot(self):
        view = self._active_practice_view()
        return view.current_snapshot() if view is self.sentence_practice_view else view.session.snapshot()

    def _save_sentence_attempt(self, attempt) -> None:
        if self.current_course_session is not None:
            if self.sentence_practice_view.learning is not None:
                self.current_course_session.sync_index(self.sentence_practice_view.learning.current_index)
            item_stable_key = self.current_course_session.current_item_stable_key
            if item_stable_key:
                try:
                    self.context.course_progress_service.complete_item(
                        self.current_course_session.course_id,
                        item_stable_key,
                    )
                except Exception as exc:
                    self._handle_course_state_error("保存课程进度失败", item_stable_key, exc)
            return
        with self.context.database.transaction() as connection:
            attempt_id = self._sentence_attempts.insert(connection, attempt)
        self._sentence_attempt_ids.append(attempt_id)

    def _handle_course_state_error(
        self,
        action: str,
        item_stable_key: str | None,
        exc: Exception,
    ) -> None:
        session = self.current_course_session
        self._logger.error(
            "course learning state error action=%s course_id=%s course_stable_key=%s lesson_stable_key=%s item_stable_key=%s reason=%s",
            action,
            session.course_id if session else None,
            session.course_stable_key if session else None,
            session.lesson_stable_key if session else None,
            item_stable_key,
            exc,
        )
        self.sentence_practice_view.state_label.setText(
            f"{action}。课程内容可能已刷新；当前输入仍可继续，退出后请重新加载课程。"
        )

    def _attach_sentence_attempts(self) -> None:
        session = self._active_practice_view().session
        if not self._sentence_attempt_ids or session is None or session.persisted_session_id is None:
            return
        with self.context.database.transaction() as connection:
            self._sentence_attempts.attach_to_session(connection, self._sentence_attempt_ids, session.persisted_session_id)

    def _request_sentence_translation(self, sentence, retry: bool = False) -> None:
        decision = self.context.translation_service.prepare(
            sentence,
            provider="deepseek",
            model=self.settings.translation_model,
            prompt_version=self.settings.translation_prompt_version,
            retry=retry,
        )
        if decision.cached and decision.cached.status == "completed":
            self.sentence_practice_view.show_translation(decision.cached, cached=True)
            return
        if not decision.should_request:
            if decision.cached and decision.cached.status == "failed":
                self.sentence_practice_view.show_translation_failed(decision.cached.error_message or "翻译失败")
            return
        self._handle_learning_update(self.context.learning_time_tracker.suspend_for_network())
        try:
            api_key = self.context.credential_store.get()
            provider = DeepSeekTranslationProvider(api_key or "", model=self.settings.translation_model, timeout=10.0)
        except Exception as exc:
            error = exc if isinstance(exc, TranslationProviderError) else TranslationProviderError("credential", "无法读取 API Key。")
            self.context.translation_service.fail(sentence.sentence_hash, error)
            self.sentence_practice_view.show_translation_failed(str(error))
            return
        index = self.sentence_practice_view.sentences.index(sentence)
        previous = self.sentence_practice_view.sentences[index - 1].normalized_text if index > 0 else ""
        following = self.sentence_practice_view.sentences[index + 1].normalized_text if index + 1 < len(self.sentence_practice_view.sentences) else ""
        worker = TranslationWorker(self.context.translation_service, provider, sentence, previous=previous, following=following)
        self._translation_workers.add(worker)
        worker.signals.completed.connect(lambda item, result, p=provider, w=worker: self._translation_completed(item, result, p, w))
        worker.signals.failed.connect(lambda item, error, w=worker: self._translation_failed(item, error, w))
        self._thread_pool.start(worker)

    def _translation_completed(self, sentence, result, provider, worker) -> None:
        self._translation_workers.discard(worker)
        cached = self.context.translation_service.complete(
            sentence.sentence_hash, result, provider=provider.name, model=provider.model,
            prompt_version=self.settings.translation_prompt_version,
        )
        current = self.sentence_practice_view.current_sentence
        if cached and current and current.sentence_hash == sentence.sentence_hash:
            self.sentence_practice_view.show_translation(cached)

    def _translation_failed(self, sentence, error, worker) -> None:
        self._translation_workers.discard(worker)
        provider_error = error if isinstance(error, TranslationProviderError) else TranslationProviderError("unknown", "翻译请求失败。")
        self.context.translation_service.fail(sentence.sentence_hash, provider_error)
        current = self.sentence_practice_view.current_sentence
        if current and current.sentence_hash == sentence.sentence_hash:
            self.sentence_practice_view.show_translation_failed(str(provider_error))

    def _edit_sentence_translation(self, sentence) -> None:
        cached = self.context.translation_service.get(sentence.sentence_hash)
        current = cached.chinese_translation if cached else ""
        text, accepted = QInputDialog.getMultiLineText(self, "编辑翻译", "中文翻译：", current)
        if accepted and text.strip():
            updated = self.context.translation_service.edit(sentence.sentence_hash, text.strip(), cached.key_expressions if cached else [])
            if updated:
                self.sentence_practice_view.show_translation(updated)
    def _rename_selected_article(self) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            return
        article = self.context.article_library.get_article(article_id)
        if article is None:
            return
        text, accepted = QInputDialog.getText(self, "重命名文章", "新的标题：", text=article.title)
        if accepted and text.strip():
            self.context.article_library.rename_article(article_id, text.strip())
            self._reload_articles()

    def _delete_selected_article(self) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            return
        answer = QMessageBox.question(self, "删除文章", "删除后文章会从列表中隐藏，但历史记录会保留。")
        if answer == QMessageBox.StandardButton.Yes:
            self.context.article_library.soft_delete_article(article_id)
            self._reload_articles()
            self._refresh_history()
            self._refresh_statistics()

    def _resegment_selected_article(self) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            return
        answer = QMessageBox.question(self, "重新分段", "重新分段会重置当前文章进度，但不会删除历史记录。")
        if answer == QMessageBox.StandardButton.Yes:
            self.context.article_library.resegment_article(article_id, self.settings.section_target_characters)
            self._reload_articles()

    def _save_settings(self) -> None:
        self.settings = self.context.settings_service.save_settings(self.settings_page.build_settings())
        self.context.fsrs_review_service.set_desired_retention(self.settings.fsrs_desired_retention)
        self._apply_settings()
        self.settings_page.status_label.setText("设置已保存，新练习会使用新的配置。")
        self._refresh_statistics()
        self._refresh_overview()

    def _save_api_key(self) -> None:
        api_key = self.settings_page.api_key_input.text().strip()
        if not api_key:
            QMessageBox.information(self, "未输入 Key", "请输入 DeepSeek API Key。")
            return
        try:
            self.context.credential_store.set(api_key)
            self.settings_page.api_key_input.clear()
            self.settings_page.set_api_key_status(mask_api_key(api_key))
            QMessageBox.information(self, "保存成功", "API Key 已保存到 Windows 凭据管理器。")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"无法保存 API Key：{exc}")

    def _delete_api_key(self) -> None:
        try:
            self.context.credential_store.delete()
            self.settings_page.api_key_input.clear()
            self.settings_page.set_api_key_status("未保存")
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", f"无法删除 API Key：{exc}")

    def _save_tts_key(self) -> None:
        key=self.settings_page.tts_api_key_input.text().strip()
        if not key: QMessageBox.information(self,"未输入 Key","请输入 MiniMax API Key。"); return
        try:
            self.context.tts_credential_store.set(key); self.settings_page.tts_api_key_input.clear(); self.settings_page.set_tts_api_key_status(mask_secret(key))
            QMessageBox.information(self,"保存成功","MiniMax API Key 已保存到 Windows 凭据管理器。")
        except Exception as exc: QMessageBox.critical(self,"保存失败",f"无法保存 MiniMax API Key：{exc}")

    def _delete_tts_key(self) -> None:
        try:
            self.context.tts_credential_store.delete(); self.settings_page.tts_api_key_input.clear(); self.settings_page.set_tts_api_key_status("未保存")
        except Exception as exc: QMessageBox.critical(self,"删除失败",f"无法删除 MiniMax API Key：{exc}")

    def _save_pronunciation_key(self) -> None:
        key = self.settings_page.pronunciation_key_input.text().strip()
        if not key:
            QMessageBox.information(self, "未输入 Key", "请输入 Azure Speech Key。")
            return
        try:
            self.context.pronunciation_credential_store.set(key)
            self.settings_page.pronunciation_key_input.clear()
            self.settings_page.set_pronunciation_key_status(mask_secret(key))
            QMessageBox.information(self, "保存成功", "Azure Speech Key 已保存到 Windows 凭据管理器。")
        except Exception as exc:
            QMessageBox.critical(self, "保存失败", f"无法保存 Azure Speech Key：{exc}")

    def _delete_pronunciation_key(self) -> None:
        try:
            self.context.pronunciation_credential_store.delete()
            self.settings_page.pronunciation_key_input.clear()
            self.settings_page.set_pronunciation_key_status("未保存")
        except Exception as exc:
            QMessageBox.critical(self, "删除失败", f"无法删除 Azure Speech Key：{exc}")

    def _test_tts_connection(self) -> None:
        try:
            provider=MiniMaxTTSProvider(self.context.tts_credential_store.get() or "", timeout=10.0)
        except Exception as exc: QMessageBox.warning(self,"连接失败",str(exc)); return
        request=TTSRequest(text="Hello.",model=str(self.settings_page.tts_model_combo.currentData()),voice_id=str(self.settings_page.tts_voice_combo.currentData()),speed=float(self.settings_page.tts_speed_combo.currentData()))
        worker=TTSWorker(self.context.tts_service,provider,request); self._tts_workers.add(worker)
        worker.signals.completed.connect(lambda _request,_audio,w=worker:self._tts_test_finished(True,"",w)); worker.signals.failed.connect(lambda _request,error,w=worker:self._tts_test_finished(False,str(error),w)); self._thread_pool.start(worker)

    def _tts_test_finished(self, success: bool, message: str, worker) -> None:
        self._tts_workers.discard(worker)
        if success: QMessageBox.information(self,"测试连接","MiniMax 语音连接成功。")
        else: QMessageBox.warning(self,"测试连接",message)
        stats=self.context.tts_service.stats(); self.settings_page.set_tts_cache_stats(stats.file_count,stats.total_size_bytes)

    def _clear_tts_cache(self) -> None:
        if self._tts_workers:
            QMessageBox.information(self, "语音生成中", "请等待当前语音生成完成后再清理缓存。")
            return
        if QMessageBox.question(self,"清理语音缓存","确定删除全部本地语音缓存吗？文章、翻译和练习记录不会受影响。") != QMessageBox.StandardButton.Yes: return
        self.audio_playback.stop(); self.context.tts_service.clear_cache(); self.settings_page.set_tts_cache_stats(0,0)

    def _test_api_connection(self) -> None:
        try:
            provider = DeepSeekTranslationProvider(self.context.credential_store.get() or "", model=self.settings_page.translation_model_combo.currentData(), timeout=10.0)
        except TranslationProviderError as exc:
            QMessageBox.warning(self, "连接失败", str(exc))
            return
        sentence = ArticleSentence(None, 0, 0, 0, "Hello.", "Hello.", "connection-test", 0, 6)
        worker = TranslationWorker(self.context.translation_service, provider, sentence)
        self._translation_workers.add(worker)
        worker.signals.completed.connect(lambda _sentence, _result, w=worker: self._api_test_finished(True, "连接成功", w))
        worker.signals.failed.connect(lambda _sentence, error, w=worker: self._api_test_finished(False, str(error), w))
        self._thread_pool.start(worker)

    def _api_test_finished(self, success: bool, message: str, worker) -> None:
        self._translation_workers.discard(worker)
        if success:
            QMessageBox.information(self, "测试连接", "DeepSeek 连接成功。")
        else:
            QMessageBox.warning(self, "测试连接", message)

    def _translate_selected_article(self) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            return
        self._translate_article(article_id)

    def _translate_current_article(self) -> None:
        if self.current_material is None or self.current_material.article_id is None:
            return
        self._translate_article(self.current_material.article_id)

    def _translate_article(self, article_id: int) -> None:
        try:
            api_key = self.context.credential_store.get()
            if not api_key:
                raise TranslationProviderError("missing_key", "请先在设置中保存 DeepSeek API Key。")
            self._bulk_provider = DeepSeekTranslationProvider(api_key, model=self.settings.translation_model, timeout=10.0)
        except Exception as exc:
            QMessageBox.warning(self, "无法开始翻译", str(exc))
            return
        sentences = []
        for section in self.context.article_library.get_sections(article_id):
            sentences.extend(self.context.sentence_service.ensure_for_section(section.id))
        cached_count = sum(1 for item in sentences if (cached := self.context.translation_service.get(item.sentence_hash)) and cached.status == "completed")
        request_count = len(sentences) - cached_count
        estimated = sum(len(item.normalized_text) for item in sentences if not self.context.translation_service.get(item.sentence_hash))
        answer = QMessageBox.question(
            self,
            "翻译整篇文章",
            f"本文共 {len(sentences)} 句\n已有翻译 {cached_count} 句\n本次需要翻译 {request_count} 句\n预计发送约 {estimated} 个英文字符（仅供参考）。\n\n是否继续？",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._bulk_queue = list(sentences)
        self._bulk_total = len(sentences)
        self._bulk_done = 0
        self._bulk_success = 0
        self._bulk_failed = 0
        self._bulk_retry_counts = {}
        self._bulk_cancelled = False
        self._bulk_progress = QProgressDialog("正在翻译文章……", "取消", 0, self._bulk_total, self)
        self._bulk_progress.setWindowTitle("翻译整篇文章")
        self._bulk_progress.setAutoClose(False)
        self._bulk_progress.canceled.connect(self._cancel_bulk_translation)
        self._bulk_progress.show()
        self._start_next_bulk_translation()

    def _start_next_bulk_translation(self) -> None:
        if not getattr(self, "_bulk_queue", None):
            if hasattr(self, "_bulk_progress"):
                self._bulk_progress.setValue(self._bulk_total)
                self._bulk_progress.setLabelText(f"完成：成功 {self._bulk_success}，失败 {self._bulk_failed}")
            return
        sentence = self._bulk_queue.pop(0)
        decision = self.context.translation_service.prepare(sentence, provider="deepseek", model=self.settings.translation_model, prompt_version=self.settings.translation_prompt_version)
        if not decision.should_request:
            self._bulk_done += 1
            self._bulk_success += int(bool(decision.cached and decision.cached.status == "completed"))
            self._bulk_progress.setValue(self._bulk_done)
            QTimer.singleShot(0, self._start_next_bulk_translation)
            return
        worker = TranslationWorker(self.context.translation_service, self._bulk_provider, sentence)
        self._translation_workers.add(worker)
        worker.signals.completed.connect(lambda item, result, w=worker: self._bulk_translation_completed(item, result, w))
        worker.signals.failed.connect(lambda item, error, w=worker: self._bulk_translation_failed(item, error, w))
        self._thread_pool.start(worker)

    def _bulk_translation_completed(self, sentence, result, worker) -> None:
        self._translation_workers.discard(worker)
        self.context.translation_service.complete(sentence.sentence_hash, result, provider=self._bulk_provider.name, model=self._bulk_provider.model, prompt_version=self.settings.translation_prompt_version)
        self._bulk_done += 1; self._bulk_success += 1
        self._bulk_progress.setValue(self._bulk_done)
        self._bulk_progress.setLabelText(f"{self._bulk_done} / {self._bulk_total} · 成功 {self._bulk_success} · 失败 {self._bulk_failed}")
        self._start_next_bulk_translation()

    def _bulk_translation_failed(self, sentence, error, worker) -> None:
        self._translation_workers.discard(worker)
        provider_error = error if isinstance(error, TranslationProviderError) else TranslationProviderError("unknown", "翻译失败")
        self.context.translation_service.fail(sentence.sentence_hash, provider_error)
        retryable = provider_error.category in {"rate_limit", "server", "timeout", "network"}
        retry_count = self._bulk_retry_counts.get(sentence.sentence_hash, 0)
        if retryable and retry_count < 2 and not self._bulk_cancelled:
            self._bulk_retry_counts[sentence.sentence_hash] = retry_count + 1
            delay_ms = 1000 * (2 ** retry_count)
            self._bulk_progress.setLabelText(f"请求暂时失败，{delay_ms // 1000} 秒后重试……")
            QTimer.singleShot(delay_ms, lambda item=sentence: self._retry_bulk_sentence(item))
            return
        self._bulk_done += 1; self._bulk_failed += 1
        self._bulk_progress.setValue(self._bulk_done)
        self._bulk_progress.setLabelText(f"{self._bulk_done} / {self._bulk_total} · 成功 {self._bulk_success} · 失败 {self._bulk_failed}")
        self._start_next_bulk_translation()

    def _retry_bulk_sentence(self, sentence) -> None:
        if self._bulk_cancelled:
            return
        decision = self.context.translation_service.prepare(
            sentence,
            provider="deepseek",
            model=self.settings.translation_model,
            prompt_version=self.settings.translation_prompt_version,
            retry=True,
        )
        if not decision.should_request:
            self._bulk_done += 1
            self._bulk_failed += 1
            self._start_next_bulk_translation()
            return
        worker = TranslationWorker(self.context.translation_service, self._bulk_provider, sentence)
        self._translation_workers.add(worker)
        worker.signals.completed.connect(lambda item, result, w=worker: self._bulk_translation_completed(item, result, w))
        worker.signals.failed.connect(lambda item, error, w=worker: self._bulk_translation_failed(item, error, w))
        self._thread_pool.start(worker)

    def _cancel_bulk_translation(self) -> None:
        self._bulk_cancelled = True
        self._bulk_queue = []
        if hasattr(self, "_bulk_progress"):
            self._bulk_progress.setLabelText("已取消，已完成的翻译仍保存在缓存中。")
    def _open_data_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.context.paths.data_dir)))

    def _backup_database(self) -> None:
        try:
            backup = self.context.data_management_service.backup_database()
            QMessageBox.information(self, "备份完成", f"数据库备份已保存：\n{backup}")
        except Exception as exc:
            QMessageBox.critical(self, "备份失败", f"无法创建数据库备份：\n{exc}")

    def _restore_database(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择数据库备份", str(self.context.paths.backups_dir), "SQLite 数据库 (*.db);;所有文件 (*.*)")
        if not path:
            return
        answer = QMessageBox.warning(
            self,
            "恢复数据库",
            "恢复会替换当前数据库。程序会先创建当前数据的安全备份；Windows 凭据管理器中的 API Key 不受影响。是否继续？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            safety_backup = self.context.data_management_service.restore_database(Path(path))
            self.settings = self.context.settings_service.get_settings()
            self._apply_settings()
            self._reload_articles()
            self._refresh_history()
            self._refresh_statistics()
            self._refresh_vocabulary_page()
            self._refresh_daily_learning()
            QMessageBox.information(self, "恢复完成", f"数据库已恢复。恢复前的安全备份：\n{safety_backup}")
        except Exception as exc:
            QMessageBox.critical(self, "恢复失败", f"数据库未能恢复：\n{exc}")

    def _export_diagnostics(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "选择诊断日志保存位置", str(self.context.paths.data_dir))
        if not directory:
            return
        try:
            archive = self.context.data_management_service.export_diagnostics(Path(directory))
            QMessageBox.information(self, "导出完成", f"诊断日志已导出：\n{archive}")
        except Exception as exc:
            QMessageBox.critical(self, "导出失败", f"无法导出诊断日志：\n{exc}")

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "关于 English Studio",
            "English Studio\n通过阅读、打字、听写和复习学习英语\n\n"
            "本程序默认把学习数据保存在本机。在线翻译、语音和发音评分仅在你主动配置对应服务后使用。\n\n"
            "版本信息与隐私说明请查看项目 README、PRIVACY.md 和 THIRD_PARTY_NOTICES.md。",
        )

    def _leave_practice_view(self) -> None:
        self.audio_playback.stop()
        if not self._confirm_leave_practice():
            return
        if self.current_course_session is not None:
            course_id = self.current_course_session.course_id
            lesson_id = self.current_course_session.lesson_id
            self.current_course_session = None
            self.current_course_return = None
            self.current_material = None
            self._show_courses()
            self.course_page.show_lesson(course_id, lesson_id)
            return
        if self.current_material and self.current_material.practice_type not in {"article", "article_section"}:
            self._show_special_practice()
        else:
            self._show_library()

    def _persist_current_practice(self) -> None:
        if self.current_practice_saved:
            return
        if self.current_course_session is not None:
            if self.sentence_practice_view.learning is not None:
                self.current_course_session.sync_index(self.sentence_practice_view.learning.current_index)
            self.current_practice_saved = True
            return
        if self.current_material is None or self._active_practice_view().session is None:
            self.current_practice_saved = True
            return
        snapshot = self._active_snapshot()
        self.context.practice_service.save_interrupted_session(
            self.current_material,
            self._active_practice_view().session,
            snapshot,
        )
        self.current_practice_saved = True
        self._attach_sentence_attempts()
        self._refresh_history()
        self._refresh_statistics()
        self._refresh_special_practice_page()

    def _confirm_leave_practice(self) -> bool:
        if self.current_course_session is not None:
            self._persist_current_practice()
            return True
        if self.current_practice_saved or self.current_material is None or self._active_practice_view().session is None:
            self._persist_current_practice()
            return True
        snapshot = self._active_snapshot()
        if snapshot.total_keystrokes == 0 and snapshot.position == self.current_material.resume_character_index:
            self.current_practice_saved = True
            return True
        answer = QMessageBox.question(
            self,
            "结束练习",
            "退出前是否保存当前进度？",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        if answer == QMessageBox.StandardButton.Save:
            self._persist_current_practice()
        else:
            self.current_practice_saved = True
        return True

    def _handle_session_completed(self, snapshot) -> None:
        if self.current_material is None or self._active_practice_view().session is None:
            return
        if self.current_course_session is not None:
            self._handle_course_session_completed(snapshot)
            return
        next_material = self.context.practice_service.save_completed_session(
            self.current_material,
            self._active_practice_view().session,
            snapshot,
        )
        self.current_practice_saved = True
        self._attach_sentence_attempts()
        if self.current_material.practice_set_id is not None:
            self.context.special_practice_service.note_set_practiced(self.current_material.practice_set_id)
        correct_words=self._count_correct_words(self._active_practice_view().session)
        self.context.learning_time_tracker.activity("correct_words",related_article_id=self.current_material.article_id,metadata={"count":correct_words})
        self._handle_learning_update(self.context.learning_time_tracker.flush())
        self.context.learning_time_tracker.activity("section_completed",related_article_id=self.current_material.article_id)
        review_changes = []
        if self.current_material.practice_type == "vocabulary_review" and self.current_material.practice_set_id is not None:
            mistaken = {
                self.context.normalization_service.normalize(error.word)
                for error in self._active_practice_view().session.errors
                if self.context.normalization_service.normalize(error.word)
            }
            review_changes = self.context.special_practice_service.apply_review_results(
                self.current_material.practice_set_id,
                mistaken_words=mistaken,
                completed=True,
            )
        self._refresh_history()
        self._refresh_statistics()
        self._refresh_special_practice_page()
        self._refresh_vocabulary_page()

        extra_lines = []
        if self.stack.currentWidget() is self.sentence_practice_view:
            timing = self.sentence_practice_view.learning.timing_snapshot()
            extra_lines.extend([
                f"总学习时间：{timing.total_elapsed_seconds:.1f} 秒",
                f"翻译阅读时间：{timing.learning_seconds:.1f} 秒",
                f"自动暂停时间：{timing.idle_seconds:.1f} 秒",
                f"手动暂停时间：{timing.manual_paused_seconds:.1f} 秒",
            ])
        if review_changes:
            extra_lines.extend(
                f"{change['word']}：熟练度 {change['mastery_level']}，下次复习 {change['next_review_at']}"
                for change in review_changes[:6]
            )
        dialog = ResultDialog(
            self._active_practice_view().session,
            snapshot,
            has_next_section=next_material is not None,
            title="练习完成" if self.current_material.practice_type in {"article", "article_section"} else "专项练习完成",
            extra_lines=extra_lines,
            allow_retry_errors=self.current_material.practice_type != "article",
            parent=self,
        )
        dialog.exec()

        if dialog.action == "next" and next_material is not None:
            self._begin_practice(next_material)
            return
        if dialog.action == "restart":
            restarted = replace(self.current_material, resume_character_index=0)
            self._begin_practice(restarted)
            return
        if dialog.action == "retry_errors":
            retry_material = self._build_retry_errors_material()
            if retry_material is not None:
                self._begin_practice(retry_material)
                return
        self._leave_practice_view()

    def _handle_course_session_completed(self, snapshot) -> None:
        course_session = self.current_course_session
        typing_session = self.sentence_practice_view.session
        if course_session is None or typing_session is None:
            return
        self.current_practice_saved = True
        correct_words = self._count_correct_words(typing_session)
        self.context.learning_time_tracker.activity(
            "course_correct_words",
            metadata={"count": correct_words},
        )
        self.context.learning_time_tracker.activity("course_lesson_completed")
        self._handle_learning_update(self.context.learning_time_tracker.flush())

        next_lesson = None
        extra_lines: list[str] = []
        try:
            lesson_progress = self.context.course_progress_service.get_lesson_progress(
                course_session.course_id,
                course_session.lesson_id,
            )
            course_progress = self.context.course_progress_service.get_course_progress(
                course_session.course_id
            )
            next_lesson = self.context.course_progress_service.get_next_lesson(
                course_session.course_id
            )
            extra_lines.extend(
                [
                    f"Day 进度：{lesson_progress.completed_required_items}/{lesson_progress.total_required_items}",
                    f"课程总进度：{course_progress.completion_percentage:.0f}%",
                ]
            )
        except Exception as exc:
            self._handle_course_state_error("刷新课程进度失败", None, exc)
            extra_lines.append("课程进度暂时无法刷新，请返回课程页重新加载。")
        if self.sentence_practice_view.learning is not None:
            timing = self.sentence_practice_view.learning.timing_snapshot()
            extra_lines.extend(
                [
                    f"总学习时间：{timing.total_elapsed_seconds:.1f} 秒",
                    f"译文阅读时间：{timing.learning_seconds:.1f} 秒",
                ]
            )
        self.course_page.reload()
        dialog = ResultDialog(
            typing_session,
            snapshot,
            has_next_section=next_lesson is not None,
            title="课程 Day 完成",
            extra_lines=extra_lines,
            next_button_text="学习下一课",
            parent=self,
        )
        dialog.exec()
        if dialog.action == "next" and next_lesson is not None:
            self._start_course_lesson(
                course_session.course_id,
                next_lesson.lesson_id,
                "recommended",
            )
            return
        if dialog.action == "restart":
            self._start_course_lesson(
                course_session.course_id,
                course_session.lesson_id,
                "review",
            )
            return
        self._leave_practice_view()

    @staticmethod
    def _count_correct_words(session) -> int:
        typed={item.position:item.is_correct for item in session.typed_characters}
        count=0
        for match in re.finditer(r"[A-Za-z]+(?:['’][A-Za-z]+)*(?:-[A-Za-z]+)*",session.content):
            positions=range(match.start(),match.end())
            if all(position in typed and typed[position] for position in positions):count+=1
        return count

    def _build_retry_errors_material(self) -> PracticeMaterial | None:
        if self._active_practice_view().session is None or self.current_material is None:
            return None
        wrong_words = [
            self.context.normalization_service.normalize(error.word)
            for error in self._active_practice_view().session.errors
            if self.context.normalization_service.normalize(error.word)
        ]
        if not wrong_words:
            QMessageBox.information(self, "没有可重练内容", "本次没有错误单词可重练。")
            return None
        display_words = [word for word, _ in Counter(wrong_words).most_common()]
        text = "\n".join(display_words)
        return PracticeMaterial(
            article_id=None,
            article_title="本次错词重练",
            section_id=None,
            section_index=0,
            section_count=1,
            section_text=text,
            practice_type="mixed_review",
            source_items=display_words,
        )

    def _generate_special_preview(self, payload: dict) -> None:
        mode = payload["mode"]
        generated = None
        if mode == "error_words":
            generated = self.context.special_practice_service.generate_error_word_set(
                range_key=payload["range_key"],
                word_count=payload["count"],
                repeat_count=payload["repeat_count"],
                arrangement=payload["arrangement"],
            )
        elif mode == "error_characters":
            generated = self.context.special_practice_service.generate_error_character_set(
                range_key=payload["range_key"],
                top_count=payload["count"],
            )
        elif mode == "context_sentences":
            generated = self.context.special_practice_service.generate_context_sentence_set(
                range_key=payload["range_key"],
                sentence_count=payload["count"],
            )
        elif mode == "vocabulary_review":
            generated = self.context.special_practice_service.generate_vocabulary_review_set(
                due_only=False,
                limit=payload["count"],
            )
        if generated is None:
            self.preview_special_material = None
            self.special_practice_page.set_preview("", "当前条件下还没有可生成的练习内容。")
            return
        self.preview_special_material = generated.material
        self.special_practice_page.set_preview(generated.preview_text, generated.message)
        self._refresh_special_practice_page()

    def _start_preview_special_practice(self) -> None:
        if self.preview_special_material is None:
            QMessageBox.information(self, "没有预览内容", "先生成预览，再开始练习。")
            return
        self._persist_current_practice()
        self._begin_practice(self.preview_special_material)

    def _start_saved_special_practice(self, practice_set_id: int) -> None:
        self._persist_current_practice()
        material = self.context.special_practice_service.get_material_for_set(practice_set_id)
        self._begin_practice(material)

    def _start_today_review(self) -> None:
        self._start_fsrs_review()

    def _add_vocabulary_word(self, word: str) -> None:
        try:
            result=self.context.vocabulary_learning_service.collect(word,typing_target_count=self.settings.vocabulary_typing_count)
        except ValueError as exc:
            QMessageBox.warning(self, "无效单词", str(exc))
            return
        self._refresh_vocabulary_page()
        self.vocabulary_page.set_status_message("已加入单词本。" if result.entry_created else "该单词已收藏。")
        if result.entry.id and self.settings.vocabulary_auto_enrich: self._start_vocabulary_enrichment(result.entry.id,result.context.id)

    def _save_vocabulary_item(self, item_id: int, meaning: str, note: str) -> None:
        self.context.special_practice_service.update_vocabulary_details(item_id, meaning, note)
        self._refresh_vocabulary_page()
        self.vocabulary_page.set_status_message("释义和备注已保存。")

    def _set_vocabulary_archived(self, item_id: int, archived: bool) -> None:
        self.context.special_practice_service.set_vocabulary_archived(item_id, archived)
        self._refresh_vocabulary_page()
        self._refresh_special_practice_page()
        self.vocabulary_page.set_status_message("生词状态已更新。")

    def _set_vocabulary_mastery(self, item_id: int, mastered: bool) -> None:
        self.context.vocabulary_learning_service.set_mastered(item_id,mastered)
        self._refresh_vocabulary_page()
        self._refresh_special_practice_page()
        self.vocabulary_page.set_status_message("熟练度状态已更新。")

    def _collect_selected_word(self, text: str, start: int, end: int) -> None:
        if self.current_course_session is not None:
            item = self._current_course_capability_item()
            if item is None:
                return
            try:
                result = self.context.course_capability_service.collect_word(
                    item.ref,
                    text,
                    start_offset=start,
                    end_offset=end,
                    typing_target_count=self.settings.vocabulary_typing_count,
                )
                QMessageBox.information(self, "课程词汇", "已收藏该课程语境中的单词。")
                self._refresh_vocabulary_page()
                if result.entry.id and self.settings.vocabulary_auto_enrich:
                    self._start_vocabulary_enrichment(
                        result.entry.id, result.context.id
                    )
            except Exception as exc:
                QMessageBox.warning(self, "课程词汇不可用", str(exc))
            self.sentence_practice_view._restore_focus()
            return
        view=self._active_practice_view(); sentence=""; article_sentence_id=None; local_start=start
        if view is self.sentence_practice_view and view.current_sentence:
            current=view.current_sentence; sentence=current.normalized_text; article_sentence_id=current.id
        elif self.current_material:
            sentence=self.current_material.section_text
            if self.current_material.section_id:
                sentences=self.context.sentence_service.ensure_for_section(self.current_material.section_id)
                leading_whitespace=len(self.current_material.section_text)-len(self.current_material.section_text.lstrip())
                section_start=sentences[0].start_offset-leading_whitespace if sentences else 0
                for item in sentences:
                    a=item.start_offset-section_start; b=item.end_offset-section_start
                    if a<=start<b: sentence=item.normalized_text; article_sentence_id=item.id; local_start=start-a; break
        try:
            result=self.context.vocabulary_learning_service.collect(text,sentence=sentence,
                article_id=self.current_material.article_id if self.current_material else None,
                article_sentence_id=article_sentence_id,start_offset=local_start,end_offset=local_start+len(text),
                typing_target_count=self.settings.vocabulary_typing_count)
        except ValueError as exc:
            QMessageBox.information(self,"收藏单词",str(exc)); view._restore_focus(); return
        message="已加入新的来源句。" if not result.entry_created and result.context_created else "该单词已收藏。" if not result.context_created else "已加入单词本。"
        QMessageBox.information(self,"收藏单词",message); view._restore_focus(); self._refresh_vocabulary_page()
        if result.entry.id and self.settings.vocabulary_auto_enrich:self._start_vocabulary_enrichment(result.entry.id,result.context.id)

    def _start_vocabulary_enrichment(self, entry_id: int, context_id: int | None, *, force: bool=False) -> None:
        entry=self.context.vocabulary_learning_service.repository.get_entry(entry_id)
        context=self.context.vocabulary_learning_service.repository.get_context(context_id) if context_id else None
        not_found_fresh=entry and entry.dictionary_status=="not_found" and entry.dictionary_fetched_at and (datetime.now()-entry.dictionary_fetched_at).days<7
        if entry and not force and (entry.dictionary_status=="ready" or not_found_fresh):
            self._update_word_enrichment_status(entry_id,context_id); return
        if (entry_id,"dictionary") in self._enrichment_loading:return
        if self._is_current_word(entry_id,context_id):self._handle_learning_update(self.context.learning_time_tracker.suspend_for_network())
        self._enrichment_errors.pop((entry_id,"dictionary"),None); self._enrichment_loading.add((entry_id,"dictionary")); self._update_word_enrichment_status(entry_id,context_id)
        task=VocabularyTask(lambda:self.context.vocabulary_learning_service.lookup_dictionary(entry_id,FreeDictionaryProvider()))
        self._vocabulary_workers.add(task)
        task.signals.completed.connect(lambda result,t=task:self._dictionary_enriched(entry_id,context_id,result,t))
        task.signals.failed.connect(lambda error,t=task:self._vocabulary_task_failed(entry_id,context_id,"dictionary",error,t))
        self._thread_pool.start(task)

    def _dictionary_enriched(self,entry_id,context_id,result,task):
        self._vocabulary_workers.discard(task); self._enrichment_loading.discard((entry_id,"dictionary")); self.context.vocabulary_learning_service.apply_dictionary_result(entry_id,result); self._refresh_vocabulary_page()
        self._refresh_open_word_details(entry_id,context_id); self._update_word_enrichment_status(entry_id,context_id)

    def _start_word_explanation(self,context_id:int, *, force: bool=False):
        try:
            payload,context=self.context.vocabulary_learning_service.build_explanation_request(context_id)
            if context.is_manual or (context.ai_status in {"ready","failed"} and not force):
                self._update_word_enrichment_status(context.vocabulary_entry_id,context_id); return
            provider=DeepSeekWordExplanationProvider(self.context.credential_store.get() or "",model=self.settings.translation_model)
        except Exception as exc:
            entry_id=context.vocabulary_entry_id if "context" in locals() else 0
            if entry_id:self._enrichment_errors[(entry_id,"ai")]=str(exc); self._update_word_enrichment_status(entry_id,context_id)
            return
        entry_id=context.vocabulary_entry_id
        if (entry_id,"ai") in self._enrichment_loading:return
        if self._is_current_word(entry_id,context_id):self._handle_learning_update(self.context.learning_time_tracker.suspend_for_network())
        self._enrichment_errors.pop((entry_id,"ai"),None); self._enrichment_loading.add((entry_id,"ai")); self._update_word_enrichment_status(entry_id,context_id)
        task=VocabularyTask(lambda:provider.explain(**payload)); self._vocabulary_workers.add(task)
        task.signals.completed.connect(lambda result,t=task:self._word_explained(context_id,result,t)); task.signals.failed.connect(lambda error,t=task:self._vocabulary_task_failed(entry_id,context_id,"ai",error,t)); self._thread_pool.start(task)

    def _word_explained(self,context_id,result,task):
        self._vocabulary_workers.discard(task); context=self.context.vocabulary_learning_service.repository.get_context(context_id)
        if not context:return
        entry_id=context.vocabulary_entry_id; self._enrichment_loading.discard((entry_id,"ai")); self.context.vocabulary_learning_service.apply_explanation_result(context_id,result); self._refresh_vocabulary_page()
        context=self.context.vocabulary_learning_service.repository.get_context(context_id)
        if context:self._refresh_open_word_details(context.vocabulary_entry_id,context_id); self._update_word_enrichment_status(context.vocabulary_entry_id,context_id)

    def _vocabulary_task_failed(self,entry_id:int,context_id:int|None,kind:str,error,task):
        self._vocabulary_workers.discard(task); self._enrichment_loading.discard((entry_id,kind)); self._enrichment_errors[(entry_id,kind)]=error
        if kind=="ai" and context_id:self.context.vocabulary_learning_service.mark_explanation_failed(context_id)
        self._update_word_enrichment_status(entry_id,context_id)

    def _open_word_learning(self,entry_id:int):
        rows=self._current_vocabulary_rows(); ids=[]
        for row in rows:
            if row.get("status")=="mastered":continue
            item_id=row.get("id")
            if not item_id and row.get("display_word"):
                source=row.get("source_sentence","") or ""; local=max(source.find(row["display_word"]),0)
                collected=self.context.vocabulary_learning_service.collect(row["display_word"],sentence=source,article_id=self.current_vocabulary_article_id,start_offset=local,end_offset=local+len(row["display_word"]),typing_target_count=self.settings.vocabulary_typing_count)
                item_id=collected.entry.id
            if item_id:ids.append(int(item_id))
        ids=[entry_id]+[item for item in ids if item!=entry_id]
        items=[]
        for item_id in ids:
            entry,contexts,state=self.context.vocabulary_learning_service.detail(item_id)
            if entry and state:items.append((entry,contexts,state))
        if not items:return
        self.word_learning_page.load_queue(items); self.stack.setCurrentWidget(self.word_learning_page); self.sidebar.hide()
        if self.word_learning_page.entry:self._ensure_current_word_enrichment(self.word_learning_page.entry.id)

    def _current_vocabulary_rows(self):
        return list(getattr(self.vocabulary_page,"_rows",[]))

    def _is_current_word(self,entry_id:int,context_id:int|None) -> bool:
        if self.stack.currentWidget() is not self.word_learning_page or not self.word_learning_page.entry or self.word_learning_page.entry.id!=entry_id:return False
        return context_id is None or (self.word_learning_page.current_context and self.word_learning_page.current_context.id==context_id)

    def _refresh_open_word_details(self,entry_id:int,context_id:int|None=None):
        if not self._is_current_word(entry_id,context_id):return
        entry,contexts,state=self.context.vocabulary_learning_service.detail(entry_id)
        if entry and state:self.word_learning_page.update_details(entry,contexts,state)

    def _update_word_enrichment_status(self,entry_id:int,context_id:int|None) -> None:
        if not self._is_current_word(entry_id,context_id):return
        entry=self.context.vocabulary_learning_service.repository.get_entry(entry_id); context=self.context.vocabulary_learning_service.repository.get_context(context_id) if context_id else None
        if not entry:return
        loading_dict=(entry_id,"dictionary") in self._enrichment_loading; loading_ai=(entry_id,"ai") in self._enrichment_loading
        dict_error=self._enrichment_errors.get((entry_id,"dictionary")); ai_error=self._enrichment_errors.get((entry_id,"ai"))
        if dict_error or ai_error:
            detail="；".join(filter(None,("词典获取失败" if dict_error else "","中文讲解获取失败" if ai_error else "")))
            if ai_error and "Key" in ai_error:self.word_learning_page.set_enrichment_status("未配置 DeepSeek Key",True)
            else:self.word_learning_page.set_enrichment_status(f"{detail}，可重试",True)
            return
        labels=[]
        if loading_dict:labels.append("正在获取词典")
        elif entry.dictionary_status=="not_found":labels.append("词典未找到")
        elif entry.dictionary_status=="ready":labels.append("词典已完成")
        if context:
            if loading_ai:labels.append("正在获取中文讲解")
            elif context.ai_status=="failed":labels.append("中文讲解获取失败")
            elif context.ai_status=="ready":labels.append("中文讲解已完成")
        self.word_learning_page.set_enrichment_status("；".join(labels) or "等待获取",False)

    def _retry_current_word_enrichment(self,entry_id:int,context_id:int|None) -> None:
        self._enrichment_errors.pop((entry_id,"dictionary"),None); self._enrichment_errors.pop((entry_id,"ai"),None)
        self._start_vocabulary_enrichment(entry_id,context_id,force=True)
        if context_id:self._start_word_explanation(context_id,force=True)

    def _ensure_current_word_enrichment(self,entry_id:int):
        entry,contexts,_=self.context.vocabulary_learning_service.detail(entry_id)
        if not entry:return
        context_id=contexts[0].id if contexts else None
        if self.settings.vocabulary_auto_enrich:
            self._start_vocabulary_enrichment(entry_id,context_id)
            if context_id:self._start_word_explanation(context_id)

    def _ensure_current_context_enrichment(self,context_id:int):
        page=self.word_learning_page
        if not page.entry or not self.settings.vocabulary_auto_enrich:return
        self._start_vocabulary_enrichment(page.entry.id,context_id)
        self._start_word_explanation(context_id)

    def _record_vocabulary_attempt(self,attempt:VocabularyAttempt):
        self.context.vocabulary_learning_service.record_attempt(attempt)
        if self.word_learning_page.entry:
            self.word_learning_page.state=self.context.vocabulary_learning_service.repository.get_state(self.word_learning_page.entry.id)
            if self.word_learning_page.queue:self.word_learning_page.queue[self.word_learning_page.queue_index]=(self.word_learning_page.entry,self.word_learning_page.contexts,self.word_learning_page.state)
            self.word_learning_page._update_prompt()

    def _play_vocabulary_word(self,entry_id:int):
        entry,contexts,_=self.context.vocabulary_learning_service.detail(entry_id)
        if entry:self._play_word_from_learning(entry,contexts[0] if contexts else None)

    def _play_dictation_audio(self, text: str, speed: float) -> None:
        """Prefer the cached dictionary recording for a word, otherwise use cached/generated TTS."""
        item = self.dictation_page.current
        if item and self.dictation_page.kind.currentData() == "word":
            self._play_word_from_learning(item.entry, item.context, focus_widget=self.dictation_page.input, speed=speed)
            return
        self._request_speech(text, speed)

    def _play_course_dictation_audio(
        self, item: CourseCapabilityItem, speed: float
    ) -> None:
        self.current_course_capability_item = item
        self._request_course_speech(item.text, speed, item.ref)

    def _play_word_from_learning(self,entry,context,focus_widget=None,speed=None):
        from english_typing_trainer.services.dictionary_provider import parse_dictionary_payload
        audio_url=""
        if isinstance(entry.dictionary_payload,list) and entry.dictionary_payload:
            try:audio_url=parse_dictionary_payload(entry.normalized_word,entry.dictionary_payload).audio_url
            except Exception:pass
        playback_speed = self.settings.tts_speed if speed is None else speed
        if audio_url:
            task=VocabularyTask(lambda:self.context.dictionary_audio_service.get_or_download(audio_url,entry.display_word)); self._vocabulary_workers.add(task)
            task.signals.completed.connect(lambda audio,t=task,w=focus_widget:self._dictionary_audio_ready(audio,t,w)); task.signals.failed.connect(lambda _error,t=task,w=focus_widget,s=playback_speed:self._dictionary_audio_fallback(entry.display_word,t,w,s)); self._thread_pool.start(task)
        else:self._request_speech(entry.display_word,playback_speed)

    def _dictionary_audio_ready(self,audio,task,focus_widget=None):
        self._vocabulary_workers.discard(task); self.context.tts_service.mark_played(audio.cache_key); self.audio_playback.toggle(audio.file_path); (focus_widget or self.word_learning_page.input).setFocus()

    def _dictionary_audio_fallback(self,word,task,focus_widget=None,speed=None):
        self._vocabulary_workers.discard(task); self._request_speech(word,self.settings.tts_speed if speed is None else speed)

    def _delete_vocabulary_entry(self,entry_id:int):
        if QMessageBox.question(self,"删除单词","确定删除该词条、来源和学习记录吗？")!=QMessageBox.StandardButton.Yes:return
        self.context.vocabulary_learning_service.delete(entry_id); self._refresh_vocabulary_page()

    def _review_single_vocabulary(self, item_id: int) -> None:
        generated = self.context.special_practice_service.generate_vocabulary_review_set(due_only=False, item_ids=[item_id])
        if generated is None:
            QMessageBox.information(self, "无法开始复习", "这个单词暂时无法载入复习。")
            return
        self.preview_special_material = generated.material
        self.special_practice_page.set_preview(generated.preview_text, generated.message)
        self._begin_practice(generated.material)

    def _show_session_detail(self, session_id: int) -> None:
        session_row, error_rows = self.context.history_service.get_session_detail(session_id)
        if session_row is None:
            QMessageBox.information(self, "记录不存在", "这条练习记录已不存在。")
            self._refresh_history()
            return
        dialog = SessionDetailDialog(session_row, error_rows, self)
        dialog.exec()

    def _delete_session(self, session_id: int) -> None:
        answer = QMessageBox.question(self, "删除练习记录", "删除后将同时移除该次练习的详细错误记录。")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.context.history_service.delete_session(session_id)
        self._refresh_history()
        self._refresh_statistics()

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._confirm_leave_practice():
            event.ignore()
            return
        self.audio_playback.stop()
        self.context.recording_service.cancel()
        self._handle_learning_update(self.context.learning_time_tracker.stop())
        for worker in self._tts_workers:
            worker.cancel()
        for worker in self._proofreading_workers:
            worker.cancel()
        self._thread_pool.clear()
        self._thread_pool.waitForDone(10000)
        super().closeEvent(event)
