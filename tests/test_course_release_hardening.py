from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from english_typing_trainer.application.bootstrap import run_acceptance_smoke
from english_typing_trainer.application.context import AppContext, build_app_context
from english_typing_trainer.courses.paths import default_courses_root
from english_typing_trainer.models.course_progress import CourseActivityType
from english_typing_trainer.models.pronunciation import PronunciationResult
from english_typing_trainer.models.tts import TTSAudioResult, TTSRequest
from english_typing_trainer.services.audio_playback import AudioPlaybackService
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.recording_service import RecordingService
from english_typing_trainer.ui.course_page import CoursePage
from english_typing_trainer.ui.main_window import MainWindow


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COURSE_ID = "ai-large-models"
DAY_ONE = "ai-l1-u01-d01"
FIRST_ITEM = "ai-large-models-sentence-0001"
SECOND_ITEM = "ai-large-models-sentence-0002"
DICTATION_ITEM = "ai-large-models-sentence-0008"
SPEAKING_ITEM = "ai-large-models-sentence-0007"


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _copy_courses(tmp_path: Path) -> Path:
    destination = tmp_path / "courses"
    shutil.copytree(PROJECT_ROOT / "courses", destination)
    return destination


def _context(data_dir: Path, courses_root: Path | None = None):
    return build_app_context(
        data_dir=data_dir,
        courses_root=courses_root,
        credential_store=MemoryCredentialStore(),
        tts_credential_store=MemoryCredentialStore(),
        pronunciation_credential_store=MemoryCredentialStore(),
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _complete_required_course_activities(context: AppContext) -> None:
    activity_types: dict[str, CourseActivityType] = {
        "typing": "typing",
        "dictation": "dictation",
        "speaking": "speaking",
        "vocabulary": "vocabulary",
        "review": "review",
        "fsrs": "review",
        "listening": "review",
        "reading": "typing",
        "translation": "typing",
        "self_test": "typing",
    }
    course = context.course_repository.get_course(COURSE_ID)
    assert course is not None
    required: set[tuple[str, CourseActivityType]] = set()
    for level in course.levels:
        for unit in level.units:
            sentences = {sentence.sentence_id: sentence for sentence in unit.sentences}
            for lesson in unit.lessons:
                for activity in lesson.activities:
                    if not activity.required:
                        continue
                    activity_type = activity_types.get(activity.activity_type, "typing")
                    required.update(
                        (sentences[sentence_id].stable_key, activity_type)
                        for sentence_id in activity.sentence_ids
                    )
    for stable_key, activity_type in sorted(required):
        context.course_progress_service.complete_activity(
            COURSE_ID,
            stable_key,
            activity_type,
        )


def test_course_state_and_capability_history_survive_new_app_context(
    tmp_path: Path,
) -> None:
    courses_root = _copy_courses(tmp_path)
    data_dir = tmp_path / "state"
    first = _context(data_dir, courses_root)
    try:
        progress = first.course_progress_service
        progress.complete_item(COURSE_ID, FIRST_ITEM, 96.0)
        dictation = first.course_capability_service.item(COURSE_ID, DICTATION_ITEM)
        speaking = first.course_capability_service.item(COURSE_ID, SPEAKING_ITEM)
        first.course_capability_service.record_dictation(
            dictation.ref,
            score=88.0,
            error_count=1,
            omitted_count=0,
            inserted_count=0,
            replay_count=2,
            duration_ms=1200,
        )
        first.course_capability_service.record_speaking(
            speaking.ref,
            PronunciationResult(
                status="completed",
                provider="azure",
                overall_score=82.0,
                accuracy_score=83.0,
                fluency_score=81.0,
                completeness_score=84.0,
                prosody_score=80.0,
            ),
            duration_ms=900,
        )
        card = first.course_capability_service.ensure_sentence_review(
            first.course_capability_service.content_ref(COURSE_ID, FIRST_ITEM)
        )
        reviewed = first.course_capability_service.rate_sentence_review(
            card.id or 0, "good"
        )
        assert reviewed.last_reviewed_at_utc is not None
        enrollment = progress.get_enrollment(COURSE_ID)
        assert enrollment is not None
        remembered_lesson = enrollment.current_lesson_stable_key
    finally:
        first.database.close()

    reopened = _context(data_dir, courses_root)
    try:
        progress = reopened.course_progress_service
        enrollment = progress.get_enrollment(COURSE_ID)
        assert enrollment is not None
        assert enrollment.status == "active"
        assert enrollment.current_lesson_stable_key == remembered_lesson
        assert progress.get_item_progress(COURSE_ID, FIRST_ITEM).status == "completed"
        typing = progress.get_activity_progress(COURSE_ID, FIRST_ITEM, "typing")
        dictation = progress.get_activity_progress(
            COURSE_ID, DICTATION_ITEM, "dictation"
        )
        speaking = progress.get_activity_progress(
            COURSE_ID, SPEAKING_ITEM, "speaking"
        )
        assert (typing.status, typing.latest_score) == ("completed", 96.0)
        assert (dictation.status, dictation.attempt_count, dictation.latest_score) == (
            "completed",
            1,
            88.0,
        )
        assert (speaking.status, speaking.attempt_count, speaking.latest_score) == (
            "completed",
            1,
            82.0,
        )
        stored_card = reopened.course_capability_service.ensure_sentence_review(
            reopened.course_capability_service.content_ref(COURSE_ID, FIRST_ITEM)
        )
        assert stored_card.id == card.id
        assert len(
            reopened.course_capability_repository.list_review_logs(card.id or 0)
        ) == 1
        assert reopened.database.connect().execute(
            "SELECT COUNT(*) FROM course_review_cards"
        ).fetchone()[0] == 1

        progress.set_enrollment_status(COURSE_ID, "paused")
        assert progress.get_next_lesson(COURSE_ID) is None
        progress.set_enrollment_status(COURSE_ID, "archived")
        assert progress.get_next_lesson(COURSE_ID) is None
        progress.set_enrollment_status(COURSE_ID, "active")
        assert progress.get_next_lesson(COURSE_ID) is not None

        unit_path = (
            courses_root
            / "ai-large-models"
            / "units"
            / "unit-01-foundations.json"
        )
        unit = _load_json(unit_path)
        unit["sentences"][0]["order"], unit["sentences"][1]["order"] = (
            unit["sentences"][1]["order"],
            unit["sentences"][0]["order"],
        )
        unit["sentences"][0]["chinese"] = "新建一段对话。"
        _save_json(unit_path, unit)
        reopened.course_repository.reload()
        assert progress.get_item_progress(COURSE_ID, FIRST_ITEM).status == "completed"
        progress.complete_item(COURSE_ID, FIRST_ITEM, 90.0)
        assert reopened.database.connect().execute(
            "SELECT COUNT(*) FROM course_item_progress WHERE item_stable_key = ?",
            (FIRST_ITEM,),
        ).fetchone()[0] == 1
        assert reopened.database.connect().execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0] == 0
    finally:
        reopened.database.close()


def test_due_course_review_ui_rates_cards_and_keeps_normal_queue_separate(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = _app()
    context = _context(tmp_path / "data")
    service = context.course_capability_service
    first = service.ensure_sentence_review(
        service.content_ref(COURSE_ID, FIRST_ITEM), "sentence_listening"
    )
    second = service.ensure_sentence_review(
        service.content_ref(COURSE_ID, SECOND_ITEM), "sentence_review"
    )
    now = datetime.now(timezone.utc)
    first.due_at_utc = now - timedelta(hours=1)
    second.due_at_utc = now - timedelta(hours=2)
    service.repository.update_review_card(first, now)
    service.repository.update_review_card(second, now)
    window = MainWindow(context)
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )
    try:
        window.show()
        window._show_courses()
        app.processEvents()
        assert "2" in window.course_page.due_review_button.text()
        window._start_course_due_review()
        assert window.stack.currentWidget() is window.dictation_page
        assert window.dictation_page._course_review_mode
        assert window.dictation_page.current.ref.item_stable_key == SECOND_ITEM
        assert "AI 与大模型英语" in window.dictation_page.context.text()
        assert "Day 1" in window.dictation_page.context.text()
        window.dictation_page.input.setPlainText(window.dictation_page.current.text)
        window.dictation_page._submit()
        window.dictation_page._rate("good")
        assert len(service.repository.list_review_logs(second.id or 0)) == 1
        rated = service.repository.get_review_card_by_id(second.id or 0)
        assert rated is not None
        assert rated.due_at_utc > now
        assert rated.last_reviewed_at_utc is not None
        assert rated.state in {"learning", "review", "relearning"}
        assert "1" in window.course_page.due_review_button.text()
        connection = context.database.connect()
        assert connection.execute(
            "SELECT COUNT(*) FROM course_capability_attempts"
        ).fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM dictation_attempts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM vocabulary_review_cards").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 0

        current_index = window.dictation_page.index
        window.dictation_page.input.setPlainText(window.dictation_page.current.text)
        window.dictation_page._submit()
        monkeypatch.setattr(
            service,
            "rate_sentence_review",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("database unavailable")),
        )
        window.dictation_page._rate("good")
        assert window.dictation_page.index == current_index
        assert "暂时无法保存" in window.dictation_page.feedback.text()

        context.course_progress_service.set_enrollment_status(COURSE_ID, "paused")
        assert service.due_sentence_reviews() == ()
        context.course_progress_service.set_enrollment_status(COURSE_ID, "active")
        assert len(service.due_sentence_reviews()) == 1
        context.course_progress_service.set_enrollment_status(COURSE_ID, "archived")
        window._leave_dictation()
        window._start_course_due_review()
        assert messages == ["当前没有已到期的课程复习卡。"]
    finally:
        window.current_practice_saved = True
        window.current_course_session = None
        window.close()
        context.database.close()


def test_course_version_upgrade_notice_preserves_completed_stable_state(
    tmp_path: Path,
) -> None:
    app = _app()
    courses_root = _copy_courses(tmp_path)
    data_dir = tmp_path / "state"
    original = _context(data_dir, courses_root)
    try:
        original.course_progress_service.complete_item(COURSE_ID, FIRST_ITEM)
        _complete_required_course_activities(original)
        enrollment = original.course_progress_service.get_enrollment(COURSE_ID)
        assert enrollment is not None and enrollment.status == "completed"
    finally:
        original.database.close()

    course_path = courses_root / "ai-large-models" / "course.json"
    catalog_path = courses_root / "catalog.json"
    unit_path = (
        courses_root / "ai-large-models" / "units" / "unit-01-foundations.json"
    )
    course_doc = _load_json(course_path)
    course_doc["version"] = "1.1.0"
    course_doc["content_version"] = "1.1.0"
    course_doc["estimated_sentences"] = 177
    _save_json(course_path, course_doc)
    catalog = _load_json(catalog_path)
    catalog["courses"][0]["version"] = "1.1.0"
    _save_json(catalog_path, catalog)
    unit = _load_json(unit_path)
    new_sentence = dict(
        next(
            sentence
            for sentence in unit["sentences"]
            if sentence["sentence_id"] == "ai-s0012"
        )
    )
    new_sentence.update(
        {
            "sentence_id": "ai-s0177",
            "stable_key": "ai-large-models-sentence-0177",
            "order": 7,
            "english": "Use stable references for new course content.",
            "chinese": "为课程新内容使用稳定引用。",
            "content_version": "1.1.0",
        }
    )
    unit["sentences"].append(new_sentence)
    unit["lessons"][1]["new_sentence_ids"].append("ai-s0177")
    unit["lessons"][1]["activities"][0]["sentence_ids"].append("ai-s0177")
    _save_json(unit_path, unit)

    upgraded = _context(data_dir, courses_root)
    page = CoursePage(upgraded.course_repository, upgraded.course_progress_service)
    try:
        status = upgraded.course_progress_service.get_version_status(COURSE_ID)
        assert status is not None
        assert status.has_new_content and status.completed_recorded_version
        assert status.recorded_content_version == "1.0.0"
        assert status.current_content_version == "1.1.0"
        progress = upgraded.course_progress_service.get_course_progress(COURSE_ID)
        assert (progress.completed_required_items, progress.total_required_items) == (
            256,
            257,
        )
        assert upgraded.course_progress_service.get_item_progress(
            COURSE_ID, FIRST_ITEM
        ).status == "completed"
        page.show()
        page.show_course(COURSE_ID)
        app.processEvents()
        assert "课程有新内容" in page.version_notice_label.text()
        assert "你曾完成" in page.version_notice_label.text()
        assert "1.0.0" in page.version_notice_label.text()
        assert "1.1.0" in page.version_notice_label.text()
        assert page.view_new_content_button.isVisibleTo(page)
        page.view_new_content_button.click()
        assert "Day 2" in page.detail_status_label.text()
    finally:
        page.close()
        upgraded.database.close()


def test_packaged_smoke_contract_restores_state_on_second_context(
    tmp_path: Path,
) -> None:
    app = _app()
    data_dir = tmp_path / "package-data"
    first_context = _context(data_dir)
    first_window = MainWindow(first_context)
    seed_report = tmp_path / "seed.json"
    try:
        first_window.show()
        assert run_acceptance_smoke(
            first_context, first_window, seed_report, "seed"
        )
        app.processEvents()
    finally:
        first_window.current_practice_saved = True
        first_window.close()
        first_context.database.close()
    second_context = _context(data_dir)
    second_window = MainWindow(second_context)
    verify_report = tmp_path / "verify.json"
    try:
        second_window.show()
        assert run_acceptance_smoke(
            second_context, second_window, verify_report, "verify"
        )
        seed = _load_json(seed_report)
        verify = _load_json(verify_report)
        assert seed["schema_version"] == verify["schema_version"] == 13
        assert seed["first_item_status"] == verify["first_item_status"] == "in_progress"
        assert seed["current_lesson_stable_key"] == verify["current_lesson_stable_key"]
        assert verify["article_count"] == 0
    finally:
        second_window.current_practice_saved = True
        second_window.close()
        second_context.database.close()


def test_pyinstaller_course_path_simulation_ignores_working_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(PROJECT_ROOT / "courses", bundle / "courses")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    assert default_courses_root() == bundle / "courses"
    context = _context(tmp_path / "data")
    try:
        assert len(context.course_repository.list_courses()) == 1
        assert len(context.course_repository.list_courses()[0].levels) == 5
    finally:
        context.database.close()


class _FakeTTSProvider:
    name = "minimax"

    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, request, *, cancel_event=None):
        self.calls += 1
        return TTSAudioResult(
            b"ID3-course-cache",
            request.audio_format,
            request.provider,
            request.model,
            request.voice_id,
        )


def test_course_audio_corruption_and_missing_devices_degrade_cleanly(
    tmp_path: Path,
) -> None:
    _app()
    context = _context(tmp_path / "data")
    try:
        item = context.course_capability_service.item(COURSE_ID, FIRST_ITEM)
        request = TTSRequest(text=item.text)
        provider = _FakeTTSProvider()
        cached = context.tts_service.get_or_generate_course(
            provider, request, item.ref
        )
        cached.file_path.write_bytes(b"")
        assert context.tts_service.get_cached_course(item.ref, request) is None
        regenerated = context.tts_service.get_or_generate_course(
            provider, request, item.ref
        )
        assert provider.calls == 2 and regenerated.file_path.stat().st_size > 0
        row = context.database.connect().execute(
            "SELECT text_preview FROM tts_audio_cache WHERE cache_key = ?",
            (regenerated.cache_key,),
        ).fetchone()
        assert row is not None and row[0] == ""

        messages: list[str] = []
        playback = AudioPlaybackService(output_available=lambda: False)
        playback.playback_failed.connect(messages.append)
        playback.toggle(tmp_path / "missing.mp3")
        valid = tmp_path / "valid.mp3"
        valid.write_bytes(b"audio")
        playback.toggle(valid)
        assert messages == [
            "音频文件缺失或损坏，请重新生成。",
            "未检测到可用的音频播放设备。",
        ]

        class NullDevice:
            def isNull(self) -> bool:
                return True

        recording_messages: list[str] = []
        recording = RecordingService(
            tmp_path / "recordings", device_provider=lambda: NullDevice()
        )
        recording.failed.connect(recording_messages.append)
        assert recording.start() is None
        denied = RecordingService(
            tmp_path / "denied",
            device_provider=lambda: (_ for _ in ()).throw(PermissionError()),
        )
        denied.failed.connect(recording_messages.append)
        assert denied.start() is None
        assert recording_messages == [
            "未检测到可用麦克风。",
            "无法启动麦克风录音，请检查设备和系统权限。",
        ]
    finally:
        context.database.close()


def test_missing_minimax_key_reports_error_and_does_not_leave_activity_running(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()
    context = _context(tmp_path / "data")
    window = MainWindow(context)
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )
    try:
        window._start_course_capability(COURSE_ID, DAY_ONE, "tts")
        assert messages == ["尚未配置 MiniMax API Key。"]
        assert context.course_progress_service.get_activity_progress(
            COURSE_ID, FIRST_ITEM, "review"
        ).status == "failed"
        assert context.database.connect().execute(
            "SELECT COUNT(*) FROM tts_audio_cache"
        ).fetchone()[0] == 0
        assert context.database.connect().execute(
            "SELECT COUNT(*) FROM articles"
        ).fetchone()[0] == 0
    finally:
        window.current_practice_saved = True
        window.close()
        context.database.close()


def test_missing_azure_credentials_stay_in_course_history_only(
    tmp_path: Path,
) -> None:
    _app()
    context = _context(tmp_path / "data")
    window = MainWindow(context)
    try:
        item = context.course_capability_service.item(COURSE_ID, SPEAKING_ITEM)
        window._open_course_pronunciation(item)
        recording = tmp_path / "short-recording.m4a"
        recording.write_bytes(b"temporary-audio")
        window.pronunciation_page.set_recorded(recording)
        window._assess_pronunciation("sentence", recording, False)
        assert "未配置 Azure Speech" in window.pronunciation_page.scores.text()
        row = context.database.connect().execute(
            """
            SELECT capability_type,status,provider
            FROM course_capability_attempts
            """
        ).fetchone()
        assert tuple(row) == ("speaking", "not_configured", "azure")
        assert context.course_progress_service.get_activity_progress(
            COURSE_ID, SPEAKING_ITEM, "speaking"
        ).status == "failed"
        assert context.database.connect().execute(
            "SELECT COUNT(*) FROM pronunciation_attempts"
        ).fetchone()[0] == 0
        assert not recording.exists()
    finally:
        window.current_practice_saved = True
        window.close()
        context.database.close()


def test_course_tts_cache_database_failure_is_recoverable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _app()
    context = _context(tmp_path / "data")
    window = MainWindow(context)
    messages: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: messages.append(message),
    )
    monkeypatch.setattr(
        context.tts_service,
        "get_cached_course",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    try:
        window._start_course_capability(COURSE_ID, DAY_ONE, "tts")
        assert messages == ["音频缓存暂时无法读取，请稍后重试。"]
        assert context.course_progress_service.get_activity_progress(
            COURSE_ID, FIRST_ITEM, "review"
        ).status == "failed"
        assert window.stack.currentWidget() is not None
    finally:
        window.current_practice_saved = True
        window.close()
        context.database.close()
