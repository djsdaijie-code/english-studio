from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QWidget


def style_root() -> Path:
    return Path(__file__).resolve().parents[3] / "resources" / "styles"


def resolve_theme(theme_name: str) -> str:
    if theme_name == "system":
        return "light"
    return theme_name if theme_name in {"light", "dark"} else "light"


def load_stylesheet(theme_name: str) -> str:
    theme_key = resolve_theme(theme_name)
    path = style_root() / f"{theme_key}.qss"
    return path.read_text(encoding="utf-8")


def build_app_font(font_size: int = 14) -> QFont:
    for font_path in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\msyhbd.ttc"),
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
    ):
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
    font = QFont("Microsoft YaHei UI", font_size)
    font.setStyleStrategy(QFont.PreferAntialias)
    return font


def apply_theme(widget: QWidget, theme_name: str, *, font_size: int = 14) -> None:
    app = QApplication.instance()
    if app is not None:
        app.setFont(build_app_font(font_size))
    widget.setStyleSheet(load_stylesheet(theme_name))
