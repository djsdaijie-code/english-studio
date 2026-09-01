from __future__ import annotations


def is_cjk_character(character: str) -> bool:
    if len(character) != 1:
        return False
    codepoint = ord(character)
    return any(
        start <= codepoint <= end
        for start, end in (
            (0x3400, 0x4DBF),
            (0x4E00, 0x9FFF),
            (0xF900, 0xFAFF),
            (0x20000, 0x2FA1F),
        )
    )


def count_cjk_characters(text: str) -> int:
    return sum(1 for character in text if is_cjk_character(character))


def is_chinese_typing_text(text: str) -> bool:
    return count_cjk_characters(text) > 0
