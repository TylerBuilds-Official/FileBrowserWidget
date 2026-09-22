"""Motion shared by the whole app, so every move reads as the same hand.

Windows 11 animates with a few fixed durations and three curves: decelerate for things
arriving, accelerate for things leaving, and standard for things moving while on screen.
When the user turns animation effects off in Windows, every duration here becomes zero and
the app snaps, as Windows itself does. A headless platform has nobody to see motion, so it
snaps too, which also keeps the tests deterministic; a test that is about motion turns it on
with `override`.
"""
import ctypes
import os
from ctypes import wintypes

from PyQt6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPointF, QPropertyAnimation
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QWidget

FAST     = 100
NORMAL   = 167
SLOW     = 250

override: bool | None = None

SPI_GETCLIENTAREAANIMATION = 0x1042


def bezier(x1: float, y1: float, x2: float, y2: float) -> QEasingCurve:
    curve = QEasingCurve(QEasingCurve.Type.BezierSpline)
    curve.addCubicBezierSegment(QPointF(x1, y1), QPointF(x2, y2), QPointF(1.0, 1.0))

    return curve


DECELERATE = bezier(0.1, 0.9, 0.2, 1.0)
ACCELERATE = bezier(0.7, 0.0, 1.0, 0.5)
STANDARD   = bezier(0.8, 0.0, 0.2, 1.0)


def animations_enabled() -> bool:
    """Windows' own "Animation effects" switch, read each time so a change applies at once."""

    if override is not None:
        return override
    if QGuiApplication.platformName() == "offscreen":
        return False
    if os.name != "nt":
        return True
    value = wintypes.BOOL()
    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(value), 0):
        return bool(value.value)

    return True


def duration(milliseconds: int) -> int:
    return milliseconds if animations_enabled() else 0


def arrive(widget: QWidget, offset: QPoint, milliseconds: int = SLOW) -> QParallelAnimationGroup | None:
    """Slide a shown widget in from an offset and, for a window, fade it up, decelerating into place."""

    length = duration(milliseconds)
    target = widget.pos()
    if length == 0:
        if widget.isWindow():
            widget.setWindowOpacity(1.0)
        return None
    group = QParallelAnimationGroup(widget)
    slide = QPropertyAnimation(widget, b"pos", group)
    slide.setStartValue(target + offset)
    slide.setEndValue(target)
    slide.setDuration(length)
    slide.setEasingCurve(DECELERATE)
    group.addAnimation(slide)
    if widget.isWindow():
        fade = QPropertyAnimation(widget, b"windowOpacity", group)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setDuration(length)
        fade.setEasingCurve(DECELERATE)
        group.addAnimation(fade)
    widget.move(target + offset)
    group.finished.connect(group.deleteLater)
    group.start()

    return group


def travel(widget: QWidget, target: QPoint, milliseconds: int = NORMAL) -> QPropertyAnimation | None:
    """Move a widget that is already on screen to a new place along the standard curve."""

    length = duration(milliseconds)
    if length == 0 or widget.pos() == target:
        widget.move(target)
        return None
    slide = QPropertyAnimation(widget, b"pos", widget)
    slide.setEndValue(target)
    slide.setDuration(length)
    slide.setEasingCurve(STANDARD)
    slide.finished.connect(slide.deleteLater)
    slide.start()

    return slide
