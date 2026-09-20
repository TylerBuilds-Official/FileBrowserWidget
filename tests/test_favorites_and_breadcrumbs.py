import os
import shutil
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton

from src.ui.file_browser import FileBrowser
from src.ui.breadcrumbs import Breadcrumbs
from src.utils.favorites import Favorites


class FavoritesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".favorites-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        self.settings = QSettings(str(self.root / "settings.ini"), QSettings.Format.IniFormat)
        self.first = self.root / "Alpha.txt"
        self.last = self.root / "Zebra.txt"
        self.first.touch()
        self.last.touch()
        self.browser = FileBrowser(settings=self.settings)
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.create_list_items(self.root)

    def remove_fixture(self):
        self.settings.sync()
        assert self.root.resolve().parent == Path(__file__).resolve().parent
        shutil.rmtree(self.root)

    def test_star_pins_without_opening_and_persists(self):
        opened = []
        self.browser.program_clicked.connect(opened.append)
        layout = self.browser.file_list_layout
        row = next(layout.itemAt(i).widget() for i in range(layout.count())
                   if layout.itemAt(i).widget().toolTip() == str(self.last))
        row.findChild(QPushButton).click()
        self.assertEqual(opened, [])
        self.assertEqual(layout.itemAt(0).widget().toolTip(), str(self.last))
        saved = Favorites(self.settings)
        self.assertTrue(saved.contains(self.last))
        self.assertEqual(saved.files()[0].name, "Zebra.txt")
        self.browser.search_edit.setText("Alpha")
        QTest.qWait(FileBrowser.SEARCH_DELAY + 50)
        self.assertEqual(layout.count(), 1)
        self.assertEqual(layout.itemAt(0).widget().toolTip(), str(self.first))

    def test_star_is_shown_when_pinned_and_hidden_until_the_row_is_used(self):
        self.browser.show()
        self.browser.activateWindow()
        self.app.processEvents()
        layout = self.browser.file_list_layout
        rows = {layout.itemAt(i).widget().toolTip(): layout.itemAt(i).widget() for i in range(layout.count())}
        quiet = rows[str(self.first)]
        self.assertEqual(quiet.star_button.property("quiet"), "true")
        quiet.setFocus()
        self.assertEqual(quiet.star_button.property("quiet"), "false")
        self.browser.toggle_favorite(self.last)
        pinned = next(layout.itemAt(i).widget() for i in range(layout.count())
                      if layout.itemAt(i).widget().toolTip() == str(self.last))
        self.assertEqual(pinned.star_button.property("pinned"), "true")
        self.assertEqual(pinned.star_button.property("quiet"), "false")

    def test_favorites_open_across_folders_and_missing_can_be_removed(self):
        self.browser.toggle_favorite(self.last)
        folder = self.root / "Child"
        folder.mkdir()
        self.browser.navigate_to(folder)
        opened = []
        self.browser.program_clicked.connect(opened.append)
        def choose(menu, position):
            menu.actions()[0].trigger()
        with patch("src.ui.file_browser.QMenu.exec", choose):
            self.browser.show_favorites_menu()
        self.assertEqual(opened, [str(self.last)])
        self.last.unlink()
        self.browser.open_favorite(self.last)
        self.assertEqual(self.browser.status_label.text(), "Favorite no longer exists.")
        self.browser.toggle_favorite(self.last)
        self.assertFalse(Favorites(self.settings).contains(self.last))

    def test_desktop_button_and_breadcrumb_keep_history(self):
        folder = self.root / "Child"
        folder.mkdir()
        self.browser.desktop_folder = self.root
        self.browser.navigate_to(folder)
        breadcrumb = self.browser.path_label
        breadcrumb.linkActivated.emit(str(breadcrumb.paths.index(self.root)))
        self.assertEqual(self.browser.current_folder, self.root)
        self.browser.go_back()
        self.assertEqual(self.browser.current_folder, folder)
        self.browser.home_button.click()
        self.assertEqual(self.browser.current_folder, self.root)

    def test_breadcrumb_overflow_escapes_names_and_opens_ancestor(self):
        path = self.root / "A&B" / "Long child folder" / "Another long folder"
        widget = Breadcrumbs(path)
        self.addCleanup(widget.deleteLater)
        widget.resize(160, 26)
        widget.update_links()
        self.assertTrue(widget.hidden_paths)
        chosen = []
        widget.folder_clicked.connect(chosen.append)
        def choose(menu, position):
            menu.actions()[-1].trigger()
        with patch("src.ui.breadcrumbs.QMenu.exec", choose):
            widget.open_link("more")
        self.assertEqual(chosen, [widget.hidden_paths[-1]])
        widget.resize(4000, 26)
        widget.update_links()
        self.assertIn("A&amp;B", widget.text())


if __name__ == "__main__":
    unittest.main()
