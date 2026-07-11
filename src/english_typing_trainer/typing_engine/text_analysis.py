from __future__ import annotations

import re

WORD_PATTERN = re.compile(r"[A-Za-z]+(?:['-][A-Za-z]+)*")
PUNCTUATION_CHARACTERS = set('.,;:!?"\'()[]{}<>-_')


def extract_target_word(text: str, character_index: int) -> str:
    if not text or character_index < 0 or character_index >= len(text):
        return ""
    character = text[character_index]
    if not _is_word_character(character):
        return ""
    for match in WORD_PATTERN.finditer(text):
        if match.start() <= character_index < match.end():
            return match.group(0)
    return ""


def classify_error(expected_character: str, actual_character: str) -> str:
    if expected_character == "\n":
        return "newline_error"
    if expected_character == " ":
        return "space_error"
    if expected_character == "\t":
        return "wrong_character"
    if expected_character.isalpha() and actual_character.isalpha():
        if expected_character.casefold() == actual_character.casefold() and expected_character != actual_character:
            return "case_error"
    if _is_punctuation(expected_character):
        return "punctuation_error"
    return "wrong_character"


def humanize_character(character: str) -> str:
    if character == " ":
        return "[Space]"
    if character == "\n":
        return "[Enter]"
    if character == "\t":
        return "[Tab]"
    if character == "":
        return "[Empty]"
    return character


def _is_word_character(character: str) -> bool:
    return bool(re.match(r"[A-Za-z'-]", character))


def _is_punctuation(character: str) -> bool:
    return character in PUNCTUATION_CHARACTERS
