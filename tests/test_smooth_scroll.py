import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QScrollArea, QWidget
from PyQt6.QtTest import QTest
from src.ui.smooth_scroll import SmoothScroll


class SmoothScrollTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.area = QScrollArea()
        content = QWidget()
        content.resize(100, 2000)
        self.area.setWidget(content)
        self.area.resize(200, 300)
        self.scroll = SmoothScroll(self.area)
        self.area.show()
        self.app.processEvents()
        self.bar = self.area.verticalScrollBar()
        self.bar.setSingleStep(20)
        self.addCleanup(self.area.deleteLater)
        self.addCleanup(self.area.hide)

    def wheel(self, angle=-120, pixels=0):
        event = QWheelEvent(QPointF(20, 20), QPointF(20, 20), QPoint(0, pixels), QPoint(0, angle),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        self.app.sendEvent(self.area.viewport(), event)

    def test_wheel_animates_and_accumulates(self):
        self.wheel()
        self.wheel()
        target = 2 * QApplication.wheelScrollLines() * 20
        self.assertEqual(self.scroll.vertical.target, target)
        self.assertLess(self.bar.value(), target)
        QTest.qWait(200)
        self.assertEqual(self.bar.value(), target)

    def test_touchpad_pixels_are_applied_without_extra_inertia(self):
        self.wheel(pixels=-27)
        self.assertEqual(self.bar.value(), 27)
        QTest.qWait(200)
        self.assertEqual(self.bar.value(), 27)

    def test_manual_position_and_hide_cancel_animation(self):
        self.wheel()
        self.bar.setValue(300)
        QTest.qWait(200)
        self.assertEqual(self.bar.value(), 300)
        self.wheel()
        self.area.hide()
        position = self.bar.value()
        QTest.qWait(200)
        self.assertEqual(self.bar.value(), position)

    def test_reverse_and_bounds(self):
        self.bar.setValue(100)
        self.wheel()
        self.wheel(angle=120)
        self.assertLess(self.scroll.vertical.target, 100)
        self.bar.setValue(self.bar.maximum() - 1)
        self.wheel()
        QTest.qWait(200)
        self.assertEqual(self.bar.value(), self.bar.maximum())


if __name__ == "__main__":
    unittest.main()
