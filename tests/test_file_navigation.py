import os
import shutil
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF, Qt
from PyQt6.QtGui import QContextMenuEvent, QDrag, QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.ui.file_browser import FileBrowser
from src.utils import shell_actions
from src.utils.file_opener import FileOpener


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
            self.assertEqual(self.browser.current_folder, folder)
            self.assertTrue(self.browser.back_button.isEnabled())
            self.assertEqual(self.browser.path_label.toolTip(), str(folder))
        self.assertEqual(self.browser.status_label.text(), "0 items")
        self.assertEqual(opened, [])
        for folder in [self.deep.parent, self.folder / "Second", self.folder, self.root]:
            self.browser.back_button.click()
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
        self.browser.settings_modal.extensions_check.setChecked(True)
        self.browser.create_list_items()
        self.assertEqual(self.browser.current_folder, self.folder)
        self.assertEqual(self.browser.folder_history, [(self.root, 0)])
        self.assertIsNotNone(self.row_for(self.folder / "Second"))

    def test_unreadable_folder_preserves_current_view(self):
        count = self.browser.file_list_layout.count()
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("Access denied")):
            self.browser.open_item(self.folder)
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(self.browser.folder_history, [])
        self.assertEqual(self.browser.file_list_layout.count(), count)
        self.assertEqual(self.browser.status_label.text(), "Could not open this folder.")
        self.browser.refresh_files()
        self.assertEqual(self.browser.status_label.toolTip(), "")

    def choose_action(self, file, label):
        def execute(menu, position):
            actions = {action.text(): action for action in menu.actions()}
            self.assertEqual(menu.defaultAction().text(), "Open")
            actions[label].trigger()
        with patch("src.ui.file_browser.QMenu.exec", execute):
            self.browser.show_file_menu(file, QPoint(20, 20))

    def test_context_actions_use_the_selected_item(self):
        opened, locations = [], []
        self.browser.program_clicked.connect(opened.append)
        self.browser.file_location_clicked.connect(locations.append)
        self.choose_action(self.file, "Open")
        self.choose_action(self.file, "Open file location")
        self.choose_action(self.folder, "Open in File Explorer")
        self.choose_action(self.folder, "Open file location")
        self.assertEqual(opened, [str(self.file), str(self.folder)])
        self.assertEqual(locations, [str(self.file), str(self.folder)])
        self.choose_action(self.folder, "Open")
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
            recycle.assert_called_once_with(self.file)
        with patch("src.ui.file_browser.shell_actions.recycle", return_value="Windows could not delete this item."):
            self.choose_action(self.file, "Delete")
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
            recycle.assert_called_once_with(self.file)
        self.browser.settings_button.setFocus()
        with patch("src.ui.file_browser.shell_actions.recycle", return_value="") as recycle:
            QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Delete)
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
        self.browser.open_item(self.folder / "Second")
        self.browser.go_back()
        self.browser.go_back()
        self.assertTrue(self.browser.forward_button.isEnabled())
        self.browser.forward_button.click()
        self.assertEqual(self.browser.current_folder, self.folder)
        self.browser.go_forward()
        self.assertEqual(self.browser.current_folder, self.folder / "Second")
        self.assertFalse(self.browser.forward_button.isEnabled())
        self.browser.go_back()
        self.browser.go_back()
        self.browser.open_item(self.folder)
        self.assertEqual(self.browser.forward_history, [])
        self.assertFalse(self.browser.forward_button.isEnabled())

    def test_failed_navigation_leaves_the_shown_folder_refreshing(self):
        self.show_browser()
        self.browser.mark_dirty()
        self.assertTrue(self.browser.refresh_timer.isActive())
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("No access")):
            self.browser.open_item(self.folder)
        self.assertTrue(self.browser.refresh_timer.isActive())
        self.assertTrue(self.browser._dirty)
        self.assertTrue(self.browser._loaded)

    def test_cancelling_windows_delete_is_not_an_error(self):
        with patch("src.utils.shell_actions.ctypes.WinDLL") as library:
            library.return_value.SHFileOperationW.return_value = shell_actions.DE_OPCANCELLED
            self.assertEqual(shell_actions.recycle(self.file), "")
            library.return_value.SHFileOperationW.return_value = 5
            self.assertIn("error 5", shell_actions.recycle(self.file))
        self.assertEqual(shell_actions.recycle(self.root / "gone.txt"), "That item no longer exists.")

    def test_failed_forward_keeps_history_and_refresh_does_not_clear_it(self):
        self.browser.open_item(self.folder)
        self.browser.go_back()
        self.browser.refresh_files()
        self.assertEqual(self.browser.forward_history, [(self.folder, 0)])
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("No access")):
            self.browser.go_forward()
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(self.browser.forward_history, [(self.folder, 0)])
        self.assertEqual(self.browser.folder_history, [])

    def test_mouse_side_buttons_work_over_children(self):
        self.show_browser()
        for target in (self.browser, self.browser.path_label,
                       self.browser.scroll_area.viewport(), self.browser.settings_button):
            with self.subTest(target=target.objectName()):
                self.browser.open_item(self.folder)
                QTest.mouseClick(target, Qt.MouseButton.BackButton)
                self.assertEqual(self.browser.current_folder, self.root)
                QTest.mouseClick(target, Qt.MouseButton.ForwardButton)
                self.assertEqual(self.browser.current_folder, self.folder)
                self.browser.go_back()
        self.browser.open_item(self.folder)
        QTest.mouseClick(self.row_for(self.folder / "Second"), Qt.MouseButton.BackButton)
        self.assertEqual(self.browser.current_folder, self.root)

    def test_keyboard_history_up_and_refresh(self):
        self.show_browser()
        self.browser.open_item(self.folder)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(self.browser.current_folder, self.root)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(self.browser.current_folder, self.folder)
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Backspace)
        self.assertEqual(self.browser.current_folder, self.root)
        self.browser.go_forward()
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Up, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(self.browser.current_folder, self.root)
        for key, modifiers in ((Qt.Key.Key_F5, Qt.KeyboardModifier.NoModifier),
                               (Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)):
            with patch.object(self.browser, "traverse_level", wraps=self.browser.traverse_level) as traverse:
                QTest.keyClick(self.browser.settings_button, key, modifiers)
                traverse.assert_called_once_with(self.root)

    def test_arrow_keys_focus_rows_and_enter_activates(self):
        self.show_browser()
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Down)
        first = self.browser.file_list_layout.itemAt(0).widget()
        second = self.browser.file_list_layout.itemAt(1).widget()
        self.assertEqual(self.app.focusWidget(), first)
        QTest.keyClick(first, Qt.Key.Key_Down)
        self.assertEqual(self.app.focusWidget(), second)
        QTest.keyClick(second, Qt.Key.Key_Home)
        self.assertEqual(self.app.focusWidget(), first)
        QTest.keyClick(first, Qt.Key.Key_End)
        self.assertEqual(self.app.focusWidget(), second)
        opened = []
        self.browser.program_clicked.connect(opened.append)
        row = self.row_for(self.file)
        row.setFocus()
        QTest.keyClick(row, Qt.Key.Key_Return)
        self.assertEqual(opened, [str(self.file)])
        row = self.row_for(self.folder)
        row.setFocus()
        QTest.keyClick(row, Qt.Key.Key_Return)
        self.assertEqual(self.browser.current_folder, self.folder)

    def test_settings_do_not_navigate_underneath(self):
        self.show_browser()
        self.browser.open_item(self.folder)
        self.browser.show_settings_modal()
        QTest.qWait(220)
        combo = self.browser.settings_modal.theme_combo
        combo.setFocus()
        QTest.keyClick(combo, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
        self.assertEqual(self.browser.current_folder, self.folder)
        QTest.mouseClick(self.browser.settings_modal, Qt.MouseButton.ForwardButton)
        self.assertEqual(self.browser.current_folder, self.folder)
        QTest.mouseClick(self.browser.settings_modal, Qt.MouseButton.BackButton)
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
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(650)
        self.assertEqual(bar.value(), 650)
        self.browser.open_item(self.folder)
        self.app.processEvents()
        self.assertEqual(bar.value(), 0)
        self.browser.go_back()
        self.app.processEvents()
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(bar.value(), 650)

    def test_back_and_forward_restore_each_visit(self):
        self.make_scrollable(self.root)
        self.make_scrollable(self.folder)
        self.browser.refresh_files()
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(500)
        self.browser.open_item(self.folder)
        self.app.processEvents()
        self.assertEqual(bar.value(), 0)
        bar.setValue(300)
        self.browser.go_back()
        self.app.processEvents()
        self.assertEqual(bar.value(), 500)
        bar.setValue(700)
        self.browser.go_forward()
        self.app.processEvents()
        self.assertEqual(bar.value(), 300)
        self.browser.go_back()
        self.app.processEvents()
        self.assertEqual(bar.value(), 700)

    def test_refresh_and_extension_changes_preserve_scroll(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(600)
        self.browser.refresh_files()
        self.app.processEvents()
        self.assertEqual(bar.value(), 600)
        self.browser.settings_modal.extensions_check.setChecked(True)
        self.app.processEvents()
        self.assertEqual(bar.value(), 600)

    def test_removed_files_clamp_restored_scroll_to_new_range(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())
        previous_position = bar.value()
        self.browser.open_item(self.folder)
        for i in range(20):
            (self.root / f"scroll-item-{i:02}.txt").unlink()
        self.browser.go_back()
        self.app.processEvents()
        self.assertLess(bar.maximum(), previous_position)
        self.assertGreater(bar.maximum(), 0)
        self.assertEqual(bar.value(), bar.maximum())

    def test_failed_navigation_keeps_scroll_and_history(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        bar.setValue(500)
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("No access")):
            self.browser.open_item(self.folder)
        self.assertEqual(bar.value(), 500)
        self.assertEqual(self.browser.folder_history, [])


    def test_keyboard_and_mouse_back_restore_scroll(self):
        self.make_scrollable(self.root)
        self.browser.refresh_files()
        self.show_browser()
        bar = self.browser.scroll_area.verticalScrollBar()
        for use_mouse in (False, True):
            with self.subTest(use_mouse=use_mouse):
                row = self.row_for(self.folder)
                row.setFocus()
                bar.setValue(450)
                QTest.keyClick(row, Qt.Key.Key_Return)
                self.app.processEvents()
                self.assertEqual(self.browser.current_folder, self.folder)
                if use_mouse:
                    QTest.mouseClick(self.browser.scroll_area.viewport(), Qt.MouseButton.BackButton)
                else:
                    QTest.keyClick(self.browser.settings_button, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
                self.app.processEvents()
                self.assertEqual(self.browser.current_folder, self.root)
                self.assertEqual(bar.value(), 450)


if __name__ == "__main__":
    unittest.main()
