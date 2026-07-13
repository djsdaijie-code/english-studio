from __future__ import annotations

from datetime import datetime, timezone
import json
import sqlite3

from english_typing_trainer.models.fsrs_review import FsrsProfile, VocabularyReviewCard, VocabularyReviewLog
from english_typing_trainer.models.vocabulary import VocabularyContext, VocabularyEntry


def _utc(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


class FsrsReviewRepository:
    def __init__(self, connection_provider) -> None:
        self._connection_provider = connection_provider

    def get_profile(self) -> FsrsProfile | None:
        row = self._connection_provider().execute("SELECT * FROM fsrs_profiles WHERE id=1").fetchone()
        if row is None:
            return None
        return FsrsProfile(row["scheduler_json"], float(row["desired_retention"]), row["parameters_version"], _utc(row["optimized_at"]))

    def save_profile(self, connection: sqlite3.Connection, profile: FsrsProfile, now: datetime) -> None:
        connection.execute(
            """INSERT INTO fsrs_profiles(id,scheduler_json,desired_retention,parameters_version,optimized_at,created_at,updated_at)
               VALUES (1,?,?,?,?,?,?)
               ON CONFLICT(id) DO UPDATE SET scheduler_json=excluded.scheduler_json,desired_retention=excluded.desired_retention,
                 parameters_version=excluded.parameters_version,optimized_at=excluded.optimized_at,updated_at=excluded.updated_at""",
            (profile.scheduler_json, profile.desired_retention, profile.parameters_version,
             _iso(profile.optimized_at) if profile.optimized_at else None, _iso(now), _iso(now)),
        )

    def get_card(self, card_id: int) -> VocabularyReviewCard | None:
        row = self._connection_provider().execute("SELECT * FROM vocabulary_review_cards WHERE id=?", (card_id,)).fetchone()
        return self._card(row) if row else None

    def get_card_for_entry(self, entry_id: int, card_type: str) -> VocabularyReviewCard | None:
        row = self._connection_provider().execute(
            "SELECT * FROM vocabulary_review_cards WHERE vocabulary_entry_id=? AND card_type=?", (entry_id, card_type)
        ).fetchone()
        return self._card(row) if row else None

    def create_card(self, connection: sqlite3.Connection, card: VocabularyReviewCard, now: datetime) -> VocabularyReviewCard:
        cursor = connection.execute(
            """INSERT INTO vocabulary_review_cards(vocabulary_entry_id,vocabulary_context_id,card_type,fsrs_card_json,due_at_utc,
                  last_reviewed_at_utc,state,is_suspended,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (card.vocabulary_entry_id, card.vocabulary_context_id, card.card_type, card.fsrs_card_json, _iso(card.due_at_utc),
             _iso(card.last_reviewed_at_utc) if card.last_reviewed_at_utc else None, card.state, int(card.is_suspended), _iso(now), _iso(now)),
        )
        card.id = int(cursor.lastrowid)
        return card

    def update_card(self, connection: sqlite3.Connection, card: VocabularyReviewCard, now: datetime) -> None:
        connection.execute(
            """UPDATE vocabulary_review_cards SET vocabulary_context_id=?,fsrs_card_json=?,due_at_utc=?,last_reviewed_at_utc=?,
                  state=?,is_suspended=?,updated_at=? WHERE id=?""",
            (card.vocabulary_context_id, card.fsrs_card_json, _iso(card.due_at_utc),
             _iso(card.last_reviewed_at_utc) if card.last_reviewed_at_utc else None, card.state, int(card.is_suspended), _iso(now), card.id),
        )

    def add_log(self, connection: sqlite3.Connection, log: VocabularyReviewLog, now: datetime) -> VocabularyReviewLog:
        cursor = connection.execute(
            """INSERT INTO vocabulary_review_logs(vocabulary_review_card_id,rating,review_log_json,previous_card_json,reviewed_at_utc,created_at)
               VALUES (?,?,?,?,?,?)""",
            (log.vocabulary_review_card_id, log.rating, log.review_log_json, log.previous_card_json, _iso(log.reviewed_at_utc), _iso(now)),
        )
        log.id = int(cursor.lastrowid)
        return log

    def list_due(self, now: datetime, limit: int) -> list[tuple[VocabularyReviewCard, VocabularyEntry, VocabularyContext | None]]:
        rows = self._connection_provider().execute(
            """SELECT c.*, e.normalized_word entry_normalized_word,e.display_word entry_display_word,e.lemma,e.phonetic,
                      e.primary_part_of_speech,e.dictionary_status,e.dictionary_payload_json,e.dictionary_fetched_at,e.created_at entry_created_at,e.updated_at entry_updated_at,
                      x.id context_id,x.vocabulary_entry_id context_entry_id,x.source_word,x.source_sentence,x.article_id,x.article_sentence_id,
                      x.start_offset,x.end_offset,x.contextual_part_of_speech,x.contextual_meaning_zh,x.explanation_zh,x.common_collocation,
                      x.example_en,x.example_zh,x.ai_status,x.ai_prompt_version,x.ai_generated_at,x.is_manual,x.created_at context_created_at,x.updated_at context_updated_at
               FROM vocabulary_review_cards c JOIN vocabulary_entries e ON e.id=c.vocabulary_entry_id
               LEFT JOIN vocabulary_contexts x ON x.id=c.vocabulary_context_id
               LEFT JOIN vocabulary_learning_state s ON s.vocabulary_entry_id=e.id
               WHERE c.is_suspended=0 AND c.due_at_utc<=? AND COALESCE(s.status,'')!='mastered'
               ORDER BY c.due_at_utc,c.id LIMIT ?""",
            (_iso(now), limit),
        ).fetchall()
        return [(self._card(row), self._entry(row), self._context(row)) for row in rows]

    def count_due(self, now: datetime) -> tuple[int, int, int]:
        row = self._connection_provider().execute(
            """SELECT SUM(CASE WHEN due_at_utc < ? THEN 1 ELSE 0 END) overdue,
                      COUNT(*) due,
                      SUM(CASE WHEN state IN ('learning','relearning') THEN 1 ELSE 0 END) learning
               FROM vocabulary_review_cards c LEFT JOIN vocabulary_learning_state s ON s.vocabulary_entry_id=c.vocabulary_entry_id
               WHERE c.is_suspended=0 AND c.due_at_utc<=? AND COALESCE(s.status,'')!='mastered'""",
            (_iso(now), _iso(now)),
        ).fetchone()
        return int(row["overdue"] or 0), int(row["due"] or 0), int(row["learning"] or 0)

    def list_new_entries(self, limit: int) -> list[tuple[VocabularyEntry, VocabularyContext | None, str | None]]:
        rows = self._connection_provider().execute(
            """SELECT e.*, s.next_review_at legacy_due, c.id context_id,c.source_word,c.source_sentence,c.article_id,c.article_sentence_id,
                      c.start_offset,c.end_offset,c.contextual_part_of_speech,c.contextual_meaning_zh,c.explanation_zh,c.common_collocation,
                      c.example_en,c.example_zh,c.ai_status,c.ai_prompt_version,c.ai_generated_at,c.is_manual,c.created_at context_created_at,c.updated_at context_updated_at
               FROM vocabulary_entries e JOIN vocabulary_learning_state s ON s.vocabulary_entry_id=e.id
               LEFT JOIN vocabulary_contexts c ON c.id=(SELECT id FROM vocabulary_contexts WHERE vocabulary_entry_id=e.id ORDER BY created_at DESC,id DESC LIMIT 1)
               WHERE s.status!='mastered' AND NOT EXISTS (SELECT 1 FROM vocabulary_review_cards r WHERE r.vocabulary_entry_id=e.id)
               ORDER BY e.created_at,e.id LIMIT ?""", (limit,)
        ).fetchall()
        return [(self._entry(row), self._context(row), row["legacy_due"]) for row in rows]

    def count_reviewed_new_for_day(self, day_start: datetime, day_end: datetime) -> int:
        row = self._connection_provider().execute(
            """SELECT COUNT(DISTINCT c.vocabulary_entry_id) FROM vocabulary_review_logs l
               JOIN vocabulary_review_cards c ON c.id=l.vocabulary_review_card_id
               WHERE l.reviewed_at_utc>=? AND l.reviewed_at_utc<?""", (_iso(day_start), _iso(day_end))
        ).fetchone()
        return int(row[0] or 0)

    @staticmethod
    def _card(row) -> VocabularyReviewCard:
        return VocabularyReviewCard(row["vocabulary_entry_id"], row["card_type"], row["fsrs_card_json"], _utc(row["due_at_utc"]),
            row["vocabulary_context_id"], _utc(row["last_reviewed_at_utc"]), row["state"], bool(row["is_suspended"]), row["id"])

    @staticmethod
    def _entry(row) -> VocabularyEntry:
        keys = set(row.keys())
        normalized_word = row["entry_normalized_word"] if "entry_normalized_word" in keys else row["normalized_word"]
        display_word = row["entry_display_word"] if "entry_display_word" in keys else row["display_word"]
        entry_id = row["vocabulary_entry_id"] if "entry_normalized_word" in keys else row["id"]
        return VocabularyEntry(normalized_word, display_word,
            lemma=row["lemma"] or "", phonetic=row["phonetic"] or "", primary_part_of_speech=row["primary_part_of_speech"] or "",
            dictionary_status=row["dictionary_status"], dictionary_payload=json.loads(row["dictionary_payload_json"] or "{}"), id=entry_id)

    @staticmethod
    def _context(row) -> VocabularyContext | None:
        keys = set(row.keys())
        context_id = row["context_id"] if "context_id" in keys else None
        if context_id is None:
            return None
        entry_id = row["context_entry_id"] if "context_entry_id" in keys else (row["vocabulary_entry_id"] if "vocabulary_entry_id" in keys else row["id"])
        return VocabularyContext(entry_id, row["source_word"], row["source_sentence"] or "",
            row["article_id"], row["article_sentence_id"], row["start_offset"], row["end_offset"], row["contextual_part_of_speech"] or "",
            row["contextual_meaning_zh"] or "", row["explanation_zh"] or "", row["common_collocation"] or "", row["example_en"] or "", row["example_zh"] or "",
            row["ai_status"], row["ai_prompt_version"], _utc(row["ai_generated_at"]), bool(row["is_manual"]), id=context_id)
