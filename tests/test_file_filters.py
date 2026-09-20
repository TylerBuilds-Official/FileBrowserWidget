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
from src.utils.file_listing import describe_file, filter_options, visible_entries


class FileFilterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".filter-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        (self.root / "Folder").mkdir()
        (self.root / "Notes.TXT").write_text("hello")
        (self.root / "App.exe").touch()
        (self.root / "Game.url").write_text("[InternetShortcut]\nURL=steam://rungameid/123")
        (self.root / "Website.url").write_text("[InternetShortcut]\nURL=https://example.com/game")
        self.browser = FileBrowser()
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.create_list_items(self.root)

    def remove_fixture(self):
        assert self.root.resolve().parent == Path(__file__).resolve().parent
        shutil.rmtree(self.root)

    def names(self):
        layout = self.browser.file_list_layout
        return [Path(layout.itemAt(i).widget().toolTip()).name for i in range(layout.count())]

    def search(self, text):
        self.browser.search_edit.setText(text)
        QTest.qWait(FileBrowser.SEARCH_DELAY + 50)

    def test_options_only_include_detected_types(self):
        values = dict((value, label) for label, value in filter_options(self.browser.entries))
        self.assertIn("games", values)
        self.assertIn("programs", values)
        self.assertIn("ext:.txt", values)
        self.assertNotIn("ext:.pdf", values)
        self.assertEqual(values["games"], "Games (1)")
        self.browser.navigate_to(self.root / "Folder")
        self.assertEqual(self.browser.filter_combo.count(), 1)

    def test_game_detection_uses_target_not_filename(self):
        self.assertIn("games", describe_file(self.root / "Game.url").kinds)
        self.assertNotIn("games", describe_file(self.root / "Website.url").kinds)
        broken = self.root / "Broken.url"
        broken.write_text("not an INI file")
        self.assertEqual(describe_file(broken).kinds, {"shortcuts", "ext:.url"})
        link = self.root / "Editor.lnk"
        link.touch()
        with patch("src.utils.file_listing.QFileInfo") as info:
            info.return_value.symLinkTarget.return_value = "C:/Apps/Editor.exe"
            self.assertIn("programs", describe_file(link).kinds)

    def test_unreadable_item_keeps_the_type_its_name_gives_it(self):
        locked = self.root / "Locked"
        locked.mkdir()
        real_stat = Path.stat

        def deny_locked(path, *args, **kwargs):
            if path == locked:
                raise PermissionError("Access is denied")
            return real_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", deny_locked):
            self.browser.create_list_items(force=True)
        self.assertEqual(self.browser._entry_cache[locked].kinds, {"no_extension"})
        labels = [label for label, value in filter_options(self.browser.entries)]
        self.assertIn("No extension (1)", labels)
        self.assertNotIn(" (1)", labels)

    def test_search_combines_with_filter_without_rescanning(self):
        with patch.object(self.browser, "traverse_level") as scan:
            self.search("GAME")
            self.assertEqual(self.names(), ["Game.url"])
            self.browser.filter_combo.setCurrentIndex(self.browser.filter_combo.findData("programs"))
            self.assertEqual(self.browser.status_label.text(), "0 of 5 items")
            self.assertEqual(self.browser.file_list_layout.itemAt(0).widget().text(), "No matching files.")
            scan.assert_not_called()

    def test_sort_size_and_name(self):
        entries = self.browser.entries
        self.assertEqual(visible_entries(entries, sort="size")[0].path.name, "Website.url")
        self.assertEqual(visible_entries(entries, sort="name_desc")[0].path.name, "Website.url")
        self.assertEqual(visible_entries(entries, sort="type")[0].path.name, "Folder")

    def test_search_edit_keeps_normal_typing_and_backspace(self):
        self.browser.show()
        self.browser.activateWindow()
        self.browser.settings_button.setFocus()
        self.app.processEvents()
        QTest.keyClick(self.browser.settings_button, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(self.app.focusWidget(), self.browser.search_edit)
        QTest.keyClicks(self.browser.search_edit, "Notes")
        QTest.keyClick(self.browser.search_edit, Qt.Key.Key_Backspace)
        self.assertEqual(self.browser.search_edit.text(), "Note")
        self.assertEqual(self.browser.current_folder, self.root)
        QTest.keyClick(self.browser.search_edit, Qt.Key.Key_Escape)
        self.assertFalse(self.browser.filter_menu.isVisible())
        self.assertEqual(self.browser.search_edit.text(), "Note")
        self.browser.filter_button.setFocus()
        QTest.keyClick(self.browser.filter_button, Qt.Key.Key_Escape)
        self.assertEqual(self.browser.search_edit.text(), "")
        self.assertTrue(self.browser.isVisible())

    def test_filter_popup_keeps_list_space_and_active_state(self):
        self.browser.resize(400, 640)
        self.browser.show()
        self.app.processEvents()
        before = self.browser.scroll_area.geometry()
        self.assertLess(before.top(), 110)
        self.browser.filter_button.click()
        self.app.processEvents()
        self.assertTrue(self.browser.filter_menu.isVisible())
        self.assertEqual(self.browser.scroll_area.geometry(), before)
        self.search("Notes")
        self.browser.filter_menu.done_button.click()
        self.assertFalse(self.browser.filter_menu.isVisible())
        self.assertTrue(self.browser.filter_button.isChecked())
        self.assertEqual(self.names(), ["Notes.TXT"])
        self.browser.filter_button.click()
        self.browser.filter_menu.clear_button.click()
        self.assertFalse(self.browser.filter_button.isChecked())
        self.assertEqual(len(self.names()), 5)

    def test_escape_closes_type_dropdown_before_filter_popup(self):
        self.browser.show()
        self.browser.activateWindow()
        self.browser.focus_search()
        combo = self.browser.filter_combo
        combo.setFocus()
        combo.showPopup()
        self.app.processEvents()
        QTest.keyClick(combo.view(), Qt.Key.Key_Escape)
        self.assertFalse(combo.view().isVisible())
        self.assertTrue(self.browser.filter_menu.isVisible())
        QTest.keyClick(combo, Qt.Key.Key_Escape)
        self.assertFalse(self.browser.filter_menu.isVisible())
        self.assertTrue(self.browser.isVisible())

    def test_filter_popup_reaches_its_dropdowns_from_the_keyboard(self):
        self.browser.show()
        self.browser.activateWindow()
        self.browser.focus_search()
        self.app.processEvents()
        self.assertEqual(self.app.focusWidget(), self.browser.search_edit)
        QTest.keyClick(self.browser.search_edit, Qt.Key.Key_Tab)
        self.assertEqual(self.app.focusWidget(), self.browser.filter_combo)
        QTest.keyClick(self.browser.filter_combo, Qt.Key.Key_Tab)
        self.assertEqual(self.app.focusWidget(), self.browser.sort_combo)

    def test_clicking_outside_closes_the_filter_popup(self):
        self.browser.show()
        self.browser.focus_search()
        self.app.processEvents()
        self.assertTrue(self.browser.filter_menu.isVisible())
        QTest.mouseClick(self.browser.filter_menu, Qt.MouseButton.LeftButton, pos=QPoint(-40, -40))
        self.assertFalse(self.browser.filter_menu.isVisible())

    def test_hiding_browser_closes_popup(self):
        self.browser.show()
        self.browser.focus_search()
        self.browser.hide()
        self.assertFalse(self.browser.filter_menu.isVisible())
        self.browser.show()
        self.assertFalse(self.browser.filter_menu.isVisible())

    def test_navigation_clears_query_and_refresh_keeps_it(self):
        self.browser.search_edit.setText("Notes")
        self.browser.refresh_files()
        self.assertEqual(self.browser.search_edit.text(), "Notes")
        self.browser.navigate_to(self.root / "Folder")
        self.assertEqual(self.browser.search_edit.text(), "")


if __name__ == "__main__":
    unittest.main()
