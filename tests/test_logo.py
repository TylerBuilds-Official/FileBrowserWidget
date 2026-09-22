import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QFile, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from src.ui.settings.settings_modal import SettingsModal
from src.utils.assets import asset
from src.version import VERSION


class LogoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_app_icon_is_square_at_every_size_windows_draws(self):
        icon = QIcon(asset("logo/fb_icon.ico"))
        sizes = {(size.width(), size.height()) for size in icon.availableSizes()}
        for side in (16, 20, 24, 32, 48, 64, 256):
            self.assertIn((side, side), sizes)
        self.assertFalse(icon.pixmap(QSize(16, 16)).isNull())

    def test_compiled_resources_import_pyqt_not_pyside(self):
        # The freeze excludes PySide6, so a PySide6 import here would kill the packaged app at launch.
        source = (Path(__file__).resolve().parents[1] / "src" / "assets" / "resources_rc.py").read_text(encoding="utf-8")
        self.assertIn("from PyQt6 import QtCore", source)
        self.assertNotIn("from PySide6", source)

    def test_bundle_carries_the_logo_and_not_the_old_icon(self):
        self.assertTrue(QFile(":/assets/logo/fb_icon.ico").exists())
        self.assertTrue(QFile(":/assets/logo/fb_icon_header.png").exists())
        self.assertFalse(QFile(":/assets/filter.ico").exists())

    def test_about_card_shows_the_mark_and_the_version(self):
        modal = SettingsModal()
        self.addCleanup(modal.deleteLater)
        pixmap = modal.about_icon.pixmap()
        self.assertFalse(pixmap.isNull())
        height = pixmap.height() / pixmap.devicePixelRatio()
        width = pixmap.width() / pixmap.devicePixelRatio()
        self.assertEqual(height, modal.ABOUT_ICON)
        self.assertGreater(width, height)
        self.assertEqual(modal.about_version.text(), f"Version {VERSION}")
        self.assertFalse(hasattr(modal, "logo"))

    def test_settings_rail_sits_where_the_list_rail_does(self):
        modal = SettingsModal()
        self.addCleanup(modal.deleteLater)
        self.assertEqual(modal.layout.contentsMargins().right(), 12)
        self.assertEqual(modal.layout.contentsMargins().left(), 20)


if __name__ == "__main__":
    unittest.main()
