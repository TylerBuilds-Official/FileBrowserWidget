import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtWidgets import QApplication

from src.ui.settings.settings_modal import SettingsModal
from src.ui.ui_functions import UIFunctions
from src.utils.system_info import SystemInfo


class DockingPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.screen = Mock()
        # A monitor left of the primary, with a reserved strip at its top.
        self.screen.availableGeometry.return_value = QRect(-1920, 40, 1920, 1040)
        self.app = Mock()
        self.app.screenAt.return_value = self.screen
        self.app.tray_icon.geometry.return_value = QRect(-100, 1080, 20, 20)
        self.app.file_browser.width.return_value = 400
        self.app.file_browser.height.return_value = 600
        self.info = SystemInfo(self.app)

    def test_all_positions_on_offset_monitor(self):
        expected = {
            "top_left": QPoint(-1910, 45),
            "top_center": QPoint(-1160, 45),
            "top_right": QPoint(-410, 45),
            "bottom_left": QPoint(-1910, 475),
            "bottom_center": QPoint(-1160, 475),
            "bottom_right": QPoint(-410, 475),
        }
        for position, point in expected.items():
            with self.subTest(position=position):
                self.assertEqual(self.info.get_popup_position(position), point)
        self.app.primaryScreen.assert_not_called()

    def test_default_and_unknown_position_use_bottom_right(self):
        self.assertEqual(self.info.get_popup_position(), QPoint(-410, 475))
        self.assertEqual(self.info.get_popup_position("unknown"), QPoint(-410, 475))
        self.assertEqual(self.info.get_bottom_left_popup_pos(), QPoint(-1910, 475))

    def test_missing_tray_screen_falls_back_to_primary(self):
        self.app.screenAt.return_value = None
        self.app.primaryScreen.return_value = self.screen
        self.assertEqual(self.info.get_popup_position(), QPoint(-410, 475))
        self.app.primaryScreen.assert_called_once()

    def test_tight_space_reduces_margins(self):
        self.screen.availableGeometry.return_value = QRect(100, 50, 410, 604)
        self.assertEqual(self.info.get_popup_position(), QPoint(105, 52))
        self.screen.availableGeometry.return_value = QRect(100, 50, 300, 400)
        self.assertEqual(self.info.get_popup_position(), QPoint(100, 50))

    def test_dropdown_notifies_and_passes_selection_to_positioning(self):
        modal = SettingsModal()
        self.addCleanup(modal.deleteLater)
        self.assertEqual(modal.docking_position, "bottom_right")
        self.assertEqual(modal.docking_combo.count(), 6)
        changes = []
        refreshes = []
        modal.docking_position_changed.connect(lambda: changes.append(modal.docking_position))
        modal.refresh_files.connect(lambda: refreshes.append(True))
        ui = SimpleNamespace(file_browser=SimpleNamespace(settings_modal=modal))
        functions = UIFunctions(ui)
        functions.system_info_helper = self.info
        for index in range(modal.docking_combo.count()):
            modal.docking_combo.setCurrentIndex(index)
            self.assertEqual(functions.get_popup_pos(), self.info.get_popup_position(modal.docking_position))
        self.assertEqual(len(changes), 6)
        self.assertEqual(refreshes, [])


if __name__ == "__main__":
    unittest.main()
