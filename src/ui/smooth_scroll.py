from PyQt6.QtCore import QObject, QEvent, QTimer, QVariantAnimation, QEasingCurve, Qt
from PyQt6.QtWidgets import (QApplication, QComboBox, QListView, QAbstractItemView,
                             QAbstractScrollArea)


class ScrollAxis(QObject):
    def __init__(self, bar, parent):
        super().__init__(parent)
        self.bar = bar
        self.target = bar.value()
        self.applying = False
        self.animation = QVariantAnimation(self)
        self.animation.setDuration(160)
        self.animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.animation.valueChanged.connect(self.set_value)
        bar.valueChanged.connect(self.external_change)
        bar.sliderPressed.connect(self.stop)
        bar.rangeChanged.connect(self.stop)

    def stop(self, *_):
        self.animation.stop()
        self.target = self.bar.value()

    def external_change(self, _):
        if not self.applying:
            self.stop()

    def set_value(self, value):
        self.applying = True
        self.bar.setValue(round(value))
        self.applying = False

    def scroll(self, delta, immediate=False):
        if immediate:
            self.stop()
            self.bar.setValue(round(self.bar.value() + delta))
            return
        # Reverse from the current position instead of fighting queued motion.
        if (self.target - self.bar.value()) * delta < 0:
            self.target = self.bar.value()
        self.target = max(self.bar.minimum(), min(self.bar.maximum(), self.target + delta))
        self.animation.stop()
        self.animation.setStartValue(float(self.bar.value()))
        self.animation.setEndValue(float(self.target))
        self.animation.start()


class SmoothScroll(QObject):
    """Smooth mouse wheels; preserve touchpad pixels and direct scrollbar input."""

    def __init__(self, area):
        super().__init__(area)
        self.area = area
        self.vertical = ScrollAxis(area.verticalScrollBar(), self)
        self.horizontal = ScrollAxis(area.horizontalScrollBar(), self)
        for widget in (area, area.viewport(), area.verticalScrollBar(), area.horizontalScrollBar()):
            widget.installEventFilter(self)
        # Owned by this object, so a pending re-check dies with the area instead of outliving it.
        self.rail_timer = QTimer(self)
        self.rail_timer.setSingleShot(True)
        self.rail_timer.timeout.connect(self.recheck_rail)
        self.expand_rail(False)

    def recheck_rail(self):
        self.expand_rail(self.area.underMouse())

    def stop(self):
        self.vertical.stop()
        self.horizontal.stop()

    def expand_rail(self, expanded):
        """Windows thickens its hairline rail while the pointer is anywhere over the list."""
        for bar in (self.vertical.bar, self.horizontal.bar):
            value = "true" if expanded else "false"
            if bar.property("expanded") != value:
                bar.setProperty("expanded", value)
                bar.style().unpolish(bar)
                bar.style().polish(bar)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Enter:
            self.expand_rail(True)
        elif event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
            # A move between the list and the bar leaves one and enters the other, so re-check.
            self.rail_timer.start()
        if event.type() in (QEvent.Type.Hide, QEvent.Type.KeyPress, QEvent.Type.MouseButtonPress):
            self.stop()
        if event.type() != QEvent.Type.Wheel:
            return False
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            return False
        pixels, angle = event.pixelDelta(), event.angleDelta()
        horizontal = (watched == self.area.horizontalScrollBar() or
                      bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier) or
                      (angle.y() == 0 and angle.x() != 0) or (pixels.y() == 0 and pixels.x() != 0))
        axis = self.horizontal if horizontal else self.vertical
        if axis.bar.maximum() == axis.bar.minimum():
            return False
        pixel_delta = (pixels.x() or pixels.y()) if horizontal else pixels.y()
        if not pixels.isNull():
            axis.scroll(-pixel_delta, immediate=True)
        else:
            delta = (angle.x() or angle.y()) if horizontal else angle.y()
            axis.scroll(-delta / 120 * QApplication.wheelScrollLines() * axis.bar.singleStep())
        event.accept()
        return True


class SmoothComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        view = QListView()
        view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.setView(view)
        self.setMaxVisibleItems(10)
        self.smooth_scroll = SmoothScroll(view)

    def wheelEvent(self, event):
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        # Scroll the page the box sits on instead of changing the value under the cursor.
        event.ignore()
        area = self.parentWidget()
        while area is not None and not isinstance(area, QAbstractScrollArea):
            area = area.parentWidget()
        if area is not None:
            QApplication.sendEvent(area.viewport(), event)
