from __future__ import annotations

from collections import Counter
from dataclasses import replace

from PySide6.QtCore import Qt, QTimer, QUrl, QThreadPool
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
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QStyle,
)

from english_typing_trainer.application.context import AppContext
from english_typing_trainer.models.article import Article
from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.settings import AppSettings
from english_typing_trainer.models.sentence import ArticleSentence
from english_typing_trainer.services.credential_store import mask_api_key
from english_typing_trainer.database.sentence_repositories import SentenceAttemptRepository
from english_typing_trainer.services.translation_provider import DeepSeekTranslationProvider, TranslationProviderError
from english_typing_trainer.ui.history_page import HistoryPage
from english_typing_trainer.ui.practice_view import PracticeView
from english_typing_trainer.ui.result_dialog import ResultDialog
from english_typing_trainer.ui.segmented_control import SegmentedControl
from english_typing_trainer.ui.session_detail_dialog import SessionDetailDialog
from english_typing_trainer.ui.sentence_practice_view import SentencePracticeView
from english_typing_trainer.ui.translation_tasks import TranslationWorker
from english_typing_trainer.ui.settings_page import SettingsPage as SettingsScreen
from english_typing_trainer.ui.special_practice_page import SpecialPracticePage
from english_typing_trainer.ui.statistics_page import StatisticsPage
from english_typing_trainer.ui.theme import apply_theme
from english_typing_trainer.ui.vocabulary_page import VocabularyPage


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
    def __init__(self, context: AppContext) -> None:
        super().__init__()
        self.context = context
        self.settings = self.context.settings_service.get_settings()
        self.articles: list[Article] = []
        self.current_material: PracticeMaterial | None = None
        self.current_practice_saved = True
        self.preview_special_material: PracticeMaterial | None = None

        self.setWindowTitle("英语打字练习")
        self.setMinimumSize(1280, 720)
        self.resize(1500, 1000)

        self.practice_view = PracticeView()
        self.practice_view.session_completed.connect(self._handle_session_completed)
        self.practice_view.back_requested.connect(self._leave_practice_view)
        self.sentence_practice_view = SentencePracticeView()
        self.sentence_practice_view.session_completed.connect(self._handle_session_completed)
        self.sentence_practice_view.back_requested.connect(self._leave_practice_view)
        self.sentence_practice_view.attempt_completed.connect(self._save_sentence_attempt)
        self.sentence_practice_view.translation_requested.connect(self._request_sentence_translation)
        self.sentence_practice_view.edit_translation_requested.connect(self._edit_sentence_translation)
        self.sentence_practice_view.translate_article_requested.connect(self._translate_current_article)
        self._sentence_attempts = SentenceAttemptRepository(self.context.database.connect)
        self._sentence_attempt_ids: list[int] = []
        self._thread_pool = QThreadPool(self)
        self._thread_pool.setMaxThreadCount(3)
        self._translation_workers: set[TranslationWorker] = set()

        self.settings_page = SettingsScreen(str(self.context.paths.data_dir.resolve()))
        self.settings_page.save_button.clicked.connect(self._save_settings)
        self.settings_page.open_data_dir_button.clicked.connect(self._open_data_dir)
        self.settings_page.save_api_key_button.clicked.connect(self._save_api_key)
        self.settings_page.delete_api_key_button.clicked.connect(self._delete_api_key)
        self.settings_page.test_api_button.clicked.connect(self._test_api_connection)
        self.history_page = HistoryPage()
        self.history_page.view_detail_requested.connect(self._show_session_detail)
        self.history_page.delete_session_requested.connect(self._delete_session)
        self.statistics_page = StatisticsPage()
        self.special_practice_page = SpecialPracticePage()
        self.special_practice_page.generate_requested.connect(self._generate_special_preview)
        self.special_practice_page.start_preview_requested.connect(self._start_preview_special_practice)
        self.special_practice_page.start_saved_requested.connect(self._start_saved_special_practice)
        self.special_practice_page.refresh_requested.connect(self._refresh_special_practice_page)
        self.special_practice_page.start_today_review_requested.connect(self._start_today_review)
        self.vocabulary_page = VocabularyPage()
        self.vocabulary_page.refresh_requested.connect(self._refresh_vocabulary_page)
        self.vocabulary_page.add_requested.connect(self._add_vocabulary_word)
        self.vocabulary_page.save_requested.connect(self._save_vocabulary_item)
        self.vocabulary_page.archive_requested.connect(self._set_vocabulary_archived)
        self.vocabulary_page.mastery_requested.connect(self._set_vocabulary_mastery)
        self.vocabulary_page.review_requested.connect(self._review_single_vocabulary)

        self._build_ui()
        self._apply_settings()
        self._reload_articles()
        self._refresh_history()
        self._refresh_statistics()
        self._refresh_special_practice_page()
        self._refresh_vocabulary_page()

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

        app_title = QLabel("英语打字练习")
        app_title.setProperty("role", "app-title")
        app_subtitle = QLabel("专注速度、正确率与长期记忆")
        app_subtitle.setProperty("role", "subtitle")
        sidebar_layout.addWidget(app_title)
        sidebar_layout.addWidget(app_subtitle)
        sidebar_layout.addSpacing(8)

        self.stack = QStackedWidget()
        self.library_page = self._build_library_page()
        self.stack.addWidget(self.library_page)
        self.stack.addWidget(self.special_practice_page)
        self.stack.addWidget(self.vocabulary_page)
        self.stack.addWidget(self.history_page)
        self.stack.addWidget(self.statistics_page)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.practice_view)
        self.stack.addWidget(self.sentence_practice_view)

        self.nav_buttons: dict[int, QPushButton] = {}
        nav_specs = [
            (0, "文章库", QStyle.StandardPixmap.SP_DirHomeIcon),
            (1, "专项练习", QStyle.StandardPixmap.SP_MediaPlay),
            (2, "生词本", QStyle.StandardPixmap.SP_FileDialogDetailedView),
            (3, "练习记录", QStyle.StandardPixmap.SP_FileDialogListView),
            (4, "学习统计", QStyle.StandardPixmap.SP_ComputerIcon),
            (5, "设置", QStyle.StandardPixmap.SP_FileDialogContentsView),
        ]
        for index, text, icon_type in nav_specs:
            button = QPushButton(text)
            button.setIcon(self.style().standardIcon(icon_type))
            button.setProperty("nav", "true")
            button.clicked.connect(lambda checked=False, idx=index: self._switch_page(idx))
            sidebar_layout.addWidget(button)
            self.nav_buttons[index] = button
        sidebar_layout.addStretch(1)

        version_label = QLabel("版本 0.2.0-dev")
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

        self._switch_page(0)
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
            "导入一篇英文 TXT，在打字过程中练习英语并记录速度和正确率。",
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
        detail_layout.addWidget(self.preview_content, stretch=1)
        self.content_split.addWidget(detail_card, stretch=2)
        layout.addLayout(self.content_split, stretch=1)
        return page

    def _switch_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        self.sidebar.setVisible(index not in {6, 7})
        for button_index, button in self.nav_buttons.items():
            button.setProperty("active", "true" if button_index == index else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _apply_settings(self) -> None:
        apply_theme(self, self.settings.theme, font_size=14)
        self.practice_view.apply_settings(self.settings)
        self.settings_page.load_settings(self.settings)
        self.preview_content.setStyleSheet(f"font-size: {max(14, self.settings.font_size - 1)}px;")
        self.practice_mode_control.set_value("sentence" if self.settings.sentence_learning_enabled else "continuous")

    def _set_practice_mode(self, mode: str) -> None:
        enabled = mode == "sentence"
        if enabled == self.settings.sentence_learning_enabled:
            return
        self.settings = self.context.settings_service.save_settings(
            replace(self.settings, sentence_learning_enabled=enabled)
        )
        self.settings_page.load_settings(self.settings)

    def _show_library(self) -> None:
        self._switch_page(0)
        self._reload_articles()

    def _show_special_practice(self) -> None:
        self._switch_page(1)
        self._refresh_special_practice_page()

    def _show_vocabulary(self) -> None:
        self._switch_page(2)
        self._refresh_vocabulary_page()

    def _show_history(self) -> None:
        self._switch_page(3)
        self._refresh_history()

    def _show_statistics(self) -> None:
        self._switch_page(4)
        self._refresh_statistics()

    def _show_settings(self) -> None:
        self.settings_page.load_settings(self.settings)
        try:
            self.settings_page.set_api_key_status(mask_api_key(self.context.credential_store.get()))
        except Exception:
            self.settings_page.set_api_key_status("读取失败")
        self._switch_page(5)

    def _reload_articles(self) -> None:
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
            self.article_list.setCurrentRow(0)
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
        items = self.context.special_practice_service.list_vocabulary(
            search=self.vocabulary_page.search_input.text(),
            status=self.vocabulary_page.status_combo.currentData(),
            archived=self.vocabulary_page.archived_checkbox.isChecked(),
            due_only=self.vocabulary_page.due_only_checkbox.isChecked(),
        )
        rows = []
        for item in items:
            rows.append(
                {
                    "id": item.id,
                    "display_word": item.display_word,
                    "meaning": item.meaning,
                    "status": item.status,
                    "mastery_level": item.mastery_level,
                    "next_review_at": item.next_review_at.isoformat() if item.next_review_at else "",
                    "last_reviewed_at": item.last_reviewed_at.isoformat() if item.last_reviewed_at else "",
                    "error_count": self.context.special_practice_service.vocabulary_error_count(item.normalized_word),
                    "source_sentence": item.source_sentence,
                    "note": item.note,
                    "is_archived": item.is_archived,
                }
            )
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

    def _import_articles(self) -> None:
        file_paths, _ = QFileDialog.getOpenFileNames(self, "导入 TXT 文章", "", "文本文件 (*.txt)")
        if not file_paths:
            return
        messages: list[str] = []
        for file_path in file_paths:
            result = self.context.article_library.import_txt_file(
                file_path,
                self.settings.section_target_characters,
            )
            name = result.article.title if result.article else file_path
            messages.append(f"{result.status}：{name} - {result.message}")
        self._reload_articles()
        QMessageBox.information(self, "导入结果", "\n".join(messages))

    def _start_selected_article(self, mode: str) -> None:
        article_id = self._selected_article_id()
        if article_id is None:
            QMessageBox.information(self, "未选择文章", "请先选择一篇文章。")
            return
        self._persist_current_practice()
        material = self.context.practice_service.load_practice_material(article_id, mode=mode)
        self._begin_practice(material)

    def _begin_practice(self, material: PracticeMaterial) -> None:
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
            self.practice_view.start_practice(material, self.settings)
            self.stack.setCurrentWidget(self.practice_view)
        self.sidebar.hide()
        for button in self.nav_buttons.values():
            button.setProperty("active", "false")
            button.style().unpolish(button)
            button.style().polish(button)

    def _active_practice_view(self):
        return self.sentence_practice_view if self.stack.currentWidget() is self.sentence_practice_view else self.practice_view

    def _active_snapshot(self):
        view = self._active_practice_view()
        return view.current_snapshot() if view is self.sentence_practice_view else view.session.snapshot()

    def _save_sentence_attempt(self, attempt) -> None:
        with self.context.database.transaction() as connection:
            attempt_id = self._sentence_attempts.insert(connection, attempt)
        self._sentence_attempt_ids.append(attempt_id)

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

    def _leave_practice_view(self) -> None:
        if not self._confirm_leave_practice():
            return
        if self.current_material and self.current_material.practice_type not in {"article", "article_section"}:
            self._show_special_practice()
        else:
            self._show_library()

    def _persist_current_practice(self) -> None:
        if self.current_practice_saved:
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
        next_material = self.context.practice_service.save_completed_session(
            self.current_material,
            self._active_practice_view().session,
            snapshot,
        )
        self.current_practice_saved = True
        self._attach_sentence_attempts()
        if self.current_material.practice_set_id is not None:
            self.context.special_practice_service.note_set_practiced(self.current_material.practice_set_id)
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
        generated = self.context.special_practice_service.generate_vocabulary_review_set(due_only=True, limit=20)
        if generated is None:
            QMessageBox.information(self, "今日复习", "今天没有待复习单词")
            return
        self.preview_special_material = generated.material
        self.special_practice_page.set_preview(generated.preview_text, generated.message)
        self._begin_practice(generated.material)

    def _add_vocabulary_word(self, word: str) -> None:
        try:
            self.context.special_practice_service.add_vocabulary_word(word)
        except ValueError as exc:
            QMessageBox.warning(self, "无效单词", str(exc))
            return
        self._refresh_vocabulary_page()
        self._refresh_special_practice_page()
        self.vocabulary_page.set_status_message("已加入生词本。")

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
        self.context.special_practice_service.set_vocabulary_mastery(item_id, mastered)
        self._refresh_vocabulary_page()
        self._refresh_special_practice_page()
        self.vocabulary_page.set_status_message("熟练度状态已更新。")

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
        self._thread_pool.clear()
        self._thread_pool.waitForDone(10000)
        super().closeEvent(event)
