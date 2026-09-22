"""Build the Windows icon and the header image from the logo master.

Windows wants a square icon with a frame for each size it draws: 16 to 32 in the tray and
taskbar at the common scales, 48 and 64 in Explorer, and 256 for the large tiles. The mark
is wider than it is tall, so every frame letterboxes it on a transparent square. Frames up
to 128 are stored as plain bitmaps, which everything that reads an .ico understands; 256 is
stored as PNG, the way Windows stores its own. The header image keeps the mark's own
proportions at three times the height the settings header draws it, enough for any scale.

    .venv\\Scripts\\python.exe tools\\build-icon.py
"""
import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QBuffer, QIODevice, Qt
from PyQt6.QtGui import QGuiApplication, QImage, QPainter

LOGO          = Path(__file__).resolve().parents[1] / "src" / "assets" / "logo"
SIZES         = (16, 20, 24, 32, 40, 48, 64, 128, 256)
PNG_MIN       = 256
HEADER_HEIGHT = 84


def squared(source: QImage) -> QImage:
    """The wordmark centred on a transparent square, so every frame keeps its shape."""

    side = max(source.width(), source.height())
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawImage((side - source.width()) // 2, (side - source.height()) // 2, source)
    painter.end()

    return canvas


def bitmap_frame(frame: QImage) -> bytes:
    """A 32-bit DIB as .ico stores it: header, bottom-up BGRA rows, then an empty mask."""

    width, height = frame.width(), frame.height()
    frame = frame.convertToFormat(QImage.Format.Format_ARGB32)
    stride = frame.bytesPerLine()
    pixels = frame.bits().asstring(stride * height)
    rows = [pixels[y * stride:y * stride + width * 4] for y in reversed(range(height))]
    mask = bytes(((width + 31) // 32) * 4 * height)
    header = struct.pack("<IiiHHIIiiII", 40, width, height * 2, 1, 32, 0,
                         width * height * 4 + len(mask), 0, 0, 0, 0)

    return header + b"".join(rows) + mask


def png_frame(frame: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    frame.save(buffer, "PNG")

    return bytes(buffer.data())


def build_icon(master: Path, target: Path) -> list[int]:
    """Write every frame into one .ico: the directory first, then the frames in order."""

    QGuiApplication.instance() or QGuiApplication(sys.argv)
    source = QImage(str(master))
    if source.isNull():
        raise FileNotFoundError(master)
    square = squared(source)
    frames = []
    for size in SIZES:
        frame = square.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        frames.append((size, png_frame(frame) if size >= PNG_MIN else bitmap_frame(frame)))
    directory = struct.pack("<HHH", 0, 1, len(frames))
    offset = len(directory) + 16 * len(frames)
    entries = []
    for size, data in frames:
        entries.append(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    target.write_bytes(directory + b"".join(entries) + b"".join(data for _, data in frames))

    return [size for size, _ in frames]


def build_header(master: Path, target: Path) -> QImage:
    """The mark at its own proportions, sized for the settings header on a high-DPI screen."""

    QGuiApplication.instance() or QGuiApplication(sys.argv)
    source = QImage(str(master))
    if source.isNull():
        raise FileNotFoundError(master)
    header = source.scaledToHeight(HEADER_HEIGHT, Qt.TransformationMode.SmoothTransformation)
    header.save(str(target), "PNG")

    return header


if __name__ == "__main__":
    written = build_icon(LOGO / "fb_icon.png", LOGO / "fb_icon.ico")
    print(f"Wrote {LOGO / 'fb_icon.ico'} with frames {written}")
    header = build_header(LOGO / "fb_icon.png", LOGO / "fb_icon_header.png")
    print(f"Wrote {LOGO / 'fb_icon_header.png'} at {header.width()}x{header.height()}")
