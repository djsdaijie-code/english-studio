from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from english_typing_trainer.models.learning import LearningDashboard
from english_typing_trainer.services.learning_progress import ACHIEVEMENT_NAMES


RANK_COLORS = {
    "启程": "#8291a5",
    "微光": "#3d8fa8",
    "晨星": "#8eb9d7",
    "星河": "#6e72bf",
    "极光": "#4d9e9a",
    "天穹": "#36527a",
    "恒星": "#c9a34c",
}


class ProgressRing(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._progress = 0.0
        self.setFixedSize(126, 126)

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, value: float) -> None:
        self._progress = max(0.0, float(value))
        self.update()

    progress = Property(float, get_progress, set_progress)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        dark = self.palette().window().color().lightness() < 128
        rect = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        painter.setPen(QPen(QColor("#2a3a50" if dark else "#dfe7f4"), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)
        painter.setPen(QPen(QColor("#5f8fe8" if dark else "#2f6fec"), 10, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 90 * 16, -int(360 * 16 * min(1.0, self._progress)))

        painter.setPen(self.palette().text().color())
        font = painter.font()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(0, 35, self.width(), 38), Qt.AlignmentFlag.AlignCenter, f"{int(self._progress * 100)}%")
        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor("#9aa9bb" if dark else "#64748b"))
        painter.drawText(QRectF(0, 68, self.width(), 24), Qt.AlignmentFlag.AlignCenter, "已完成")


class DailyLearningCard(QFrame):
    review_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeGoalCard")
        self.setMinimumHeight(236)
        self.setMaximumHeight(252)
        self._played: set[int] = set()
        self._animation: QPropertyAnimation | None = None
        self._last_rank: str | None = None
        self._effects: list[tuple[QGraphicsOpacityEffect, QPropertyAnimation]] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(10)
        title = QLabel("今日目标")
        title.setProperty("role", "home-section-title")
        root.addWidget(title)

        body = QHBoxLayout()
        body.setSpacing(22)
        self.ring = ProgressRing()
        body.addWidget(self.ring, alignment=Qt.AlignmentFlag.AlignVCenter)

        details = QVBoxLayout()
        details.setSpacing(0)
        self.goal_label = self._detail_row("今日目标", "15 分钟")
        self.time_label = self._detail_row("已完成", "0 分钟")
        self.streak_label = self._detail_row("连续学习", "0 天")
        self.rank_value = self._detail_row("当前等级", "启程 III")
        for row, _value in (self.goal_label, self.time_label, self.streak_label, self.rank_value):
            details.addLayout(row)
        body.addLayout(details, stretch=1)
        root.addLayout(body, stretch=1)

        self.heading = QLabel("开始今天的学习")
        self.heading.setProperty("role", "home-goal-footer")
        self.tier_label = QLabel("达到 15 分钟后自动完成今日打卡")
        self.tier_label.setProperty("role", "home-meta")
        root.addWidget(self.heading)
        root.addWidget(self.tier_label)

        # Retain the public fields used by the learning progression controller.
        self.checkin_label = QLabel()
        self.total_label = QLabel()
        self.week_label = QLabel()
        self.rank_badge = QLabel("启程 III")
        self.xp_label = QLabel("累计经验 0")
        self.rank_progress = QProgressBar()
        self.rank_hint = QLabel()
        self.achievement_label = QLabel()
        self.review_button = QPushButton("开始今日复习")
        self.review_button.hide()
        self.review_button.clicked.connect(self.review_requested.emit)

    @staticmethod
    def _detail_row(label: str, value: str) -> tuple[QHBoxLayout, QLabel]:
        row = QHBoxLayout()
        row.setContentsMargins(0, 6, 0, 6)
        name = QLabel(label)
        name.setProperty("role", "home-meta")
        value_label = QLabel(value)
        value_label.setProperty("role", "home-goal-value")
        row.addWidget(name)
        row.addStretch(1)
        row.addWidget(value_label)
        return row, value_label

    def update_dashboard(
        self,
        data: LearningDashboard,
        goal_minutes: int,
        *,
        animate: bool = False,
        reduce_motion: bool = False,
    ) -> None:
        goal_seconds = max(60, goal_minutes * 60)
        target = data.effective_seconds / goal_seconds
        if animate and not reduce_motion:
            self._animate_ring(target)
        else:
            self.ring.set_progress(target)

        elapsed = int(data.effective_seconds)
        self.goal_label[1].setText(f"{goal_minutes} 分钟")
        self.time_label[1].setText(f"{elapsed // 60} 分钟")
        self.streak_label[1].setText(f"{data.current_streak} 天")
        self.rank_value[1].setText(data.current_rank)
        self.heading.setText("今日已完成，坚持得很好" if data.checked_in else "继续一点，进步看得见")
        if data.next_tier_minutes is None:
            self.tier_label.setText("已达到今日最高经验档位，继续学习仍会记录有效时间")
        else:
            remaining = max(0, data.next_tier_minutes * 60 - data.effective_seconds)
            self.tier_label.setText(f"距离 {data.next_tier_minutes} 分钟档位还差 {int(remaining) // 60} 分钟")

        self.checkin_label.setText("今日已自动打卡" if data.checked_in else "达到 15 分钟自动打卡")
        self.total_label.setText(f"累计有效打卡 {data.total_checkin_days} 天 · 本月 {data.month_completed} 天")
        self.week_label.setText(" ".join("●" if done else "○" for done in data.week_track))
        self.rank_badge.setText(data.current_rank)
        family = data.current_rank.split()[0]
        color = RANK_COLORS.get(family, "#8291a5")
        self.rank_badge.setStyleSheet(f"padding: 8px 14px; border: 1px solid {color}; border-radius: 14px; font-weight: 650;")
        if self._last_rank is not None and self._last_rank != data.current_rank and not reduce_motion:
            self._fade_in(self.rank_value[1], 1400)
        self._last_rank = data.current_rank
        self.xp_label.setText(f"累计经验 {data.total_xp}")
        self.rank_progress.setRange(0, max(1, data.rank_days_required))
        self.rank_progress.setValue(data.rank_days_current)
        self.rank_hint.setText("已达到最高等级" if data.next_rank is None else f"距离 {data.next_rank} 还差 {max(0, data.rank_days_required - data.rank_days_current)} 天")
        achievement = ACHIEVEMENT_NAMES.get(data.latest_achievement, data.latest_achievement)
        self.achievement_label.setText(f"最近成就：{achievement}")

    def play_milestone(self, minutes: int, reduce_motion: bool = False) -> bool:
        if minutes in self._played:
            return False
        self._played.add(minutes)
        if not reduce_motion:
            self._animate_ring(self.ring.progress)
        return True

    def play_achievement(self, name: str, reduce_motion: bool = False) -> None:
        self.achievement_label.setText(f"最近成就：{name}")
        if not reduce_motion:
            self._fade_in(self.achievement_label, 650)

    def _fade_in(self, widget: QWidget, duration: int) -> None:
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        animation = QPropertyAnimation(effect, b"opacity", self)
        animation.setDuration(duration)
        animation.setStartValue(0.15)
        animation.setEndValue(1.0)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(
            lambda: self._effects.remove((effect, animation)) if (effect, animation) in self._effects else None
        )
        self._effects.append((effect, animation))
        animation.start()

    def _animate_ring(self, target: float) -> None:
        animation = QPropertyAnimation(self.ring, b"progress", self)
        animation.setDuration(750)
        animation.setStartValue(self.ring.progress)
        animation.setEndValue(target)
        animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.start()
        self._animation = animation
