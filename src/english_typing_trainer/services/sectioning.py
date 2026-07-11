from __future__ import annotations

from dataclasses import dataclass

from english_typing_trainer.models.section import ArticleSection

ALLOWED_SECTION_TARGETS = (300, 500, 800, 1000)


@dataclass(slots=True)
class SectioningService:
    default_target_characters: int = 500

    def split_into_sections(self, text: str, target_characters: int | None = None) -> list[ArticleSection]:
        if not text:
            return []

        target = target_characters or self.default_target_characters
        if target <= 0:
            target = self.default_target_characters

        sections: list[ArticleSection] = []
        start = 0
        section_index = 0
        text_length = len(text)

        while start < text_length:
            remaining = text_length - start
            if remaining <= target:
                end = text_length
            else:
                end = self._choose_breakpoint(text, start, target)

            if end <= start:
                end = min(text_length, max(start + 1, start + target))

            chunk = text[start:end]
            if not chunk:
                break

            sections.append(
                ArticleSection(
                    section_index=section_index,
                    text=chunk,
                    start_offset=start,
                    end_offset=end,
                )
            )
            section_index += 1
            start = end

        return sections

    def _choose_breakpoint(self, text: str, start: int, target: int) -> int:
        preferred = min(len(text), start + target)
        lower = min(len(text), start + max(1, target // 2))
        upper = min(len(text), start + max(target + target // 3, target))
        extended_upper = min(len(text), start + max(target + target // 2, target + 1))

        candidate = self._find_best_boundary(text, lower, preferred, upper)
        if candidate is not None:
            return candidate

        candidate = self._find_best_boundary(text, start + 1, preferred, extended_upper)
        if candidate is not None:
            return candidate

        return min(len(text), preferred)

    def _find_best_boundary(
        self,
        text: str,
        lower: int,
        preferred: int,
        upper: int,
    ) -> int | None:
        best_position: int | None = None
        best_rank: int | None = None
        best_distance: int | None = None

        for position in range(lower, upper + 1):
            rank = self._boundary_rank(text, position)
            if rank is None:
                continue
            distance = abs(position - preferred)
            if (
                best_rank is None
                or rank < best_rank
                or (rank == best_rank and distance < (best_distance or 10**9))
            ):
                best_rank = rank
                best_distance = distance
                best_position = position

        return best_position

    def _boundary_rank(self, text: str, position: int) -> int | None:
        if position <= 0 or position >= len(text):
            return position if position == len(text) else None

        before = text[:position]
        prev_char = before[-1]
        prev_two = before[-2:] if len(before) >= 2 else before

        if "\n\n" in prev_two:
            return 0

        previous_visible = self._previous_visible_char(before)
        if previous_visible and previous_visible in ".?!":
            return 1
        if previous_visible and previous_visible in ";:":
            return 2
        if prev_char.isspace():
            return 3
        return None

    def _previous_visible_char(self, text: str) -> str:
        for char in reversed(text):
            if char in "\"'”’)]}":
                continue
            if char.isspace():
                continue
            return char
        return ""
