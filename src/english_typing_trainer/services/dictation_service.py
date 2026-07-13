from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
import re

from english_typing_trainer.database.dictation_repository import DictationRepository
from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.models.dictation import DictationAttempt, DictationComparison


class DictationService:
    """Deterministic, offline dictation comparison and persistence."""

    def __init__(self, database: DatabaseManager, *, now_provider=None) -> None:
        self.database = database
        self.repository = DictationRepository(database.connect)
        self._now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def normalize_sentence(text: str, mode: str) -> str:
        value = re.sub(r"\s+", " ", text.strip())
        if mode == "learning":
            value = re.sub(r"[.!?]+$", "", value).rstrip()
            if value:
                value = value[0].lower() + value[1:]
        return value

    def compare(self, expected: str, actual: str, *, dictation_type: str, mode: str = "strict") -> DictationComparison:
        if dictation_type not in {"word", "sentence"} or mode not in {"strict", "learning"}:
            raise ValueError("无效的听写类型或比较模式。")
        left = expected if dictation_type == "word" else self.normalize_sentence(expected, mode)
        right = actual if dictation_type == "word" else self.normalize_sentence(actual, mode)
        operations: list[tuple[str, str]] = []
        errors = omitted = inserted = 0
        for tag, a0, a1, b0, b1 in SequenceMatcher(None, left, right).get_opcodes():
            if tag == "equal":
                operations.extend(("equal", char) for char in right[b0:b1])
            elif tag == "delete":
                omitted += a1 - a0; errors += a1 - a0
                operations.extend(("omitted", char) for char in left[a0:a1])
            elif tag == "insert":
                inserted += b1 - b0; errors += b1 - b0
                operations.extend(("inserted", char) for char in right[b0:b1])
            else:
                errors += max(a1 - a0, b1 - b0)
                operations.extend(("replace", char) for char in right[b0:b1])
        return DictationComparison(expected, actual, left, right, left == right, errors, omitted, inserted, operations)

    def save(self, attempt: DictationAttempt) -> DictationAttempt:
        now = self._now_provider()
        now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
        with self.database.transaction() as connection:
            return self.repository.add_attempt(connection, attempt, now)
