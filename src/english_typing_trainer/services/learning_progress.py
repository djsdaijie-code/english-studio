from __future__ import annotations

import json
from datetime import date, datetime

from english_typing_trainer.database.learning_repository import LearningRepository


ACHIEVEMENT_NAMES = {
    "first_checkin": "初次启程", "week_five": "一周同行", "month_twenty": "稳定一月",
    "hundred_days": "百日积累", "first_article": "第一篇文章", "thousand_words": "千词输入",
    "vocabulary_collector": "词汇收藏家", "listen_read": "听读同行",
    "finish_word_queue": "有始有终", "precision_typing": "精准输入",
}


class LearningProgressService:
    def __init__(self, repository: LearningRepository) -> None:
        self.repository = repository

    def evaluate_achievements(self, today: date | None = None) -> list[str]:
        today = today or date.today()
        connection = self.repository.database.connect()
        total_days = connection.execute("SELECT COUNT(*) FROM daily_learning_stats WHERE checked_in=1").fetchone()[0]
        week_start = today.fromordinal(today.toordinal() - today.weekday()).isoformat()
        week_end = today.fromordinal(today.toordinal() - today.weekday() + 6).isoformat()
        week_days = connection.execute("SELECT COUNT(*) FROM daily_learning_stats WHERE checked_in=1 AND date BETWEEN ? AND ?", (week_start, week_end)).fetchone()[0]
        month_days = connection.execute("SELECT COUNT(*) FROM daily_learning_stats WHERE checked_in=1 AND date LIKE ?", (today.strftime("%Y-%m") + "%",)).fetchone()[0]
        first_article = connection.execute("""SELECT COUNT(*) FROM article_progress p JOIN articles a ON a.id=p.article_id
            WHERE a.section_count>0 AND p.completed_section_count>=a.section_count""").fetchone()[0]
        mastered = connection.execute("SELECT COUNT(*) FROM vocabulary_learning_state WHERE status='mastered'").fetchone()[0]
        listened = connection.execute("SELECT COUNT(DISTINCT related_sentence_id) FROM learning_events WHERE event_type='audio_started' AND related_sentence_id IS NOT NULL").fetchone()[0]
        queue_done = connection.execute("SELECT COUNT(*) FROM learning_events WHERE event_type='word_queue_completed'").fetchone()[0]
        precise = connection.execute("""SELECT COUNT(*) FROM practice_sessions WHERE completed=1 AND correct_characters>=100
            AND active_seconds>=30 AND accuracy>=99""").fetchone()[0]
        correct_words = 0
        for row in connection.execute("SELECT metadata_json FROM learning_events WHERE event_type='correct_words'"):
            try: correct_words += int(json.loads(row[0] or "{}").get("count", 0))
            except (ValueError, TypeError, json.JSONDecodeError): pass
        checks = {
            "first_checkin": (total_days, 1), "week_five": (week_days, 5), "month_twenty": (month_days, 20),
            "hundred_days": (total_days, 100), "first_article": (first_article, 1),
            "thousand_words": (correct_words, 1000), "vocabulary_collector": (mastered, 100),
            "listen_read": (listened, 100), "finish_word_queue": (queue_done, 1), "precision_typing": (precise, 1),
        }
        unlocked=[]
        for key, (progress, threshold) in checks.items():
            if self.repository.unlock_achievement(key, progress, threshold): unlocked.append(ACHIEVEMENT_NAMES[key])
        return unlocked
