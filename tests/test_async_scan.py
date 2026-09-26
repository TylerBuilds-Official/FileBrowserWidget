import os
import shutil
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QThread
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.ui.file_browser import FileBrowser
from support import drain_workers, settle


class AsyncScanTests(unittest.TestCase):
    """Folders are read on a worker: the panel stays live, and the newest request wins."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".async-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        self.slow = self.root / "Slow"
        self.fast = self.root / "Fast"
        for folder in (self.slow, self.fast):
            folder.mkdir()
            (folder / f"{folder.name.lower()}.txt").write_text("x", encoding="utf-8")
        self.browser = FileBrowser()
        self.browser.resize(400, 640)
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.desktop_folder = self.root
        self.browser.create_list_items(self.root)
        settle(self.browser)

    def remove_fixture(self):
        drain_workers()  # A worker still reading must not have the folder vanish under it.
        root = self.root.resolve()
        assert root.parent == Path(__file__).resolve().parent
        shutil.rmtree(root)

    def slowed(self, folder, seconds):
        """traverse_level, except that reading `folder` takes `seconds`."""
        real = FileBrowser.traverse_level

        def traverse(path):
            if Path(path) == folder:
                time.sleep(seconds)
            return real(path)

        return traverse

    def names(self):
        return [entry.path.name for entry in self.browser.entries]

    def test_the_folder_is_read_off_the_ui_thread(self):
        threads = []
        real = FileBrowser.traverse_level

        def traverse(path):
            threads.append(QThread.currentThread())
            return real(path)

        with patch.object(self.browser, "traverse_level", traverse):
            self.browser.navigate_to(self.fast)
            settle(self.browser)
        self.assertTrue(threads)
        self.assertNotEqual(threads[0], self.app.thread())
        self.assertEqual(self.browser.current_folder, self.fast)

    def test_a_slow_folder_leaves_the_panel_live_and_says_so(self):
        with patch.object(self.browser, "traverse_level", self.slowed(self.slow, 0.4)):
            started = time.monotonic()
            self.browser.navigate_to(self.slow)
            self.assertLess(time.monotonic() - started, 0.1)  # Returned at once, not after the read.
            self.assertEqual(self.browser.current_folder, self.root)  # Still showing where it was.
            QTest.qWait(250)
            self.assertEqual(self.browser.status_label.text(), "Loading\u2026")
            settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.slow)
        self.assertEqual(self.names(), ["slow.txt"])

    def test_the_newest_request_wins_over_a_slower_older_one(self):
        with patch.object(self.browser, "traverse_level", self.slowed(self.slow, 0.4)):
            self.browser.navigate_to(self.slow)
            self.browser.navigate_to(self.fast)
            settle(self.browser)
            drain_workers()  # Let the slow read finish too, and land late.
        self.assertEqual(self.browser.current_folder, self.fast)
        self.assertEqual(self.names(), ["fast.txt"])
        self.assertEqual([folder for folder, _ in self.browser.folder_history], [self.root])

    def test_a_background_refresh_never_cancels_a_navigation(self):
        self.browser.show()
        self.app.processEvents()
        with patch.object(self.browser, "traverse_level", self.slowed(self.slow, 0.3)):
            self.browser.navigate_to(self.slow)
            self.browser.mark_dirty()  # The watcher reports a change mid-read,
            self.browser.refresh_if_visible()  # and its refresh comes due.
            settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.slow)
        self.assertEqual([folder for folder, _ in self.browser.folder_history], [self.root])

    def test_a_change_during_a_read_is_not_lost(self):
        with patch.object(self.browser, "traverse_level", self.slowed(self.root, 0.3)):
            self.browser.create_list_items()
            self.browser.mark_dirty()  # Something changed after the worker started reading.
            settle(self.browser)
        self.assertTrue(self.browser._dirty)  # So the next refresh still reads again.
        self.browser.create_list_items()
        settle(self.browser)
        self.assertFalse(self.browser._dirty)

    def test_reopening_drops_a_read_still_in_flight(self):
        with patch.object(self.browser, "traverse_level", self.slowed(self.slow, 0.3)):
            self.browser.navigate_to(self.slow)
            self.browser.reset_location()  # Closed and reopened before the folder was read.
            drain_workers()
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(self.browser.folder_history, [])


if __name__ == "__main__":
    unittest.main()
