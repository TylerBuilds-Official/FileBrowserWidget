import os
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from src.ui.file_browser import FileBrowser
from src.ui.win_tray_app import WinTrayApp


class BrowserCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / (".cache-test-" + uuid4().hex)
        self.root.mkdir()
        self.addCleanup(self.cleanup)
        for i in range(20):
            (self.root / f"item-{i:02}.txt").write_text("text")
        self.browser = FileBrowser()
        self.browser.resize(400, 640)
        self.browser.create_list_items(self.root)
        self.drain_icons()

    def drain_icons(self):
        """Icons load a batch per event loop turn; tests want them all in place."""
        while self.browser._icon_queue:
            self.browser.fill_icons()

    def cleanup(self):
        self.browser.hide()
        self.browser.deleteLater()
        assert self.root.resolve().parent == Path(__file__).resolve().parent
        shutil.rmtree(self.root)

    def test_reopen_does_no_scan_or_icon_work(self):
        rows = dict(self.browser._rows)
        with patch.object(self.browser, "traverse_level") as scan, \
                patch.object(self.browser.icon_provider, "icon") as icons, \
                patch.object(Path, "stat") as stat:
            for _ in range(20):
                self.browser.ensure_loaded()
            scan.assert_not_called()
            icons.assert_not_called()
            stat.assert_not_called()
        self.assertEqual(self.browser._rows, rows)

    def test_filters_sort_and_extensions_reuse_widgets(self):
        rows = dict(self.browser._rows)
        with patch.object(self.browser, "traverse_level") as scan:
            self.browser.search_edit.setText("item-01")
            self.browser.search_edit.clear()
            self.browser.sort_combo.setCurrentIndex(1)
            self.browser.settings_modal.extensions_check.setChecked(True)
            scan.assert_not_called()
        self.assertEqual(self.browser._rows, rows)
        self.assertEqual(rows[self.root / "item-01.txt"].name_label._name, "item-01.txt")

    def test_rows_appear_before_their_icons_are_read(self):
        with patch.object(self.browser.icon_provider, "icon", wraps=self.browser.icon_provider.icon) as icons:
            self.browser.create_list_items(force=True)
            icons.assert_not_called()
            self.assertEqual(len(self.browser._icon_queue), 20)
            first = self.browser.file_list_layout.itemAt(0).widget()
            self.assertFalse(first.icon_label.pixmap().isNull())
            self.browser.fill_icons()
            self.assertEqual(icons.call_count, self.browser.ICON_BATCH)
        QTest.qWait(400)
        self.assertFalse(self.browser._icon_queue)
        self.assertIn(self.root / "item-00.txt", self.browser._icons)

    def test_changed_file_invalidates_only_its_metadata_and_icon(self):
        entries = dict(self.browser._entry_cache)
        changed = self.root / "item-00.txt"
        changed.write_text("a longer file")
        with patch.object(self.browser.icon_provider, "icon", wraps=self.browser.icon_provider.icon) as icons:
            self.browser.create_list_items()
            self.drain_icons()
            icons.assert_called_once_with(changed)
        self.assertIsNot(self.browser._entry_cache[changed], entries[changed])
        self.assertIs(self.browser._entry_cache[self.root / "item-01.txt"], entries[self.root / "item-01.txt"])

    def test_removed_hidden_rows_are_released(self):
        removed = self.root / "item-01.txt"
        self.browser.search_edit.setText("not-found")
        removed.unlink()
        self.browser.create_list_items()
        self.assertNotIn(removed, self.browser._rows)
        self.assertNotIn(removed, self.browser._icons)

    def test_rendering_again_does_not_ask_for_icons(self):
        self.browser.render_entries()
        with patch.object(self.browser.icon_provider, "icon") as icons:
            self.browser._rendered_state = None
            self.browser.render_entries()
            self.browser.settings_modal.extensions_check.setChecked(True)
            self.browser.toggle_favorite(self.root / "item-00.txt")
            icons.assert_not_called()

    def test_icons_survive_leaving_and_returning_to_a_folder(self):
        child = self.root / "Child"
        child.mkdir()
        (child / "other.txt").touch()
        self.browser.create_list_items()
        self.drain_icons()
        kept = self.root / "item-00.txt"
        self.browser.navigate_to(child)
        self.drain_icons()
        with patch.object(self.browser.icon_provider, "icon") as icons:
            self.browser.go_back()
            self.drain_icons()
            icons.assert_not_called()
        self.assertIn(kept, self.browser._icons)

    def test_hidden_files_are_left_out(self):
        hidden = self.root / "hidden.txt"
        hidden.write_text("secret")
        subprocess.run(["attrib", "+H", str(hidden)], check=True)
        self.browser.create_list_items()
        self.assertNotIn(hidden, self.browser._entry_cache)
        self.assertIn(self.root / "item-00.txt", self.browser._entry_cache)

    def test_unreadable_current_folder_offers_a_retry_and_reloads_on_reopen(self):
        with patch.object(self.browser, "traverse_level", side_effect=PermissionError("Access denied")):
            self.browser.create_list_items()
            self.assertEqual(self.browser.file_list_layout.itemAt(0).widget().text(),
                             "Could not open this folder.")
            retry = self.browser.file_list_layout.itemAt(2).widget()
            self.assertEqual(retry.text(), "Try again")
            self.assertTrue(self.browser.needs_scan())
        retry.click()
        self.assertIn(self.root / "item-00.txt", self.browser._entry_cache)

    def test_hidden_panel_releases_its_watches(self):
        self.browser.show()
        self.app.processEvents()
        self.assertTrue(self.browser.watcher.directories())
        self.browser.hide()
        self.assertEqual(self.browser.watcher.directories(), [])
        self.browser.show()
        self.app.processEvents()
        self.assertTrue(self.browser.watcher.directories())

    def test_hidden_panel_lets_explorer_rename_the_folder_above(self):
        child = self.root / "Child"
        child.mkdir()
        self.browser.create_list_items(child)
        self.browser.show()
        self.app.processEvents()
        moved = self.root.with_name(self.root.name + "-moved")
        with self.assertRaises(OSError):
            os.rename(self.root, moved)
        self.browser.hide()
        os.rename(self.root, moved)
        os.rename(moved, self.root)

    def test_reopening_an_unchanged_folder_stays_quiet_while_unwatched(self):
        self.browser.show()
        self.app.processEvents()
        self.browser.hide()
        with patch.object(self.browser, "traverse_level") as scan:
            self.browser.ensure_loaded()
            scan.assert_not_called()
        (self.root / "new-item.txt").touch()
        self.browser.ensure_loaded()
        self.assertIn(self.root / "new-item.txt", self.browser._entry_cache)

    def test_reopening_returns_to_the_desktop_and_shows_before_scanning(self):
        child = self.root / "Child"
        child.mkdir()
        self.browser.desktop_folder = self.root
        self.browser.navigate_to(child)
        self.browser.hide()
        app = SimpleNamespace(file_browser=self.browser, reposition_popup=lambda: None)
        with patch.object(self.browser, "create_list_items") as scan:
            WinTrayApp.show_browser(app)
            self.assertEqual(self.browser.current_folder, self.root)
            self.assertEqual(self.browser.folder_history, [])
            self.assertEqual(self.browser.file_list_layout.itemAt(0).widget().text(), "Loading…")
            scan.assert_not_called()
        QTest.qWait(20)
        self.assertIn(self.root / "item-00.txt", self.browser._entry_cache)

    def test_reopening_drops_history_even_when_it_ends_on_the_desktop(self):
        child = self.root / "Child"
        child.mkdir()
        self.browser.desktop_folder = self.root
        self.browser.navigate_to(child)
        self.browser.go_home()
        self.assertTrue(self.browser.folder_history)
        self.browser.reset_location()
        self.assertEqual(self.browser.folder_history, [])
        self.assertEqual(self.browser.forward_history, [])
        self.assertFalse(self.browser.back_button.isEnabled())

    def test_watcher_refreshes_visible_folder_and_hidden_changes_wait(self):
        self.browser.show()
        self.app.processEvents()
        created = self.root / "new.txt"
        created.touch()
        for _ in range(30):
            if created in self.browser._entry_cache:
                break
            QTest.qWait(30)
        self.assertIn(created, self.browser._entry_cache)
        self.browser.hide()
        another = self.root / "hidden.txt"
        another.touch()
        QTest.qWait(250)
        self.assertNotIn(another, self.browser._entry_cache)
        self.browser.ensure_loaded()
        self.assertIn(another, self.browser._entry_cache)


if __name__ == "__main__":
    unittest.main()
