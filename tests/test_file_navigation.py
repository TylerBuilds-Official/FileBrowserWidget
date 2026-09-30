import os
import shutil
import threading
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QDrag, QKeyEvent, QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.ui.file_browser import FileBrowser
from src.utils import shell_actions
from src.utils.file_opener import FileOpener
from support import drain_workers, settle


class FileNavigationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".navigation-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        self.folder = self.root / "Folder with spaces"
        self.deep = self.folder / "Second" / "Third" / "Fourth"
        self.deep.mkdir(parents=True)
        self.file = self.root / "Notes & ideas.txt"
        self.file.write_text("hello", encoding="utf-8")
        self.browser = FileBrowser()
        self.browser.resize(400, 640)
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.create_list_items(self.root)
        settle(self.browser)

    def remove_fixture(self):
        root = self.root.resolve()
        assert root.parent == Path(__file__).resolve().parent
        assert root.name.startswith(".navigation-test-")
        shutil.rmtree(root)

    def row_for(self, path):
        for i in range(self.browser.file_list_layout.count()):
            row = self.browser.file_list_layout.itemAt(i).widget()
            if row.toolTip() == str(path):
                return row
        self.fail(f"No row for {path}")

    def test_folder_clicks_navigate_four_levels_and_back(self):
        opened = []
        self.browser.program_clicked.connect(opened.append)
        self.assertFalse(self.browser.back_button.isEnabled())
        levels = [self.folder, self.folder / "Second", self.deep.parent, self.deep]
        for folder in levels:
            self.row_for(folder).clicked.emit()
            settle(self.browser)
            self.assertEqual(self.browser.current_folder, folder)
            self.assertTrue(self.browser.back_button.isEnabled())
            self.assertEqual(self.browser.path_label.toolTip(), str(folder))
        self.assertEqual(self.browser.status_label.text(), "0 items")
        self.assertEqual(opened, [])
        for folder in [self.deep.parent, self.folder / "Second", self.folder, self.root]:
            self.browser.back_button.click()
            settle(self.browser)
            self.assertEqual(self.browser.current_folder, folder)
        self.assertFalse(self.browser.back_button.isEnabled())
        self.assertEqual(self.browser.folder_history, [])

    def test_file_activation_emits_its_own_path(self):
        opened = []
        self.browser.program_clicked.connect(opened.append)
        self.row_for(self.file).clicked.emit()
        self.assertEqual(opened, [str(self.file)])
        self.assertEqual(self.browser.current_folder, self.root)

    def test_refresh_keeps_current_folder_and_history(self):
        self.browser.open_item(self.folder)
        settle(self.browser)
        self.browser.settings_modal.extensions_check.setChecked(True)
        self.browser.create_list_items()
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder)
        self.assertEqual(self.browser.folder_history, [(self.root, 0)])
        self.assertIsNotNone(self.row_for(self.folder / "Second"))

    def test_unreadable_folder_preserves_current_view(self):
        count = self.browser.file_list_layout.count()
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("Access denied")):
            self.browser.open_item(self.folder)
            settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(self.browser.folder_history, [])
        self.assertEqual(self.browser.file_list_layout.count(), count)
        self.assertEqual(self.browser.status_label.text(), "Could not open this folder.")
        self.browser.refresh_files()
        settle(self.browser)
        self.assertEqual(self.browser.status_label.toolTip(), "")

    def choose_action(self, file, label):
        def execute(menu, position):
            actions = {action.text(): action for action in menu.actions()}
            self.assertEqual(menu.defaultAction().text(), "Open")
            actions[label].trigger()
        with patch("src.ui.file_browser.QMenu.exec", execute):
            self.browser.show_file_menu(file, QPoint(20, 20))
        settle(self.browser)

    def test_context_actions_use_the_selected_item(self):
        opened, locations = [], []
        self.browser.program_clicked.connect(opened.append)
        self.browser.file_location_clicked.connect(locations.append)
        self.choose_action(self.file, "Open")
        settle(self.browser)
        self.choose_action(self.file, "Open file location")
        settle(self.browser)
        self.choose_action(self.folder, "Open in File Explorer")
        settle(self.browser)
        self.choose_action(self.folder, "Open file location")
        settle(self.browser)
        self.assertEqual(opened, [str(self.file), str(self.folder)])
        self.assertEqual(locations, [str(self.file), str(self.folder)])
        self.choose_action(self.folder, "Open")
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder)

    def test_right_click_does_not_activate_and_requests_correct_menu(self):
        row = self.row_for(self.file)
        opened = []
        self.browser.program_clicked.connect(opened.append)
        QTest.mouseClick(row, Qt.MouseButton.RightButton)
        self.assertEqual(opened, [])
        with patch.object(self.browser, "show_file_menu") as menu:
            local = QPoint(12, 12)
            event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local, row.mapToGlobal(local))
            self.app.sendEvent(row, event)
            menu.assert_called_once_with(self.file, row.mapToGlobal(local))

    def test_click_opens_on_release_and_a_drag_hands_over_the_file_instead(self):
        row = self.row_for(self.file)
        opened = []
        self.browser.program_clicked.connect(opened.append)
        QTest.mouseClick(row, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
        self.assertEqual(opened, [str(self.file)])

        dragged = []
        with patch.object(QDrag, "exec", lambda drag, *args: dragged.extend(drag.mimeData().urls())):
            QTest.mousePress(row, Qt.MouseButton.LeftButton, pos=QPoint(8, 8))
            move = QMouseEvent(QEvent.Type.MouseMove, QPointF(90, 20), QPointF(90, 20),
                               Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton,
                               Qt.KeyboardModifier.NoModifier)
            self.app.sendEvent(row, move)
            QTest.mouseRelease(row, Qt.MouseButton.LeftButton, pos=QPoint(90, 20))
        self.assertEqual([Path(url.toLocalFile()) for url in dragged], [self.file])
        self.assertEqual(opened, [str(self.file)])

    def test_context_menu_copies_deletes_and_opens_properties(self):
        with patch("src.ui.file_browser.shell_actions.recycle", return_value="") as recycle:
            self.choose_action(self.file, "Delete")
            drain_workers()  # The Recycle Bin is asked on a worker.
            recycle.assert_called_once_with(self.file)
        with patch("src.ui.file_browser.shell_actions.recycle", return_value="Windows could not delete this item."):
            self.choose_action(self.file, "Delete")
            drain_workers()
        self.assertEqual(self.browser.status_label.text(), "Windows could not delete this item.")
        with patch("src.ui.file_browser.shell_actions.show_properties", return_value="") as properties:
            self.choose_action(self.file, "Properties")
            properties.assert_called_once_with(self.file)
        self.choose_action(self.file, "Copy")
        urls = QApplication.clipboard().mimeData().urls()
        self.assertEqual([Path(url.toLocalFile()) for url in urls], [self.file])

    def test_keyboard_copy_and_delete_use_the_focused_row(self):
        self.show_browser()
        row = self.row_for(self.file)
        row.setFocus()
        with patch("src.ui.file_browser.shell_actions.recycle", return_value="") as recycle:
            QTest.keyClick(row, Qt.Key.Key_Delete)
            drain_workers()
            recycle.assert_called_once_with(self.file)
        self.browser.settings_button.setFocus()
        with patch("src.ui.file_browser.shell_actions.recycle", return_value="") as recycle:
            QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Delete)
            drain_workers()
            recycle.assert_not_called()

    def test_open_location_opens_containing_folder(self):
        with patch.object(FileOpener, "open_file") as open_file:
            FileOpener.open_file_location(self.file)
            open_file.assert_called_once_with(self.root)
            open_file.reset_mock()
            FileOpener.open_file_location(self.folder)
            open_file.assert_called_once_with(self.root)


    def show_browser(self):
        self.browser.show()
        self.browser.activateWindow()
        self.browser.settings_button.setFocus()
        self.app.processEvents()

    def test_forward_history_and_new_branch(self):
        self.browser.open_item(self.folder)
        settle(self.browser)
        self.browser.open_item(self.folder / "Second")
        settle(self.browser)
        self.browser.go_back()
        settle(self.browser)
        self.browser.go_back()
        settle(self.browser)
        self.assertTrue(self.browser.forward_button.isEnabled())
        self.browser.forward_button.click()
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder)
        self.browser.go_forward()
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder / "Second")
        self.assertFalse(self.browser.forward_button.isEnabled())
        self.browser.go_back()
        settle(self.browser)
        self.browser.go_back()
        settle(self.browser)
        self.browser.open_item(self.folder)
        settle(self.browser)
        self.assertEqual(self.browser.forward_history, [])
        self.assertFalse(self.browser.forward_button.isEnabled())

    def test_failed_navigation_leaves_the_shown_folder_refreshing(self):
        self.show_browser()
        self.browser.mark_dirty()
        self.assertTrue(self.browser.refresh_timer.isActive())
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("No access")):
            self.browser.open_item(self.folder)
            settle(self.browser)
        self.assertTrue(self.browser.refresh_timer.isActive())
        self.assertTrue(self.browser._dirty)
        self.assertTrue(self.browser._loaded)

    def test_cancelling_windows_delete_is_not_an_error(self):
        with patch("src.utils.shell_actions.ctypes.WinDLL") as library:
            library.return_value.SHFileOperationW.return_value = shell_actions.DE_OPCANCELLED
            self.assertEqual(shell_actions.recycle(self.file), "")
            library.return_value.SHFileOperationW.return_value = 5
            self.assertIn("error 5", shell_actions.recycle(self.file))
            # Gone by the time the shell looks: the shell says so, and nothing asks the disk before it.
            library.return_value.SHFileOperationW.return_value = shell_actions.ERROR_FILE_NOT_FOUND
            with patch.object(Path, "exists") as exists:
                self.assertEqual(shell_actions.recycle(self.root / "gone.txt"), "That item no longer exists.")
                exists.assert_not_called()

    def test_failed_forward_keeps_history_and_refresh_does_not_clear_it(self):
        self.browser.open_item(self.folder)
        settle(self.browser)
        self.browser.go_back()
        settle(self.browser)
        self.browser.refresh_files()
        settle(self.browser)
        self.assertEqual(self.browser.forward_history, [(self.folder, 0)])
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("No access")):
            self.browser.go_forward()
            settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(self.browser.forward_history, [(self.folder, 0)])
        self.assertEqual(self.browser.folder_history, [])

    def test_mouse_side_buttons_work_over_children(self):
        self.show_browser()
        for target in (self.browser, self.browser.path_label,
                       self.browser.scroll_area.viewport(), self.browser.settings_button):
            with self.subTest(target=target.objectName()):
                self.browser.open_item(self.folder)
                settle(self.browser)
                QTest.mouseClick(target, Qt.MouseButton.BackButton)
                settle(self.browser)
                self.assertEqual(self.browser.current_folder, self.root)
                QTest.mouseClick(target, Qt.MouseButton.ForwardButton)
                settle(self.browser)
                self.assertEqual(self.browser.current_folder, self.folder)
                self.browser.go_back()
                settle(self.browser)
        self.browser.open_item(self.folder)
        settle(self.browser)
        QTest.mouseClick(self.row_for(self.folder / "Second"), Qt.MouseButton.BackButton)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)

    def test_keyboard_history_up_and_refresh(self):
        self.show_browser()
        self.browser.open_item(self.folder)
        settle(self.browser)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Backspace)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)
        self.browser.go_forward()
        settle(self.browser)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)
        for key, modifiers in ((Qt.Key.Key_F5, Qt.KeyboardModifier.NoModifier),
                               (Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)):
            with patch.object(self.browser, "traverse_level", wraps=self.browser.traverse_level) as traverse:
                QTest.keyClick(self.browser.settings_button, key, modifiers)
                settle(self.browser)
                traverse.assert_called_once_with(self.root)

    def test_arrow_keys_focus_rows_and_enter_activates(self):
        self.show_browser()
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Down)
        settle(self.browser)
        first = self.browser.file_list_layout.itemAt(0).widget()
        second = self.browser.file_list_layout.itemAt(1).widget()
        self.assertEqual(self.app.focusWidget(), first)
        QTest.keyClick(first, Qt.Key.Key_Down)
        settle(self.browser)
        self.assertEqual(self.app.focusWidget(), second)
        QTest.keyClick(second, Qt.Key.Key_Home)
        settle(self.browser)
        self.assertEqual(self.app.focusWidget(), first)
        QTest.keyClick(first, Qt.Key.Key_End)
        settle(self.browser)
        self.assertEqual(self.app.focusWidget(), second)
        opened = []
        self.browser.program_clicked.connect(opened.append)
        row = self.row_for(self.file)
        row.setFocus()
        QTest.keyClick(row, Qt.Key.Key_Return)
        settle(self.browser)
        self.assertEqual(opened, [str(self.file)])
        row = self.row_for(self.folder)
        row.setFocus()
        QTest.keyClick(row, Qt.Key.Key_Return)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder)
        self.browser.go_back()
        settle(self.browser)
        row = self.row_for(self.file)
        row.setFocus()
        QTest.keyClick(row, Qt.Key.Key_Space)
        settle(self.browser)
        self.assertEqual(opened, [str(self.file)] * 2)
        # A held key repeats; the row opens once for the press, not once per repeat.
        held = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier, "", True)
        self.app.sendEvent(row, held)
        settle(self.browser)
        self.assertEqual(opened, [str(self.file)] * 2)
        self.assertTrue(held.isAccepted())  # Still the row's key, never the panel's shortcuts'.

    def test_settings_do_not_navigate_underneath(self):
        self.show_browser()
        self.browser.open_item(self.folder)
        settle(self.browser)
        self.browser.show_settings_modal()
        QTest.qWait(220)
        combo = self.browser.settings_modal.theme_combo
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder)
        QTest.mouseClick(self.browser.settings_modal, Qt.MouseButton.ForwardButton)
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.folder)
        QTest.mouseClick(self.browser.settings_modal, Qt.MouseButton.BackButton)
        settle(self.browser)
        QTest.qWait(220)
        self.assertTrue(self.browser.settings_modal.isHidden())
        self.assertEqual(self.browser.current_folder, self.folder)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Escape)
        self.assertTrue(self.browser.isHidden())

    def test_escape_closes_combo_popup_before_settings(self):
        self.show_browser()
        self.browser.show_settings_modal()
        QTest.qWait(220)
        combo = self.browser.settings_modal.theme_combo
        combo.setFocus()
        combo.showPopup()
        self.app.processEvents()
        QTest.keyClick(combo.view(), Qt.Key.Key_Escape)
        self.assertFalse(combo.view().isVisible())
        self.assertTrue(self.browser.settings_modal.isVisible())

    def test_up_at_filesystem_root_does_not_add_history(self):
        self.browser.current_folder = Path(self.root.anchor)
        with patch.object(self.browser, "create_list_items") as refresh:
            self.browser.go_up()
            refresh.assert_not_called()
        self.assertEqual(self.browser.folder_history, [])


    def make_scrollable(self, folder):
        for i in range(40):
            (folder / f"scroll-item-{i:02}.txt").touch()

    def test_back_restores_scroll_from_short_folder_to_long_folder(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        settle(self.browser)
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(650)
        self.assertEqual(bar.value(), 650)
        self.browser.open_item(self.folder)
        settle(self.browser)
        self.app.processEvents()
        self.assertEqual(bar.value(), 0)
        self.browser.go_back()
        settle(self.browser)
        self.app.processEvents()
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(bar.value(), 650)

    def test_back_and_forward_restore_each_visit(self):
        self.make_scrollable(self.root)
        self.make_scrollable(self.folder)
        self.browser.refresh_files()
        settle(self.browser)
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(500)
        self.browser.open_item(self.folder)
        settle(self.browser)
        self.app.processEvents()
        self.assertEqual(bar.value(), 0)
        bar.setValue(300)
        self.browser.go_back()
        settle(self.browser)
        self.app.processEvents()
        self.assertEqual(bar.value(), 500)
        bar.setValue(700)
        self.browser.go_forward()
        settle(self.browser)
        self.app.processEvents()
        self.assertEqual(bar.value(), 300)
        self.browser.go_back()
        settle(self.browser)
        self.app.processEvents()
        self.assertEqual(bar.value(), 700)

    def test_refresh_and_extension_changes_preserve_scroll(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        settle(self.browser)
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(600)
        self.browser.refresh_files()
        settle(self.browser)
        self.app.processEvents()
        self.assertEqual(bar.value(), 600)
        self.browser.settings_modal.extensions_check.setChecked(True)
        self.app.processEvents()
        self.assertEqual(bar.value(), 600)

    def test_removed_files_clamp_restored_scroll_to_new_range(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        settle(self.browser)
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())
        previous_position = bar.value()
        self.browser.open_item(self.folder)
        settle(self.browser)
        for i in range(20):
            (self.root / f"scroll-item-{i:02}.txt").unlink()
        self.browser.go_back()
        settle(self.browser)
        self.app.processEvents()
        self.assertLess(bar.maximum(), previous_position)
        self.assertGreater(bar.maximum(), 0)
        self.assertEqual(bar.value(), bar.maximum())

    def test_failed_navigation_keeps_scroll_and_history(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        settle(self.browser)
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(500)
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("No access")):
            self.browser.open_item(self.folder)
            settle(self.browser)
        self.assertEqual(bar.value(), 500)
        self.assertEqual(self.browser.folder_history, [])


    def test_keyboard_and_mouse_back_restore_scroll(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        settle(self.browser)
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        for use_mouse in (False, True):
            with self.subTest(use_mouse=use_mouse):
                row = self.row_for(self.folder)
                row.setFocus()
                bar.setValue(450)
                QTest.keyClick(row, Qt.Key.Key_Return)
                settle(self.browser)
                self.app.processEvents()
                self.assertEqual(self.browser.current_folder, self.folder)
                if use_mouse:
                    QTest.mouseClick(self.browser.scroll_area.viewport(), Qt.MouseButton.BackButton)
                    settle(self.browser)
                else:
                    QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
                    settle(self.browser)
                self.app.processEvents()
                self.assertEqual(self.browser.current_folder, self.root)
                self.assertEqual(bar.value(), 450)

    @contextmanager
    def disk_questions_on_the_ui_thread(self):
        """Every stat, exists, is_dir or is_file asked on the UI thread while it is open.

        Workers may ask the disk. The UI thread may not: a share can take seconds to answer.
        """
        asked = []
        ui_thread = threading.current_thread()
        with ExitStack() as stack:
            for name in ("stat", "exists", "is_dir", "is_file"):
                def spy(path, *args, real=getattr(Path, name), name=name, **kwargs):
                    if threading.current_thread() is ui_thread:
                        asked.append((name, path))
                    return real(path, *args, **kwargs)
                stack.enter_context(patch.object(Path, name, spy))
            yield asked

    def test_opening_a_listed_item_asks_the_listing_not_the_disk(self):
        opened, located, menus = [], [], []
        self.browser.program_clicked.connect(opened.append)
        self.browser.file_location_clicked.connect(located.append)

        def look(menu, position):
            menus.append([action.text() for action in menu.actions()])

        with self.disk_questions_on_the_ui_thread() as asked:
            self.row_for(self.file).clicked.emit()
            self.row_for(self.file).middle_clicked.emit()
            self.row_for(self.folder).middle_clicked.emit()
            with patch("src.ui.file_browser.QMenu.exec", look):
                self.browser.show_file_menu(self.folder, QPoint(20, 20))
                self.browser.show_file_menu(self.file, QPoint(20, 20))
            self.row_for(self.folder).clicked.emit()
            settle(self.browser)
        self.assertEqual(asked, [])
        self.assertEqual(opened, [str(self.file), str(self.folder)])
        self.assertEqual(located, [str(self.file)])
        self.assertIn("Open in File Explorer", menus[0])
        self.assertNotIn("Open in File Explorer", menus[1])
        self.assertEqual(self.browser.current_folder, self.folder)

    def test_an_item_that_was_never_listed_is_looked_up_on_a_worker(self):
        opened = []
        self.browser.program_clicked.connect(opened.append)
        inner = self.deep / "inner.txt"
        inner.write_text("x", encoding="utf-8")
        with self.disk_questions_on_the_ui_thread() as asked:
            self.browser.open_item(inner)
            self.assertEqual(opened, [])  # Not yet: the disk is being asked on a worker.
            drain_workers()
            self.browser.open_item(self.deep)
            drain_workers()
            settle(self.browser)
        self.assertEqual(asked, [])
        self.assertEqual(opened, [str(inner)])
        self.assertEqual(self.browser.current_folder, self.deep)

    def test_a_slow_look_up_never_pulls_the_panel_from_where_it_went_since(self):
        self.browser.desktop_folder = self.root
        release = threading.Event()
        real = Path.stat

        def sleeping_share(path, *args, **kwargs):
            if path == self.deep:
                release.wait(5)
            return real(path, *args, **kwargs)

        moves = {"a navigation": lambda: self.browser.navigate_to(self.folder),
                 "a reopen": self.browser.reset_location}
        for move, go in moves.items():
            with self.subTest(move), patch.object(Path, "stat", sleeping_share):
                release.clear()
                self.browser.open_favorite(self.deep)
                go()
                settle(self.browser)
                where = self.browser.current_folder
                release.set()
                drain_workers()
                settle(self.browser)
                self.assertEqual(self.browser.current_folder, where)
                self.assertNotEqual(where, self.deep)

    def test_deleting_asks_the_recycle_bin_off_the_ui_thread(self):
        threads = []

        def record(file):
            threads.append(threading.current_thread())
            return ""

        with patch("src.ui.file_browser.shell_actions.recycle", side_effect=record), \
                self.disk_questions_on_the_ui_thread() as asked:
            self.browser.delete_file(self.file)
            drain_workers()
        self.assertEqual(asked, [])
        self.assertEqual(len(threads), 1)
        self.assertIsNot(threads[0], threading.current_thread())
        self.assertTrue(self.browser._dirty)  # The listing is read again once the item has gone.

    def test_a_slow_share_says_what_it_is_waiting_on_then_gives_the_count_back(self):
        release = threading.Event()
        count = self.browser.status_label.text()

        def slow_recycle(file):
            release.wait(5)
            return ""

        real = Path.stat
        slow_file = self.deep / "far.txt"  # A file, so opening it launches rather than moves the panel.
        slow_file.write_text("x", encoding="utf-8")
        self.browser.program_clicked.connect(lambda file: None)

        def slow_stat(path, *args, **kwargs):
            if path == slow_file:
                release.wait(5)
            return real(path, *args, **kwargs)

        actions = ((lambda: self.browser.delete_file(self.deep / "x.txt"), "Deleting x.txt…"),
                   (lambda: self.browser.open_favorite(slow_file), "Opening far.txt…"))
        for go, notice in actions:
            with self.subTest(notice):
                release.clear()
                with patch("src.ui.file_browser.shell_actions.recycle", slow_recycle), \
                        patch.object(Path, "stat", slow_stat):
                    go()
                    QTest.qWait(50)  # Well within the grace the notice gives a quick answer.
                    self.assertEqual(self.browser.status_label.text(), count)  # Nothing yet: it may be quick.
                    QTest.qWait(250)
                    self.assertEqual(self.browser.status_label.text(), notice)
                    release.set()
                    drain_workers()
                    settle(self.browser)
                self.assertEqual(self.browser.status_label.text(), count)

    def test_a_quick_action_never_shows_its_notice(self):
        count = self.browser.status_label.text()
        with patch("src.ui.file_browser.shell_actions.recycle", return_value=""):
            self.browser.delete_file(self.file)
            drain_workers()
            QTest.qWait(250)  # Long past the notice's due time; it was called off when the delete landed.
        self.assertEqual(self.browser.status_label.text(), count)

    def test_a_favorite_that_does_not_answer_is_not_reported_gone(self):
        real = Path.stat

        def unreachable(path, *args, **kwargs):
            if path == self.deep:
                raise TimeoutError("The semaphore timeout period has expired")
            return real(path, *args, **kwargs)

        with patch.object(Path, "stat", unreachable):
            self.browser.open_favorite(self.deep)
            drain_workers()
        self.assertEqual(self.browser.status_label.text(), "Could not open this item.")
        self.assertEqual(self.browser.current_folder, self.root)


if __name__ == "__main__":
    unittest.main()
