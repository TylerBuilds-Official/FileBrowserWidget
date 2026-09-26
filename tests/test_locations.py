import ctypes
import os
import shutil
import threading
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
from src.utils import locations
from src.utils.locations import Drive
from support import drain_workers, settle


class DriveTests(unittest.TestCase):
    """Drives are named as Explorer names them, and listing them asks no drive anything."""

    def test_a_drive_is_named_by_its_label_and_letter(self):
        self.assertEqual(Drive(Path("C:\\"), "fixed", "Boot").name, "Boot (C:)")

    def test_a_drive_without_a_label_is_named_for_its_kind(self):
        self.assertEqual(Drive(Path("D:\\"), "fixed").name, "Local Disk (D:)")
        self.assertEqual(Drive(Path("E:\\"), "removable").name, "USB Drive (E:)")
        self.assertEqual(Drive(Path("F:\\"), "optical").name, "DVD Drive (F:)")

    def test_a_mapped_share_is_named_for_the_share_then_where_it_lives(self):
        self.assertEqual(Drive(Path("M:\\"), "network", remote=r"\\nas\Media").name, r"Media (\\nas) (M:)")
        deeper = Drive(Path("P:\\"), "network", remote="\\\\files\\Projects\\2026\\")
        self.assertEqual(deeper.name, r"2026 (\\files\Projects) (P:)")

    def test_the_system_drive_is_listed_as_a_fixed_drive_with_its_label(self):
        system = Path(os.environ["SystemDrive"] + "\\")
        drives = {drive.root: drive for drive in locations.list_drives()}
        self.assertEqual(drives[system].kind, "fixed")
        label, remote, connected = locations.read_names([drives[system]])[system]
        self.assertEqual((remote, connected), ("", True))

    def test_a_share_is_on_another_machine_and_the_system_drive_is_not(self):
        self.assertTrue(locations.is_remote(r"\\nas\Media\Photos"))
        self.assertFalse(locations.is_remote(os.environ["SystemDrive"] + "\\Windows"))

    def test_a_mapped_letter_is_on_another_machine_and_only_its_bare_root_is_asked(self):
        with patch("src.utils.locations.drive_kind", return_value="network") as kind:
            self.assertTrue(locations.is_remote(Path("M:\\Films\\2026")))
        kind.assert_called_once_with("M:\\")

    def test_quieting_drive_errors_holds_for_the_thread_that_asks(self):
        kernel = ctypes.WinDLL("kernel32")
        modes = []

        def worker():
            kernel.SetThreadErrorMode(0, None)  # Whatever this process inherited, start from nothing.
            modes.append(kernel.GetThreadErrorMode())
            locations.quiet_drive_errors()
            modes.append(kernel.GetThreadErrorMode())

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join()
        self.assertEqual(modes[0] & locations.SEM_FAILCRITICALERRORS, 0)
        self.assertTrue(modes[1] & locations.SEM_FAILCRITICALERRORS)


class LocationsMenuTests(unittest.TestCase):
    """The locations menu opens at once and fills in what it reads; no pick waits on a drive."""

    GO_TO = "Go to path\tCtrl+L"  # As drawn: Qt leaves the ellipsis out of an action's plain text.

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".locations-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        # Folders in the fixture stand in for the user's folders and for drive roots.
        self.documents = self.root / "Documents"
        self.disk = self.root / "Disk"
        self.share = self.root / "Share"
        for folder in (self.documents, self.disk, self.share):
            folder.mkdir()
            (folder / "inside.txt").touch()
        self.drives = [Drive(self.disk, "fixed"), Drive(self.share, "network")]
        self.names = {self.disk: ("Games & Media", "", True), self.share: ("", r"\\nas\Media", False)}
        # read_names is looked up on the worker, which can run after a test's own patch has gone;
        # this one stays for the whole test, so no real drive is ever asked.
        for name, value in (("user_folders", [("Documents", self.documents)]), ("list_drives", self.drives),
                            ("read_names", {})):
            patcher = patch(f"src.utils.locations.{name}", return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(drain_workers)  # Cleanups run last-first: the workers finish before the stand-ins go.
        self.browser = FileBrowser()
        self.addCleanup(self.browser.deleteLater)
        self.addCleanup(self.browser.hide)
        self.browser.desktop_folder = self.root
        self.browser.create_list_items(self.root)
        settle(self.browser)
        drain_workers()  # The list's own icon reads, so only the menu's are counted.

    def remove_fixture(self):
        drain_workers()  # Name and icon reads outlive the menu that asked for them.
        root = self.root.resolve()
        assert root.parent == Path(__file__).resolve().parent
        shutil.rmtree(root)

    def open_menu(self, inside):
        """Open the menu, running `inside(menu)` while it is up, as exec would."""
        with patch("src.ui.file_browser.QMenu.exec", lambda menu, position: inside(menu)):
            self.browser.show_locations_menu()

    @staticmethod
    def shown(menu):
        """What the menu shows: separators as dashes, and each name as drawn, mnemonics and all."""
        return ["-" if action.isSeparator() else action.iconText() for action in menu.actions()]

    def wait_for(self, condition, timeout=5.0):
        deadline = time.monotonic() + timeout
        while not condition():
            QTest.qWait(5)
            self.assertLess(time.monotonic(), deadline, "it never happened")

    def choose(self, name):
        def inside(menu):
            next(action for action in menu.actions() if action.iconText() == name).trigger()
        return inside

    def test_it_opens_on_the_drive_kinds_and_names_them_as_the_names_land(self):
        release = threading.Event()

        def slow_names(drives):
            release.wait(5)
            return self.names

        seen = []

        def inside(menu):
            seen.append((time.monotonic() - started, self.shown(menu)))
            release.set()
            self.wait_for(lambda: self.shown(menu) != seen[0][1])
            seen.append((0, self.shown(menu)))

        with patch("src.utils.locations.read_names", slow_names):
            started = time.monotonic()
            self.open_menu(inside)
        (waited, cold), (_, warm) = seen
        self.assertLess(waited, 1.0)  # Up at once, not after the names.
        disk, share = (drive.name for drive in self.drives)
        self.assertEqual(cold, ["Desktop", "Documents", "-", disk, "-", share, "-", self.GO_TO])
        disk = Drive(self.disk, "fixed", "Games & Media").name
        share = Drive(self.share, "network", remote=r"\\nas\Media").name
        self.assertEqual(warm, ["Desktop", "Documents", "-", disk, "-", share, "-", self.GO_TO])
        self.assertIn("Games & Media", disk)  # The ampersand is drawn, not taken as a mnemonic.

    def test_it_reopens_on_the_names_already_read(self):
        with patch("src.utils.locations.read_names", return_value=self.names):
            self.open_menu(lambda menu: None)
            drain_workers()  # They land after the menu has closed, and are kept all the same.
        seen = []
        blocked = threading.Event()
        with patch("src.utils.locations.read_names", lambda drives: blocked.wait(5) and {}):
            self.open_menu(lambda menu: seen.append(self.shown(menu)))
            blocked.set()
        self.assertEqual(seen[0][3], Drive(self.disk, "fixed", "Games & Media").name)
        self.assertEqual(seen[0][5], Drive(self.share, "network", remote=r"\\nas\Media").name)

    def test_a_disconnected_share_is_pictured_as_one(self):
        with patch("src.utils.locations.read_names", return_value=self.names):
            self.open_menu(lambda menu: None)
            drain_workers()
            icons = {}
            self.open_menu(lambda menu: icons.update((action.iconText(), action.icon().cacheKey())
                                                     for action in menu.actions()))
        connected = self.browser.drive_icon(Drive(self.share, "network"))
        disconnected = self.browser.drive_icon(Drive(self.share, "network", connected=False))
        self.assertFalse(disconnected.isNull())
        self.assertNotEqual(disconnected.cacheKey(), connected.cacheKey())
        self.assertEqual(icons[Drive(self.share, "network", remote=r"\\nas\Media").name], disconnected.cacheKey())

    def test_choosing_a_drive_opens_it(self):
        with patch("src.utils.locations.read_names", return_value={}):
            self.open_menu(self.choose(self.drives[0].name))
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.disk)
        self.assertEqual([folder for folder, _ in self.browser.folder_history], [self.root])

    def test_a_drive_that_cannot_be_read_leaves_the_panel_where_it_was(self):
        empty = Drive(self.root / "Empty", "removable")  # A card reader with no card in it.
        self.drives.append(empty)
        with patch("src.utils.locations.read_names", return_value={}):
            self.open_menu(self.choose(empty.name))
        settle(self.browser)
        self.assertEqual(self.browser.current_folder, self.root)
        self.assertEqual(self.browser.status_label.text(), "Could not open this folder.")
        self.assertEqual(self.browser.folder_history, [])

    def test_folder_icons_are_read_off_the_ui_thread_and_only_once(self):
        calls = []
        real = self.browser.icon_provider.icon

        def record(path):
            calls.append((Path(path), QThread.currentThread()))
            return real(path)

        with patch.object(self.browser.icon_provider, "icon", side_effect=record), \
                patch("src.utils.locations.read_names", return_value={}):
            self.open_menu(lambda menu: None)
            drain_workers()
            self.assertEqual(sorted(path for path, _ in calls), sorted([self.root, self.documents]))
            self.assertNotIn(self.app.thread(), [thread for _, thread in calls])
            self.open_menu(lambda menu: None)
            drain_workers()
        self.assertEqual(len(calls), 2)  # The second time, every icon came from the cache.

    def test_a_drive_root_is_titled_as_explorer_names_it_once_its_label_is_read(self):
        root, other = Path("Q:\\"), Path("R:\\")
        labels = {root: ("Backup", "", True), other: ("Old", "", True)}
        with patch("src.utils.locations.drive_kind", return_value="fixed"), \
                patch("src.utils.locations.read_names", lambda drives: {d.root: labels[d.root] for d in drives}):
            self.browser.current_folder = root
            self.browser.show_location(root)
            self.assertEqual(self.browser.title_label._name, "Local Disk (Q:)")  # By its kind, at once,
            drain_workers()
            self.assertEqual(self.browser.title_label._name, "Backup (Q:)")  # then by its label.
            self.assertEqual(self.browser.title_label.toolTip(), "Q:\\")
            # A label that lands after the panel has moved on leaves the new title alone.
            self.browser.current_folder = other
            self.browser.show_location(other)
            self.browser.current_folder = self.root
            self.browser.show_location(self.root)
            drain_workers()
        self.assertEqual(self.browser.title_label._name, "Desktop")

    def test_a_share_is_titled_by_its_own_name(self):
        self.browser.show_location(Path("\\\\nas\\Media\\"))
        self.assertEqual(self.browser.title_label._name, "Media")

    def test_the_folder_read_quiets_drive_errors_on_its_own_thread(self):
        threads = []
        with patch("src.utils.locations.quiet_drive_errors", lambda: threads.append(QThread.currentThread())):
            self.browser.navigate_to(self.disk)
            settle(self.browser)
        self.assertTrue(threads)
        self.assertNotIn(self.app.thread(), threads)


if __name__ == "__main__":
    unittest.main()
