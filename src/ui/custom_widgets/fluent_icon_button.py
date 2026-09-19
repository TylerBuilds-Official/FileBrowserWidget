from functools import lru_cache
from pathlib import Path

from PyQt6.QtCore import QEvent, QRectF, QSize, Qt
from PyQt6.QtGui import QIcon, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QPushButton


@lru_cache
def _svg_source(name):
    return (Path(__file__).resolve().parents[2] / "assets" / "icons" / f"{name}.svg").read_text(encoding="utf-8")


class FluentIconButton(QPushButton):
    """A Fluent SVG button that follows the current palette and display scale."""

    def __init__(self, icon_name, label, parent=None):
        super().__init__(parent)
        self._icon_name = icon_name
        self.setProperty("role", "iconButton")
        self.setFixedSize(36, 36)
        self.setIconSize(QSize(20, 20))
        self.setAccessibleName(label)
        self.setToolTip(label)
        self._update_icon()

    def _update_icon(self):
        color = self.palette().color(QPalette.ColorRole.ButtonText).name()
        source = _svg_source(self._icon_name).replace("#212121", color)
        renderer = QSvgRenderer(source.encode("utf-8"))
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(20 * ratio), round(20 * ratio))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter, QRectF(0, 0, 20, 20))
        painter.end()
        self.setIcon(QIcon(pixmap))

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "_icon_name") and event.type() in (
            QEvent.Type.PaletteChange, QEvent.Type.StyleChange,
            QEvent.Type.DevicePixelRatioChange,
        ):
            self._update_icon()

