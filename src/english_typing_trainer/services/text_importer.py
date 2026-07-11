from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from english_typing_trainer.models.article import Article

SUPPORTED_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk")


@dataclass(slots=True)
class ImportedText:
    title: str
    original_filename: str
    source_path: str
    content: str


def import_txt_file(path: str | Path) -> Article:
    imported = read_text_file(path)
    return Article(
        title=imported.title,
        full_text=imported.content,
        original_filename=imported.original_filename,
        source_path=imported.source_path,
    )


def read_text_file(path: str | Path) -> ImportedText:
    file_path = Path(path)
    raw_bytes = file_path.read_bytes()
    content = _decode_bytes(raw_bytes)
    normalized = normalize_text(content)
    return ImportedText(
        title=file_path.stem,
        original_filename=file_path.name,
        source_path=str(file_path),
        content=normalized,
    )


def _decode_bytes(raw_bytes: bytes) -> str:
    for encoding in SUPPORTED_ENCODINGS:
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def normalize_text(content: str) -> str:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    cleaned_chars: list[str] = []
    for char in content:
        if char == "\n" or char == "\t" or char.isprintable():
            cleaned_chars.append(char)
    return "".join(cleaned_chars).strip()
