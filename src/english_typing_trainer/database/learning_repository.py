from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.models.learning import LearningDashboard, LearningEvent, LearningUpdate


TIERS = ((15, 100), (30, 60), (45, 40), (60, 30), (90, 20))
REMINDERS = (120, 180, 240)
RANKS = (
    (1, "启程 III"), (3, "启程 II"), (7, "启程 I"),
    (14, "微光 III"), (21, "微光 II"), (30, "微光 I"),
    (45, "晨星 III"), (60, "晨星 II"), (90, "晨星 I"),
    (120, "星河 III"), (180, "星河 II"), (240, "星河 I"),
    (365, "极光"), (500, "天穹"), (730, "恒星"),
)


def rank_for_days(days: int) -> tuple[str, str | None, int, int]:
    current_name = RANKS[0][1]
    current_threshold = 0
    next_name: str | None = RANKS[0][1]
    next_threshold = RANKS[0][0]
    for index, (threshold, name) in enumerate(RANKS):
        if days >= threshold:
            current_name = name
            current_threshold = threshold
            if index + 1 < len(RANKS):
                next_threshold, next_name = RANKS[index + 1]
            else:
                next_name = None
                next_threshold = threshold
        else:
            next_name = name
            next_threshold = threshold
            break
    return current_name, next_name, current_threshold, next_threshold


class LearningRepository:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def save_events(self, events: list[LearningEvent]) -> LearningUpdate:
        update = LearningUpdate()
        if not events:
            return update
        affected: set[str] = set()
        with self.database.transaction() as connection:
            for event in events:
                stamp = event.occurred_at.isoformat(timespec="seconds")
                day = event.occurred_at.date().isoformat()
                affected.add(day)
                connection.execute(
                    """INSERT INTO learning_events(event_type,active_seconds,related_article_id,
                       related_sentence_id,related_vocabulary_id,metadata_json,occurred_at)
                       VALUES (?,?,?,?,?,?,?)""",
                    (event.event_type, event.active_seconds, event.related_article_id,
                     event.related_sentence_id, event.related_vocabulary_id,
                     json.dumps(event.metadata, ensure_ascii=False), stamp),
                )
                connection.execute(
                    """INSERT INTO daily_learning_stats(date,effective_seconds,first_activity_at,last_activity_at,created_at,updated_at)
                       VALUES (?,?,?,?,?,?)
                       ON CONFLICT(date) DO UPDATE SET
                         effective_seconds=effective_seconds+excluded.effective_seconds,
                         first_activity_at=COALESCE(first_activity_at,excluded.first_activity_at),
                         last_activity_at=excluded.last_activity_at,updated_at=excluded.updated_at""",
                    (day, event.active_seconds, stamp, stamp, stamp, stamp),
                )
            for day in affected:
                row = connection.execute("SELECT * FROM daily_learning_stats WHERE date=?", (day,)).fetchone()
                seconds = float(row["effective_seconds"])
                values = {minutes: seconds >= minutes * 60 for minutes, _xp in TIERS}
                for minutes, _xp in TIERS:
                    if values[minutes] and not row[f"reached_{minutes}"]:
                        update.milestones.append(minutes)
                awarded = sum(xp for minutes, xp in TIERS if values[minutes])
                connection.execute(
                    """UPDATE daily_learning_stats SET checked_in=?,reached_15=?,reached_30=?,reached_45=?,
                       reached_60=?,reached_90=?,awarded_xp=?,updated_at=? WHERE date=?""",
                    (int(values[15]), *(int(values[m]) for m in (15, 30, 45, 60, 90)),
                     awarded, datetime.now().isoformat(timespec="seconds"), day),
                )
        self.refresh_profile(max(event.occurred_at.date() for event in events))
        return update

    def mark_reminder(self, day: str, minutes: int) -> bool:
        if minutes not in REMINDERS:
            return False
        column = f"reminder_{minutes}_shown"
        with self.database.transaction() as connection:
            row = connection.execute(f"SELECT {column} FROM daily_learning_stats WHERE date=?", (day,)).fetchone()
            if not row or row[0]:
                return False
            connection.execute(f"UPDATE daily_learning_stats SET {column}=1 WHERE date=?", (day,))
        return True

    def refresh_profile(self, today: date | None = None) -> dict[str, object]:
        today = today or date.today()
        rows = self.database.connect().execute(
            "SELECT date,awarded_xp FROM daily_learning_stats WHERE checked_in=1 ORDER BY date"
        ).fetchall()
        dates = [date.fromisoformat(row["date"]) for row in rows]
        total_xp = sum(int(row["awarded_xp"]) for row in rows)
        longest = 0
        run = 0
        previous = None
        for item in dates:
            run = run + 1 if previous and item == previous + timedelta(days=1) else 1
            longest = max(longest, run)
            previous = item
        current = 0
        cursor = today
        checked = set(dates)
        if cursor not in checked:
            cursor -= timedelta(days=1)
        while cursor in checked:
            current += 1
            cursor -= timedelta(days=1)
        rank, _next, _start, _required = rank_for_days(len(dates))
        stamp = datetime.now().isoformat(timespec="seconds")
        with self.database.transaction() as connection:
            connection.execute(
                """INSERT INTO profile_progress(id,total_xp,total_checkin_days,current_streak,longest_streak,current_rank,updated_at)
                   VALUES (1,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET total_xp=excluded.total_xp,
                   total_checkin_days=excluded.total_checkin_days,current_streak=excluded.current_streak,
                   longest_streak=excluded.longest_streak,current_rank=excluded.current_rank,updated_at=excluded.updated_at""",
                (total_xp, len(dates), current, longest, rank, stamp),
            )
        return {"total_xp": total_xp, "total_checkin_days": len(dates), "current_streak": current,
                "longest_streak": longest, "current_rank": rank}

    def dashboard(self, today: date | None = None) -> LearningDashboard:
        today = today or date.today()
        day = today.isoformat()
        row = self.database.connect().execute("SELECT * FROM daily_learning_stats WHERE date=?", (day,)).fetchone()
        profile_row = self.database.connect().execute("SELECT * FROM profile_progress WHERE id=1").fetchone()
        profile = dict(profile_row) if profile_row else self.refresh_profile(today)
        seconds = float(row["effective_seconds"]) if row else 0.0
        current_tier = max((minutes for minutes, _xp in TIERS if seconds >= minutes * 60), default=0)
        next_tier = next((minutes for minutes, _xp in TIERS if seconds < minutes * 60), None)
        week_start = today - timedelta(days=today.weekday())
        week_days = [week_start + timedelta(days=i) for i in range(7)]
        checked_rows = self.database.connect().execute(
            "SELECT date FROM daily_learning_stats WHERE checked_in=1 AND date BETWEEN ? AND ?",
            (week_days[0].isoformat(), week_days[-1].isoformat()),
        ).fetchall()
        checked_week = {item["date"] for item in checked_rows}
        month_prefix = today.strftime("%Y-%m") + "%"
        month_completed = self.database.connect().execute(
            "SELECT COUNT(*) FROM daily_learning_stats WHERE checked_in=1 AND date LIKE ?", (month_prefix,)
        ).fetchone()[0]
        rank, next_rank, rank_start, rank_required = rank_for_days(int(profile["total_checkin_days"]))
        latest = self.database.connect().execute(
            "SELECT achievement_key FROM achievements WHERE unlocked_at IS NOT NULL ORDER BY unlocked_at DESC LIMIT 1"
        ).fetchone()
        return LearningDashboard(
            date=day, effective_seconds=seconds, checked_in=bool(row and row["checked_in"]),
            current_tier_minutes=current_tier, next_tier_minutes=next_tier,
            awarded_xp=int(row["awarded_xp"]) if row else 0, total_xp=int(profile["total_xp"]),
            total_checkin_days=int(profile["total_checkin_days"]), current_streak=int(profile["current_streak"]),
            longest_streak=int(profile["longest_streak"]), current_rank=rank, next_rank=next_rank,
            rank_days_current=max(0, int(profile["total_checkin_days"]) - rank_start),
            rank_days_required=max(1, rank_required - rank_start), week_completed=len(checked_week),
            month_completed=int(month_completed), week_track=[item.isoformat() in checked_week for item in week_days],
            latest_achievement=latest[0] if latest else "尚未解锁成就",
        )

    def weekly_effective_seconds(self, today: date | None = None) -> list[float]:
        """Return Monday-to-Sunday effective study time for the home dashboard."""
        today = today or date.today()
        week_start = today - timedelta(days=today.weekday())
        week_days = [week_start + timedelta(days=index) for index in range(7)]
        rows = self.database.connect().execute(
            "SELECT date,effective_seconds FROM daily_learning_stats WHERE date BETWEEN ? AND ?",
            (week_days[0].isoformat(), week_days[-1].isoformat()),
        ).fetchall()
        seconds_by_day = {row["date"]: float(row["effective_seconds"]) for row in rows}
        return [seconds_by_day.get(day.isoformat(), 0.0) for day in week_days]

    def unlock_achievement(self, key: str, progress: float, threshold: float, metadata: dict[str, object] | None = None) -> bool:
        stamp = datetime.now().isoformat(timespec="seconds")
        with self.database.transaction() as connection:
            row = connection.execute("SELECT unlocked_at FROM achievements WHERE achievement_key=?", (key,)).fetchone()
            unlocked = progress >= threshold
            if row and row["unlocked_at"]:
                return False
            connection.execute(
                """INSERT INTO achievements(achievement_key,unlocked_at,progress,metadata_json) VALUES (?,?,?,?)
                   ON CONFLICT(achievement_key) DO UPDATE SET unlocked_at=COALESCE(achievements.unlocked_at,excluded.unlocked_at),
                   progress=MAX(achievements.progress,excluded.progress),metadata_json=excluded.metadata_json""",
                (key, stamp if unlocked else None, progress, json.dumps(metadata or {}, ensure_ascii=False)),
            )
        return unlocked
