from PyQt6.QtCore import QPropertyAnimation, Qt, pyqtProperty
from PyQt6.QtGui import QPainter, QPixmap
from PyQt6.QtWidgets import QWidget

from src.ui import motion


class PageTransition(QWidget):
    """Drill-in and drill-out for the file list, as Windows Settings moves between pages.

    The new page slides in over the old one and fades up. Both are pictures, so the real
    rows underneath are already final when the picture goes, and the pointer passes through
    to them throughout.
    """

    DISTANCE = 24

    def __init__(self, viewport: QWidget, before: QPixmap, after: QPixmap, forward: bool):
        super().__init__(viewport)
        self.before = before
        self.after = after
        self.direction = 1 if forward else -1
        self._progress = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setGeometry(viewport.rect())
        self.show()
        self.raise_()
        self.animation = QPropertyAnimation(self, b"progress", self)
        self.animation.setStartValue(0.0)
        self.animation.setEndValue(1.0)
        self.animation.setDuration(motion.duration(motion.NORMAL))
        self.animation.setEasingCurve(motion.DECELERATE)
        self.animation.finished.connect(self.close)
        self.animation.start()

    def get_progress(self) -> float:
        return self._progress

    def set_progress(self, value: float):
        self._progress = value
        self.update()

    progress = pyqtProperty(float, get_progress, set_progress)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self.before)
        painter.setOpacity(self._progress)
        painter.drawPixmap(round(self.direction * self.DISTANCE * (1.0 - self._progress)), 0, self.after)
        painter.end()

    @classmethod
    def play(cls, viewport: QWidget, before: QPixmap, forward: bool) -> "PageTransition | None":
        """Over a viewport whose contents just changed, from a picture taken before the change."""

        if before is None or motion.duration(motion.NORMAL) == 0 or not viewport.isVisible():
            return None

        return cls(viewport, before, viewport.grab(), forward)
