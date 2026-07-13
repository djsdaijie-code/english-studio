from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest

from english_typing_trainer.application.context import build_app_context
from english_typing_trainer.database.migrations import MigrationRunner
from english_typing_trainer.models.pronunciation import PronunciationRequest
from english_typing_trainer.services.credential_store import MemoryCredentialStore
from english_typing_trainer.services.pronunciation_provider import AzurePronunciationAssessmentProvider, FakePronunciationAssessmentProvider
from english_typing_trainer.ui.main_window import MainWindow


def _app(): return QApplication.instance() or QApplication([])


def test_azure_provider_without_key_returns_no_score(tmp_path: Path) -> None:
    audio=tmp_path / "recording.m4a"; audio.write_bytes(b"audio")
    result=AzurePronunciationAssessmentProvider("", "").assess(PronunciationRequest("Hello.", "en-US", audio))
    assert result.status == "not_configured"
    assert result.overall_score is None and result.provider == "azure"


def test_schema_10_to_11_creates_pronunciation_tables_and_rolls_back(tmp_path: Path, monkeypatch) -> None:
    connection=sqlite3.connect(tmp_path / "legacy.db"); connection.execute("CREATE TABLE schema_version(version INTEGER NOT NULL)")
    runner=MigrationRunner()
    for version in range(1, 11): getattr(runner, f"_apply_version_{version}")(connection)
    original=runner._apply_version_11
    monkeypatch.setattr(runner,"_apply_version_11",lambda _connection: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError): runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 10
    monkeypatch.setattr(runner,"_apply_version_11",original); runner.migrate(connection)
    assert connection.execute("SELECT version FROM schema_version").fetchone()[0] == 11
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='pronunciation_attempts'").fetchone()


def test_fake_provider_is_deterministic_but_only_explicitly_used_in_test(tmp_path: Path) -> None:
    audio=tmp_path / "recording.m4a"; audio.write_bytes(b"audio")
    first=FakePronunciationAssessmentProvider().assess(PronunciationRequest("Hello world", "en-US", audio))
    second=FakePronunciationAssessmentProvider().assess(PronunciationRequest("Hello world", "en-US", audio))
    assert first.provider == second.provider == "fake"
    assert first.overall_score == second.overall_score == 88.0


def test_not_configured_assessment_persists_status_and_cleans_temporary_audio(tmp_path: Path) -> None:
    context=build_app_context(data_dir=tmp_path / "data")
    audio=tmp_path / "recording.m4a"; audio.write_bytes(b"audio")
    attempt=context.pronunciation_assessment_service.assess(
        PronunciationRequest("Hello.","en-US",audio), AzurePronunciationAssessmentProvider("",""),
        target_type="sentence",entry_id=None,context_id=None,keep_audio=False,
    )
    assert attempt.status == "not_configured" and attempt.overall_score is None and not audio.exists()
    row=context.database.connect().execute("SELECT status,provider,overall_score,audio_path FROM pronunciation_attempts").fetchone()
    assert tuple(row) == ("not_configured","azure",None,None)


def test_kept_recording_is_deleted_with_history(tmp_path: Path) -> None:
    context=build_app_context(data_dir=tmp_path / "data")
    audio=tmp_path / "keep.m4a"; audio.write_bytes(b"audio")
    attempt=context.pronunciation_assessment_service.assess(
        PronunciationRequest("Hello.","en-US",audio), FakePronunciationAssessmentProvider(),
        target_type="word",entry_id=None,context_id=None,keep_audio=True,
    )
    assert audio.exists() and attempt.id
    context.pronunciation_assessment_service.delete_attempt(attempt.id or 0)
    assert not audio.exists()


def test_main_window_never_uses_fake_provider_for_unconfigured_user_path(tmp_path: Path) -> None:
    app=_app(); store=MemoryCredentialStore()
    context=build_app_context(data_dir=tmp_path / "data", pronunciation_credential_store=store)
    collected=context.vocabulary_learning_service.collect("English", sentence="English helps people.")
    window=MainWindow(context); window._start_pronunciation(collected.entry.id or 0)
    page=window.pronunciation_page; page.audio_path=tmp_path / "recording.m4a"; page.audio_path.write_bytes(b"audio")
    assert not page.assess_button.isEnabled()
    page.set_recorded(page.audio_path)
    assert page.assess_button.isEnabled()
    window._assess_pronunciation("word",page.audio_path,False)
    for _ in range(20):
        app.processEvents(); QTest.qWait(10)
    assert "未配置 Azure Speech" in page.scores.text()
    row=context.database.connect().execute("SELECT provider,status,overall_score FROM pronunciation_attempts").fetchone()
    assert tuple(row)==("azure","not_configured",None)
    window.close(); context.database.close()
