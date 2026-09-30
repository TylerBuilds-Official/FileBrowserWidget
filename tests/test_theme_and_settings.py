import os
from uuid import uuid4
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, Qt, QSettings, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.ui import motion
from src.ui.file_browser import FileBrowser
from src.ui.settings.settings_modal import SettingsModal
from src.utils.locations import Drive
from src.utils.system_theme import SystemTheme, accent_colors, contrast


class FakeStyleHints(QObject):
    colorSchemeChanged = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.system = Qt.ColorScheme.Light
        self.override = Qt.ColorScheme.Unknown

    def colorScheme(self):
        return self.system if self.override == Qt.ColorScheme.Unknown else self.override

    def setColorScheme(self, scheme):
        self.override = scheme
        self.colorSchemeChanged.emit(self.colorScheme())

    def change_system(self, scheme):
        self.system = scheme
        self.colorSchemeChanged.emit(self.colorScheme())


class ThemeAndSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.settings_path = Path(__file__).resolve().parent / f".theme-test-{uuid4().hex}.ini"
        self.settings = QSettings(str(self.settings_path), QSettings.Format.IniFormat)
        self.addCleanup(self._cleanup_settings)

    def _cleanup_settings(self):
        self.settings.sync()
        self.settings_path.unlink(missing_ok=True)

    def test_system_changes_and_explicit_override(self):
        hints = FakeStyleHints()
        with patch.object(self.app, "styleHints", return_value=hints):
            helper = SystemTheme(self.app, self.settings)
            self.assertEqual(helper.effective_theme, "light")
            hints.change_system(Qt.ColorScheme.Dark)
            self.app.processEvents()
            self.assertEqual(helper.effective_theme, "dark")
            self.assertEqual(self.app.palette().color(QPalette.ColorRole.Window).name(), "#202020")
            helper.set_mode("light")
            hints.change_system(Qt.ColorScheme.Dark)
            self.app.processEvents()
            self.assertEqual(helper.effective_theme, "light")
            helper.set_mode("system")
            self.assertEqual(helper.effective_theme, "dark")
            hints.change_system(Qt.ColorScheme.Light)
            self.app.processEvents()
            self.assertEqual(helper.effective_theme, "light")
            helper.deleteLater()

    def test_theme_mode_persists_and_invalid_saved_value_falls_back(self):
        hints = FakeStyleHints()
        with patch.object(self.app, "styleHints", return_value=hints):
            helper = SystemTheme(self.app, self.settings)
            helper.set_mode("dark")
            restored = SystemTheme(self.app, self.settings)
            self.assertEqual(restored.mode, "dark")
            with self.assertRaises(ValueError):
                helper.set_mode("sepia")
            self.settings.setValue("appearance/theme", "bad")
            fallback = SystemTheme(self.app, self.settings)
            self.assertEqual(fallback.mode, "system")
            for obj in (helper, restored, fallback):
                obj.deleteLater()

    def test_accent_uses_a_shade_the_surface_can_carry(self):
        # A dark accent, as Windows shades it: lightest first, the user's own colour in the middle.
        shades = [QColor(value) for value in ("#036ad2", "#0358af", "#024b96", "#023f7d",
                                              "#013264", "#01254b", "#001428")]
        with patch("src.utils.system_theme.accent_shades", return_value=shades):
            dark, light = accent_colors("dark"), accent_colors("light")
        self.assertEqual(dark["accent_fill"], "#0358af")
        self.assertEqual(light["accent_fill"], "#013264")
        # #023f7d is the user's own accent but it disappears on #202020, so dark steps lighter.
        self.assertEqual(dark["accent"], "#036ad2")
        self.assertEqual(light["accent"], "#023f7d")
        self.assertEqual(dark["accent_text"], "#ffffff")
        self.assertGreater(contrast(QColor(dark["accent"]), QColor("#202020")), 3)

    def test_all_preferences_restore(self):
        modal = SettingsModal(settings=self.settings)
        modal.theme_combo.setCurrentIndex(modal.theme_combo.findData("dark"))
        modal.docking_combo.setCurrentIndex(modal.docking_combo.findData("top_left"))
        modal.extensions_check.setChecked(True)
        modal.sort_combo.setCurrentIndex(modal.sort_combo.findData("type"))
        modal.hover_combo.setCurrentIndex(modal.hover_combo.findData("cascade"))
        modal.start_combo.setCurrentIndex(modal.start_combo.findData("last"))
        self.settings.sync()
        fresh_settings = QSettings(self.settings.fileName(), QSettings.Format.IniFormat)
        restored = SettingsModal(settings=fresh_settings)
        self.assertEqual(restored.theme_mode, "dark")
        self.assertEqual(restored.docking_position, "top_left")
        self.assertTrue(restored.show_extensions)
        self.assertEqual(restored.default_sort, "type")
        self.assertEqual(restored.hover_behavior, "cascade")
        self.assertTrue(restored.reopen_last)
        modal.deleteLater()
        restored.deleteLater()

    def test_start_in_offers_the_users_folders_the_drives_that_stay_and_where_i_left_off(self):
        drives = [Drive(Path("C:\\"), "fixed"), Drive(Path("E:\\"), "removable"), Drive(Path("M:\\"), "network")]
        with patch("src.utils.locations.list_drives", return_value=drives):
            modal = SettingsModal(settings=self.settings)
        self.addCleanup(modal.deleteLater)
        combo = modal.start_combo
        self.assertEqual([combo.itemData(i) for i in range(combo.count())],
                         ["desktop", "downloads", "documents", "C:\\", "M:\\", "last"])
        self.assertEqual(combo.itemText(3), "C: drive")
        self.assertEqual(modal.start_in, "desktop")  # Nothing changes unless someone chooses.

    def test_reopen_where_i_left_off_carries_over_as_where_the_panel_starts(self):
        self.settings.setValue("files/reopen_last", True)
        modal = SettingsModal(settings=self.settings)
        self.addCleanup(modal.deleteLater)
        self.assertEqual(modal.start_in, "last")
        self.assertTrue(modal.reopen_last)

    def test_a_start_drive_that_is_away_today_stays_the_choice(self):
        self.settings.setValue("files/start_in", "Q:\\")
        with patch("src.utils.locations.list_drives", return_value=[]):
            modal = SettingsModal(settings=self.settings)
        self.addCleanup(modal.deleteLater)
        self.assertEqual(modal.start_in, "Q:\\")
        self.assertEqual(modal.start_combo.currentText(), "Q: drive")
        self.assertEqual(modal.start_combo.itemData(modal.start_combo.count() - 1), "last")

    def test_start_in_can_be_a_folder_of_your_own(self):
        # Choose… opens the folder dialog. The panel is a popup, and a dialog over a popup closes it
        # and goes with it, so the panel steps aside for the dialog and comes back with Settings open.
        folder = Path(__file__).resolve().parent
        browser = FileBrowser(settings=self.settings)
        browser.resize(400, 640)
        browser.show()
        self.addCleanup(browser.deleteLater)
        self.addCleanup(browser.hide)
        self.app.processEvents()
        browser.show_settings_modal()
        modal = browser.settings_modal
        seen = []

        def dialog(parent, title, start):
            seen.append((parent, browser.isVisible(), modal.isVisible(), start))
            return str(folder)

        with patch("src.ui.settings.settings_modal.QFileDialog.getExistingDirectory", dialog):
            modal.start_browse.click()
        self.assertEqual(seen, [(None, False, False, str(Path.home()))])
        self.assertTrue(browser.isVisible())
        self.assertTrue(modal.isVisible())
        self.assertEqual(modal.start_in, str(folder))
        self.assertEqual(modal.start_combo.currentText(), folder.name)
        self.assertEqual(modal.start_combo.itemData(modal.start_combo.count() - 1), "last")
        self.assertEqual(browser.start_folder(), folder)
        self.settings.sync()
        restored = SettingsModal(settings=QSettings(self.settings.fileName(), QSettings.Format.IniFormat))
        self.addCleanup(restored.deleteLater)
        self.assertEqual(restored.start_in, str(folder))
        self.assertEqual(restored.start_combo.currentText(), folder.name)
        # Choosing again takes the place of the last folder chosen; cancelling changes nothing.
        with patch("src.ui.settings.settings_modal.QFileDialog.getExistingDirectory", return_value=str(folder.parent)):
            modal.start_browse.click()
        self.assertEqual(modal.start_in, str(folder.parent))
        values = [modal.start_combo.itemData(i) for i in range(modal.start_combo.count())]
        self.assertNotIn(str(folder), values)
        with patch("src.ui.settings.settings_modal.QFileDialog.getExistingDirectory", return_value=""):
            modal.start_browse.click()
        self.assertEqual(modal.start_in, str(folder.parent))
        self.assertTrue(browser.isVisible())
        # A named folder or a drive chosen this way is its own entry, not a new one.
        with patch("src.utils.locations.user_folders", return_value=[("Downloads", folder), ("Documents", folder.parent)]):
            modal.set_start(folder)
            self.assertEqual(modal.start_in, "downloads")
        modal.set_start(browser.desktop_folder)
        self.assertEqual(modal.start_in, "desktop")
        drive = Path(folder.drive + "\\")
        with patch("src.utils.locations.list_drives", return_value=[Drive(drive, "fixed")]):
            fresh = SettingsModal(settings=self.settings)
        self.addCleanup(fresh.deleteLater)
        fresh.set_start(drive)
        self.assertEqual(fresh.start_in, str(drive))
        self.assertEqual(fresh.start_combo.currentText(), f"{folder.drive} drive")

    def test_slide_over_covers_browser_resizes_and_returns_focus(self):
        browser = FileBrowser()
        browser.resize(400, 640)
        browser.show()
        self.addCleanup(browser.deleteLater)
        self.addCleanup(browser.hide)
        self.app.processEvents()
        browser.show_settings_modal()
        QTest.qWait(240)
        modal = browser.settings_modal
        self.assertEqual(modal.geometry(), browser.rect())
        self.assertFalse(browser.content.isEnabled())
        browser.resize(480, 720)
        self.app.processEvents()
        self.assertEqual(modal.geometry(), browser.rect())
        QTest.keyClick(modal.close_button, Qt.Key.Key_Escape)
        QTest.qWait(240)
        self.assertTrue(modal.isHidden())
        self.assertTrue(browser.content.isEnabled())
        self.assertEqual(self.app.focusWidget(), browser.settings_button)
        browser.show_settings_modal()
        browser.hide()
        self.assertTrue(modal.isHidden())
        self.assertTrue(browser.content.isEnabled())

    def test_back_button_uses_animation_and_can_reopen(self):
        motion.override = True
        self.addCleanup(setattr, motion, "override", None)
        browser = FileBrowser()
        browser.resize(400, 640)
        browser.show()
        self.addCleanup(browser.deleteLater)
        self.addCleanup(browser.hide)
        browser.show_settings_modal()
        self.assertEqual(browser.settings_modal._animation.duration(), motion.SLOW)
        QTest.qWait(400)
        browser.settings_modal.close_button.click()
        self.assertFalse(browser.settings_modal.isHidden())
        self.assertEqual(browser.settings_modal._animation.duration(), motion.NORMAL)
        QTest.qWait(400)
        self.assertTrue(browser.settings_modal.isHidden())
        browser.show_settings_modal()
        QTest.qWait(400)
        self.assertEqual(browser.settings_modal.geometry(), browser.rect())
        browser.hide()
        QTest.qWait(300)  # The panel's ghost must not outlive the test.


if __name__ == "__main__":
    unittest.main()
