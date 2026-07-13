from __future__ import annotations

from datetime import datetime, time, timedelta
from time import monotonic
from typing import Callable

from english_typing_trainer.database.learning_repository import LearningRepository
from english_typing_trainer.models.learning import LearningEvent, LearningUpdate
from english_typing_trainer.services.learning_progress import LearningProgressService


class LearningTimeTracker:
    def __init__(self, repository: LearningRepository, progress: LearningProgressService, *,
                 monotonic_clock: Callable[[], float] = monotonic,
                 wall_clock: Callable[[], datetime] = datetime.now,
                 idle_timeout_seconds: int = 90, flush_interval_seconds: int = 20,
                 health_reminders_enabled: bool = True) -> None:
        self.repository=repository; self.progress=progress; self.monotonic_clock=monotonic_clock; self.wall_clock=wall_clock
        self.idle_timeout_seconds=idle_timeout_seconds; self.flush_interval_seconds=flush_interval_seconds
        self.active=False; self.last_monotonic=0.0; self.last_activity_monotonic=0.0; self.last_wall:datetime|None=None; self.current_event_type="learning"
        self.related_article_id=None; self.related_sentence_id=None; self.related_vocabulary_id=None
        self.pending:list[LearningEvent]=[]; self.pending_seconds=0.0; self.last_update=LearningUpdate()
        self.health_reminders_enabled=health_reminders_enabled

    def configure(self, idle_timeout_seconds: int, health_reminders_enabled: bool | None = None) -> None:
        self.idle_timeout_seconds=max(1,int(idle_timeout_seconds))
        if health_reminders_enabled is not None:self.health_reminders_enabled=bool(health_reminders_enabled)

    def activity(self,event_type:str,*,related_article_id:int|None=None,related_sentence_id:int|None=None,
                 related_vocabulary_id:int|None=None,metadata:dict[str,object]|None=None) -> LearningUpdate:
        now_mono=self.monotonic_clock(); now_wall=self.wall_clock()
        if self.active:self._accrue(now_mono)
        else:self.last_monotonic=now_mono; self.last_wall=now_wall
        self.active=True; self.last_activity_monotonic=now_mono; self.current_event_type=event_type
        self.related_article_id=related_article_id; self.related_sentence_id=related_sentence_id; self.related_vocabulary_id=related_vocabulary_id
        if metadata or event_type not in {"typing_activity","source_changed"}:
            self.pending.append(LearningEvent(event_type,0,now_wall,related_article_id,related_sentence_id,related_vocabulary_id,metadata or {}))
        if self.pending_seconds>=self.flush_interval_seconds:return self.flush()
        return LearningUpdate()

    def tick(self) -> LearningUpdate:
        if not self.active:return LearningUpdate()
        now=self.monotonic_clock()
        if now-self.last_activity_monotonic>=self.idle_timeout_seconds:
            self._accrue(self.last_activity_monotonic+self.idle_timeout_seconds); self.active=False
            return self.flush()
        self._accrue(now)
        if self.pending_seconds>=self.flush_interval_seconds:return self.flush()
        return LearningUpdate()

    def stop(self, *, count_elapsed: bool=True) -> LearningUpdate:
        if self.active and count_elapsed:self._accrue(self.monotonic_clock())
        self.active=False
        return self.flush()

    def suspend_for_network(self) -> LearningUpdate:
        return self.stop(count_elapsed=False)

    def flush(self) -> LearningUpdate:
        if not self.pending:return LearningUpdate()
        update=self.repository.save_events(self.pending); update.achievements=self.progress.evaluate_achievements(self.wall_clock().date())
        dashboard=self.repository.dashboard(self.wall_clock().date())
        if self.health_reminders_enabled:
            for minutes in (120,180,240):
                if dashboard.effective_seconds>=minutes*60 and self.repository.mark_reminder(dashboard.date,minutes):update.reminders.append(minutes)
        self.pending=[]; self.pending_seconds=0.0; self.last_update=update; return update

    def _accrue(self, now_mono: float) -> None:
        if not self.active or self.last_wall is None:return
        raw=now_mono-self.last_monotonic
        if raw<=0:return
        seconds=min(raw,float(self.idle_timeout_seconds))
        start=self.last_wall; remaining=seconds
        while remaining>0:
            midnight=datetime.combine(start.date()+timedelta(days=1),time.min)
            span=min(remaining,max(0.0,(midnight-start).total_seconds()))
            if span<=0:span=remaining
            self._append_active_time(span,start)
            self.pending_seconds+=span; remaining-=span; start+=timedelta(seconds=span)
        self.last_monotonic=now_mono; self.last_wall=start

    def _append_active_time(self, seconds: float, occurred_at: datetime) -> None:
        if self.pending:
            previous=self.pending[-1]
            same_target=(previous.event_type==self.current_event_type
                and previous.related_article_id==self.related_article_id
                and previous.related_sentence_id==self.related_sentence_id
                and previous.related_vocabulary_id==self.related_vocabulary_id)
            if same_target and not previous.metadata and previous.occurred_at.date()==occurred_at.date():
                previous.active_seconds+=seconds
                return
        self.pending.append(LearningEvent(self.current_event_type,seconds,occurred_at,self.related_article_id,
            self.related_sentence_id,self.related_vocabulary_id))
