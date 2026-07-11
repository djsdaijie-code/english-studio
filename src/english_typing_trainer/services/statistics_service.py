from __future__ import annotations

from datetime import date, timedelta

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import PracticeRepository
from english_typing_trainer.typing_engine.text_analysis import humanize_character

ERROR_TYPE_LABELS = {
    "wrong_character": "字符错误",
    "case_error": "大小写错误",
    "space_error": "空格错误",
    "newline_error": "换行错误",
    "punctuation_error": "标点错误",
}


class StatisticsService:
    def __init__(self, database: DatabaseManager) -> None:
        self._repository = PracticeRepository(database.connect)

    def overview(self) -> dict[str, object]:
        return self._repository.aggregate_overview(date.today())

    def trend_data(self, range_key: str) -> list[dict[str, object]]:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(range_key)
        rows = self._repository.trend_series(days)
        mapped = {
            row["practice_date"]: {
                "date": row["practice_date"],
                "average_wpm": row["average_wpm"] or 0.0,
                "average_accuracy": row["average_accuracy"] or 0.0,
                "active_minutes": row["active_minutes"] or 0.0,
            }
            for row in rows
        }
        if days is None:
            return list(mapped.values())

        start = date.today() - timedelta(days=days - 1)
        results: list[dict[str, object]] = []
        for offset in range(days):
            current = start + timedelta(days=offset)
            key = current.isoformat()
            results.append(
                mapped.get(
                    key,
                    {
                        "date": key,
                        "average_wpm": 0.0,
                        "average_accuracy": 0.0,
                        "active_minutes": 0.0,
                    },
                )
            )
        return results

    def trend_data_by_group(self, range_key: str, practice_group: str) -> list[dict[str, object]]:
        days = {"7d": 7, "30d": 30, "90d": 90}.get(range_key)
        rows = self._repository.trend_series(days, practice_group=practice_group)
        return [
            {
                "date": row["practice_date"],
                "average_wpm": row["average_wpm"] or 0.0,
                "average_accuracy": row["average_accuracy"] or 0.0,
                "active_minutes": row["active_minutes"] or 0.0,
            }
            for row in rows
        ]

    def error_analysis(self, range_key: str) -> dict[str, list[dict[str, object]]]:
        days = {"7d": 7, "30d": 30}.get(range_key)
        data = self._repository.error_analysis(days)
        types_total = sum(row["error_count"] for row in data["types"]) or 1
        return {
            "characters": [
                {
                    "expected_character": humanize_character(row["expected_character"]),
                    "error_count": row["error_count"],
                }
                for row in data["characters"]
            ],
            "combinations": [
                {
                    "expected_character": humanize_character(row["expected_character"]),
                    "actual_character": humanize_character(row["actual_character"]),
                    "error_count": row["error_count"],
                }
                for row in data["combinations"]
            ],
            "words": [
                {
                    "target_word": row["target_word"],
                    "error_count": row["error_count"],
                }
                for row in data["words"]
            ],
            "types": [
                {
                    "error_type": ERROR_TYPE_LABELS.get(row["error_type"], row["error_type"]),
                    "error_count": row["error_count"],
                    "percentage": (row["error_count"] / types_total) * 100,
                }
                for row in data["types"]
            ],
        }

    def wrong_word_trend(self, days: int = 30) -> list[dict[str, object]]:
        rows = self._repository.recent_wrong_word_series(days)
        mapped = {row["error_date"]: int(row["error_count"]) for row in rows}
        start = date.today() - timedelta(days=days - 1)
        return [
            {
                "date": (start + timedelta(days=offset)).isoformat(),
                "error_count": mapped.get((start + timedelta(days=offset)).isoformat(), 0),
            }
            for offset in range(days)
        ]
