from PyQt6.QtCore import QPropertyAnimation, Qt, pyqtProperty
from PyQt6.QtGui import QPainter, QPalette, QPixmap
from PyQt6.QtWidgets import QWidget

from src.ui import motion


class PageTransition(QWidget):
    """A fade between file-list pages, as Windows Settings moves between pages.

    The old page goes at once and the new one fades up in place over the background, so the two
    never overlap and their icons never double. The new page is a picture, so the real rows
    underneath are already final when it goes, and the pointer passes through to them.
    """

    def __init__(self, viewport: QWidget, after: QPixmap):
        super().__init__(viewport)
        self.after = after
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
        # The background covers the real new rows, so the new page fades up from it rather than
        # over the old one; the old page is never drawn, so nothing doubles. No slide: it fades
        # in place, so a row never jitters sideways.
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().color(QPalette.ColorRole.Window))
        painter.setOpacity(self._progress)
        painter.drawPixmap(0, 0, self.after)
        painter.end()

    @classmethod
    def play(cls, viewport: QWidget, before: object) -> "PageTransition | None":
        """Over a viewport whose contents just changed. `before` only says there was a page to leave."""

        if before is None or motion.duration(motion.NORMAL) == 0 or not viewport.isVisible():
            return None

        return cls(viewport, viewport.grab())
