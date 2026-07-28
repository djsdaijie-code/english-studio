from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.services.app_paths import AppPathService, AppPaths
from english_typing_trainer.services.article_library import ArticleLibraryService
from english_typing_trainer.services.credential_store import CredentialStore, FallbackCredentialStore, MemoryCredentialStore, WindowsCredentialStore
from english_typing_trainer.services.history_service import HistoryService
from english_typing_trainer.services.practice_service import PracticeService
from english_typing_trainer.services.review_planning import ReviewPlanningService
from english_typing_trainer.services.sectioning import SectioningService
from english_typing_trainer.services.sentence_service import SentenceService
from english_typing_trainer.services.settings_service import SettingsService
from english_typing_trainer.services.special_practice import SpecialPracticeService
from english_typing_trainer.services.statistics_service import StatisticsService
from english_typing_trainer.services.translation_service import TranslationService
from english_typing_trainer.services.tts_service import PronunciationService as TTSPronunciationService, TTSService
from english_typing_trainer.services.word_normalization import WordNormalizationService
from english_typing_trainer.services.vocabulary_learning import VocabularyLearningService
from english_typing_trainer.services.dictionary_audio import DictionaryAudioService
from english_typing_trainer.services.article_word_index import ArticleWordIndexService
from english_typing_trainer.database.learning_repository import LearningRepository
from english_typing_trainer.database.course_progress_repository import CourseProgressRepository
from english_typing_trainer.database.course_capability_repository import CourseCapabilityRepository
from english_typing_trainer.services.learning_progress import LearningProgressService
from english_typing_trainer.services.learning_time import LearningTimeTracker
from english_typing_trainer.services.fsrs_review import FsrsReviewService
from english_typing_trainer.services.data_management import DataManagementService
from english_typing_trainer.courses.repository import CourseRepository
from english_typing_trainer.services.course_progress import CourseProgressService
from english_typing_trainer.services.course_learning import CourseLearningService
from english_typing_trainer.services.course_capabilities import CourseCapabilityService
from english_typing_trainer.services.article_proofreading import ArticleProofreadingService


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
    pronunciation_service: TTSPronunciationService
    tts_credential_store: CredentialStore
    vocabulary_learning_service: VocabularyLearningService
    dictionary_audio_service: DictionaryAudioService
    article_word_index_service: ArticleWordIndexService
    learning_repository: LearningRepository
    learning_progress_service: LearningProgressService
    learning_time_tracker: LearningTimeTracker
    fsrs_review_service: FsrsReviewService
    data_management_service: DataManagementService
    course_repository: CourseRepository
    course_progress_repository: CourseProgressRepository
    course_progress_service: CourseProgressService
    course_learning_service: CourseLearningService
    course_capability_repository: CourseCapabilityRepository
    course_capability_service: CourseCapabilityService
    article_proofreading_service: ArticleProofreadingService


def build_app_context(
    data_dir: Path | None = None,
    credential_store: CredentialStore | None = None,
    tts_credential_store: CredentialStore | None = None,
    courses_root: Path | None = None,
) -> AppContext:
    path_service = AppPathService(base_dir=data_dir)
    paths = path_service.ensure_directories()
    database = DatabaseManager(paths.database_path)
    database.initialize()
    sectioning_service = SectioningService()
    normalization_service = WordNormalizationService()
    review_planning_service = ReviewPlanningService()
    settings_service = SettingsService(database)
    sentence_service = SentenceService(database)
    article_word_index_service=ArticleWordIndexService(database,normalization_service)
    article_library = ArticleLibraryService(database, sectioning_service, article_word_index_service)
    practice_service = PracticeService(database)
    history_service = HistoryService(database)
    statistics_service = StatisticsService(database)
    translation_service = TranslationService(database)
    tts_service = TTSService(database, paths.audio_cache_dir)
    pronunciation_service = TTSPronunciationService(tts_service)
    vocabulary_learning_service = VocabularyLearningService(database, normalization_service)
    dictionary_audio_service = DictionaryAudioService(database, paths.audio_cache_dir)
    learning_repository = LearningRepository(database)
    learning_progress_service = LearningProgressService(learning_repository)
    learning_settings=settings_service.get_settings()
    learning_time_tracker = LearningTimeTracker(learning_repository, learning_progress_service,
        idle_timeout_seconds=learning_settings.learning_idle_timeout_seconds,
        health_reminders_enabled=learning_settings.health_reminders_enabled)
    fsrs_review_service = FsrsReviewService(database)
    data_management_service = DataManagementService(database, paths.backups_dir, paths.logs_dir)
    course_repository = CourseRepository(courses_root)
    course_progress_repository = CourseProgressRepository(database)
    course_progress_service = CourseProgressService(course_repository, course_progress_repository)
    course_learning_service = CourseLearningService(course_repository, course_progress_service)
    course_capability_repository = CourseCapabilityRepository(database)
    course_capability_service = CourseCapabilityService(
        course_repository,
        course_progress_service,
        course_capability_repository,
        vocabulary_learning_service,
        article_word_index_service,
        fsrs_review_service,
    )
    article_proofreading_service = ArticleProofreadingService()
    vocabulary_learning_service.set_context_resolver(
        course_capability_service.resolve_context
    )
    fsrs_review_service.set_context_resolver(course_capability_service.resolve_context)
    if credential_store is None:
        credential_store = MemoryCredentialStore() if os.environ.get("PYTEST_CURRENT_TEST") else FallbackCredentialStore(
            WindowsCredentialStore("English Studio/DeepSeek API", "DeepSeek API"), WindowsCredentialStore()
        )
    if tts_credential_store is None:
        tts_credential_store = MemoryCredentialStore() if os.environ.get("PYTEST_CURRENT_TEST") else FallbackCredentialStore(
            WindowsCredentialStore("English Studio/MiniMax TTS", "MiniMax TTS"), WindowsCredentialStore("EnglishTypingTrainer/MiniMax TTS", "MiniMax TTS")
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
        vocabulary_learning_service=vocabulary_learning_service,
        dictionary_audio_service=dictionary_audio_service,
        article_word_index_service=article_word_index_service,
        learning_repository=learning_repository,
        learning_progress_service=learning_progress_service,
        learning_time_tracker=learning_time_tracker,
        fsrs_review_service=fsrs_review_service,
        data_management_service=data_management_service,
        course_repository=course_repository,
        course_progress_repository=course_progress_repository,
        course_progress_service=course_progress_service,
        course_learning_service=course_learning_service,
        course_capability_repository=course_capability_repository,
        course_capability_service=course_capability_service,
        article_proofreading_service=article_proofreading_service,
    )
