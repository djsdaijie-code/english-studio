from english_typing_trainer.services.sectioning import SectioningService


def test_short_article_stays_in_one_section() -> None:
    service = SectioningService()
    sections = service.split_into_sections("Short article.", 300)
    assert len(sections) == 1
    assert sections[0].text == "Short article."


def test_multi_paragraph_article_prefers_natural_breaks() -> None:
    service = SectioningService()
    text = "Paragraph one ends here.\n\nParagraph two ends here.\n\nParagraph three."
    sections = service.split_into_sections(text, 25)
    assert "".join(section.text for section in sections) == text
    assert len(sections) >= 2


def test_no_punctuation_long_article_does_not_lose_characters() -> None:
    service = SectioningService()
    text = " ".join(["word"] * 250)
    sections = service.split_into_sections(text, 300)
    assert "".join(section.text for section in sections) == text
    assert len(sections) >= 2


def test_super_long_word_is_force_split_without_infinite_loop() -> None:
    service = SectioningService()
    text = "x" * 1400
    sections = service.split_into_sections(text, 300)
    assert "".join(section.text for section in sections) == text
    assert all(section.text for section in sections)


def test_consecutive_blank_lines_are_preserved_in_reconstruction() -> None:
    service = SectioningService()
    text = "One.\n\n\nTwo.\n\n\n\nThree."
    sections = service.split_into_sections(text, 8)
    assert "".join(section.text for section in sections) == text


def test_quotes_and_dashes_are_preserved() -> None:
    service = SectioningService()
    text = '"Stay calm," she said -- and then paused. "Keep typing!"'
    sections = service.split_into_sections(text, 25)
    assert "".join(section.text for section in sections) == text


def test_multiple_targets_preserve_full_text() -> None:
    service = SectioningService()
    text = ("Sentence one. Sentence two? Sentence three! " * 40).strip()
    for target in (300, 500, 800, 1000):
        sections = service.split_into_sections(text, target)
        assert "".join(section.text for section in sections) == text
        assert all(section.text for section in sections)
