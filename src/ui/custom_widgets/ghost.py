from PyQt6 import sip
from PyQt6.QtCore import QParallelAnimationGroup, QPoint, QPropertyAnimation, QRectF, Qt
from PyQt6.QtGui import QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QApplication, QWidget

from src.ui import motion


class Ghost(QWidget):
    """A window's stand-in for its exit, leaving the way a Windows flyout does.

    The real window hides at once, so the click that dismissed it lands where it should and
    focus moves on; only this picture slides and fades, and it takes no input. It waits over
    its window, mapped and fully transparent, from the moment that window shows: a window
    first shown at the exit paints a frame late, and the desktop flashes through the gap.
    It clips itself to the corner radius the compositor gives the window it stands in for.
    """

    RADIUS = 8

    def __init__(self, owner: QWidget):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowTransparentForInput | Qt.WindowType.WindowDoesNotAcceptFocus
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.owner = owner
        self.picture = QPixmap()
        self.group = None
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        owner.destroyed.connect(self.deleteLater)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), self.RADIUS, self.RADIUS)
        painter.setClipPath(clip)
        painter.drawPixmap(0, 0, self.picture)
        painter.end()

    def prepare(self):
        """Wait over the owner, invisible but on screen, so the exit can start on the next frame."""

        if not motion.animations_enabled() or QApplication.closingDown():
            return
        self._settle()
        self.setWindowOpacity(0.0)
        self.setGeometry(self.owner.frameGeometry())
        self.show()

    def depart(self, offset: QPoint, milliseconds: int = motion.NORMAL) -> QParallelAnimationGroup | None:
        """Take the owner's picture and go along the accelerate curve; the owner can hide at once."""

        length = motion.duration(milliseconds)
        if length == 0 or QApplication.closingDown() or not self.isVisible():
            self.hide()
            return None
        self._settle()
        self.picture = self.owner.grab()
        self.setGeometry(self.owner.frameGeometry())
        self.repaint()  # Flushed now, still transparent: the window is mapped, so this lands.
        self.setWindowOpacity(self.owner.windowOpacity())
        group = QParallelAnimationGroup(self)
        slide = QPropertyAnimation(self, b"pos", group)
        slide.setEndValue(self.pos() + offset)
        slide.setDuration(length)
        slide.setEasingCurve(motion.ACCELERATE)
        group.addAnimation(slide)
        fade = QPropertyAnimation(self, b"windowOpacity", group)
        fade.setEndValue(0.0)
        fade.setDuration(length)
        fade.setEasingCurve(motion.ACCELERATE)
        group.addAnimation(fade)
        group.finished.connect(self.hide)
        group.start()
        self.group = group

        return group

    def _settle(self):
        """Cut short an exit still playing; the owner is back, or going again."""

        if self.group is not None and not sip.isdeleted(self.group):
            self.group.stop()
            self.group.deleteLater()
        self.group = None
