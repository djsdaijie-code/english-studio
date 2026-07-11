from __future__ import annotations

import re

WORD_CORE_PATTERN = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
EDGE_PUNCTUATION = " \t\r\n\"'`“”‘’.,;:!?()[]{}<>«»"


class WordNormalizationService:
    def normalize(self, raw_text: str) -> str:
        cleaned = raw_text.strip().replace("—", "-").replace("–", "-")
        cleaned = cleaned.strip(EDGE_PUNCTUATION)
        if not cleaned:
            return ""
        match = WORD_CORE_PATTERN.fullmatch(cleaned)
        if match is None:
            return ""
        return match.group(0).lower()

    def is_valid_word(self, raw_text: str) -> bool:
        return bool(self.normalize(raw_text))
