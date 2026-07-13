from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fsrs import Card, Rating, Scheduler

from english_typing_trainer.database.fsrs_review_repository import FsrsReviewRepository
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.models.fsrs_review import FsrsProfile, ReviewQueue, ReviewQueueItem, VocabularyReviewCard, VocabularyReviewLog


RATINGS = {"again": Rating.Again, "hard": Rating.Hard, "good": Rating.Good, "easy": Rating.Easy}
RATING_LABELS = {"again": "忘记了", "hard": "困难", "good": "记得", "easy": "很熟"}


class FsrsReviewService:
    """Keeps all FSRS state in UTC while allowing deterministic clocks in tests."""

    def __init__(self, database: DatabaseManager, *, now_provider=None, local_timezone: ZoneInfo | None = None) -> None:
        self.database = database
        self.repository = FsrsReviewRepository(database.connect)
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self.local_timezone = local_timezone or datetime.now().astimezone().tzinfo or timezone.utc

    def now(self) -> datetime:
        value = self._now_provider()
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    def profile(self) -> FsrsProfile:
        current = self.repository.get_profile()
        if current is not None:
            return current
        now = self.now()
        scheduler = Scheduler(desired_retention=0.90, enable_fuzzing=True)
        profile = FsrsProfile(scheduler.to_json(), 0.90)
        with self.database.transaction() as connection:
            self.repository.save_profile(connection, profile, now)
        return profile

    def set_desired_retention(self, value: float) -> FsrsProfile:
        if value not in {0.85, 0.90, 0.93}:
            raise ValueError("期望记忆保持率仅支持 85%、90% 或 93%。")
        profile = self.profile()
        scheduler = Scheduler(desired_retention=value, enable_fuzzing=True)
        profile.scheduler_json = scheduler.to_json()
        profile.desired_retention = value
        with self.database.transaction() as connection:
            self.repository.save_profile(connection, profile, self.now())
        return profile

    def build_today_queue(self, *, new_limit: int = 20, soft_limit: int = 100) -> ReviewQueue:
        now = self.now()
        overdue, due, learning = self.repository.count_due(now)
        due_rows = self.repository.list_due(now, max(0, soft_limit))
        items = [ReviewQueueItem(card, entry, context) for card, entry, context in due_rows]
        if len(items) < soft_limit:
            day_start, day_end = self._utc_day_bounds(now)
            used_new = self.repository.count_reviewed_new_for_day(day_start, day_end)
            new_entries = self.repository.list_new_entries(max(0, min(new_limit - used_new, soft_limit - len(items))))
            for entry, context, legacy_due in new_entries:
                items.extend(item for item in self._create_initial_cards(entry.id, context.id if context else None, legacy_due, now) if item.card.due_at_utc <= now)
        return ReviewQueue(items[:soft_limit], overdue, due, learning, max(0, len(items) - len(due_rows)))

    def rate(self, card_id: int, rating: str) -> VocabularyReviewCard:
        if rating not in RATINGS:
            raise ValueError("未知的 FSRS 评分。")
        stored = self.repository.get_card(card_id)
        if stored is None:
            raise ValueError("复习卡不存在。")
        now = self.now()
        profile = self.profile()
        scheduler = Scheduler.from_json(profile.scheduler_json)
        previous_json = stored.fsrs_card_json
        card = Card.from_json(previous_json)
        updated, review_log = scheduler.review_card(card, RATINGS[rating], review_datetime=now)
        stored.fsrs_card_json = updated.to_json()
        stored.due_at_utc = updated.due.astimezone(timezone.utc)
        stored.last_reviewed_at_utc = now
        stored.state = updated.state.name.lower()
        log = VocabularyReviewLog(stored.id or 0, rating, review_log.to_json(), previous_json, now)
        with self.database.transaction() as connection:
            self.repository.update_card(connection, stored, now)
            self.repository.add_log(connection, log, now)
        return stored

    def defer(self, card_id: int, minutes: int = 10) -> VocabularyReviewCard:
        stored = self.repository.get_card(card_id)
        if stored is None:
            raise ValueError("复习卡不存在。")
        now = self.now()
        card = Card.from_json(stored.fsrs_card_json)
        card.due = now + timedelta(minutes=minutes)
        stored.fsrs_card_json = card.to_json()
        stored.due_at_utc = card.due
        with self.database.transaction() as connection:
            self.repository.update_card(connection, stored, now)
        return stored

    def suspend_entry(self, entry_id: int, suspended: bool = True) -> None:
        now = self.now()
        for card_type in ("spelling", "meaning", "listening"):
            card = self.repository.get_card_for_entry(entry_id, card_type)
            if card is None:
                continue
            card.is_suspended = suspended
            with self.database.transaction() as connection:
                self.repository.update_card(connection, card, now)

    def _create_initial_cards(self, entry_id: int, context_id: int | None, legacy_due: str | None, now: datetime) -> list[ReviewQueueItem]:
        created: list[ReviewQueueItem] = []
        entry, contexts, _state = self._entry_detail(entry_id)
        if entry is None:
            return created
        context = next((item for item in contexts if item.id == context_id), contexts[0] if contexts else None)
        initial_due = self._legacy_due(legacy_due, now)
        with self.database.transaction() as connection:
            for card_type in ("spelling", "meaning"):
                existing = self.repository.get_card_for_entry(entry_id, card_type)
                if existing is not None:
                    created.append(ReviewQueueItem(existing, entry, context))
                    continue
                fsrs_card = Card()
                fsrs_card.due = initial_due
                card = VocabularyReviewCard(entry_id, card_type, fsrs_card.to_json(), fsrs_card.due, context.id if context else None, state=fsrs_card.state.name.lower())
                self.repository.create_card(connection, card, now)
                created.append(ReviewQueueItem(card, entry, context))
        return created

    def _entry_detail(self, entry_id: int):
        from english_typing_trainer.database.vocabulary_learning_repository import VocabularyLearningRepository
        repository = VocabularyLearningRepository(self.database.connect)
        return repository.get_entry(entry_id), repository.list_contexts(entry_id), repository.get_state(entry_id)

    def _legacy_due(self, value: str | None, now: datetime) -> datetime:
        if not value:
            return now
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=self.local_timezone)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return now

    def _utc_day_bounds(self, now: datetime) -> tuple[datetime, datetime]:
        local = now.astimezone(self.local_timezone)
        start = local.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)
