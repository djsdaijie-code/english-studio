"""Render the editable SVG into reproducible PNG, ICO and ICNS app icons."""

from __future__ import annotations

import argparse
from pathlib import Path
import struct

from PySide6.QtCore import QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon, QImage, QImageReader, QPainter
from PySide6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parents[1]
ICON_DIR = ROOT / "resources" / "icons"


def render(renderer: QSvgRenderer, size: int) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise RuntimeError(f"Could not encode {size}px icon")
    return bytes(buffer.data())


def export_icons(source: Path, output_dir: Path) -> None:
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError(f"Invalid SVG: {source}")
    output_dir.mkdir(parents=True, exist_ok=True)
    ico_sizes = (16, 24, 32, 48, 64, 128, 256)
    icns_sizes = ((b"icp4", 16), (b"icp5", 32), (b"icp6", 64), (b"ic07", 128), (b"ic08", 256), (b"ic09", 512), (b"ic10", 1024))
    frames = {size: render(renderer, size) for size in set(ico_sizes) | {size for _, size in icns_sizes}}
    (output_dir / "shiju.png").write_bytes(frames[1024])

    # Windows ICO directory entries point to independently rendered PNG frames.
    offset = 6 + 16 * len(ico_sizes)
    directory = []
    for size in ico_sizes:
        frame = frames[size]
        directory.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(frame), offset))
        offset += len(frame)
    (output_dir / "shiju.ico").write_bytes(
        struct.pack("<HHH", 0, 1, len(ico_sizes)) + b"".join(directory) + b"".join(frames[size] for size in ico_sizes)
    )

    elements = b"".join(kind + struct.pack(">I", len(frames[size]) + 8) + frames[size] for kind, size in icns_sizes)
    (output_dir / "shiju.icns").write_bytes(b"icns" + struct.pack(">I", len(elements) + 8) + elements)

    for name in ("shiju.png", "shiju.ico", "shiju.icns"):
        reader = QImageReader(str(output_dir / name))
        if not reader.canRead() or reader.read().isNull():
            raise RuntimeError(f"Qt cannot decode generated asset: {name}")
    actual_sizes = {size.width() for size in QIcon(str(output_dir / "shiju.ico")).availableSizes()}
    if actual_sizes != set(ico_sizes):
        raise RuntimeError(f"Unexpected ICO sizes: {actual_sizes}")
    print("Exported shiju.png (1024px), shiju.ico (7 sizes), shiju.icns (16-1024px)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ICON_DIR)
    parser.add_argument("--preview", action="store_true")
    options = parser.parse_args()
    app = QGuiApplication.instance() or QGuiApplication([])
    export_icons(ICON_DIR / "shiju.svg", options.output_dir)
    if options.preview:
        preview = QImage(880, 520, QImage.Format.Format_ARGB32_Premultiplied)
        preview.fill(QColor("#edf1f5"))
        painter = QPainter(preview)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor("#193249"))
        painter.setFont(QFont("Microsoft YaHei UI", 20, QFont.Weight.Bold))
        painter.drawText(24, 42, "拾句")
        painter.setFont(QFont("Microsoft YaHei UI", 11))
        painter.drawText(112, 40, "拾句习语，读懂英文。")
        renderer = QSvgRenderer(str(ICON_DIR / "shiju.svg"))
        for x, background, foreground in ((24, "#ffffff", "#64748b"), (452, "#152538", "#b3c4d5")):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(background))
            painter.drawRoundedRect(QRectF(x, 64, 404, 432), 20, 20)
            renderer.render(painter, QRectF(x + 92, 86, 220, 220))
            painter.setPen(QColor(foreground))
            painter.setFont(QFont("Microsoft YaHei UI", 10))
            for offset, size in ((28, 16), (84, 24), (148, 32), (220, 48), (300, 64)):
                renderer.render(painter, QRectF(x + offset, 365 - size / 2, size, size))
                painter.drawText(QRectF(x + offset - 10, 410, size + 20, 24), Qt.AlignmentFlag.AlignCenter, str(size))
        painter.end()
        if not preview.save(str(options.output_dir / "shiju-preview.png")):
            raise RuntimeError("Could not save preview")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
