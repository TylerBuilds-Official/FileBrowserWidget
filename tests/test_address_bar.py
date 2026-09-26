import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.ui.file_browser import FileBrowser
from src.utils.locations import typed_path
from support import drain_workers, settle


class TypedPathTests(unittest.TestCase):
    """What is typed or pasted into the address is read the way Explorer reads it."""

    base = Path("C:\\Users\\Public")

    def test_quotes_and_spaces_from_copy_as_path_are_dropped(self):
        self.assertEqual(typed_path('  "C:\\Program Files\\Common Files"  ', self.base),
                         Path("C:\\Program Files\\Common Files"))

    def test_variables_are_spelled_out(self):
        self.assertEqual(typed_path("%SystemRoot%\\System32", self.base), Path(os.environ["SystemRoot"]) / "System32")

    def test_a_drive_letter_alone_is_its_root(self):
        self.assertEqual(typed_path("d:", self.base), Path("d:\\"))

    def test_a_relative_path_is_taken_from_the_folder_shown(self):
        self.assertEqual(typed_path("Documents\\..\\Music", self.base), self.base / "Music")
        self.assertEqual(typed_path("..", self.base), Path("C:\\Users"))

    def test_forward_slashes_and_shares_read_as_windows_paths(self):
        self.assertEqual(typed_path("C:/Users/Public", self.base), self.base)
        self.assertEqual(str(typed_path(r"\\nas\Media\Photos", self.base)), r"\\nas\Media\Photos")

    def test_nothing_typed_goes_nowhere(self):
        self.assertIsNone(typed_path('  ""  ', self.base))


class AddressBarTests(unittest.TestCase):
    """The path turns into text to type a place into, and the panel's keys leave that text alone."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".address-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        self.folder = self.root / "Folder"
        self.folder.mkdir()
        (self.folder / "inside.txt").write_text("x", encoding="utf-8")  # A row for Up and Down to reach.
        self.notes = self.root / "Notes.txt"
        self.notes.write_text("x", encoding="utf-8")
        self.browser = FileBrowser()
        self.browser.resize(400, 640)
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.desktop_folder = self.root
        self.browser.create_list_items(self.root)
        settle(self.browser)
        self.browser.show()
        self.browser.activateWindow()
        self.app.processEvents()
        self.edit = self.browser.address_edit

    def remove_fixture(self):
        drain_workers()  # A look-up still asking must not have the fixture vanish under it.
        root = self.root.resolve()
        assert root.parent == Path(__file__).resolve().parent
        shutil.rmtree(root)

    def go_to(self, text):
        self.browser.edit_address()
        self.edit.setText(text)
        QTest.keyClick(self.edit, Qt.Key.Key_Return)
        drain_workers()
        settle(self.browser)

    def test_ctrl_l_and_alt_d_turn_the_path_into_text_ready_to_replace(self):
        for key, modifier in ((Qt.Key.Key_L, Qt.KeyboardModifier.ControlModifier),
                              (Qt.Key.Key_D, Qt.KeyboardModifier.AltModifier)):
            with self.subTest(key=key):
                self.browser.settings_button.setFocus()
                QTest.keyClick(self.browser.settings_button, key, modifier)
                self.assertTrue(self.edit.isVisible())
                self.assertFalse(self.browser.path_label.isVisible())
                self.assertEqual(self.app.focusWidget(), self.edit)
                self.assertEqual(self.edit.selectedText(), str(self.root))
                QTest.keyClick(self.edit, Qt.Key.Key_Escape)
                self.assertFalse(self.edit.isVisible())
                self.assertTrue(self.browser.path_label.isVisible())
                self.assertTrue(self.browser.isVisible())  # Esc put the crumbs back; the panel stays.

    def test_the_panels_keys_leave_the_text_alone(self):
        self.browser.navigate_to(self.folder)  # So Backspace would have somewhere to go back to.
        settle(self.browser)
        self.browser.edit_address()
        QTest.keyClicks(self.edit, "abc")
        QTest.keyClick(self.edit, Qt.Key.Key_Backspace)
        self.assertEqual(self.edit.text(), "ab")
        QTest.keyClick(self.edit, Qt.Key.Key_Home)
        self.assertEqual(self.edit.cursorPosition(), 0)
        QTest.keyClick(self.edit, Qt.Key.Key_Right)
        self.assertEqual(self.edit.cursorPosition(), 1)
        QTest.keyClick(self.edit, Qt.Key.Key_Delete)
        self.assertEqual(self.edit.text(), "a")
        for key in (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_End, Qt.Key.Key_Left):
            QTest.keyClick(self.edit, key)
            self.assertEqual(self.app.focusWidget(), self.edit)
        self.assertEqual(self.browser.current_folder, self.folder)
        self.assertTrue(self.edit.isVisible())

    def test_enter_opens_a_typed_folder_or_file(self):
        opened = []
        self.browser.program_clicked.connect(opened.append)
        self.go_to(str(self.folder))
        self.assertEqual(self.browser.current_folder, self.folder)
        self.assertEqual([folder for folder, _ in self.browser.folder_history], [self.root])
        self.assertFalse(self.edit.isVisible())
        self.go_to(f'"{self.notes}"')  # As Copy as path puts it.
        self.assertEqual(opened, [str(self.notes)])
        self.go_to("..")
        self.assertEqual(self.browser.current_folder, self.root)

    def test_a_path_that_is_not_there_says_so_and_stays_put(self):
        self.go_to(str(self.root / "Missing"))
        self.assertEqual(self.browser.status_label.text(), "There is no such file or folder.")
        self.assertEqual(self.browser.current_folder, self.root)

    def test_clicking_beside_the_crumbs_types_the_path_and_a_crumb_still_opens(self):
        crumbs = self.browser.path_label
        # The bar's top edge, clear of the line of text.
        QTest.mouseClick(crumbs, Qt.MouseButton.LeftButton, pos=QPoint(crumbs.width() // 2, 1))
        self.assertTrue(self.edit.isVisible())
        QTest.keyClick(self.edit, Qt.Key.Key_Escape)
        # A long path starts with the overflow crumb, whose menu stands in for any crumb's action.
        with patch("src.ui.breadcrumbs.QMenu.exec") as overflow:
            QTest.mouseClick(crumbs, Qt.MouseButton.LeftButton, pos=QPoint(3, crumbs.height() // 2))
        overflow.assert_called_once()
        self.assertFalse(self.edit.isVisible())

    def test_clicking_away_puts_the_crumbs_back(self):
        self.browser.edit_address()
        self.browser.settings_button.setFocus()
        self.assertFalse(self.edit.isVisible())
        self.assertTrue(self.browser.path_label.isVisible())

    def test_closing_the_panel_puts_the_crumbs_back(self):
        self.browser.edit_address()
        self.browser.hide()
        self.browser.show()
        self.app.processEvents()
        self.assertFalse(self.edit.isVisible())
        self.assertTrue(self.browser.path_label.isVisible())

    def test_go_to_path_in_the_locations_menu_opens_the_address(self):
        def choose(menu, position):
            next(action for action in menu.actions() if action.text().startswith("Go to path")).trigger()

        with patch("src.utils.locations.list_drives", return_value=[]), \
                patch("src.utils.locations.user_folders", return_value=[]), \
                patch("src.utils.locations.read_names", return_value={}), \
                patch("src.ui.file_browser.QMenu.exec", choose):
            self.browser.show_locations_menu()
            drain_workers()
        self.assertTrue(self.edit.isVisible())
        self.assertEqual(self.app.focusWidget(), self.edit)


if __name__ == "__main__":
    unittest.main()
