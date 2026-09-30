import os
import shutil
import threading
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
from support import drain_workers, settle


class FavoritesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".favorites-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        # Kept out of the browsed folder: QSettings writes it, and a lock file beside it, as it goes.
        self.settings_path = self.root.parent / f".favorites-settings-{uuid4().hex}.ini"
        self.settings = QSettings(str(self.settings_path), QSettings.Format.IniFormat)
        self.first = self.root / "Alpha.txt"
        self.last = self.root / "Zebra.txt"
        self.first.touch()
        self.last.touch()
        self.browser = FileBrowser(settings=self.settings)
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.desktop_folder = self.root  # The folder the panel opens on, where favorites lead.
        self.browser.create_list_items(self.root)
        settle(self.browser)

    def remove_fixture(self):
        drain_workers()
        self.settings.sync()
        self.settings_path.unlink(missing_ok=True)
        assert self.root.resolve().parent == Path(__file__).resolve().parent
        shutil.rmtree(self.root)

    def names(self):
        layout = self.browser.file_list_layout
        return [layout.itemAt(i).widget().path.name for i in range(layout.count())]

    def row_for(self, path):
        layout = self.browser.file_list_layout
        return next(layout.itemAt(i).widget() for i in range(layout.count()) if layout.itemAt(i).widget().path == path)

    def test_favorites_from_anywhere_lead_the_start_folder_and_only_there(self):
        # In the folder the panel opens on, every favorite heads the list, wherever it lives, in the
        # order it was starred. Drilled into any other folder the list keeps its order, as it does
        # everywhere with the setting off. Favorites elsewhere are described on a worker: one on a
        # share that is asleep must not hold the start folder.
        elsewhere = self.root.parent / f".favorites-elsewhere-{uuid4().hex}"
        elsewhere.mkdir()
        self.addCleanup(shutil.rmtree, elsewhere)
        kept = elsewhere / "Kept.txt"
        kept.write_text("x", encoding="utf-8")
        gone = elsewhere / "Gone.txt"
        for path in (gone, kept, self.last):
            self.browser.favorites.toggle(str(path))
        threads = []
        original = Path.stat

        def stat(path, *args, **kwargs):
            if path == kept:
                threads.append(threading.get_ident())
            return original(path, *args, **kwargs)

        with patch.object(Path, "stat", stat):
            self.browser.create_list_items(self.root)
            settle(self.browser)
            drain_workers()
        self.app.processEvents()
        self.assertEqual(self.names(), ["Kept.txt", "Zebra.txt", "Alpha.txt"])  # Gone is left to the menu.
        self.assertTrue(threads)
        self.assertNotIn(threading.get_ident(), threads)
        self.assertIs(self.browser.listed_as_folder(kept), False)  # Listed, so it opens without a look-up.
        row = self.row_for(kept)
        self.browser._rendered_state = None
        self.browser.render_entries(0)
        self.assertIs(self.row_for(kept), row)  # Its row is kept across renders like any other's.
        child = self.root / "Child"
        child.mkdir()
        (child / "Beta.txt").touch()
        (child / "Zulu.txt").touch()
        self.browser.favorites.toggle(str(child / "Zulu.txt"))
        self.browser.navigate_to(child)
        settle(self.browser)
        drain_workers()
        self.assertEqual(self.names(), ["Beta.txt", "Zulu.txt"])  # Starred, but drilled in: its own place.
        self.browser.go_back()
        settle(self.browser)
        drain_workers()
        self.app.processEvents()
        self.assertEqual(self.names(), ["Kept.txt", "Zebra.txt", "Zulu.txt", "Alpha.txt", "Child"])
        modal = self.browser.settings_modal
        modal.favorites_check.setChecked(False)
        self.assertEqual(self.names(), ["Alpha.txt", "Child", "Zebra.txt"])
        self.assertFalse(self.settings.value("files/favorites_on_top", type=bool))
        modal.favorites_check.setChecked(True)
        drain_workers()
        self.app.processEvents()
        self.assertEqual(self.names(), ["Kept.txt", "Zebra.txt", "Zulu.txt", "Alpha.txt", "Child"])
        self.browser.toggle_favorite(kept)  # Unstarred, a favorite from elsewhere leaves the list.
        self.assertEqual(self.names(), ["Zebra.txt", "Zulu.txt", "Alpha.txt", "Child"])
        self.assertNotIn(kept, self.browser._rows)  # And its row is released, as any unlisted item's is.

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
        settle(self.browser)
        opened = []
        self.browser.program_clicked.connect(opened.append)
        def choose(menu, position):
            menu.actions()[0].trigger()
        with patch("src.ui.file_browser.QMenu.exec", choose):
            self.browser.show_favorites_menu()
        drain_workers()  # A favorite is looked up on a worker before it opens.
        self.assertEqual(opened, [str(self.last)])
        self.last.unlink()
        self.browser.open_favorite(self.last)
        drain_workers()
        self.assertEqual(self.browser.status_label.text(), "Favorite no longer exists.")
        self.browser.toggle_favorite(self.last)
        self.assertFalse(Favorites(self.settings).contains(self.last))

    def test_desktop_button_and_breadcrumb_keep_history(self):
        folder = self.root / "Child"
        folder.mkdir()
        self.browser.desktop_folder = self.root
        self.browser.navigate_to(folder)
        settle(self.browser)
        breadcrumb = self.browser.path_label
        breadcrumb.linkActivated.emit(str(breadcrumb.paths.index(self.root)))
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)
        self.browser.go_back()
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, folder)
        self.browser.home_button.click()
        settle(self.browser)
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

    def test_crumbs_on_a_share_start_at_its_server(self):
        # A share is the top of its path, but the panel can list the server above it, so the crumbs
        # go there too; the server and the share are called by their names, as Explorer calls them.
        widget = Breadcrumbs(r"\\nas\Media\Photos")
        self.addCleanup(widget.deleteLater)
        widget.resize(4000, 26)
        widget.update_links()
        self.assertEqual(widget.paths, [Path(r"\\nas"), Path(r"\\nas") / "Media", Path(r"\\nas\Media\Photos")])
        self.assertEqual([Breadcrumbs.label(path) for path in widget.paths], ["nas", "Media", "Photos"])
        chosen = []
        widget.folder_clicked.connect(chosen.append)
        widget.open_link("0")
        self.assertEqual(chosen, [Path(r"\\nas")])
        widget.set_name(r"\\nas")
        self.assertEqual(widget.paths, [Path(r"\\nas")])
        self.assertEqual(Breadcrumbs.label(Path("C:\\")), "C:\\")


class FavoritesKeyTests(unittest.TestCase):
    def test_a_path_asked_about_again_is_keyed_once(self):
        # contains() runs several times per row on every render, and the key asks Windows for the
        # full path each time; a path already asked about is answered from its remembered key.
        keyed = []
        original = Favorites.key
        with patch.object(Favorites, "key", staticmethod(lambda path: keyed.append(path) or original(path))):
            favorites = Favorites()
            path = Path(__file__).resolve()
            self.assertEqual([favorites.contains(path) for _ in range(3)], [False, False, False])
            self.assertEqual(keyed.count(path), 1)
            favorites.toggle(path)  # Keys the path once itself, then the saved list by its strings.
            self.assertEqual([favorites.contains(path) for _ in range(3)], [True, True, True])
            self.assertEqual(keyed.count(path), 2)


if __name__ == "__main__":
    unittest.main()
