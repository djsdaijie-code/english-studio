from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.models.learning import LearningDashboard
from english_typing_trainer.ui.daily_learning_card import DailyLearningCard


class HomeActionCard(QFrame):
    """Small action card retained for callers that use the legacy card attributes."""

    def __init__(self, title: str, description: str, action_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeQuickCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setProperty("role", "home-quick-title")
        description_label = QLabel(description)
        description_label.setProperty("role", "home-meta")
        description_label.setWordWrap(True)
        self.action_button = QPushButton(action_text)
        self.action_button.setProperty("variant", "home-quick")
        layout.addWidget(title_label)
        layout.addWidget(description_label, stretch=1)
        layout.addWidget(self.action_button)


class ContinueLearningCard(QFrame):
    requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeContinueCard")
        self.setMinimumHeight(236)
        self.setMaximumHeight(252)

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        self.cover = QFrame()
        self.cover.setObjectName("HomeCourseCover")
        self.cover.setFixedWidth(142)
        cover_layout = QVBoxLayout(self.cover)
        cover_layout.setContentsMargins(16, 18, 16, 18)
        cover_layout.addStretch(1)
        self.cover_title = QLabel("English\nStudio")
        self.cover_title.setProperty("role", "home-cover-title")
        self.cover_title.setWordWrap(True)
        self.cover_meta = QLabel("每日学习")
        self.cover_meta.setProperty("role", "home-cover-meta")
        cover_layout.addWidget(self.cover_title)
        cover_layout.addWidget(self.cover_meta)
        cover_layout.addStretch(1)
        root.addWidget(self.cover)

        details = QVBoxLayout()
        details.setSpacing(7)
        self.kicker = QLabel("继续上次学习")
        self.kicker.setProperty("role", "home-kicker")
        self.course_title = QLabel("选择一项学习内容")
        self.course_title.setProperty("role", "home-course-title")
        self.course_title.setWordWrap(True)
        self.location = QLabel("文章与内置课程都可以从这里继续")
        self.location.setProperty("role", "home-meta")
        self.lesson_title = QLabel("打开学习内容，开始今天的练习")
        self.lesson_title.setProperty("role", "home-lesson-title")
        self.lesson_title.setWordWrap(True)
        details.addWidget(self.kicker, alignment=Qt.AlignmentFlag.AlignLeft)
        details.addWidget(self.course_title)
        details.addWidget(self.location)
        details.addWidget(self.lesson_title)
        details.addStretch(1)

        progress_row = QHBoxLayout()
        progress_row.setSpacing(10)
        progress_label = QLabel("课程进度")
        progress_label.setProperty("role", "home-meta")
        self.progress = QProgressBar()
        self.progress.setObjectName("HomeCourseProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(7)
        self.progress_percent = QLabel("0%")
        self.progress_percent.setProperty("role", "home-meta")
        progress_row.addWidget(progress_label)
        progress_row.addWidget(self.progress, stretch=1)
        progress_row.addWidget(self.progress_percent)
        details.addLayout(progress_row)

        footer = QHBoxLayout()
        self.remaining = QLabel("从任意内容开始")
        self.remaining.setProperty("role", "home-meta")
        self.action_button = QPushButton("继续学习")
        self.action_button.setProperty("variant", "primary")
        self.action_button.clicked.connect(self.requested.emit)
        footer.addWidget(self.remaining)
        footer.addStretch(1)
        footer.addWidget(self.action_button)
        details.addLayout(footer)
        root.addLayout(details, stretch=1)

    def update_course(self, data: dict[str, object] | None) -> None:
        if not data:
            self.cover_title.setText("English\nStudio")
            self.cover_meta.setText("每日学习")
            self.course_title.setText("选择一项学习内容")
            self.location.setText("文章与内置课程都可以从这里继续")
            self.lesson_title.setText("打开学习内容，开始今天的练习")
            self.progress.setValue(0)
            self.progress_percent.setText("0%")
            self.remaining.setText("从任意内容开始")
            return
        title = str(data.get("course_title") or "内置课程")
        level = str(data.get("level") or "课程")
        unit = str(data.get("unit") or "")
        day = data.get("day")
        progress = max(0, min(100, int(round(float(data.get("progress") or 0)))))
        self.cover_title.setText(title)
        self.cover_meta.setText(level)
        self.course_title.setText(title)
        location_parts = [part for part in (level, unit, f"Day {day}" if day else "") if part]
        self.location.setText("  ·  ".join(location_parts))
        self.lesson_title.setText(str(data.get("lesson_title") or "继续课程学习"))
        self.progress.setValue(progress)
        self.progress_percent.setText(f"{progress}%")
        remaining = max(0, int(data.get("remaining_items") or 0))
        self.remaining.setText("课程已完成" if remaining == 0 and progress == 100 else f"剩余 {remaining} 项学习内容")


class HomeTaskRow(QFrame):
    requested = Signal()

    def __init__(self, badge: str, title: str, detail: str, action: str, tone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeTaskRow")
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 7, 0, 7)
        root.setSpacing(12)
        self.badge = QLabel(badge)
        self.badge.setObjectName("HomeTaskBadge")
        self.badge.setProperty("tone", tone)
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge.setFixedSize(36, 36)
        text = QVBoxLayout()
        text.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "home-task-title")
        self.detail_label = QLabel(detail)
        self.detail_label.setProperty("role", "home-meta")
        text.addWidget(self.title_label)
        text.addWidget(self.detail_label)
        self.status_label = QLabel("")
        self.status_label.setProperty("role", "home-task-status")
        self.action_button = QPushButton(action)
        self.action_button.setProperty("variant", "home-outline")
        self.action_button.clicked.connect(self.requested.emit)
        root.addWidget(self.badge)
        root.addLayout(text, stretch=1)
        root.addWidget(self.status_label)
        root.addWidget(self.action_button)

    def set_detail(self, detail: str, *, completed: bool = False) -> None:
        self.detail_label.setText(detail)
        self.status_label.setText("已完成" if completed else "待学习")
        self.status_label.setProperty("completed", "true" if completed else "false")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)


class WeeklyBarsWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.values = [0.0] * 7
        self.setMinimumHeight(148)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_values(self, values: Sequence[float]) -> None:
        normalized = [max(0.0, float(value)) for value in values[:7]]
        self.values = normalized + [0.0] * (7 - len(normalized))
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = self.palette().window().color().lightness() < 128
        muted = QColor("#90a0b5" if dark else "#64748b")
        track = QColor("#25374d" if dark else "#e8eef8")
        fill = QColor("#5f8fe8" if dark else "#2f6fec")
        labels = ("一", "二", "三", "四", "五", "六", "日")
        maximum = max(max(self.values), 3600.0)
        width = self.width() / 7.0
        chart_top = 22.0
        chart_bottom = max(chart_top + 12.0, self.height() - 28.0)
        usable_height = chart_bottom - chart_top
        painter.setPen(muted)
        small = painter.font()
        small.setPointSize(8)
        painter.setFont(small)
        for index, seconds in enumerate(self.values):
            center = width * index + width / 2.0
            bar_width = min(24.0, width * 0.34)
            painter.setBrush(track)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(QRectF(center - bar_width / 2, chart_top, bar_width, usable_height), 4, 4)
            bar_height = usable_height * min(1.0, seconds / maximum)
            if seconds > 0:
                painter.setBrush(fill)
                painter.drawRoundedRect(QRectF(center - bar_width / 2, chart_bottom - bar_height, bar_width, bar_height), 4, 4)
            painter.setPen(muted)
            painter.drawText(QRectF(center - width / 2, chart_bottom + 5, width, 20), Qt.AlignmentFlag.AlignCenter, labels[index])
            if seconds > 0:
                hours = seconds / 3600.0
                value_text = f"{hours:.1f}h" if hours >= 1 else f"{int(seconds / 60)}m"
                painter.drawText(QRectF(center - width / 2, 0, width, 18), Qt.AlignmentFlag.AlignCenter, value_text)


class WeeklyLearningCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomePanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(4)
        header = QHBoxLayout()
        title = QLabel("本周学习")
        title.setProperty("role", "home-section-title")
        self.total_label = QLabel("本周累计 0 分钟")
        self.total_label.setProperty("role", "home-meta")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(self.total_label)
        self.bars = WeeklyBarsWidget()
        self.compare_label = QLabel("开始记录本周的有效学习时间")
        self.compare_label.setProperty("role", "home-meta")
        root.addLayout(header)
        root.addWidget(self.bars, stretch=1)
        root.addWidget(self.compare_label)

    def set_values(self, values: Sequence[float]) -> None:
        values = list(values[:7]) + [0.0] * max(0, 7 - len(values))
        total = sum(values)
        self.bars.set_values(values)
        self.total_label.setText(f"本周累计 {total / 3600:.1f} 小时" if total >= 3600 else f"本周累计 {int(total / 60)} 分钟")
        active_days = sum(1 for value in values if value > 0)
        self.compare_label.setText(f"本周已有 {active_days} 天开始学习" if active_days else "开始记录本周的有效学习时间")


class RecentLearningCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomePanel")
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(0)
        title = QLabel("最近学习")
        title.setProperty("role", "home-section-title")
        root.addWidget(title)
        self.rows: list[tuple[QLabel, QLabel, QProgressBar, QLabel]] = []
        for _index in range(3):
            row_frame = QFrame()
            row_frame.setObjectName("HomeRecentRow")
            row = QHBoxLayout(row_frame)
            row.setContentsMargins(0, 8, 0, 8)
            row.setSpacing(12)
            name = QLabel("暂无学习记录")
            name.setProperty("role", "home-task-title")
            meta = QLabel("")
            meta.setProperty("role", "home-meta")
            progress = QProgressBar()
            progress.setObjectName("HomeRecentProgress")
            progress.setRange(0, 100)
            progress.setValue(0)
            progress.setTextVisible(False)
            progress.setFixedWidth(130)
            progress.setFixedHeight(6)
            percent = QLabel("")
            percent.setProperty("role", "home-meta")
            row.addWidget(name, stretch=2)
            row.addWidget(meta, stretch=2)
            row.addWidget(progress)
            row.addWidget(percent)
            root.addWidget(row_frame)
            self.rows.append((name, meta, progress, percent))

    def set_items(self, items: Sequence[dict[str, object]]) -> None:
        for index, widgets in enumerate(self.rows):
            name, meta, progress, percent = widgets
            if index >= len(items):
                name.setText("暂无更多学习记录" if index == 0 else "")
                meta.setText("")
                progress.hide()
                percent.setText("")
                continue
            item = items[index]
            value = max(0, min(100, int(item.get("progress") or 0)))
            name.setText(str(item.get("title") or "未命名内容"))
            meta.setText(str(item.get("meta") or ""))
            progress.setValue(value)
            progress.show()
            percent.setText(f"{value}%")


class HomePage(QWidget):
    article_library_requested = Signal()
    courses_requested = Signal()
    special_practice_requested = Signal()
    vocabulary_requested = Signal()
    fsrs_review_requested = Signal()
    history_requested = Signal()
    statistics_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("HomeScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)

        content = QWidget()
        content.setObjectName("HomeContent")
        self.scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 22, 28, 24)
        layout.setSpacing(16)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(3)
        title = QLabel("继续学习")
        title.setProperty("role", "page-title")
        self.subtitle = QLabel("今天尚未开始学习，选择一项内容进入状态。")
        self.subtitle.setProperty("role", "subtitle")
        heading.addWidget(title)
        heading.addWidget(self.subtitle)
        header.addLayout(heading)
        header.addStretch(1)
        layout.addLayout(header)

        top = QGridLayout()
        top.setHorizontalSpacing(16)
        top.setVerticalSpacing(16)
        self.continue_card = ContinueLearningCard()
        self.daily_learning_card = DailyLearningCard()
        top.addWidget(self.continue_card, 0, 0)
        top.addWidget(self.daily_learning_card, 0, 1)
        top.setColumnStretch(0, 5)
        top.setColumnStretch(1, 4)
        layout.addLayout(top)

        middle = QGridLayout()
        middle.setHorizontalSpacing(16)
        middle.setVerticalSpacing(16)

        tasks_card = QFrame()
        tasks_card.setObjectName("HomePanel")
        tasks_layout = QVBoxLayout(tasks_card)
        tasks_layout.setContentsMargins(20, 14, 20, 14)
        tasks_layout.setSpacing(0)
        tasks_title = QLabel("今日学习任务")
        tasks_title.setProperty("role", "home-section-title")
        tasks_layout.addWidget(tasks_title)
        self.course_task = HomeTaskRow("课", "继续课程", "选择一节课程继续学习", "继续学习", "blue")
        self.review_task = HomeTaskRow("词", "单词复习", "读取今日待复习单词", "开始复习", "green")
        self.error_task = HomeTaskRow("错", "错句练习", "根据错误记录安排专项练习", "开始练习", "violet")
        for task in (self.course_task, self.review_task, self.error_task):
            tasks_layout.addWidget(task)
        middle.addWidget(tasks_card, 0, 0, 2, 1)

        self.weekly_card = WeeklyLearningCard()
        middle.addWidget(self.weekly_card, 0, 1)

        quick_card = QFrame()
        quick_card.setObjectName("HomePanel")
        quick_layout = QVBoxLayout(quick_card)
        quick_layout.setContentsMargins(20, 14, 20, 14)
        quick_layout.setSpacing(10)
        quick_title = QLabel("快速开始")
        quick_title.setProperty("role", "home-section-title")
        quick_layout.addWidget(quick_title)
        quick_grid = QGridLayout()
        quick_grid.setSpacing(8)
        self.article_card = HomeActionCard("文章阅读", "导入与练习", "打开", self)
        self.course_card = HomeActionCard("内置课程", "按推荐顺序学习", "打开", self)
        self.special_card = HomeActionCard("专项练习", "复习错误内容", "打开", self)
        self.vocabulary_card = HomeActionCard("单词复习", "单词与 FSRS", "打开", self)
        self.history_card = HomeActionCard("练习记录", "查看最近成绩", "打开", self)
        for index, card in enumerate((self.article_card, self.course_card, self.special_card, self.vocabulary_card, self.history_card)):
            quick_grid.addWidget(card, 0, index)
            quick_grid.setColumnStretch(index, 1)
        quick_layout.addLayout(quick_grid)
        middle.addWidget(quick_card, 1, 1)
        middle.setColumnStretch(0, 5)
        middle.setColumnStretch(1, 4)
        layout.addLayout(middle)

        self.recent_card = RecentLearningCard()
        layout.addWidget(self.recent_card)

        self.continue_card.requested.connect(self.courses_requested.emit)
        self.article_card.action_button.clicked.connect(self.article_library_requested.emit)
        self.course_card.action_button.clicked.connect(self.courses_requested.emit)
        self.special_card.action_button.clicked.connect(self.special_practice_requested.emit)
        self.vocabulary_card.action_button.clicked.connect(self.vocabulary_requested.emit)
        self.history_card.action_button.clicked.connect(self.history_requested.emit)
        self.course_task.requested.connect(self.courses_requested.emit)
        self.review_task.requested.connect(self.fsrs_review_requested.emit)
        self.error_task.requested.connect(self.special_practice_requested.emit)

    def update_dashboard(self, data: LearningDashboard, goal_minutes: int, weekly_seconds: Sequence[float]) -> None:
        self.daily_learning_card.update_dashboard(data, goal_minutes)
        elapsed = int(data.effective_seconds)
        if elapsed:
            self.subtitle.setText(f"今天已学习 {elapsed // 60} 分钟，连续学习 {data.current_streak} 天。")
        else:
            self.subtitle.setText("今天尚未开始学习，选择一项内容进入状态。")
        self.weekly_card.set_values(weekly_seconds)

    def update_course(self, data: dict[str, object] | None) -> None:
        self.continue_card.update_course(data)
        if not data:
            self.course_task.set_detail("选择一节课程开始学习")
            return
        progress = int(round(float(data.get("progress") or 0)))
        title = str(data.get("lesson_title") or data.get("course_title") or "继续课程")
        self.course_task.set_detail(f"{title} · 课程进度 {progress}%", completed=progress >= 100)

    def update_tasks(self, *, due_words: int, due_errors: int) -> None:
        self.review_task.set_detail(f"{due_words} 个待复习单词" if due_words else "今日暂无到期单词", completed=due_words == 0)
        self.error_task.set_detail(f"{due_errors} 项待复习内容" if due_errors else "暂无到期错误复习", completed=due_errors == 0)

    def update_recent(self, items: Sequence[dict[str, object]]) -> None:
        self.recent_card.set_items(items)
