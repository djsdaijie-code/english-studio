from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.services.app_paths import AppPathService, AppPaths
from english_typing_trainer.services.article_library import ArticleLibraryService
from english_typing_trainer.services.credential_store import CredentialStore, MemoryCredentialStore, WindowsCredentialStore
from english_typing_trainer.services.history_service import HistoryService
from english_typing_trainer.services.practice_service import PracticeService
from english_typing_trainer.services.review_planning import ReviewPlanningService
from english_typing_trainer.services.sectioning import SectioningService
from english_typing_trainer.services.sentence_service import SentenceService
from english_typing_trainer.services.settings_service import SettingsService
from english_typing_trainer.services.special_practice import SpecialPracticeService
from english_typing_trainer.services.statistics_service import StatisticsService
from english_typing_trainer.services.translation_service import TranslationService
from english_typing_trainer.services.tts_service import PronunciationService, TTSService
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
    sentence_service: SentenceService
    normalization_service: WordNormalizationService
    review_planning_service: ReviewPlanningService
    special_practice_service: SpecialPracticeService
    translation_service: TranslationService
    credential_store: CredentialStore
    tts_service: TTSService
    pronunciation_service: PronunciationService
    tts_credential_store: CredentialStore


def build_app_context(data_dir: Path | None = None, credential_store: CredentialStore | None = None, tts_credential_store: CredentialStore | None = None) -> AppContext:
    path_service = AppPathService(base_dir=data_dir)
    paths = path_service.ensure_directories()
    database = DatabaseManager(paths.database_path)
    database.initialize()
    sectioning_service = SectioningService()
    normalization_service = WordNormalizationService()
    review_planning_service = ReviewPlanningService()
    settings_service = SettingsService(database)
    sentence_service = SentenceService(database)
    article_library = ArticleLibraryService(database, sectioning_service)
    practice_service = PracticeService(database)
    history_service = HistoryService(database)
    statistics_service = StatisticsService(database)
    translation_service = TranslationService(database)
    tts_service = TTSService(database, paths.audio_cache_dir)
    pronunciation_service = PronunciationService(tts_service)
    if credential_store is None:
        credential_store = MemoryCredentialStore() if os.environ.get("PYTEST_CURRENT_TEST") else WindowsCredentialStore()
    if tts_credential_store is None:
        tts_credential_store = MemoryCredentialStore() if os.environ.get("PYTEST_CURRENT_TEST") else WindowsCredentialStore(
            "English Studio/MiniMax TTS", "MiniMax TTS"
        )
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
        sentence_service=sentence_service,
        normalization_service=normalization_service,
        review_planning_service=review_planning_service,
        special_practice_service=special_practice_service,
        translation_service=translation_service,
        credential_store=credential_store,
        tts_service=tts_service,
        pronunciation_service=pronunciation_service,
        tts_credential_store=tts_credential_store,
    )
