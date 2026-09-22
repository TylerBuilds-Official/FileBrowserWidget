import os
import shutil
import time
import unittest
from pathlib import Path
from time import monotonic
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, Qt
from PyQt6.QtGui import QKeyEvent, QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon

from src.ui.file_browser import FileBrowser
from src.ui.win_tray_app import WinTrayApp
from src.utils import shell_actions


class NativePolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".polish-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        for name in ("alpha.txt", "beta.txt", "bravo.txt", "charlie.txt"):
            (self.root / name).write_text("x", encoding="utf-8")
        self.folder = self.root / "Docs"
        (self.folder / "Inner").mkdir(parents=True)
        self.settings_path = self.root.parent / f".polish-settings-{uuid4().hex}.ini"
        self.settings = QSettings(str(self.settings_path), QSettings.Format.IniFormat)
        self.browser = self.make_browser()

    def make_browser(self):
        browser = FileBrowser(settings=self.settings)
        browser.resize(400, 640)
        browser.move(100, 100)
        browser.desktop_folder = self.root
        self.addCleanup(browser.deleteLater)
        self.addCleanup(browser.hide)
        browser.create_list_items(self.root)
        return browser

    def remove_fixture(self):
        self.settings.sync()
        self.settings_path.unlink(missing_ok=True)
        root = self.root.resolve()
        assert root.parent == Path(__file__).resolve().parent
        assert root.name.startswith(".polish-test-")
        shutil.rmtree(root)

    def row_for(self, path):
        for i in range(self.browser.file_list_layout.count()):
            row = self.browser.file_list_layout.itemAt(i).widget()
            if row.path == path:
                return row
        self.fail(f"No row for {path}")

    def show(self):
        self.browser.show()
        self.app.processEvents()

    def wait_for(self, predicate, timeout=2000):
        deadline = time.monotonic() + timeout / 1000
        while not predicate():
            if time.monotonic() > deadline:
                self.fail("Timed out waiting")
            QTest.qWait(10)

    def tray_app(self):
        tray = Mock()
        tray.geometry.return_value = QRect(1800, 1040, 24, 24)
        return SimpleNamespace(file_browser=self.browser, tray_icon=tray, show_browser=Mock(),
                               global_hotkey=Mock(), focusWidget=lambda: None)

    def focused_name(self):
        return self.browser.focusWidget().path.name

    def test_tray_click_opens_closes_and_ignores_the_press_that_just_closed(self):
        app = self.tray_app()
        trigger = QSystemTrayIcon.ActivationReason.Trigger
        WinTrayApp.tray_click_router(app, trigger)
        app.show_browser.assert_called_once()
        app.show_browser.reset_mock()
        self.show()
        WinTrayApp.tray_click_router(app, trigger)
        self.assertFalse(self.browser.isVisible())
        app.show_browser.assert_not_called()
        # The press on the tray icon closes the popup; the click it turns into must not reopen it.
        self.browser.record_dismissal(QPoint(1810, 1050))
        WinTrayApp.tray_click_router(app, trigger)
        app.show_browser.assert_not_called()
        self.browser.record_dismissal(QPoint(500, 500))
        WinTrayApp.tray_click_router(app, trigger)
        app.show_browser.assert_called_once()
        app.show_browser.reset_mock()
        self.browser._dismissed = (monotonic() - 1, QPoint(1810, 1050))
        WinTrayApp.tray_click_router(app, trigger)
        app.show_browser.assert_called_once()
        WinTrayApp.tray_click_router(app, QSystemTrayIcon.ActivationReason.Context)
        app.show_browser.assert_called_once()

    def test_hotkey_toggles_the_panel(self):
        app = self.tray_app()
        WinTrayApp.hotkey_activated(app)
        app.show_browser.assert_called_once()
        self.show()
        WinTrayApp.hotkey_activated(app)
        self.assertFalse(self.browser.isVisible())
        app.show_browser.assert_called_once()

    def test_a_press_outside_the_panel_closes_it_and_is_remembered(self):
        self.show()
        outside = self.browser.mapToGlobal(QPoint(-30, 10))
        press = QMouseEvent(QEvent.Type.MouseButtonPress, QPointF(-30, 10), QPointF(outside),
                            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        self.app.sendEvent(self.browser, press)
        self.assertFalse(self.browser.isVisible())
        self.assertTrue(self.browser.dismissed_by_press_in(QRect(outside.x() - 5, outside.y() - 5, 10, 10)))
        self.assertFalse(self.browser.dismissed_by_press_in(QRect(0, 0, 10, 10)))

    def test_typing_jumps_to_names_and_the_same_letter_steps_on(self):
        self.show()
        handler = self.browser.keyboard_handler
        rows = handler.rows()
        self.assertEqual([row.path.name for row in rows], ["alpha.txt", "beta.txt", "bravo.txt", "charlie.txt", "Docs"])
        rows[0].setFocus()
        QTest.keyClick(rows[0], "b")
        self.assertEqual(self.focused_name(), "beta.txt")
        QTest.keyClick(self.browser.focusWidget(), "r")  # Quickly: the prefix grows to "br".
        self.assertEqual(self.focused_name(), "bravo.txt")
        handler.typed_at -= 2  # A pause starts over.
        QTest.keyClick(self.browser.focusWidget(), "b")
        self.assertEqual(self.focused_name(), "beta.txt")  # The next b-name after bravo, wrapping.
        QTest.keyClick(self.browser.focusWidget(), "b")  # The same letter again steps on.
        self.assertEqual(self.focused_name(), "bravo.txt")
        handler.typed_at -= 2
        QTest.keyClick(self.browser.focusWidget(), "D")
        self.assertEqual(self.focused_name(), "Docs")
        handler.typed_at -= 2
        QTest.keyClick(self.browser.focusWidget(), "z")
        self.assertEqual(self.focused_name(), "Docs")  # Nothing starts with z; focus stays.

    def test_only_plain_printable_keys_count_as_typing(self):
        handler = self.browser.keyboard_handler

        def key(text, modifiers=Qt.KeyboardModifier.NoModifier):
            return QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, modifiers, text)

        self.assertTrue(handler.is_typing(key("a")))
        self.assertTrue(handler.is_typing(key("A", Qt.KeyboardModifier.ShiftModifier)))
        self.assertFalse(handler.is_typing(key("a", Qt.KeyboardModifier.ControlModifier)))
        self.assertFalse(handler.is_typing(key("a", Qt.KeyboardModifier.AltModifier)))
        self.assertFalse(handler.is_typing(key(" ")))
        self.assertFalse(handler.is_typing(key("")))
        self.assertFalse(handler.is_typing(key("\x08")))
        self.show()
        self.browser.show_settings_modal()
        self.assertFalse(handler.is_typing(key("a")))

    def test_right_fans_out_a_focused_folder_and_left_hands_the_keyboard_back(self):
        self.show()
        self.assertEqual(self.browser.settings_modal.hover_behavior, "none")
        row = self.row_for(self.folder)
        row.setFocus()
        QTest.keyClick(row, Qt.Key.Key_Right)
        cascade = self.browser.cascade
        self.assertTrue(cascade.is_open())
        self.wait_for(lambda: cascade._menu.isVisible() and cascade._menu.filled)
        menu = cascade._menu
        self.assertEqual([action.text() for action in menu.actions()], ["Inner"])
        self.assertEqual(menu.activeAction().text(), "Inner")
        QTest.keyClick(menu, Qt.Key.Key_Left)
        self.assertFalse(cascade.is_open())
        alpha = self.row_for(self.root / "alpha.txt")
        alpha.setFocus()
        QTest.keyClick(alpha, Qt.Key.Key_Right)  # A file has nothing to fan out.
        self.assertFalse(cascade.is_open())

    def test_alt_enter_opens_properties_for_the_focused_row(self):
        self.show()
        row = self.row_for(self.root / "alpha.txt")
        row.setFocus()
        with patch.object(shell_actions, "show_properties", return_value="") as properties:
            QTest.keyClick(row, Qt.Key.Key_Return, Qt.KeyboardModifier.AltModifier)
        properties.assert_called_once_with(self.root / "alpha.txt")

    def test_middle_click_shows_the_item_in_explorer(self):
        opened, located = [], []
        self.browser.program_clicked.connect(opened.append)
        self.browser.file_location_clicked.connect(located.append)
        QTest.mouseClick(self.row_for(self.folder), Qt.MouseButton.MiddleButton, pos=QPoint(8, 8))
        QTest.mouseClick(self.row_for(self.root / "alpha.txt"), Qt.MouseButton.MiddleButton, pos=QPoint(8, 8))
        self.assertEqual(opened, [str(self.folder)])
        self.assertEqual(located, [str(self.root / "alpha.txt")])
        self.assertEqual(self.browser.current_folder, self.root)

    def test_reopen_where_i_left_off_keeps_the_folder_and_history_and_survives_a_restart(self):
        modal = self.browser.settings_modal
        self.browser.navigate_to(self.folder)
        self.browser.reset_location()
        self.assertEqual(self.browser.current_folder, self.root)
        modal.reopen_check.setChecked(True)
        self.browser.navigate_to(self.folder)
        self.browser.navigate_to(self.folder / "Inner")
        self.browser.reset_location()
        self.assertEqual(self.browser.current_folder, self.folder / "Inner")
        self.assertEqual(len(self.browser.folder_history), 2)
        self.settings.sync()
        self.assertEqual(self.settings.value("files/last_folder"), str(self.folder / "Inner"))
        restarted = FileBrowser(settings=QSettings(str(self.settings_path), QSettings.Format.IniFormat))
        self.addCleanup(restarted.deleteLater)
        self.assertEqual(restarted.current_folder, self.folder / "Inner")
        self.assertEqual(restarted.title_label._name, "Inner")

    def test_the_debug_entry_is_gone_from_the_tray_menu(self):
        self.assertFalse(hasattr(WinTrayApp, "test_func_connection"))


if __name__ == "__main__":
    unittest.main()
