import os
from uuid import uuid4
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QObject, Qt, QSettings, pyqtSignal
from PyQt6.QtGui import QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.ui.file_browser import FileBrowser
from src.ui.settings.settings_modal import SettingsModal
from src.utils.system_theme import SystemTheme


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

    def test_all_preferences_restore(self):
        modal = SettingsModal(settings=self.settings)
        modal.theme_combo.setCurrentIndex(modal.theme_combo.findData("dark"))
        modal.docking_combo.setCurrentIndex(modal.docking_combo.findData("top_left"))
        modal.extensions_check.setChecked(True)
        self.settings.sync()
        fresh_settings = QSettings(self.settings.fileName(), QSettings.Format.IniFormat)
        restored = SettingsModal(settings=fresh_settings)
        self.assertEqual(restored.theme_mode, "dark")
        self.assertEqual(restored.docking_position, "top_left")
        self.assertTrue(restored.show_extensions)
        modal.deleteLater()
        restored.deleteLater()

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
        browser = FileBrowser()
        browser.resize(400, 640)
        browser.show()
        self.addCleanup(browser.deleteLater)
        self.addCleanup(browser.hide)
        browser.show_settings_modal()
        QTest.qWait(220)
        browser.settings_modal.close_button.click()
        self.assertFalse(browser.settings_modal.isHidden())
        QTest.qWait(220)
        self.assertTrue(browser.settings_modal.isHidden())
        browser.show_settings_modal()
        QTest.qWait(220)
        self.assertEqual(browser.settings_modal.geometry(), browser.rect())


if __name__ == "__main__":
    unittest.main()
