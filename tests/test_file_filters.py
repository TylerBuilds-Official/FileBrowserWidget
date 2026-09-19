import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
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

    def test_search_combines_with_filter_without_rescanning(self):
        with patch.object(self.browser, "traverse_level") as scan:
            self.browser.search_edit.setText("GAME")
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
        self.assertEqual(self.browser.search_edit.text(), "")
        self.assertTrue(self.browser.isVisible())

    def test_navigation_clears_query_and_refresh_keeps_it(self):
        self.browser.search_edit.setText("Notes")
        self.browser.refresh_files()
        self.assertEqual(self.browser.search_edit.text(), "Notes")
        self.browser.navigate_to(self.root / "Folder")
        self.assertEqual(self.browser.search_edit.text(), "")


if __name__ == "__main__":
    unittest.main()
