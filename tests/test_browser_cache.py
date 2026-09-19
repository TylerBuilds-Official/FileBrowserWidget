import os
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest
from src.ui.file_browser import FileBrowser


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

    def test_changed_file_invalidates_only_its_metadata_and_icon(self):
        entries = dict(self.browser._entry_cache)
        changed = self.root / "item-00.txt"
        changed.write_text("a longer file")
        with patch.object(self.browser.icon_provider, "icon", wraps=self.browser.icon_provider.icon) as icons:
            self.browser.create_list_items()
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
