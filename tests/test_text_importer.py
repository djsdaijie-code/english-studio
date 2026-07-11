from pathlib import Path

from english_typing_trainer.services.text_importer import import_txt_file, normalize_text


def test_normalize_text_replaces_crlf_and_strips_control_characters() -> None:
    raw = "Hello\r\nWorld\x00\x01\rAgain"
    assert normalize_text(raw) == "Hello\nWorld\nAgain"


def test_import_txt_file_reads_gbk_encoded_content(tmp_path: Path) -> None:
    file_path = tmp_path / "lesson.txt"
    file_path.write_bytes("Hello world".encode("gbk"))

    article = import_txt_file(file_path)

    assert article.title == "lesson"
    assert article.content == "Hello world"
