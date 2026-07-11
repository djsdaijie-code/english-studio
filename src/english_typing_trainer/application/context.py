from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.services.app_paths import AppPathService, AppPaths
from english_typing_trainer.services.article_library import ArticleLibraryService
from english_typing_trainer.services.history_service import HistoryService
from english_typing_trainer.services.practice_service import PracticeService
from english_typing_trainer.services.review_planning import ReviewPlanningService
from english_typing_trainer.services.sectioning import SectioningService
from english_typing_trainer.services.settings_service import SettingsService
from english_typing_trainer.services.special_practice import SpecialPracticeService
from english_typing_trainer.services.statistics_service import StatisticsService
from english_typing_trainer.services.word_normalization import WordNormalizationService


@dataclass(slots=True)
class AppContext:
    paths: AppPaths
    database: DatabaseManager
    article_library: ArticleLibraryService
    practice_service: PracticeService
    history_service: HistoryService
    statistics_service: StatisticsService
    settings_service: SettingsService
    sectioning_service: SectioningService
    normalization_service: WordNormalizationService
    review_planning_service: ReviewPlanningService
    special_practice_service: SpecialPracticeService


def build_app_context(data_dir: Path | None = None) -> AppContext:
    path_service = AppPathService(base_dir=data_dir)
    paths = path_service.ensure_directories()
    database = DatabaseManager(paths.database_path)
    database.initialize()
    sectioning_service = SectioningService()
    normalization_service = WordNormalizationService()
    review_planning_service = ReviewPlanningService()
    settings_service = SettingsService(database)
    article_library = ArticleLibraryService(database, sectioning_service)
    practice_service = PracticeService(database)
    history_service = HistoryService(database)
    statistics_service = StatisticsService(database)
    special_practice_service = SpecialPracticeService(
        database,
        normalization=normalization_service,
        review_planning=review_planning_service,
    )
    return AppContext(
        paths=paths,
        database=database,
        article_library=article_library,
        practice_service=practice_service,
        history_service=history_service,
        statistics_service=statistics_service,
        settings_service=settings_service,
        sectioning_service=sectioning_service,
        normalization_service=normalization_service,
        review_planning_service=review_planning_service,
        special_practice_service=special_practice_service,
    )
