from __future__ import annotations

import hashlib
import re

from english_typing_trainer.models.sentence import SentenceSegment


class SentenceSegmentationService:
    _abbreviations = {
        "mr.", "mrs.", "ms.", "dr.", "prof.", "sr.", "jr.", "st.",
        "vs.", "etc.", "e.g.", "i.e.", "a.m.", "p.m.",
    }
    _closers = set('"\'”’)]}')

    def __init__(self, max_sentence_characters: int = 500) -> None:
        self.max_sentence_characters = max(80, max_sentence_characters)

    def split(self, text: str) -> list[SentenceSegment]:
        if not text:
            return []
        ranges: list[tuple[int, int]] = []
        start = 0
        index = 0
        while index < len(text):
            character = text[index]
            boundary = None
            if character in ".?!" and not self._is_protected_period(text, index):
                boundary = self._terminal_boundary(text, index)
            elif character == "\n" and text[start:index].strip():
                boundary = self._consume_whitespace(text, index + 1)
            elif index - start + 1 >= self.max_sentence_characters:
                boundary = self._fallback_boundary(text, start, index + 1)

            if boundary is not None and boundary > start:
                if text[start:boundary].strip():
                    ranges.append((start, boundary))
                    start = boundary
                    index = boundary
                    continue
            index += 1

        if start < len(text):
            if text[start:].strip() or not ranges:
                ranges.append((start, len(text)))
            elif ranges:
                previous_start, _ = ranges[-1]
                ranges[-1] = (previous_start, len(text))

        return [self._segment(sentence_index, text, start_offset, end_offset) for sentence_index, (start_offset, end_offset) in enumerate(ranges)]

    def _segment(self, index: int, text: str, start: int, end: int) -> SentenceSegment:
        sentence_text = text[start:end]
        normalized = " ".join(sentence_text.split())
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return SentenceSegment(index, sentence_text, normalized, digest, start, end)

    def _terminal_boundary(self, text: str, index: int) -> int:
        end = index + 1
        while end < len(text) and text[end] in ".?!":
            end += 1
        while end < len(text) and text[end] in self._closers:
            end += 1
        return self._consume_whitespace(text, end)

    def _consume_whitespace(self, text: str, index: int) -> int:
        while index < len(text) and text[index].isspace():
            index += 1
        return index

    def _fallback_boundary(self, text: str, start: int, upper: int) -> int:
        lower = start + int(self.max_sentence_characters * 0.65)
        for index in range(min(upper, len(text)) - 1, lower - 1, -1):
            if text[index].isspace():
                return self._consume_whitespace(text, index + 1)
        return min(upper, len(text))

    def _is_protected_period(self, text: str, index: int) -> bool:
        if text[index] != ".":
            return False
        if 0 < index < len(text) - 1 and text[index - 1].isdigit() and text[index + 1].isdigit():
            return True
        if index + 2 < len(text) and text[index - 1:index].isalpha() and text[index + 1].isalpha() and text[index + 2] == ".":
            return True
        token_start = index
        while token_start > 0 and not text[token_start - 1].isspace():
            token_start -= 1
        token = text[token_start:index + 1].strip('"\'“‘([{').lower()
        if token in self._abbreviations:
            return True
        if re.fullmatch(r"(?:[a-z]\.){2,}", token, flags=re.IGNORECASE):
            return True
        return False