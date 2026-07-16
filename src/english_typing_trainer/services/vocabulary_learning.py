from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from threading import Lock

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.vocabulary_learning_repository import VocabularyLearningRepository
from english_typing_trainer.models.vocabulary import VocabularyAttempt, VocabularyContext, VocabularyEntry
from english_typing_trainer.models.learning_content import LearningContentRef
from english_typing_trainer.services.dictionary_provider import DictionaryProvider, DictionaryProviderError, DictionaryResult
from english_typing_trainer.services.word_explanation_provider import DeepSeekWordExplanationProvider, WordExplanationResult
from english_typing_trainer.services.word_normalization import WordNormalizationService


@dataclass(slots=True)
class CollectionResult:
    entry: VocabularyEntry
    context: VocabularyContext
    entry_created: bool
    context_created: bool


class VocabularyLearningService:
    def __init__(self, database: DatabaseManager, normalization: WordNormalizationService) -> None:
        self.database=database; self.normalization=normalization
        self.repository=VocabularyLearningRepository(database.connect); self._dictionary_inflight=set(); self._ai_inflight=set(); self._lock=Lock()
        self._context_resolver: Callable[[VocabularyContext], str] | None = None

    def set_context_resolver(
        self, resolver: Callable[[VocabularyContext], str] | None
    ) -> None:
        self._context_resolver = resolver

    def collect(self, raw_word: str, *, sentence: str="", article_id: int|None=None,
                article_sentence_id: int|None=None, start_offset: int=0, end_offset: int|None=None,
                typing_target_count: int=5,
                content_ref: LearningContentRef | None = None) -> CollectionResult:
        normalized,display=self.normalization.validate_selection(raw_word)
        entry=self.repository.get_by_word(normalized); created=entry is None
        with self.database.transaction() as connection:
            if entry is None:
                entry=self.repository.create_entry(connection,VocabularyEntry(normalized,display,lemma=normalized))
            assert entry.id is not None
            context,context_created=self.repository.add_context(connection,VocabularyContext(
                entry.id,
                display,
                "" if content_ref is not None else sentence,
                None if content_ref is not None else article_id,
                None if content_ref is not None else article_sentence_id,
                start_offset,
                end_offset if end_offset is not None else start_offset+len(display),
                source_type=(content_ref.source_type if content_ref is not None else "article"),
                course_stable_key=(content_ref.course_stable_key if content_ref is not None else ""),
                item_stable_key=(content_ref.item_stable_key if content_ref is not None else ""),
                content_version=(content_ref.content_version if content_ref is not None else ""),
            ))
            self.repository.ensure_state(connection,entry.id,typing_target_count)
        return CollectionResult(entry,self._resolve_context(context),created,context_created)

    def enrich_dictionary(self, entry_id: int, provider: DictionaryProvider, *, force: bool=False) -> VocabularyEntry:
        entry=self.repository.get_entry(entry_id)
        if not entry: raise ValueError("未找到单词。")
        if entry.dictionary_status=="ready" and not force: return entry
        if entry.dictionary_status=="not_found" and entry.dictionary_fetched_at and not force and datetime.now()-entry.dictionary_fetched_at<timedelta(days=7): return entry
        with self._lock:
            if entry_id in self._dictionary_inflight: return entry
            self._dictionary_inflight.add(entry_id)
        try:
            result=None
            for candidate in self.normalization.safe_lemma_candidates(entry.normalized_word):
                try: result=provider.lookup(candidate); break
                except DictionaryProviderError as exc:
                    if exc.category!="not_found": raise
            if result is None:
                with self.database.transaction() as connection:
                    self.repository.update_dictionary(connection,entry_id,lemma=entry.normalized_word,phonetic="",part_of_speech="",status="not_found",payload={})
            else:
                with self.database.transaction() as connection:
                    self.repository.update_dictionary(connection,entry_id,lemma=result.word.lower(),phonetic=result.phonetic,
                        part_of_speech=result.primary_part_of_speech,status="ready",payload=result.payload)
            return self.repository.get_entry(entry_id)  # type: ignore[return-value]
        finally:
            with self._lock: self._dictionary_inflight.discard(entry_id)

    def lookup_dictionary(self, entry_id: int, provider: DictionaryProvider) -> DictionaryResult | None:
        with self.database.independent_connection() as connection:
            row=connection.execute("SELECT normalized_word FROM vocabulary_entries WHERE id=?",(entry_id,)).fetchone()
        if not row: raise ValueError("未找到单词。")
        for candidate in self.normalization.safe_lemma_candidates(row["normalized_word"]):
            try: return provider.lookup(candidate)
            except DictionaryProviderError as exc:
                if exc.category != "not_found": raise
        return None

    def apply_dictionary_result(self, entry_id: int, result: DictionaryResult | None) -> VocabularyEntry:
        entry=self.repository.get_entry(entry_id)
        if not entry: raise ValueError("未找到单词。")
        with self.database.transaction() as connection:
            if result is None:
                self.repository.update_dictionary(connection,entry_id,lemma=entry.normalized_word,phonetic="",part_of_speech="",status="not_found",payload={})
            else:
                self.repository.update_dictionary(connection,entry_id,lemma=result.word.lower(),phonetic=result.phonetic,
                    part_of_speech=result.primary_part_of_speech,status="ready",payload=result.payload)
        return self.repository.get_entry(entry_id)  # type: ignore[return-value]

    def build_explanation_request(self, context_id: int) -> tuple[dict[str, object], VocabularyContext]:
        context=self.repository.get_context(context_id)
        if not context: raise ValueError("未找到来源语境。")
        context=self._resolve_context(context)
        entry=self.repository.get_entry(context.vocabulary_entry_id)
        if not entry: raise ValueError("未找到单词。")
        definitions=[]
        if isinstance(entry.dictionary_payload,list) and entry.dictionary_payload:
            from english_typing_trainer.services.dictionary_provider import parse_dictionary_payload
            try: definitions=parse_dictionary_payload(entry.normalized_word,entry.dictionary_payload).definitions
            except Exception: pass
        return {"word":context.source_word,"lemma":entry.lemma or entry.normalized_word,
                "sentence":context.source_sentence,"dictionary_summary":definitions},context

    def apply_explanation_result(self, context_id: int, result: WordExplanationResult) -> VocabularyContext:
        with self.database.transaction() as connection: self.repository.update_explanation(connection,context_id,result)
        context=self.repository.get_context(context_id)
        if context is None: raise ValueError("未找到来源语境。")
        return self._resolve_context(context)

    def mark_explanation_failed(self, context_id: int) -> None:
        with self.database.transaction() as connection: self.repository.mark_ai_failed(connection,context_id)

    def explain_context(self, context_id: int, provider: DeepSeekWordExplanationProvider, *, force: bool=False) -> VocabularyContext:
        context=self.repository.get_context(context_id)
        if not context: raise ValueError("未找到来源语境。")
        context=self._resolve_context(context)
        if context.is_manual or (context.ai_status=="ready" and not force): return context
        entry=self.repository.get_entry(context.vocabulary_entry_id)
        assert entry is not None
        key=(entry.id,context.source_sentence,context.ai_prompt_version)
        with self._lock:
            if key in self._ai_inflight: return context
            self._ai_inflight.add(key)
        try:
            payload=entry.dictionary_payload if isinstance(entry.dictionary_payload,list) else []
            definitions=[]
            if payload:
                from english_typing_trainer.services.dictionary_provider import parse_dictionary_payload
                try: definitions=parse_dictionary_payload(entry.normalized_word,payload).definitions
                except Exception: definitions=[]
            result=provider.explain(word=context.source_word,lemma=entry.lemma or entry.normalized_word,
                sentence=context.source_sentence,dictionary_summary=definitions)
            with self.database.transaction() as connection: self.repository.update_explanation(connection,context_id,result)
            saved=self.repository.get_context(context_id)
            return self._resolve_context(saved) if saved is not None else context
        except Exception:
            with self.database.transaction() as connection: self.repository.mark_ai_failed(connection,context_id)
            raise
        finally:
            with self._lock: self._ai_inflight.discard(key)

    def list_entries(self, *, search: str="", status: str="all"): return self.repository.list_entries(search=search,status=status)
    def detail(self, entry_id: int):
        contexts=[self._resolve_context(context) for context in self.repository.list_contexts(entry_id)]
        return self.repository.get_entry(entry_id),contexts,self.repository.get_state(entry_id)

    def _resolve_context(self, context: VocabularyContext) -> VocabularyContext:
        if context.source_type != "built_in_course" or self._context_resolver is None:
            return context
        sentence = self._context_resolver(context)
        return replace(context, source_sentence=sentence)

    def record_attempt(self, attempt: VocabularyAttempt) -> int:
        state=self.repository.get_state(attempt.vocabulary_entry_id)
        if not state: raise ValueError("未找到学习状态。")
        now=datetime.now(); state.last_practiced_at=now
        if attempt.practice_type in {"typing","sentence_cloze"} and attempt.is_correct is not None:
            if attempt.is_correct: state.correct_attempts+=1
            else: state.incorrect_attempts+=1
        if attempt.practice_type=="typing" and attempt.is_correct:
            state.typing_completed_count+=1
            if state.typing_completed_count>=state.typing_target_count and state.status=="new": state.status="learning"
        if attempt.practice_type=="meaning_recall" and attempt.self_rating:
            days={"unknown":0,"fuzzy":1,"known":3,"familiar":7}[attempt.self_rating]
            levels={"unknown":0,"fuzzy":1,"known":2,"familiar":3}
            state.familiarity_level=levels[attempt.self_rating]; state.status="learning" if attempt.self_rating in {"unknown","fuzzy"} else "reviewing"
            state.next_review_at=now+timedelta(days=days)
        with self.database.transaction() as connection:
            attempt_id=self.repository.save_attempt(connection,attempt); self.repository.update_state(connection,state)
        return attempt_id

    def set_mastered(self, entry_id: int, mastered: bool) -> None:
        state=self.repository.get_state(entry_id)
        if not state: raise ValueError("未找到学习状态。")
        state.status="mastered" if mastered else "learning"; state.mastered_at=datetime.now() if mastered else None
        with self.database.transaction() as connection: self.repository.update_state(connection,state)

    def delete(self, entry_id: int) -> None:
        with self.database.transaction() as connection: self.repository.delete_entry(connection,entry_id)

    @staticmethod
    def cloze_text(context: VocabularyContext) -> str:
        sentence=context.source_sentence; start=context.start_offset; end=context.end_offset
        if 0<=start<end<=len(sentence) and sentence[start:end]==context.source_word: return sentence[:start]+"___"+sentence[end:]
        return sentence.replace(context.source_word,"___",1)
