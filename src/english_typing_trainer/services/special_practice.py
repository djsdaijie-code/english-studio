from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime

from english_typing_trainer.database.manager import DatabaseManager
from english_typing_trainer.database.repositories import PracticeRepository, PracticeSetRepository, VocabularyRepository
from english_typing_trainer.models.practice import PracticeMaterial
from english_typing_trainer.models.vocabulary import PracticeSet, PracticeSetItem, VocabularyItem
from english_typing_trainer.services.review_planning import ReviewPlanningService
from english_typing_trainer.services.word_normalization import WordNormalizationService
from english_typing_trainer.typing_engine.text_analysis import humanize_character

MAX_GENERATED_ITEMS = 50


@dataclass(slots=True)
class GeneratedPracticeSet:
    practice_set: PracticeSet
    items: list[PracticeSetItem]
    material: PracticeMaterial
    preview_text: str
    message: str = ""


class SpecialPracticeService:
    def __init__(
        self,
        database: DatabaseManager,
        normalization: WordNormalizationService,
        review_planning: ReviewPlanningService,
    ) -> None:
        self._database = database
        self._practice_repo = PracticeRepository(database.connect)
        self._set_repo = PracticeSetRepository(database.connect)
        self._vocabulary_repo = VocabularyRepository(database.connect)
        self._normalization = normalization
        self._review_planning = review_planning

    def list_saved_sets(self, practice_mode: str | None = None) -> list[PracticeSet]:
        return self._set_repo.list_sets(practice_mode=practice_mode)

    def get_material_for_set(self, practice_set_id: int) -> PracticeMaterial:
        practice_set = self._set_repo.get_set(practice_set_id)
        if practice_set is None or practice_set.is_deleted:
            raise ValueError("未找到练习集。")
        items = self._set_repo.list_items(practice_set_id)
        source_items = [item.item_value for item in items]
        return PracticeMaterial(
            article_id=None,
            article_title=practice_set.title,
            section_id=None,
            section_index=0,
            section_count=1,
            section_text=practice_set.generated_text,
            resume_character_index=0,
            completed_section_count=0,
            practice_type=practice_set.practice_mode,
            practice_set_id=practice_set.id,
            source_items=source_items,
        )

    def generate_error_word_set(
        self,
        *,
        range_key: str,
        word_count: int,
        repeat_count: int,
        arrangement: str,
    ) -> GeneratedPracticeSet | None:
        candidates = self._collect_error_word_candidates(range_key)
        if not candidates:
            return None
        chosen = candidates[: min(word_count, MAX_GENERATED_ITEMS)]
        if arrangement == "with_context":
            lines = []
            items: list[PracticeSetItem] = []
            for order, candidate in enumerate(chosen):
                lines.append(" ".join([candidate["display_word"]] * repeat_count))
                if candidate["source_sentence"]:
                    lines.append(candidate["source_sentence"])
                items.append(
                    PracticeSetItem(
                        practice_set_id=0,
                        item_type="word",
                        item_value=candidate["normalized_word"],
                        source_article_id=candidate["article_id"],
                        source_section_id=candidate["section_id"],
                        source_character_index=candidate["character_index"],
                        source_sentence=candidate["source_sentence"],
                        error_count=candidate["error_count"],
                        sort_order=order,
                    )
                )
            generated_text = "\n".join(line for line in lines if line)
        elif arrangement == "mixed":
            words: list[str] = []
            for _ in range(repeat_count):
                words.extend(candidate["display_word"] for candidate in chosen)
            generated_text = self._stagger_words(words, chosen)
            items = [
                PracticeSetItem(
                    practice_set_id=0,
                    item_type="word",
                    item_value=candidate["normalized_word"],
                    source_article_id=candidate["article_id"],
                    source_section_id=candidate["section_id"],
                    source_character_index=candidate["character_index"],
                    source_sentence=candidate["source_sentence"],
                    error_count=candidate["error_count"],
                    sort_order=order,
                )
                for order, candidate in enumerate(chosen)
            ]
        else:
            generated_text = "\n".join(
                " ".join([candidate["display_word"]] * repeat_count) for candidate in chosen
            )
            items = [
                PracticeSetItem(
                    practice_set_id=0,
                    item_type="word",
                    item_value=candidate["normalized_word"],
                    source_article_id=candidate["article_id"],
                    source_section_id=candidate["section_id"],
                    source_character_index=candidate["character_index"],
                    source_sentence=candidate["source_sentence"],
                    error_count=candidate["error_count"],
                    sort_order=order,
                )
                for order, candidate in enumerate(chosen)
            ]

        title = f"错词练习 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        practice_set = PracticeSet(
            title=title,
            practice_mode="error_words",
            source_type="typing_errors",
            generated_text=generated_text,
            item_count=len(chosen),
            configuration={
                "range_key": range_key,
                "word_count": word_count,
                "repeat_count": repeat_count,
                "arrangement": arrangement,
            },
        )
        return self._persist_generated_set(practice_set, items, message=f"已选择 {len(chosen)} 个错词。")

    def generate_error_character_set(self, *, range_key: str, top_count: int) -> GeneratedPracticeSet | None:
        events = self._practice_repo.list_error_events(self._resolve_days(range_key))
        if not events:
            return None

        char_counts = Counter(row["expected_character"] for row in events)
        chosen_characters = [character for character, _ in char_counts.most_common(min(top_count, 20))]
        if not chosen_characters:
            return None

        confusion_counts = Counter((row["expected_character"], row["actual_character"]) for row in events)
        word_examples: dict[str, list[str]] = defaultdict(list)
        for row in events:
            word = self._normalization.normalize(row["target_word"])
            if not word:
                continue
            display = row["target_word"].strip()
            if any(char in word for char in chosen_characters) and display not in word_examples[word]:
                word_examples[word].append(display)

        lines: list[str] = []
        items: list[PracticeSetItem] = []
        for order, character in enumerate(chosen_characters):
            label = humanize_character(character)
            warmup = " ".join([character] * 3) if character not in {" ", "\n", "\t"} else " ".join([character] * 3)
            lines.append(warmup)
            pairs = []
            for (expected, actual), _count in confusion_counts.most_common():
                if expected == character and len(pairs) < 3:
                    pairs.extend([expected + actual, actual + expected, expected + expected])
            if pairs:
                lines.append(" ".join(pairs))
            examples = [display for values in word_examples.values() for display in values if character.lower() in display.lower()]
            if examples:
                lines.append(" ".join(examples[:3]))
            items.append(
                PracticeSetItem(
                    practice_set_id=0,
                    item_type="character",
                    item_value=label,
                    error_count=char_counts[character],
                    sort_order=order,
                )
            )
        generated_text = "\n".join(lines).replace("[Space]", " ").replace("[Enter]", "\n").replace("[Tab]", "\t")
        practice_set = PracticeSet(
            title=f"错误字符练习 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            practice_mode="error_characters",
            source_type="typing_errors",
            generated_text=generated_text,
            item_count=len(items),
            configuration={"range_key": range_key, "top_count": top_count},
        )
        return self._persist_generated_set(practice_set, items, message=f"已选择 {len(items)} 个重点字符。")

    def generate_context_sentence_set(self, *, range_key: str, sentence_count: int) -> GeneratedPracticeSet | None:
        candidates = self._collect_error_word_candidates(range_key)
        sentences_seen: set[str] = set()
        items: list[PracticeSetItem] = []
        lines: list[str] = []
        for candidate in candidates:
            sentence = candidate["source_sentence"]
            if not sentence or sentence in sentences_seen:
                continue
            sentences_seen.add(sentence)
            order = len(items)
            items.append(
                PracticeSetItem(
                    practice_set_id=0,
                    item_type="sentence",
                    item_value=candidate["normalized_word"],
                    source_article_id=candidate["article_id"],
                    source_section_id=candidate["section_id"],
                    source_character_index=candidate["character_index"],
                    source_sentence=sentence,
                    error_count=candidate["error_count"],
                    sort_order=order,
                )
            )
            lines.append(sentence)
            if len(items) >= min(sentence_count, MAX_GENERATED_ITEMS):
                break
        if not items:
            return None

        practice_set = PracticeSet(
            title=f"原句复习 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            practice_mode="context_sentences",
            source_type="typing_errors",
            generated_text="\n\n".join(lines),
            item_count=len(items),
            configuration={"range_key": range_key, "sentence_count": sentence_count},
        )
        return self._persist_generated_set(practice_set, items, message=f"已选择 {len(items)} 句原文上下文。")

    def generate_vocabulary_review_set(
        self,
        *,
        due_only: bool = True,
        limit: int = 20,
        item_ids: list[int] | None = None,
    ) -> GeneratedPracticeSet | None:
        if item_ids:
            items = [self._vocabulary_repo.get_item(item_id) for item_id in item_ids]
            vocabulary_items = [item for item in items if item and not item.is_archived]
        else:
            due_on = date.today() if due_only else None
            vocabulary_items = self._vocabulary_repo.list_items(due_on=due_on, limit=min(limit, MAX_GENERATED_ITEMS))
        if not vocabulary_items:
            return None

        practice_items: list[PracticeSetItem] = []
        lines: list[str] = []
        for order, item in enumerate(vocabulary_items):
            lines.append(item.display_word)
            if item.source_sentence:
                lines.append(item.source_sentence)
            practice_items.append(
                PracticeSetItem(
                    practice_set_id=0,
                    item_type="vocabulary",
                    item_value=item.normalized_word,
                    source_article_id=item.source_article_id,
                    source_section_id=item.source_section_id,
                    source_character_index=item.source_character_index,
                    source_sentence=item.source_sentence,
                    error_count=self._vocabulary_repo.count_error_occurrences(item.normalized_word),
                    sort_order=order,
                )
            )
        practice_set = PracticeSet(
            title=f"生词复习 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            practice_mode="vocabulary_review",
            source_type="vocabulary_items",
            generated_text="\n".join(lines),
            item_count=len(practice_items),
            configuration={"due_only": due_only, "limit": limit, "item_ids": item_ids or []},
        )
        return self._persist_generated_set(practice_set, practice_items, message=f"已选择 {len(practice_items)} 个生词。")

    def due_summary(self) -> dict[str, int]:
        return self._vocabulary_repo.due_summary(date.today())

    def vocabulary_error_count(self, normalized_word: str) -> int:
        return self._vocabulary_repo.count_error_occurrences(normalized_word)

    def list_vocabulary(
        self,
        *,
        search: str = "",
        status: str | None = None,
        archived: bool = False,
        due_only: bool = False,
    ) -> list[VocabularyItem]:
        return self._vocabulary_repo.list_items(
            search=search,
            status=status,
            archived=archived,
            due_on=date.today() if due_only else None,
        )

    def add_vocabulary_word(
        self,
        raw_word: str,
        *,
        meaning: str = "",
        note: str = "",
        source_article_id: int | None = None,
        source_section_id: int | None = None,
        source_character_index: int | None = None,
        source_sentence: str = "",
    ) -> VocabularyItem:
        normalized = self._normalization.normalize(raw_word)
        if not normalized:
            raise ValueError("请输入有效的英文单词。")
        item = VocabularyItem(
            normalized_word=normalized,
            display_word=raw_word.strip(),
            meaning=meaning,
            note=note,
            source_article_id=source_article_id,
            source_section_id=source_section_id,
            source_character_index=source_character_index,
            source_sentence=source_sentence,
            status="new",
            mastery_level=0,
            next_review_at=self._review_planning.next_review_date_for_level(0),
        )
        with self._database.transaction() as connection:
            return self._vocabulary_repo.add_or_restore(connection, item)

    def update_vocabulary_details(self, item_id: int, meaning: str, note: str) -> VocabularyItem:
        with self._database.transaction() as connection:
            self._vocabulary_repo.update_details(connection, item_id, meaning, note)
        item = self._vocabulary_repo.get_item(item_id)
        if item is None:
            raise ValueError("未找到对应的生词。")
        return item

    def set_vocabulary_archived(self, item_id: int, archived: bool) -> None:
        with self._database.transaction() as connection:
            self._vocabulary_repo.set_archived(connection, item_id, archived)

    def set_vocabulary_mastery(self, item_id: int, mastered: bool) -> None:
        item = self._vocabulary_repo.get_item(item_id)
        if item is None:
            raise ValueError("未找到对应的生词。")
        target_level = 5 if mastered else max(0, min(item.mastery_level, 1))
        status = "mastered" if mastered else "learning"
        with self._database.transaction() as connection:
            self._vocabulary_repo.update_learning_state(
                connection,
                item_id,
                status=status,
                mastery_level=target_level,
                next_review_at=self._review_planning.next_review_date_for_level(target_level),
            )

    def apply_review_results(self, practice_set_id: int, mistaken_words: set[str], completed: bool) -> list[dict[str, object]]:
        practice_set = self._set_repo.get_set(practice_set_id)
        if practice_set is None or practice_set.practice_mode not in {"vocabulary_review", "mixed_review"}:
            return []
        if not completed:
            return []

        items = [item for item in self._set_repo.list_items(practice_set_id) if item.item_type in {"vocabulary", "word"}]
        changes: list[dict[str, object]] = []
        with self._database.transaction() as connection:
            for practice_item in items:
                vocab_item = self._vocabulary_repo.get_by_normalized_word(practice_item.item_value)
                if vocab_item is None:
                    continue
                if practice_item.item_value in mistaken_words:
                    outcome = self._review_planning.mark_wrong(vocab_item)
                else:
                    outcome = self._review_planning.mark_correct(vocab_item)
                self._vocabulary_repo.update_learning_state(
                    connection,
                    vocab_item.id,
                    status=outcome.status,
                    mastery_level=outcome.mastery_level,
                    next_review_at=outcome.next_review_at,
                    last_reviewed_at=outcome.last_reviewed_at,
                    review_count_delta=outcome.review_count_delta,
                    correct_review_delta=outcome.correct_review_delta,
                    wrong_review_delta=outcome.wrong_review_delta,
                )
                changes.append(
                    {
                        "word": vocab_item.display_word,
                        "status": outcome.status,
                        "mastery_level": outcome.mastery_level,
                        "next_review_at": outcome.next_review_at.isoformat(),
                        "mistaken": practice_item.item_value in mistaken_words,
                    }
                )
        return changes

    def note_set_practiced(self, practice_set_id: int) -> None:
        with self._database.transaction() as connection:
            self._set_repo.touch_last_practiced(connection, practice_set_id)

    def _persist_generated_set(self, practice_set: PracticeSet, items: list[PracticeSetItem], *, message: str) -> GeneratedPracticeSet:
        with self._database.transaction() as connection:
            created = self._set_repo.create_set(connection, practice_set, items)
        material = self.get_material_for_set(created.id)
        return GeneratedPracticeSet(
            practice_set=created,
            items=self._set_repo.list_items(created.id),
            material=material,
            preview_text=created.generated_text,
            message=message,
        )

    def _collect_error_word_candidates(self, range_key: str) -> list[dict[str, object]]:
        events = self._practice_repo.list_error_events(self._resolve_days(range_key))
        grouped: dict[str, dict[str, object]] = {}
        archived_words = {item.normalized_word for item in self._vocabulary_repo.list_items(archived=True)}
        for row in events:
            normalized = self._normalization.normalize(row["target_word"])
            if not normalized or normalized in archived_words:
                continue
            existing = grouped.get(normalized)
            sentence = self._extract_sentence(row["section_text"] or "", row["character_index"])
            occurred_at = row["occurred_at"]
            if existing is None:
                grouped[normalized] = {
                    "normalized_word": normalized,
                    "display_word": row["target_word"].strip() or normalized,
                    "error_count": 1,
                    "recent_error_at": occurred_at,
                    "article_id": row["article_id"],
                    "section_id": row["section_id"],
                    "character_index": row["character_index"],
                    "source_sentence": sentence,
                }
            else:
                existing["error_count"] += 1
                if occurred_at > existing["recent_error_at"]:
                    existing["recent_error_at"] = occurred_at
                    existing["display_word"] = row["target_word"].strip() or normalized
                    existing["article_id"] = row["article_id"]
                    existing["section_id"] = row["section_id"]
                    existing["character_index"] = row["character_index"]
                    existing["source_sentence"] = sentence
        return sorted(
            grouped.values(),
            key=lambda item: (-int(item["error_count"]), -datetime.fromisoformat(str(item["recent_error_at"])).timestamp()),
        )

    def _stagger_words(self, words: list[str], chosen: list[dict[str, object]]) -> str:
        rounds: list[str] = []
        for _ in range(max(1, len(words) // max(1, len(chosen)))):
            rounds.append(" ".join(candidate["display_word"] for candidate in chosen))
        return "\n".join(rounds)

    def _resolve_days(self, range_key: str) -> int | None:
        return {"7d": 7, "30d": 30, "90d": 90}.get(range_key)

    def _extract_sentence(self, text: str, position: int) -> str:
        if not text:
            return ""
        index = max(0, min(position, max(0, len(text) - 1)))
        start = index
        while start > 0 and text[start - 1] not in ".?!\n":
            start -= 1
        end = index
        while end < len(text) and text[end] not in ".?!\n":
            end += 1
        if end < len(text):
            end += 1
        sentence = text[start:end].strip()
        if sentence:
            return sentence[:240]
        window_start = max(0, index - 80)
        window_end = min(len(text), index + 80)
        return text[window_start:window_end].strip()
