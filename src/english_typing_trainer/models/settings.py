from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class AppSettings:
    section_target_characters: int = 500
    case_sensitive: bool = True
    show_live_stats: bool = True
    target_wpm: int = 60
    target_accuracy: float = 98.0
    theme: str = "light"
    font_size: int = 18
