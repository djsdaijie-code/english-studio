from __future__ import annotations

import re

WORD_CORE_PATTERN = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
EDGE_PUNCTUATION = " \t\r\n\"'`“”‘’.,;:!?()[]{}<>«»"


class WordNormalizationService:
    def clean(self, raw_text: str) -> str:
        cleaned = raw_text.strip().replace("’", "'").replace("‘", "'")
        cleaned = cleaned.replace("—", "-").replace("–", "-")
        return cleaned.strip(EDGE_PUNCTUATION)

    def normalize(self, raw_text: str) -> str:
        cleaned = self.clean(raw_text)
        if not cleaned:
            return ""
        match = WORD_CORE_PATTERN.fullmatch(cleaned)
        if match is None:
            return ""
        return match.group(0).lower()

    def is_valid_word(self, raw_text: str) -> bool:
        return bool(self.normalize(raw_text))

    def validate_selection(self, raw_text: str) -> tuple[str, str]:
        display = self.clean(raw_text)
        normalized = self.normalize(display)
        if not normalized:
            raise ValueError("请选择一个英文单词")
        return normalized, display

    def safe_lemma_candidates(self, normalized_word: str) -> list[str]:
        candidates = [normalized_word]
        if normalized_word.endswith("ies") and len(normalized_word) > 4:
            candidates.append(normalized_word[:-3] + "y")
        elif normalized_word.endswith("s") and not normalized_word.endswith("ss") and len(normalized_word) > 3:
            candidates.append(normalized_word[:-1])
        if normalized_word.endswith("ed") and len(normalized_word) > 4:
            candidates.append(normalized_word[:-2])
        if normalized_word.endswith("ing") and len(normalized_word) > 5:
            candidates.append(normalized_word[:-3])
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))
