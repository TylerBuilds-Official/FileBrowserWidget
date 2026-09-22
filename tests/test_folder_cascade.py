import ctypes
import os
import shutil
import threading
import time
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF, QSettings, Qt
from PyQt6.QtGui import QHelpEvent, QWheelEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QStyle, QToolTip

from src.ui.custom_widgets.cascade_menu import CascadeMenu
from src.ui.file_browser import FileBrowser
from src.ui.settings.settings_modal import SettingsModal
from src.utils.file_icons import FileIcons
from src.utils.file_listing import list_folder


class FolderListingTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".cascade-listing-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(shutil.rmtree, self.root)

    def test_folders_come_first_then_files_by_name_without_hidden_items(self):
        (self.root / "zeta").mkdir()
        (self.root / "Alpha").mkdir()
        (self.root / "b.txt").write_text("b", encoding="utf-8")
        (self.root / "A.txt").write_text("a", encoding="utf-8")
        hidden = self.root / "desktop.ini"
        hidden.write_text("[.ShellClassInfo]", encoding="utf-8")
        if os.name == "nt":
            ctypes.windll.kernel32.SetFileAttributesW(str(hidden), 0x2)
        names = [entry.path.name for entry in list_folder(self.root)]
        expected = ["Alpha", "zeta", "A.txt", "b.txt"]
        if os.name != "nt":
            expected.append("desktop.ini")
        self.assertEqual(names, expected)
        self.assertEqual(list_folder(self.root)[0].kinds, {"folders"})
        self.assertTrue(list_folder(self.root)[2].stamp)

    def test_unreadable_folder_raises_for_the_menu_to_report(self):
        with self.assertRaises(OSError):
            list_folder(self.root / "missing")


class FolderCascadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".cascade-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        self.folder = self.root / "Projects"
        self.nested = self.folder / "Archive"
        self.nested.mkdir(parents=True)
        (self.folder / "Notes & ideas.txt").write_text("hello", encoding="utf-8")
        (self.folder / "readme.md").write_text("hi", encoding="utf-8")
        self.other = self.root / "Photos"
        self.other.mkdir()
        (self.other / "holiday.jpg").write_bytes(b"")
        self.file = self.root / "todo.txt"
        self.file.write_text("todo", encoding="utf-8")

        # Keep the settings file out of the browsed folder: the browser watches it and refreshes.
        self.settings_path = self.root.parent / f".cascade-settings-{uuid4().hex}.ini"
        self.settings = QSettings(str(self.settings_path), QSettings.Format.IniFormat)
        self.settings.setValue("files/hover_behavior", "cascade")
        self.browser = FileBrowser(settings=self.settings)
        self.browser.resize(400, 640)
        self.browser.move(100, 100)
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.create_list_items(self.root)
        self.browser.show()
        self.app.processEvents()
        self.cascade = self.browser.cascade
        self.cascade.timer.setInterval(30)
        self.cascade.prefetch_timer.setInterval(10)

    def remove_fixture(self):
        self.settings.sync()
        self.settings_path.unlink(missing_ok=True)
        root = self.root.resolve()
        assert root.parent == Path(__file__).resolve().parent
        assert root.name.startswith(".cascade-test-")
        shutil.rmtree(root)

    def row_for(self, path):
        for i in range(self.browser.file_list_layout.count()):
            row = self.browser.file_list_layout.itemAt(i).widget()
            if row.toolTip() == str(path):
                return row
        self.fail(f"No row for {path}")

    def hover(self, row):
        # A test move is a cursor reposition; parking twice in one spot makes no event.
        QTest.mouseMove(self.browser.status_label, QPoint(4, 4))
        QTest.mouseMove(row, QPoint(8, 8))
        self.app.processEvents()

    def settle(self):
        QTest.qWait(120)

    def wait_for(self, predicate, timeout=2000):
        deadline = time.monotonic() + timeout / 1000
        while not predicate():
            if time.monotonic() > deadline:
                self.fail("Timed out waiting for the cascade")
            QTest.qWait(10)

    def open_menu(self):
        self.assertTrue(self.cascade.is_open())
        self.wait_for(lambda: self.cascade._menu is not None and self.cascade._menu.isVisible()
                      and self.cascade._menu.filled)
        return self.cascade._menu

    def open_submenu(self, menu, index):
        action = menu.actions()[index]
        QTest.mouseMove(menu, menu.actionGeometry(action).center())
        self.wait_for(lambda: action.menu().isVisible() and action.menu().filled)
        return action.menu()

    def test_every_level_fans_out_away_from_the_panels_screen_edge(self):
        # Short names and a narrow panel keep four levels inside the 800px offscreen screen.
        chain = self.root / "A"
        (chain / "B" / "C").mkdir(parents=True)
        (chain / "B" / "C" / "f.txt").write_text("f", encoding="utf-8")
        self.browser.resize(300, 640)
        self.browser.create_list_items()
        screen = self.browser.screen().availableGeometry()
        for x, leftward in ((screen.right() - 300, True), (screen.left(), False)):
            self.cascade.close()
            self.browser.move(x, 0)
            self.app.processEvents()
            self.hover(self.row_for(chain))
            self.settle()
            menu = self.open_menu()
            second = self.open_submenu(menu, 0)
            third = self.open_submenu(second, 0)
            self.assertEqual([action.text() for action in third.actions()], ["f"])
            levels = [self.browser.frameGeometry(), menu.geometry(), second.geometry(), third.geometry()]
            # Each level sits edge to edge with the one before it, neither overlapping nor apart.
            for outer, inner in zip(levels, levels[1:]):
                if leftward:
                    self.assertEqual(inner.right(), outer.left() - 1, (x, outer, inner))
                else:
                    self.assertEqual(inner.left(), outer.right() + 1, (x, outer, inner))

    def test_folder_rows_skip_their_tooltip_while_the_cascade_is_on(self):
        def tip(row):
            QToolTip.hideText()
            QTest.qWait(400)  # Hiding starts a 300ms fade; the tip is a window until it ends.
            event = QHelpEvent(QEvent.Type.ToolTip, QPoint(8, 8), row.mapToGlobal(QPoint(8, 8)))
            self.app.sendEvent(row, event)
            return QToolTip.text() if QToolTip.isVisible() else ""

        self.assertEqual(tip(self.row_for(self.file)), str(self.file))
        self.assertEqual(tip(self.row_for(self.folder)), "")
        self.assertEqual(self.row_for(self.folder).toolTip(), str(self.folder))
        modal = self.browser.settings_modal
        modal.hover_combo.setCurrentIndex(modal.hover_combo.findData("none"))
        self.assertEqual(tip(self.row_for(self.folder)), str(self.folder))
        QToolTip.hideText()
        QTest.qWait(400)

    def test_a_long_folder_scrolls_in_one_column(self):
        for index in range(120):
            (self.other / f"photo-{index:04d}.jpg").write_bytes(b"")
        self.hover(self.row_for(self.other))
        self.settle()
        menu = self.open_menu()
        screen = self.browser.screen().availableGeometry()
        self.assertLessEqual(menu.height(), screen.height())
        self.assertLess(menu.width(), 300)

    def test_hover_fans_the_folder_out_with_folders_first_and_names_escaped(self):
        row = self.row_for(self.folder)
        self.hover(row)
        self.assertFalse(self.cascade.is_open())
        self.settle()
        menu = self.open_menu()
        self.assertTrue(menu.isVisible())
        self.assertEqual([action.text() for action in menu.actions()],
                         ["Archive", "Notes && ideas", "readme"])
        self.assertIsInstance(menu.actions()[0].menu(), CascadeMenu)
        self.assertIsNone(menu.actions()[1].menu())
        self.assertEqual(menu.actions()[1].data(), str(self.folder / "Notes & ideas.txt"))
        self.assertEqual(row.property("cascaded"), "true")
        self.assertFalse(menu.actions()[0].icon().isNull())

    def test_extensions_setting_names_the_menu_items(self):
        self.browser.settings_modal.extensions_check.setChecked(True)
        self.hover(self.row_for(self.folder))
        self.settle()
        self.assertEqual([action.text() for action in self.open_menu().actions()],
                         ["Archive", "Notes && ideas.txt", "readme.md"])

    def test_nothing_opens_when_the_setting_is_off_or_the_row_is_a_file(self):
        self.hover(self.row_for(self.file))
        self.settle()
        self.assertFalse(self.cascade.is_open())
        self.browser.settings_modal.hover_combo.setCurrentIndex(
            self.browser.settings_modal.hover_combo.findData("none"))
        self.hover(self.row_for(self.folder))
        self.settle()
        self.assertFalse(self.cascade.is_open())
        self.assertEqual(self.settings.value("files/hover_behavior"), "none")

    def test_leaving_or_pressing_before_the_delay_cancels(self):
        row = self.row_for(self.folder)
        self.hover(row)
        QTest.mouseMove(self.browser.status_label, QPoint(4, 4))
        self.settle()
        self.assertFalse(self.cascade.is_open())
        self.hover(row)
        self.assertTrue(self.cascade.timer.isActive())
        QTest.mousePress(row, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
        self.assertFalse(self.cascade.timer.isActive())
        QTest.mouseRelease(row, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
        self.assertEqual(self.browser.current_folder, self.folder)
        self.assertFalse(self.cascade.is_open())

    def test_subfolders_list_themselves_when_shown_and_files_open_on_click(self):
        opened = []
        self.browser.program_clicked.connect(opened.append)
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        submenu = menu.actions()[0].menu()
        self.assertFalse(submenu.filled)
        submenu.aboutToShow.emit()
        self.wait_for(lambda: submenu.filled)
        self.assertEqual([action.text() for action in submenu.actions()], ["Empty folder"])
        self.assertFalse(submenu.actions()[0].isEnabled())
        menu.actions()[2].trigger()
        self.assertEqual(opened, [str(self.folder / "readme.md")])
        self.assertFalse(self.cascade.is_open())
        self.assertEqual(self.row_for(self.folder).property("cascaded"), "false")

    def test_clicking_a_folder_item_drills_into_it(self):
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        target = menu.actionGeometry(menu.actions()[0]).center()
        QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=target)
        self.assertEqual(self.browser.current_folder, self.nested)
        self.assertFalse(self.cascade.is_open())
        self.assertEqual(self.browser.folder_history, [(self.root, 0)])

    def test_right_click_asks_for_the_items_own_menu(self):
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        target = menu.actionGeometry(menu.actions()[1]).center()
        with patch.object(self.browser, "show_file_menu") as file_menu:
            QTest.mouseClick(menu, Qt.MouseButton.RightButton, pos=target)
        file_menu.assert_called_once_with(self.folder / "Notes & ideas.txt", menu.mapToGlobal(target))
        self.assertFalse(self.cascade.is_open())

    def test_resting_on_another_row_moves_or_closes_the_cascade(self):
        self.hover(self.row_for(self.folder))
        self.settle()
        first = self.open_menu()
        other = self.row_for(self.other)
        self.cascade.pointer_moved(other.mapToGlobal(QPoint(8, 8)))
        self.assertTrue(self.cascade.is_open())
        self.settle()
        second = self.open_menu()
        self.assertIsNot(first, second)
        self.assertEqual([action.text() for action in second.actions()], ["holiday"])
        self.assertEqual(other.property("cascaded"), "true")
        self.assertEqual(self.row_for(self.folder).property("cascaded"), "false")
        self.cascade.pointer_moved(self.row_for(self.file).mapToGlobal(QPoint(8, 8)))
        self.settle()
        self.assertFalse(self.cascade.is_open())

    def test_a_click_on_another_row_passes_through_the_open_cascade(self):
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        other = self.row_for(self.other)
        target = menu.mapFromGlobal(other.mapToGlobal(QPoint(8, 8)))
        QTest.mousePress(menu, Qt.MouseButton.LeftButton, pos=target)
        self.assertFalse(self.cascade.is_open())
        QTest.mouseRelease(other, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
        self.assertEqual(self.browser.current_folder, self.other)

    def test_a_click_outside_the_panel_dismisses_everything(self):
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        outside = menu.mapFromGlobal(self.browser.frameGeometry().bottomRight() + QPoint(200, 200))
        QTest.mousePress(menu, Qt.MouseButton.LeftButton, pos=outside)
        self.assertFalse(self.cascade.is_open())
        self.assertTrue(self.browser.isHidden())
        QTest.mouseRelease(menu, Qt.MouseButton.LeftButton, pos=outside)  # Qt keeps button state between tests.

    def test_hiding_the_panel_or_opening_settings_closes_the_cascade(self):
        self.hover(self.row_for(self.folder))
        self.settle()
        self.open_menu()
        self.browser.show_settings_modal()
        self.assertFalse(self.cascade.is_open())
        self.browser.hide_settings_modal()
        self.browser.hide()
        self.browser.show()
        self.app.processEvents()
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        self.browser.hide()
        self.assertFalse(self.cascade.is_open())
        self.assertFalse(menu.isVisible())

    def test_a_rebuilt_list_keeps_the_menu_while_its_row_survives(self):
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        (self.root / "new.txt").write_text("new", encoding="utf-8")
        self.browser.create_list_items()
        self.app.processEvents()
        self.assertIsNotNone(self.row_for(self.root / "new.txt"))
        self.assertIs(self.cascade._menu, menu)
        self.assertEqual(self.row_for(self.folder).property("cascaded"), "true")
        shutil.rmtree(self.folder)
        self.browser.create_list_items()
        self.app.processEvents()
        self.assertFalse(self.cascade.is_open())

    def test_unreadable_folder_shows_the_reason_instead_of_items(self):
        with patch("src.ui.folder_cascade.list_folder", side_effect=PermissionError("Access denied")):
            self.hover(self.row_for(self.folder))
            self.settle()
            menu = self.open_menu()
        self.assertEqual([action.text() for action in menu.actions()], ["Could not open this folder"])
        self.assertEqual(menu.actions()[0].toolTip(), "Access denied")

    def test_long_folders_stop_at_the_cap_with_a_way_to_see_the_rest(self):
        for index in range(self.cascade.MAX_ITEMS + 5):
            (self.other / f"photo-{index:04d}.jpg").write_bytes(b"")
        self.hover(self.row_for(self.other))
        self.settle()
        menu = self.open_menu()
        self.assertEqual(len(menu.actions()), self.cascade.MAX_ITEMS + 2)
        more = menu.actions()[-1]
        self.assertEqual(more.text(), f"Show all {self.cascade.MAX_ITEMS + 6} items")
        more.trigger()
        self.assertEqual(self.browser.current_folder, self.other)
        self.assertFalse(self.cascade.is_open())

    def test_a_slow_folder_shows_loading_then_fills_without_blocking(self):
        def slow(folder, hidden):
            time.sleep(0.4)
            return list_folder(folder, hidden)

        with patch("src.ui.folder_cascade.list_folder", side_effect=slow):
            self.hover(self.row_for(self.folder))
            self.settle()
            self.wait_for(lambda: self.cascade.is_open() and self.cascade._menu.isVisible())
            menu = self.cascade._menu
            self.assertEqual([action.text() for action in menu.actions()], ["Loading…"])
            self.assertFalse(menu.filled)
            self.open_menu()
        self.assertEqual([action.text() for action in menu.actions()], ["Archive", "Notes && ideas", "readme"])

    def test_a_level_that_fills_while_showing_stays_linked_to_its_parent(self):
        opened = []
        self.browser.program_clicked.connect(opened.append)
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()

        def slow(folder, hidden):
            if folder == self.nested:
                time.sleep(0.5)
            return list_folder(folder, hidden)

        with patch("src.ui.folder_cascade.list_folder", side_effect=slow):
            action = menu.actions()[0]
            QTest.mouseMove(menu, menu.actionGeometry(action).center())
            self.wait_for(lambda: action.menu().isVisible())
            submenu = action.menu()
            self.assertEqual([item.text() for item in submenu.actions()], ["Loading…"])
            self.wait_for(lambda: submenu.filled)
        self.assertEqual([item.text() for item in submenu.actions()], ["Empty folder"])
        self.assertEqual(submenu.geometry().right(), menu.geometry().left() - 1)
        # A click on the parent's file item still reaches the parent through the showing level.
        readme = menu.mapToGlobal(menu.actionGeometry(menu.actions()[2]).center())
        QTest.mouseClick(submenu, Qt.MouseButton.LeftButton, pos=submenu.mapFromGlobal(readme))
        self.assertEqual(opened, [str(self.folder / "readme.md")])

    def test_icons_are_read_off_the_ui_thread_and_cached(self):
        threads = []
        original = FileIcons.icon

        def record(provider, path):
            threads.append(threading.get_ident())
            return original(provider, path)

        with patch.object(FileIcons, "icon", record):
            self.hover(self.row_for(self.folder))
            self.settle()
            self.open_menu()
            self.wait_for(lambda: (self.folder / "readme.md") in self.browser._icons)
        self.assertTrue(threads)
        self.assertNotIn(threading.get_ident(), threads)

    def fill_the_list(self):
        for index in range(40):  # Named to sort after the folders, which stay in view.
            (self.root / f"z-file-{index:02d}.txt").write_text("x", encoding="utf-8")
        self.browser.create_list_items()
        self.app.processEvents()
        bar = self.browser.scroll_area.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        return bar

    def test_scrolling_the_list_cancels_the_hover_until_the_pointer_really_moves(self):
        bar = self.fill_the_list()
        row = self.row_for(self.folder)
        self.hover(row)
        self.assertTrue(self.cascade.timer.isActive())
        spot = row.mapToGlobal(QPoint(8, 8))
        bar.setValue(20)  # The rows move under a pointer that has not.
        self.assertFalse(self.cascade.timer.isActive())
        QTest.mouseMove(self.browser, self.browser.mapFromGlobal(spot + QPoint(3, 3)))  # A nudge is not a move.
        self.app.processEvents()
        self.assertFalse(self.cascade.timer.isActive())
        QTest.mouseMove(self.browser, self.browser.mapFromGlobal(spot + QPoint(24, 0)))
        self.app.processEvents()
        self.assertIs(self.cascade._hover_row, row)
        self.assertTrue(self.cascade.timer.isActive())
        self.settle()
        self.open_menu()
        bar.setValue(0)
        self.assertFalse(self.cascade.is_open())

    def test_a_wheel_over_the_panel_scrolls_the_list_and_closes_the_cascade(self):
        bar = self.fill_the_list()
        self.hover(self.row_for(self.folder))
        self.settle()
        menu = self.open_menu()
        over_list = self.row_for(self.file).mapToGlobal(QPoint(8, 8))
        wheel = QWheelEvent(QPointF(menu.mapFromGlobal(over_list)), QPointF(over_list), QPoint(), QPoint(0, -120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        self.app.sendEvent(menu, wheel)
        self.assertFalse(self.cascade.is_open())
        self.wait_for(lambda: bar.value() > 0)

    def test_a_sweep_across_folders_reads_none_of_them(self):
        self.cascade.prefetch_timer.setInterval(80)
        for row in (self.row_for(self.other), self.row_for(self.folder)):
            self.hover(row)
        self.assertEqual(self.cascade._in_flight, set())
        self.assertEqual(self.cascade._listings, {})
        self.wait_for(lambda: self.cascade.cached_listing(self.folder) is not None)
        self.assertIsNone(self.cascade.cached_listing(self.other))

    def test_hover_setting_restores(self):
        modal = SettingsModal(settings=self.settings)
        self.assertEqual(modal.hover_behavior, "cascade")
        modal.hover_combo.setCurrentIndex(modal.hover_combo.findData("none"))
        self.settings.sync()
        restored = SettingsModal(settings=QSettings(str(self.settings_path), QSettings.Format.IniFormat))
        self.assertEqual(restored.hover_behavior, "none")
        modal.deleteLater()
        restored.deleteLater()


if __name__ == "__main__":
    unittest.main()
