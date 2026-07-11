from __future__ import annotations

from datetime import date, timedelta

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import HistoryQuery, PracticeRepository
from english_typing_trainer.typing_engine.text_analysis import humanize_character


class HistoryService:
    def __init__(self, database: DatabaseManager) -> None:
        self._database = database
        self._repository = PracticeRepository(database.connect)

    def list_history(
        self,
        *,
        article_id: int | None = None,
        practice_type: str | None = None,
        date_range: str = "all",
        date_from: date | None = None,
        date_to: date | None = None,
        completed: bool | None = None,
        order_by: str = "created_at",
        descending: bool = True,
        limit: int = 500,
        offset: int = 0,
        valid_only: bool = False,
    ):
        resolved_from, resolved_to = self._resolve_date_range(date_range, date_from, date_to)
        return self._repository.list_history(
            HistoryQuery(
                article_id=article_id,
                practice_type=practice_type,
                date_from=resolved_from,
                date_to=resolved_to,
                completed=completed,
                order_by=order_by,
                descending=descending,
                limit=limit,
                offset=offset,
                valid_only=valid_only,
            )
        )

    def get_session_detail(self, session_id: int) -> tuple[object | None, list[object]]:
        session, errors = self._repository.get_session_detail(session_id)
        return session, errors

    def delete_session(self, session_id: int) -> None:
        with self._database.transaction() as connection:
            self._repository.delete_session(connection, session_id)

    def format_visible_character(self, character: str) -> str:
        return humanize_character(character)

    def _resolve_date_range(
        self,
        date_range: str,
        date_from: date | None,
        date_to: date | None,
    ) -> tuple[date | None, date | None]:
        today = date.today()
        if date_range == "today":
            return today, today
        if date_range == "7d":
            return today - timedelta(days=6), today
        if date_range == "30d":
            return today - timedelta(days=29), today
        if date_range == "custom":
            return date_from, date_to
        return None, None
