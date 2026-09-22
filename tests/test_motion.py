import os
import shutil
import unittest
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import sip
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QScrollArea, QWidget

from src.ui import motion
from src.ui.custom_widgets.ghost import Ghost
from src.ui.custom_widgets.page_transition import PageTransition
from src.ui.file_browser import FileBrowser


def ghosts(app):
    """The ghosts on screen; a prepared one waits transparent, a departing one is fading."""

    return [widget for widget in app.topLevelWidgets()
            if isinstance(widget, Ghost) and not sip.isdeleted(widget) and widget.isVisible()]


class MotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        motion.override = True
        self.addCleanup(setattr, motion, "override", None)

    def window(self):
        widget = QWidget()
        widget.resize(120, 80)
        widget.move(100, 100)
        widget.show()
        self.addCleanup(widget.deleteLater)
        self.addCleanup(widget.hide)
        self.app.processEvents()
        return widget

    def test_headless_and_the_windows_switch_decide_whether_anything_moves(self):
        motion.override = None
        self.assertFalse(motion.animations_enabled())  # Nobody watches an offscreen platform.
        self.assertEqual(motion.duration(motion.SLOW), 0)
        motion.override = True
        self.assertEqual(motion.duration(motion.SLOW), motion.SLOW)
        motion.override = False
        self.assertEqual(motion.duration(motion.FAST), 0)

    def test_arrive_slides_and_fades_a_window_into_place(self):
        widget = self.window()
        self.assertIsNotNone(motion.arrive(widget, QPoint(0, 24), 60))
        self.assertEqual(widget.pos(), QPoint(100, 124))
        self.assertEqual(widget.windowOpacity(), 0.0)
        QTest.qWait(400)
        self.assertEqual(widget.pos(), QPoint(100, 100))
        self.assertEqual(widget.windowOpacity(), 1.0)
        motion.override = False
        widget.setWindowOpacity(0.0)
        self.assertIsNone(motion.arrive(widget, QPoint(0, 24), 60))
        self.assertEqual(widget.pos(), QPoint(100, 100))
        self.assertEqual(widget.windowOpacity(), 1.0)

    def test_travel_glides_to_a_new_place_and_snaps_when_motion_is_off(self):
        widget = self.window()
        self.assertIsNotNone(motion.travel(widget, QPoint(200, 150), 60))
        self.assertNotEqual(widget.pos(), QPoint(200, 150))
        QTest.qWait(400)
        self.assertEqual(widget.pos(), QPoint(200, 150))
        motion.override = False
        self.assertIsNone(motion.travel(widget, QPoint(20, 30), 60))
        self.assertEqual(widget.pos(), QPoint(20, 30))

    def test_ghost_waits_transparent_then_stands_in_for_the_hidden_window(self):
        widget = self.window()
        ghost = Ghost(widget)
        self.addCleanup(ghost.deleteLater)
        ghost.prepare()
        self.app.processEvents()
        self.assertTrue(ghost.isVisible())
        self.assertEqual(ghost.windowOpacity(), 0.0)
        self.assertEqual(ghost.geometry(), widget.frameGeometry())
        self.assertTrue(ghost.windowFlags() & Qt.WindowType.WindowTransparentForInput)
        widget.move(140, 120)
        self.assertIsNotNone(ghost.depart(QPoint(0, 12), 60))
        widget.hide()
        self.assertEqual(ghost.windowOpacity(), 1.0)
        self.assertEqual(ghost.geometry(), widget.frameGeometry())
        self.assertFalse(ghost.picture.isNull())
        QTest.qWait(400)
        self.assertFalse(ghost.isVisible())
        self.assertEqual(ghosts(self.app), [])
        motion.override = False
        ghost.prepare()
        self.assertFalse(ghost.isVisible())
        self.assertIsNone(ghost.depart(QPoint(0, 12), 60))

    def test_page_transition_covers_the_viewport_and_removes_itself(self):
        area = QScrollArea()
        area.resize(200, 150)
        area.setWidget(QLabel("page"))
        area.show()
        self.addCleanup(area.deleteLater)
        self.addCleanup(area.hide)
        self.app.processEvents()
        before = QPixmap(area.viewport().size())
        before.fill(QColor("red"))
        overlay = PageTransition.play(area.viewport(), before, forward=True)
        self.assertIsNotNone(overlay)
        self.assertEqual(overlay.geometry(), area.viewport().rect())
        self.assertTrue(overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
        self.assertEqual(overlay.direction, 1)
        QTest.qWait(400)
        self.assertTrue(sip.isdeleted(overlay))
        self.assertIsNone(PageTransition.play(area.viewport(), None, forward=True))
        motion.override = False
        self.assertIsNone(PageTransition.play(area.viewport(), before, forward=True))


class BrowserMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        motion.override = True
        self.addCleanup(setattr, motion, "override", None)
        self.root = Path(__file__).resolve().parent / f".motion-test-{uuid4().hex}"
        (self.root / "Inner").mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.root)
        self.browser = FileBrowser()
        self.browser.resize(400, 640)
        self.browser.move(100, 100)
        self.addCleanup(self.browser.deleteLater)
        self.browser.create_list_items(self.root)

    def overlays(self):
        return [widget for widget in self.browser.scroll_area.viewport().children()
                if isinstance(widget, PageTransition) and not sip.isdeleted(widget)]

    def dismiss(self):
        """Hide the panel and let its ghost finish, so nothing lingers into the next test."""

        self.browser.hide()
        QTest.qWait(300)
        self.assertEqual(ghosts(self.app), [])

    def test_navigation_drills_in_and_out_in_the_direction_taken(self):
        self.browser.show()
        self.app.processEvents()
        for move, direction in (
            (lambda: self.browser.navigate_to(self.root / "Inner"), 1),
            (self.browser.go_back, -1),
            (self.browser.go_forward, 1),
            (self.browser.go_up, -1),
        ):
            move()
            self.assertEqual([overlay.direction for overlay in self.overlays()], [direction])
            QTest.qWait(400)
            self.assertEqual(self.overlays(), [])
        self.dismiss()

    def test_a_hidden_panel_navigates_without_a_transition(self):
        self.browser.navigate_to(self.root / "Inner")
        self.assertEqual(self.browser.current_folder, self.root / "Inner")
        self.assertEqual(self.overlays(), [])

    def test_panel_arrives_from_its_docked_edge_and_leaves_a_ghost(self):
        browser = self.browser
        browser.prepare_arrival()
        self.assertEqual(browser.windowOpacity(), 0.0)
        browser.show()
        self.app.processEvents()
        self.assertTrue(browser.ghost.isVisible())  # Waiting, so the exit never shows a gap.
        self.assertEqual(browser.ghost.windowOpacity(), 0.0)
        target = browser.pos()
        browser.arrive()
        self.assertEqual(browser.pos(), target + QPoint(0, browser.SLIDE))  # Docked at the bottom.
        QTest.qWait(500)
        self.assertEqual(browser.pos(), target)
        self.assertEqual(browser.windowOpacity(), 1.0)
        browser.hide()
        self.assertFalse(browser.isVisible())
        self.assertEqual(ghosts(self.app), [browser.ghost])
        self.assertEqual(browser.ghost.windowOpacity(), 1.0)
        self.assertEqual(browser.ghost.geometry(), browser.frameGeometry())
        QTest.qWait(400)
        self.assertEqual(ghosts(self.app), [])
        modal = browser.settings_modal
        modal.docking_combo.setCurrentIndex(modal.docking_combo.findData("top_left"))
        self.assertEqual(browser.edge_offset(10), QPoint(0, -10))

    def test_filter_flyout_drops_from_its_button_and_departs(self):
        browser = self.browser
        browser.show()
        self.app.processEvents()
        browser.focus_search()
        menu = browser.filter_menu
        self.assertTrue(menu.isVisible())
        self.assertLess(menu.windowOpacity(), 1.0)
        QTest.qWait(400)
        self.assertEqual(menu.windowOpacity(), 1.0)
        menu.close()
        self.assertFalse(menu.isVisible())
        self.assertEqual(set(ghosts(self.app)), {menu.ghost, browser.ghost})
        QTest.qWait(300)
        self.assertEqual(ghosts(self.app), [browser.ghost])  # The panel's still waits, transparent.
        self.dismiss()

    def test_settings_snap_when_motion_is_off_and_slide_when_it_is_on(self):
        browser = self.browser
        browser.show()
        self.app.processEvents()
        motion.override = False
        browser.show_settings_modal()
        self.assertEqual(browser.settings_modal.pos(), QPoint(0, 0))
        browser.hide_settings_modal()
        self.assertTrue(browser.settings_modal.isHidden())
        motion.override = True
        browser.show_settings_modal()
        self.assertNotEqual(browser.settings_modal.pos(), QPoint(0, 0))
        QTest.qWait(500)
        self.assertEqual(browser.settings_modal.pos(), QPoint(0, 0))
        browser.hide_settings_modal()
        self.assertFalse(browser.settings_modal.isHidden())
        QTest.qWait(400)
        self.assertTrue(browser.settings_modal.isHidden())
        self.dismiss()


if __name__ == "__main__":
    unittest.main()
