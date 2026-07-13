from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.pronunciation_repository import PronunciationRepository
from english_typing_trainer.models.pronunciation import PronunciationAttempt, PronunciationRequest, PronunciationResult


class PronunciationService:
    def __init__(self, database: DatabaseManager, *, now_provider=None) -> None:
        self.database=database; self.repository=PronunciationRepository(database.connect); self._now=now_provider or (lambda: datetime.now(timezone.utc))

    def assess(self, request: PronunciationRequest, provider, *, target_type: str, entry_id: int | None, context_id: int | None, keep_audio: bool) -> PronunciationAttempt:
        return self.save_result(request, provider.assess(request), target_type=target_type, entry_id=entry_id, context_id=context_id, keep_audio=keep_audio)

    def save_result(self, request: PronunciationRequest, result: PronunciationResult, *, target_type: str, entry_id: int | None, context_id: int | None, keep_audio: bool) -> PronunciationAttempt:
        now=self._now()
        feedback=json.dumps([{"word":w.word,"accuracy_score":w.accuracy_score,"error_type":w.error_type,"phonemes":w.phonemes} for w in result.words],ensure_ascii=False)
        attempt=PronunciationAttempt(target_type,hashlib.sha256(request.reference_text.encode("utf-8")).hexdigest(),result.provider,request.locale,result.status,entry_id,context_id,result.overall_score,result.accuracy_score,result.fluency_score,result.completeness_score,result.prosody_score,feedback,result.error_code,now,str(request.audio_path) if keep_audio else None)
        with self.database.transaction() as connection:self.repository.add(connection,attempt,now)
        if not keep_audio and request.audio_path.exists(): request.audio_path.unlink(missing_ok=True)
        return attempt

    def delete_attempt(self, attempt_id: int) -> None:
        with self.database.transaction() as connection:path=self.repository.delete(connection,attempt_id)
        if path: Path(path).unlink(missing_ok=True)
