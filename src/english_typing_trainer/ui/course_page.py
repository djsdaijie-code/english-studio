from __future__ import annotations

import logging

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.courses.models import Course, CourseLesson, CourseUnit
from english_typing_trainer.courses.repository import CourseRepository
from english_typing_trainer.models.course_progress import CourseEnrollment, CourseProgressSummary
from english_typing_trainer.services.course_progress import CourseProgressService


_ITEM_STATUS_TEXT = {
    "not_started": "未开始",
    "in_progress": "学习中",
    "completed": "已完成",
    "skipped": "暂时跳过",
    "failed": "失败，可重试",
}
_ENROLLMENT_STATUS_TEXT = {
    "active": "学习中",
    "paused": "已暂停",
    "completed": "已完成",
    "archived": "已归档",
}
_LESSON_TYPE_TEXT = {
    "new_content": "新内容",
    "review": "复习",
    "assessment": "测评",
}
_ACTIVITY_TYPE_TEXT = {
    "typing": "打字",
    "listening": "朗读",
    "speaking": "跟读",
    "dictation": "听写",
    "vocabulary": "词汇",
    "fsrs": "课程复习",
    "review": "课程复习",
}


class CourseListCard(QFrame):
    """Presentation-only card that keeps course-list text easy to scan."""

    def __init__(self, title: str, description: str, statistics: str) -> None:
        super().__init__()
        self.setObjectName("CourseListCard")
        self.setProperty("selected", False)
        self.setMinimumHeight(128)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 16, 0)
        layout.setSpacing(14)

        self.selection_bar = QFrame()
        self.selection_bar.setObjectName("CourseListSelectionBar")
        self.selection_bar.setFixedWidth(4)
        layout.addWidget(self.selection_bar)

        content = QVBoxLayout()
        content.setContentsMargins(0, 16, 0, 16)
        content.setSpacing(7)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "course-card-title")
        self.title_label.setWordWrap(False)
        self.description_label = QLabel(description)
        self.description_label.setProperty("role", "course-card-description")
        self.description_label.setWordWrap(True)
        self.description_label.setMaximumHeight(42)
        self.description_label.setToolTip(description)
        self.statistics_label = QLabel(statistics)
        self.statistics_label.setProperty("role", "course-card-statistics")
        self.statistics_label.setWordWrap(False)
        self.statistics_label.setToolTip(statistics)
        content.addWidget(self.title_label)
        content.addWidget(self.description_label)
        content.addWidget(self.statistics_label)
        layout.addLayout(content, stretch=1)

    def set_selected(self, selected: bool) -> None:
        if self.property("selected") == selected:
            return
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.selection_bar.style().unpolish(self.selection_bar)
        self.selection_bar.style().polish(self.selection_bar)
        self.update()


class CoursePage(QWidget):
    """Course list, hierarchy and lesson confirmation in one navigable page."""

    lesson_start_requested = Signal(str, str, str)
    capability_requested = Signal(str, str, str)
    due_review_requested = Signal()

    def __init__(
        self,
        courses: CourseRepository,
        progress: CourseProgressService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.courses = courses
        self.progress = progress
        self._logger = logging.getLogger(__name__)
        self.current_course_id: str | None = None
        self.current_lesson_id: str | None = None
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.view_stack = QStackedWidget()
        self.list_view = self._build_list_view()
        self.detail_view = self._build_detail_view()
        self.lesson_view = self._build_lesson_view()
        self.view_stack.addWidget(self.list_view)
        self.view_stack.addWidget(self.detail_view)
        self.view_stack.addWidget(self.lesson_view)
        root.addWidget(self.view_stack)

    def _page_shell(
        self,
        title: str,
        subtitle: str,
        *,
        subtitle_role: str = "subtitle",
    ) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)
        title_label = QLabel(title)
        title_label.setProperty("role", "page-title")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setProperty("role", subtitle_role)
        subtitle_label.setWordWrap(True)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return page, layout

    def _build_list_view(self) -> QWidget:
        page, layout = self._page_shell(
            "内置课程",
            "按推荐顺序学习，也可以自由打开任意 Day。",
            subtitle_role="course-page-subtitle",
        )
        actions = QHBoxLayout()
        self.reload_button = QPushButton("重新加载")
        self.reload_button.clicked.connect(lambda: self.reload(force=True))
        self.open_course_button = QPushButton("查看课程")
        self.open_course_button.clicked.connect(self._open_selected_course)
        self.quick_start_button = QPushButton("开始学习")
        self.quick_start_button.setProperty("variant", "primary")
        self.quick_start_button.clicked.connect(self._start_selected_course)
        self.due_review_button = QPushButton("课程到期复习")
        self.due_review_button.clicked.connect(self.due_review_requested.emit)
        actions.addWidget(self.reload_button)
        actions.addWidget(self.due_review_button)
        actions.addStretch(1)
        actions.addWidget(self.open_course_button)
        actions.addWidget(self.quick_start_button)
        layout.addLayout(actions)

        self.catalog_error_label = QLabel("")
        self.catalog_error_label.setWordWrap(True)
        self.catalog_error_label.setStyleSheet("color:#b42318;")
        self.catalog_error_label.hide()
        layout.addWidget(self.catalog_error_label)
        self.failure_label = QLabel("")
        self.failure_label.setWordWrap(True)
        self.failure_label.setStyleSheet("color:#b54708;")
        self.failure_label.hide()
        layout.addWidget(self.failure_label)

        self.course_list = QListWidget()
        self.course_list.setObjectName("CourseList")
        self.course_list.setAlternatingRowColors(False)
        self.course_list.setSpacing(8)
        self.course_list.itemSelectionChanged.connect(self._course_selection_changed)
        self.course_list.itemDoubleClicked.connect(lambda _item: self._open_selected_course())
        layout.addWidget(self.course_list, stretch=1)
        self.course_summary_label = QLabel("选择课程后可查看详情。")
        self.course_summary_label.setWordWrap(True)
        self.course_summary_label.setProperty("role", "subtitle")
        layout.addWidget(self.course_summary_label)
        return page

    def _build_detail_view(self) -> QWidget:
        page, layout = self._page_shell("课程详情", "查看 Level、Unit 与 Day，并从任意 Day 开始。")
        top = QHBoxLayout()
        back = QPushButton("返回课程列表")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self.show_list)
        self.recommended_button = QPushButton("开始推荐 Day")
        self.recommended_button.setProperty("variant", "primary")
        self.recommended_button.clicked.connect(self._start_recommended_lesson)
        top.addWidget(back)
        top.addStretch(1)
        top.addWidget(self.recommended_button)
        layout.addLayout(top)

        self.course_title_label = QLabel("")
        self.course_title_label.setProperty("role", "section-title")
        self.course_description_label = QLabel("")
        self.course_description_label.setWordWrap(True)
        self.course_goals_label = QLabel("")
        self.course_goals_label.setWordWrap(True)
        self.course_progress_label = QLabel("")
        self.course_progress_label.setProperty("role", "subtitle")
        self.recommended_label = QLabel("")
        self.recommended_label.setWordWrap(True)
        version_row = QHBoxLayout()
        self.version_notice_label = QLabel("")
        self.version_notice_label.setWordWrap(True)
        self.version_notice_label.setStyleSheet("color:#b54708;")
        self.view_new_content_button = QPushButton("查看新内容")
        self.view_new_content_button.clicked.connect(self._focus_new_content)
        self.view_new_content_button.hide()
        layout.addWidget(self.course_title_label)
        layout.addWidget(self.course_description_label)
        layout.addWidget(self.course_goals_label)
        layout.addWidget(self.course_progress_label)
        layout.addWidget(self.recommended_label)
        version_row.addWidget(self.version_notice_label, stretch=1)
        version_row.addWidget(self.view_new_content_button)
        layout.addLayout(version_row)

        self.hierarchy_tree = QTreeWidget()
        self.hierarchy_tree.setHeaderLabels(["课程结构", "内容", "状态"])
        self.hierarchy_tree.setColumnWidth(0, 360)
        self.hierarchy_tree.itemDoubleClicked.connect(self._tree_item_activated)
        self.hierarchy_tree.itemSelectionChanged.connect(self._tree_selection_changed)
        layout.addWidget(self.hierarchy_tree, stretch=1)
        row = QHBoxLayout()
        self.detail_status_label = QLabel("双击 Day，或选中后打开。")
        self.detail_status_label.setWordWrap(True)
        self.detail_status_label.setProperty("role", "subtitle")
        self.open_day_button = QPushButton("查看 Day")
        self.open_day_button.clicked.connect(self._open_selected_lesson)
        row.addWidget(self.detail_status_label, stretch=1)
        row.addWidget(self.open_day_button)
        layout.addLayout(row)
        return page

    def _build_lesson_view(self) -> QWidget:
        page, layout = self._page_shell("Day 详情", "开始前确认本 Day 的目标与学习内容。")
        top = QHBoxLayout()
        back = QPushButton("返回课程详情")
        back.setProperty("variant", "ghost")
        back.clicked.connect(self._return_to_current_course)
        self.start_lesson_button = QPushButton("开始学习")
        self.start_lesson_button.setProperty("variant", "primary")
        self.start_lesson_button.clicked.connect(self._emit_current_lesson)
        top.addWidget(back)
        top.addStretch(1)
        top.addWidget(self.start_lesson_button)
        layout.addLayout(top)

        self.capability_row = QWidget()
        capability_layout = QHBoxLayout(self.capability_row)
        capability_layout.setContentsMargins(0, 0, 0, 0)
        self.capability_buttons: dict[str, QPushButton] = {}
        for label, capability in (
            ("朗读", "tts"),
            ("听写", "dictation"),
            ("跟读", "speaking"),
            ("查看与收藏单词", "vocabulary"),
            ("加入课程复习", "review"),
        ):
            button = QPushButton(label)
            button.clicked.connect(
                lambda _checked=False, value=capability: self._emit_capability(value)
            )
            capability_layout.addWidget(button)
            self.capability_buttons[capability] = button
        capability_layout.addStretch(1)
        layout.addWidget(self.capability_row)

        self.lesson_title_label = QLabel("")
        self.lesson_title_label.setProperty("role", "section-title")
        self.lesson_description_label = QLabel("")
        self.lesson_description_label.setWordWrap(True)
        self.lesson_goals_label = QLabel("")
        self.lesson_goals_label.setWordWrap(True)
        self.lesson_counts_label = QLabel("")
        self.lesson_progress_label = QLabel("")
        self.lesson_warning_label = QLabel("")
        self.lesson_warning_label.setWordWrap(True)
        self.lesson_warning_label.setStyleSheet("color:#b54708;")
        for widget in (
            self.lesson_title_label,
            self.lesson_description_label,
            self.lesson_goals_label,
            self.lesson_counts_label,
            self.lesson_progress_label,
            self.lesson_warning_label,
        ):
            layout.addWidget(widget)
        self.lesson_items = QListWidget()
        layout.addWidget(self.lesson_items, stretch=1)
        self.lesson_error_label = QLabel("")
        self.lesson_error_label.setWordWrap(True)
        self.lesson_error_label.setStyleSheet("color:#b42318;")
        layout.addWidget(self.lesson_error_label)
        return page

    def reload(self, *, force: bool = False) -> None:
        selected_id = self.current_course_id
        self.course_list.clear()
        self.catalog_error_label.hide()
        self.failure_label.hide()
        try:
            catalog = self.courses.reload() if force else self.courses.load_catalog()
        except Exception as exc:
            self._logger.error(
                "course catalog unavailable path=%s reason=%s",
                self.courses.courses_root,
                exc,
            )
            self.catalog_error_label.setText(
                f"课程目录暂时无法读取：{exc}\n请检查课程资源后点击“重新加载”。"
            )
            self.catalog_error_label.show()
            self.course_summary_label.setText("没有可显示的课程。")
            self.open_course_button.setEnabled(False)
            self.quick_start_button.setEnabled(False)
            self.view_stack.setCurrentWidget(self.list_view)
            return

        if catalog.failures:
            summaries = [
                f"{failure.course_id or '未知课程'}：{failure.reason}"
                for failure in catalog.failures
            ]
            self.failure_label.setText("部分课程加载失败，其他课程仍可使用：\n" + "\n".join(summaries))
            self.failure_label.show()

        for course in catalog.courses:
            item = QListWidgetItem(self._course_list_text(course))
            item.setData(Qt.ItemDataRole.UserRole, course.course_id)
            item.setSizeHint(QSize(0, 128))
            self.course_list.addItem(item)
            self.course_list.setItemWidget(item, self._course_card(course))
            if course.course_id == selected_id:
                self.course_list.setCurrentItem(item)
        if self.course_list.count() and self.course_list.currentRow() < 0:
            self.course_list.setCurrentRow(0)
        if not self.course_list.count():
            self.course_summary_label.setText("当前没有可用课程。")
        self._course_selection_changed()

    def show_list(self) -> None:
        self.view_stack.setCurrentWidget(self.list_view)

    def set_due_review_count(self, count: int) -> None:
        count = max(0, count)
        self.due_review_button.setText(
            f"课程到期复习（{count}）" if count else "课程到期复习"
        )

    def show_course(self, course_id: str) -> None:
        try:
            course = self.courses.get_course(course_id)
        except Exception as exc:
            self._log_course_read_error(course_id, exc)
            self._show_list_error(f"课程目录暂时无法读取：{exc}。请重新加载。")
            return
        if course is None:
            self._show_list_error(f"课程 {course_id!r} 已不存在，请重新加载课程目录。")
            return
        self.current_course_id = course_id
        self.current_lesson_id = None
        self.course_title_label.setText(f"{course.title} · {course.subtitle}" if course.subtitle else course.title)
        self.course_description_label.setText(course.description)
        self.course_goals_label.setText("学习目标：\n" + "\n".join(f"• {goal}" for goal in course.learning_goals))
        try:
            summary = self.progress.get_course_progress(course_id)
            enrollment = self.progress.get_enrollment(course_id)
            recommended = self.progress.get_next_lesson(course_id)
            self.course_progress_label.setText(self._summary_text(summary, enrollment))
            if recommended is not None:
                self.recommended_label.setText(f"当前推荐：Day {recommended.day} · {recommended.title}")
                self.recommended_button.setText("继续推荐 Day" if enrollment else "开始推荐 Day")
                self.recommended_button.setEnabled(True)
            elif enrollment and enrollment.status in {"paused", "archived"}:
                self.recommended_label.setText("课程已暂停或归档，不提供自动下一课；仍可自由查看并进入 Day。")
                self.recommended_button.setEnabled(False)
            else:
                self.recommended_label.setText("必做内容已完成，可以自由选择 Day 复习。")
                self.recommended_button.setText("复习第一个 Day")
                self.recommended_button.setEnabled(self._first_lesson(course) is not None)
            version_status = self.progress.get_version_status(course_id)
            if version_status is not None and version_status.has_new_content:
                completed_prefix = (
                    "你曾完成该记录版本。" if version_status.completed_recorded_version else ""
                )
                self.version_notice_label.setText(
                    "课程有新内容。"
                    f"已记录：课程 {version_status.recorded_course_version} / 内容 "
                    f"{version_status.recorded_content_version}；当前：课程 "
                    f"{version_status.current_course_version} / 内容 "
                    f"{version_status.current_content_version}。"
                    f"{completed_prefix}历史完成状态不会被清除。"
                )
                self.view_new_content_button.show()
            else:
                self.version_notice_label.setText("")
                self.view_new_content_button.hide()
        except Exception as exc:
            self._log_progress_error(course, None, exc)
            self.course_progress_label.setText("进度暂时无法读取。")
            self.recommended_label.setText("推荐 Day 暂时不可用，仍可浏览课程结构。")
            self.recommended_button.setEnabled(False)
            self.version_notice_label.setText("")
            self.view_new_content_button.hide()

        self._populate_hierarchy(course)
        self.view_stack.setCurrentWidget(self.detail_view)

    def _focus_new_content(self) -> None:
        if not self.current_course_id:
            return
        try:
            lesson = self.progress.get_next_lesson(self.current_course_id)
        except Exception as exc:
            course = self.courses.get_course(self.current_course_id)
            if course is not None:
                self._log_progress_error(course, None, exc)
            self.detail_status_label.setText("暂时无法定位新内容，请从课程结构中查看。")
            return
        if lesson is None:
            self.detail_status_label.setText("当前没有未完成的必做内容，可自由选择 Day 复习。")
            return
        iterator = QTreeWidgetItemIterator(self.hierarchy_tree)
        while iterator.value() is not None:
            item = iterator.value()
            if item.data(0, Qt.ItemDataRole.UserRole) == lesson.lesson_id:
                self.hierarchy_tree.setCurrentItem(item)
                self.hierarchy_tree.scrollToItem(item)
                self.detail_status_label.setText(
                    f"已定位到当前新内容：Day {lesson.day} · {lesson.title}。"
                )
                return
            iterator += 1

    def show_lesson(self, course_id: str, lesson_id: str) -> None:
        try:
            course = self.courses.get_course(course_id)
        except Exception as exc:
            self._log_course_read_error(course_id, exc)
            self._show_list_error(f"课程目录暂时无法读取：{exc}。请重新加载。")
            return
        found = self._find_lesson(course, lesson_id) if course else None
        if course is None or found is None:
            self._show_list_error(
                f"Day {lesson_id!r} 已不存在，课程内容可能已刷新。请返回课程列表重新加载。"
            )
            return
        unit, lesson = found
        self.current_course_id = course_id
        self.current_lesson_id = lesson_id
        self.lesson_title_label.setText(f"Day {lesson.day} · {lesson.title}")
        self.lesson_description_label.setText(lesson.description or "本 Day 暂无补充说明。")
        self.lesson_goals_label.setText(
            "学习目标：\n" + ("\n".join(f"• {goal}" for goal in lesson.learning_goals) or "• 完成本 Day 句子练习")
        )
        activity_types = "、".join(
            dict.fromkeys(
                _ACTIVITY_TYPE_TEXT.get(activity.activity_type, activity.activity_type)
                for activity in lesson.activities
            )
        ) or "句子打字"
        self.lesson_counts_label.setText(
            f"新句 {len(lesson.new_sentence_ids)} · 复习句 {len(lesson.review_sentence_ids)} · 活动 {activity_types}"
        )
        self.lesson_items.clear()
        self.lesson_error_label.setText("")
        referenced_ids = self._lesson_sentence_ids(lesson)
        sentences = {sentence.sentence_id: sentence for sentence in unit.sentences}
        missing = [sentence_id for sentence_id in referenced_ids if sentence_id not in sentences]
        if missing:
            self.lesson_error_label.setText(f"本 Day 引用的内容不存在：{', '.join(missing)}。请重新加载课程。")
        for sentence_id in referenced_ids:
            sentence = sentences.get(sentence_id)
            if sentence is None:
                continue
            try:
                status_text = self._sentence_activity_status(course, lesson, sentence.sentence_id, sentence.stable_key)
            except Exception as exc:
                self._log_progress_error(course, lesson, exc, sentence.stable_key)
                status_text = "状态不可用"
            QListWidgetItem(f"{sentence.order}. {sentence.english}  ·  {status_text}", self.lesson_items)
        try:
            summary = self.progress.get_lesson_progress(course_id, lesson_id)
            self.lesson_progress_label.setText(
                f"当前进度：{summary.completed_required_items}/{summary.total_required_items}"
                f"（{summary.completion_percentage:.0f}%） · {self._lesson_status(course, lesson)}"
            )
            self.start_lesson_button.setText("重新复习" if summary.is_completed else "开始或继续")
            self.start_lesson_button.setProperty("sessionMode", "review" if summary.is_completed else "manual")
        except Exception as exc:
            self._log_progress_error(course, lesson, exc)
            self.lesson_progress_label.setText("当前进度暂时无法读取。")
            self.start_lesson_button.setProperty("sessionMode", "manual")
        has_content = bool(referenced_ids) and not missing
        self.start_lesson_button.setEnabled(has_content)
        if not referenced_ids:
            self.lesson_error_label.setText("本 Day 还没有可学习的句子。")
        self._configure_capability_buttons(course, lesson, referenced_ids)
        self.lesson_warning_label.setText(self._prerequisite_warning(course, lesson))
        self.view_stack.setCurrentWidget(self.lesson_view)

    def _course_list_text(self, course: Course) -> str:
        units = sum(len(level.units) for level in course.levels)
        try:
            enrollment = self.progress.get_enrollment(course.course_id)
            summary = self.progress.get_course_progress(course.course_id)
            status = _ENROLLMENT_STATUS_TEXT[enrollment.status] if enrollment else "未开始"
            progress = f"{summary.completion_percentage:.0f}%"
        except Exception as exc:
            self._log_progress_error(course, None, exc)
            status, progress = "状态不可用", "--"
        return (
            f"{course.title}\n{course.description}\n"
            f"{len(course.levels)} 个 Level · {units} 个 Unit · 预计 {course.estimated_days} 天 · {status} · 完成 {progress}"
        )

    def _course_card(self, course: Course) -> CourseListCard:
        units = sum(len(level.units) for level in course.levels)
        try:
            enrollment = self.progress.get_enrollment(course.course_id)
            summary = self.progress.get_course_progress(course.course_id)
            status = _ENROLLMENT_STATUS_TEXT[enrollment.status] if enrollment else "未开始"
            progress = f"完成 {summary.completion_percentage:.0f}%"
        except Exception as exc:
            self._log_progress_error(course, None, exc)
            status, progress = "状态不可用", "完成 --"
        statistics = (
            f"{len(course.levels)} 个 Level · {units} 个 Unit · 预计 {course.estimated_days} 天"
            f" · {status} · {progress}"
        )
        return CourseListCard(course.title, course.description, statistics)

    def _sync_course_card_selection(self, selected_item: QListWidgetItem | None) -> None:
        for index in range(self.course_list.count()):
            item = self.course_list.item(index)
            card = self.course_list.itemWidget(item)
            if isinstance(card, CourseListCard):
                card.set_selected(item is selected_item)

    def _course_selection_changed(self) -> None:
        item = self.course_list.currentItem()
        self._sync_course_card_selection(item)
        enabled = item is not None
        self.open_course_button.setEnabled(enabled)
        self.quick_start_button.setEnabled(enabled)
        if item is None:
            return
        course_id = str(item.data(Qt.ItemDataRole.UserRole))
        course = self.courses.get_course(course_id)
        if course is None:
            return
        try:
            enrollment = self.progress.get_enrollment(course_id)
            next_lesson = self.progress.get_next_lesson(course_id)
            if enrollment and enrollment.status in {"paused", "archived"}:
                self.quick_start_button.setText("自动学习已暂停")
                self.quick_start_button.setEnabled(False)
            elif next_lesson is not None:
                self.quick_start_button.setText("继续学习" if enrollment else "开始学习")
            else:
                self.quick_start_button.setText("重新复习")
            self.course_summary_label.setText(
                f"{course.subtitle or course.title}\n"
                + (f"推荐从 Day {next_lesson.day} 开始。" if next_lesson else "当前没有待完成的推荐 Day。")
            )
        except Exception as exc:
            self._log_progress_error(course, None, exc)
            self.course_summary_label.setText("课程可浏览，但学习状态暂时无法读取。")
            self.quick_start_button.setEnabled(False)

    def _open_selected_course(self) -> None:
        item = self.course_list.currentItem()
        if item is not None:
            self.show_course(str(item.data(Qt.ItemDataRole.UserRole)))

    def _start_selected_course(self) -> None:
        item = self.course_list.currentItem()
        if item is None:
            return
        course_id = str(item.data(Qt.ItemDataRole.UserRole))
        self._emit_recommended(course_id)

    def _start_recommended_lesson(self) -> None:
        if self.current_course_id:
            self._emit_recommended(self.current_course_id)

    def _emit_recommended(self, course_id: str) -> None:
        try:
            course = self.courses.get_course(course_id)
        except Exception as exc:
            self._log_course_read_error(course_id, exc)
            self._show_list_error(f"课程目录暂时无法读取：{exc}。请重新加载。")
            return
        if course is None:
            self._show_list_error("课程已不存在，请重新加载。")
            return
        try:
            enrollment = self.progress.get_enrollment(course_id)
            if enrollment and enrollment.status in {"paused", "archived"}:
                self.show_course(course_id)
                self.detail_status_label.setText("课程已暂停或归档，请从课程结构中手动选择 Day。")
                return
            lesson = self.progress.get_next_lesson(course_id)
            mode = "recommended"
            if lesson is None:
                lesson = self._first_lesson(course)
                mode = "review"
            if lesson is None:
                self.show_course(course_id)
                self.detail_status_label.setText("课程还没有可学习的 Day。")
                return
            self.lesson_start_requested.emit(course_id, lesson.lesson_id, mode)
        except Exception as exc:
            self._log_progress_error(course, None, exc)
            self.show_course(course_id)
            self.detail_status_label.setText("推荐 Day 暂时不可用，请稍后重试。")

    def _populate_hierarchy(self, course: Course) -> None:
        self.hierarchy_tree.clear()
        for level in course.levels:
            level_item = QTreeWidgetItem([f"Level {level.order} · {level.title}", level.difficulty, ""])
            self.hierarchy_tree.addTopLevelItem(level_item)
            for unit in level.units:
                unit_status = "内容待补充" if not unit.is_materialized else self._unit_status(course, unit)
                unit_item = QTreeWidgetItem(
                    [f"Unit {unit.order} · {unit.title}", f"{len(unit.lessons)} 个 Day", unit_status]
                )
                level_item.addChild(unit_item)
                for lesson in unit.lessons:
                    summary_text = self._lesson_status(course, lesson)
                    content_text = (
                        f"{_LESSON_TYPE_TEXT.get(lesson.lesson_type, lesson.lesson_type)} · "
                        f"新句 {len(lesson.new_sentence_ids)} · 复习 {len(lesson.review_sentence_ids)}"
                    )
                    lesson_item = QTreeWidgetItem(
                        [f"Day {lesson.day} · {lesson.title}", content_text, summary_text]
                    )
                    lesson_item.setData(0, Qt.ItemDataRole.UserRole, lesson.lesson_id)
                    unit_item.addChild(lesson_item)
            level_item.setExpanded(True)
            for index in range(level_item.childCount()):
                level_item.child(index).setExpanded(True)
        self.open_day_button.setEnabled(False)

    def _tree_selection_changed(self) -> None:
        item = self.hierarchy_tree.currentItem()
        lesson_id = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        self.open_day_button.setEnabled(bool(lesson_id))

    def _tree_item_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        lesson_id = item.data(0, Qt.ItemDataRole.UserRole)
        if lesson_id and self.current_course_id:
            self.show_lesson(self.current_course_id, str(lesson_id))

    def _open_selected_lesson(self) -> None:
        item = self.hierarchy_tree.currentItem()
        lesson_id = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if lesson_id and self.current_course_id:
            self.show_lesson(self.current_course_id, str(lesson_id))

    def _return_to_current_course(self) -> None:
        if self.current_course_id:
            self.show_course(self.current_course_id)
        else:
            self.show_list()

    def _emit_current_lesson(self) -> None:
        if self.current_course_id and self.current_lesson_id:
            mode = self.start_lesson_button.property("sessionMode") or "manual"
            self.lesson_start_requested.emit(
                self.current_course_id,
                self.current_lesson_id,
                str(mode),
            )

    def _emit_capability(self, capability: str) -> None:
        if self.current_course_id and self.current_lesson_id:
            self.capability_requested.emit(
                self.current_course_id, self.current_lesson_id, capability
            )

    def _configure_capability_buttons(
        self,
        course: Course,
        lesson: CourseLesson,
        referenced_ids: tuple[str, ...],
    ) -> None:
        configured = {activity.activity_type for activity in lesson.activities}
        found = self._find_lesson(course, lesson.lesson_id)
        unit = found[0] if found else None
        sentences = (
            {item.sentence_id: item for item in unit.sentences}
            if unit is not None
            else {}
        )
        referenced_sentences = [
            sentences[sentence_id]
            for sentence_id in referenced_ids
            if sentence_id in sentences
        ]
        visible = {
            "tts": "listening" in configured,
            "dictation": "dictation" in configured,
            "speaking": "speaking" in configured,
            "vocabulary": any(item.core_words for item in referenced_sentences),
            "review": any("fsrs" in item.skill_tags for item in referenced_sentences),
        }
        base_labels = {
            "tts": "朗读",
            "dictation": "听写",
            "speaking": "跟读",
            "vocabulary": "查看与收藏单词",
            "review": "加入课程复习",
        }
        for capability, button in self.capability_buttons.items():
            button.setText(base_labels[capability])
            button.setVisible(visible[capability])
            button.setEnabled(bool(referenced_ids))
        progress_type = {
            "tts": "review",
            "dictation": "dictation",
            "speaking": "speaking",
            "vocabulary": "vocabulary",
            "review": "review",
        }
        if unit is None:
            return
        for capability, activity_type in progress_type.items():
            button = self.capability_buttons[capability]
            if not visible[capability]:
                continue
            configured_ids = {
                sentence_id
                for activity in lesson.activities
                if self._progress_activity_type(activity.activity_type) == activity_type
                for sentence_id in activity.sentence_ids
            }
            target_ids = configured_ids or set(referenced_ids)
            try:
                states = [
                    self.progress.get_activity_progress(
                        course.course_id,
                        sentences[sentence_id].stable_key,
                        activity_type,  # type: ignore[arg-type]
                    ).status
                    for sentence_id in target_ids
                    if sentence_id in sentences
                ]
            except Exception as exc:
                self._log_progress_error(course, lesson, exc)
                button.setText(button.text().split(" · ")[0] + " · 状态不可用")
                continue
            if states and all(state == "completed" for state in states):
                button.setText(button.text().split(" · ")[0] + " · 已完成")

    def _lesson_status(self, course: Course, lesson: CourseLesson) -> str:
        try:
            summary = self.progress.get_lesson_progress(course.course_id, lesson.lesson_id)
            if summary.is_completed:
                return "已完成"
            found = self._find_lesson(course, lesson.lesson_id)
            unit = found[0] if found else None
            sentence_by_id = {sentence.sentence_id: sentence for sentence in unit.sentences} if unit is not None else {}
            states = [
                self.progress.get_activity_progress(
                    course.course_id,
                    sentence_by_id[sentence_id].stable_key,
                    self._progress_activity_type(activity.activity_type),
                ).status
                for activity in lesson.activities
                if activity.required
                for sentence_id in activity.sentence_ids
                if sentence_id in sentence_by_id
            ]
            if summary.completed_required_items or "in_progress" in states:
                return f"学习中 · {summary.completion_percentage:.0f}%"
            if "skipped" in states:
                return "暂时跳过"
            return "未开始"
        except Exception as exc:
            self._log_progress_error(course, lesson, exc)
            return "状态不可用"

    def _sentence_activity_status(
        self,
        course: Course,
        lesson: CourseLesson,
        sentence_id: str,
        item_stable_key: str,
    ) -> str:
        labels: list[str] = []
        for activity in lesson.activities:
            if sentence_id not in activity.sentence_ids:
                continue
            activity_type = self._progress_activity_type(activity.activity_type)
            state = self.progress.get_activity_progress(
                course.course_id, item_stable_key, activity_type
            ).status
            label = _ACTIVITY_TYPE_TEXT.get(activity.activity_type, activity.activity_type)
            labels.append(f"{label} {_ITEM_STATUS_TEXT.get(state, state)}")
        return " · ".join(labels) or "未开始"

    @staticmethod
    def _progress_activity_type(activity_type: str):
        return {
            "fsrs": "review",
            "listening": "review",
            "reading": "typing",
            "translation": "typing",
            "self_test": "typing",
        }.get(activity_type, activity_type)

    def _unit_status(self, course: Course, unit: CourseUnit) -> str:
        try:
            summary = self.progress.get_unit_progress(course.course_id, unit.unit_id)
            return "已完成" if summary.is_completed else f"{summary.completion_percentage:.0f}%"
        except Exception as exc:
            self._log_progress_error(course, None, exc)
            return "状态不可用"

    @staticmethod
    def _summary_text(
        summary: CourseProgressSummary,
        enrollment: CourseEnrollment | None,
    ) -> str:
        status = _ENROLLMENT_STATUS_TEXT[enrollment.status] if enrollment else "未开始"
        return (
            f"总进度：{summary.completed_required_items}/{summary.total_required_items} "
            f"（{summary.completion_percentage:.0f}%） · {status}"
        )

    def _prerequisite_warning(self, course: Course, lesson: CourseLesson) -> str:
        earlier = [
            item
            for level in course.levels
            for unit in level.units
            for item in unit.lessons
            if (item.day, item.order) < (lesson.day, lesson.order)
        ]
        for item in earlier:
            try:
                if not self.progress.get_lesson_progress(course.course_id, item.lesson_id).is_completed:
                    return "提示：前面的 Day 尚未全部完成。本阶段允许自由进入，跳学不会自动完成前置内容。"
            except Exception:
                return "前置 Day 状态暂时无法读取，但仍可自由进入本 Day。"
        return ""

    @staticmethod
    def _lesson_sentence_ids(lesson: CourseLesson) -> tuple[str, ...]:
        result: list[str] = []
        seen: set[str] = set()
        candidates = [*lesson.new_sentence_ids, *lesson.review_sentence_ids]
        candidates.extend(
            sentence_id
            for activity in lesson.activities
            for sentence_id in activity.sentence_ids
        )
        for sentence_id in candidates:
            if sentence_id not in seen:
                result.append(sentence_id)
                seen.add(sentence_id)
        return tuple(result)

    @staticmethod
    def _find_lesson(
        course: Course,
        lesson_id: str,
    ) -> tuple[CourseUnit, CourseLesson] | None:
        for level in course.levels:
            for unit in level.units:
                for lesson in unit.lessons:
                    if lesson.lesson_id == lesson_id:
                        return unit, lesson
        return None

    @staticmethod
    def _first_lesson(course: Course) -> CourseLesson | None:
        return next(
            (
                lesson
                for level in course.levels
                for unit in level.units
                for lesson in unit.lessons
                if CoursePage._lesson_sentence_ids(lesson)
            ),
            None,
        )

    def _show_list_error(self, message: str) -> None:
        self.catalog_error_label.setText(message)
        self.catalog_error_label.show()
        self.show_list()

    def _log_progress_error(
        self,
        course: Course,
        lesson: CourseLesson | None,
        exc: Exception,
        item_stable_key: str | None = None,
    ) -> None:
        self._logger.error(
            "course UI state error course_id=%s course_stable_key=%s lesson_stable_key=%s item_stable_key=%s reason=%s",
            course.course_id,
            course.stable_key,
            lesson.stable_key if lesson else None,
            item_stable_key,
            exc,
        )

    def _log_course_read_error(self, course_id: str, exc: Exception) -> None:
        self._logger.error(
            "course UI content error course_id=%s path=%s reason=%s",
            course_id,
            self.courses.courses_root,
            exc,
        )


__all__ = ["CoursePage"]
