import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QApplication, QScrollArea, QVBoxLayout, QWidget
from PyQt6.QtTest import QTest
from src.ui.smooth_scroll import SmoothScroll, SmoothComboBox


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

    def test_rail_thickens_while_the_pointer_is_over_the_list(self):
        bar = self.area.verticalScrollBar()
        self.area.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, True)
        self.app.sendEvent(self.area.viewport(), QEvent(QEvent.Type.Enter))
        self.assertEqual(bar.property("expanded"), "true")
        self.area.setAttribute(Qt.WidgetAttribute.WA_UnderMouse, False)
        self.app.sendEvent(self.area.viewport(), QEvent(QEvent.Type.Leave))
        QTest.qWait(30)
        self.assertEqual(bar.property("expanded"), "false")

    def test_wheel_over_a_closed_combo_scrolls_the_page(self):
        area = QScrollArea()
        content = QWidget()
        layout = QVBoxLayout(content)
        combo = SmoothComboBox()
        combo.addItems(["one", "two", "three"])
        layout.addWidget(combo)
        filler = QWidget()
        filler.setFixedHeight(2000)
        layout.addWidget(filler)
        area.setWidget(content)
        area.resize(200, 300)
        scroll = SmoothScroll(area)
        area.show()
        self.app.processEvents()
        self.addCleanup(area.deleteLater)
        self.addCleanup(area.hide)
        event = QWheelEvent(QPointF(combo.rect().center()), QPointF(20, 20), QPoint(0, 0), QPoint(0, -120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        self.app.sendEvent(combo, event)
        QTest.qWait(250)
        self.assertEqual(combo.currentIndex(), 0)
        self.assertGreater(area.verticalScrollBar().value(), 0)
        self.assertEqual(scroll.vertical.bar, area.verticalScrollBar())

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
