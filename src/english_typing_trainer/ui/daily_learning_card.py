from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from english_typing_trainer.models.learning import LearningDashboard
from english_typing_trainer.services.learning_progress import ACHIEVEMENT_NAMES


RANK_COLORS = {
    "启程": "#8291a5", "微光": "#3d8fa8", "晨星": "#8eb9d7", "星河": "#6e72bf",
    "极光": "#4d9e9a", "天穹": "#36527a", "恒星": "#c9a34c",
}


class ProgressRing(QWidget):
    def __init__(self,parent=None) -> None:
        super().__init__(parent); self._progress=0.0; self.setFixedSize(116,116)

    def get_progress(self) -> float:return self._progress
    def set_progress(self,value:float) -> None:self._progress=max(0.0,min(1.0,float(value)));self.update()
    progress=Property(float,get_progress,set_progress)

    def paintEvent(self,event) -> None:  # type: ignore[override]
        painter=QPainter(self); painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect=self.rect().adjusted(9,9,-9,-9); dark=self.palette().window().color().lightness()<128
        painter.setPen(QPen(QColor("#35404e" if dark else "#dbe3ec"),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); painter.drawArc(rect,0,360*16)
        painter.setPen(QPen(QColor("#5b87ad" if dark else "#4f7698"),9,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap)); painter.drawArc(rect,90*16,-int(360*16*self._progress))
        painter.setPen(self.palette().text().color()); font=painter.font();font.setPointSize(13);font.setBold(True);painter.setFont(font)
        painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,f"{int(self._progress*100)}%")


class DailyLearningCard(QFrame):
    def __init__(self,parent=None) -> None:
        super().__init__(parent); self.setObjectName("CardAccent"); self.setMaximumHeight(196); self._played=set(); self._animation=None; self._last_rank=None; self._effects=[]
        root=QHBoxLayout(self); root.setContentsMargins(24,18,24,18); root.setSpacing(22)
        self.ring=ProgressRing(); root.addWidget(self.ring)
        main=QVBoxLayout(); main.setSpacing(5); self.heading=QLabel("今日学习"); self.heading.setProperty("role","page-title"); self.time_label=QLabel("00:00 / 15:00"); self.time_label.setStyleSheet("font-size: 22px; font-weight: 650;")
        self.tier_label=QLabel("开始一次学习，向今日目标出发"); self.tier_label.setProperty("role","subtitle"); main.addWidget(self.heading);main.addWidget(self.time_label);main.addWidget(self.tier_label);root.addLayout(main,2)
        stats=QVBoxLayout();stats.setSpacing(7);self.checkin_label=QLabel("今日未打卡");self.streak_label=QLabel("连续 0 天 · 本周 0/7");self.total_label=QLabel("累计有效打卡 0 天")
        for label in (self.checkin_label,self.streak_label,self.total_label):stats.addWidget(label)
        self.week_label=QLabel("○ ○ ○ ○ ○ ○ ○");self.week_label.setProperty("role","subtitle");stats.addWidget(self.week_label);root.addLayout(stats,2)
        rank=QVBoxLayout();rank.setSpacing(6);self.rank_badge=QLabel("启程 III");self.rank_badge.setAlignment(Qt.AlignmentFlag.AlignCenter);self.rank_badge.setMinimumWidth(120);self.rank_badge.setStyleSheet("padding: 8px 14px; border: 1px solid #8291a5; border-radius: 14px; font-weight: 650;")
        self.xp_label=QLabel("累计经验 0");self.rank_progress=QProgressBar();self.rank_progress.setTextVisible(False);self.rank_progress.setFixedHeight(7);self.rank_hint=QLabel("距离下一等级 1 天");self.rank_hint.setProperty("role","subtitle");self.achievement_label=QLabel("最近成就：尚未解锁成就");self.achievement_label.setProperty("role","subtitle")
        for widget in (self.rank_badge,self.xp_label,self.rank_progress,self.rank_hint,self.achievement_label):rank.addWidget(widget)
        root.addLayout(rank,2)

    def update_dashboard(self,data:LearningDashboard,goal_minutes:int,*,animate:bool=False,reduce_motion:bool=False) -> None:
        goal_seconds=max(60,goal_minutes*60); target=min(1.0,data.effective_seconds/goal_seconds)
        if animate and not reduce_motion:self._animate_ring(target)
        else:self.ring.set_progress(target)
        elapsed=int(data.effective_seconds); self.time_label.setText(f"{elapsed//60:02d}:{elapsed%60:02d} / {goal_minutes:02d}:00")
        if data.checked_in:self.heading.setText("今日已完成")
        else:self.heading.setText("今日学习")
        if data.next_tier_minutes is None:self.tier_label.setText("已达到今日最高经验档位，继续记录但不再增加经验")
        else:
            remaining=max(0,data.next_tier_minutes*60-data.effective_seconds)
            self.tier_label.setText(f"当前档位 {data.current_tier_minutes or '未达成'} · 距 {data.next_tier_minutes} 分钟还差 {int(remaining)//60:02d}:{int(remaining)%60:02d}")
        self.checkin_label.setText("今日已自动打卡" if data.checked_in else "达到 15 分钟自动打卡")
        self.streak_label.setText(f"连续 {data.current_streak} 天 · 本周 {data.week_completed}/7")
        self.total_label.setText(f"累计有效打卡 {data.total_checkin_days} 天 · 本月 {data.month_completed} 天")
        self.week_label.setText(" ".join("●" if done else "○" for done in data.week_track))
        self.rank_badge.setText(data.current_rank); family=data.current_rank.split()[0];color=RANK_COLORS.get(family,"#8291a5")
        self.rank_badge.setStyleSheet(f"padding: 8px 14px; border: 1px solid {color}; border-radius: 14px; font-weight: 650;")
        if self._last_rank is not None and self._last_rank!=data.current_rank and not reduce_motion:self._fade_in(self.rank_badge,1400)
        self._last_rank=data.current_rank
        self.xp_label.setText(f"累计经验 {data.total_xp}");self.rank_progress.setRange(0,max(1,data.rank_days_required));self.rank_progress.setValue(data.rank_days_current)
        self.rank_hint.setText("已达到最高等级" if data.next_rank is None else f"距离 {data.next_rank} 还差 {max(0,data.rank_days_required-data.rank_days_current)} 天")
        achievement=ACHIEVEMENT_NAMES.get(data.latest_achievement,data.latest_achievement);self.achievement_label.setText(f"最近成就：{achievement}")

    def play_milestone(self,minutes:int,reduce_motion:bool=False) -> bool:
        if minutes in self._played:return False
        self._played.add(minutes)
        if not reduce_motion:self._animate_ring(self.ring.progress)
        return True

    def play_achievement(self,name:str,reduce_motion:bool=False) -> None:
        self.achievement_label.setText(f"最近成就：{name}")
        if not reduce_motion:self._fade_in(self.achievement_label,650)

    def _fade_in(self,widget:QWidget,duration:int) -> None:
        effect=QGraphicsOpacityEffect(widget);widget.setGraphicsEffect(effect)
        animation=QPropertyAnimation(effect,b"opacity",self);animation.setDuration(duration);animation.setStartValue(0.15);animation.setEndValue(1.0);animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        animation.finished.connect(lambda:self._effects.remove((effect,animation)) if (effect,animation) in self._effects else None)
        self._effects.append((effect,animation));animation.start()

    def _animate_ring(self,target:float) -> None:
        animation=QPropertyAnimation(self.ring,b"progress",self);animation.setDuration(750);animation.setStartValue(self.ring.progress);animation.setEndValue(target);animation.setEasingCurve(QEasingCurve.Type.OutCubic);animation.start();self._animation=animation
