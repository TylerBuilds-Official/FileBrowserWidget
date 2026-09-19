import os
import stat
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication
from src.utils.desktop_paths import DesktopPaths
from src.utils.file_listing import describe_file


class DesktopPathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def desktop(self, primary, public):
        with patch("src.utils.desktop_paths.known_folder", side_effect=[primary, public]):
            return DesktopPaths()

    def test_uses_configured_onedrive_or_network_location(self):
        for path in (Path("C:/Users/Test/OneDrive - Company/Desktop"), Path("//server/users/Test/Desktop")):
            with self.subTest(path=path):
                desktop = self.desktop(path, Path("C:/Users/Public/Desktop"))
                self.assertEqual(desktop.primary, path)
                self.assertEqual(desktop.sources(), [path, Path("C:/Users/Public/Desktop")])

    def test_combines_public_and_personal_with_personal_precedence(self):
        user, public = Path("C:/User/Desktop"), Path("C:/Public/Desktop")
        desktop = self.desktop(user, public)
        traverse = Mock(side_effect=[[user / "App.lnk"], [public / "APP.lnk", public / "Shared.lnk"]])
        files, errors = desktop.list_files(traverse)
        self.assertEqual(files, [user / "App.lnk", public / "Shared.lnk"])
        self.assertEqual(errors, [])

    def test_partial_failure_is_reported_without_losing_other_source(self):
        user, public = Path("C:/User/Desktop"), Path("C:/Public/Desktop")
        desktop = self.desktop(user, public)
        error = PermissionError("Offline share")
        traverse = Mock(side_effect=[error, [public / "Shared.lnk"]])
        files, errors = desktop.list_files(traverse)
        self.assertEqual(files, [public / "Shared.lnk"])
        self.assertEqual(errors, [(user, error)])
        self.assertEqual(traverse.call_count, 2)

    def test_total_failure_raises_and_duplicate_source_is_read_once(self):
        desktop = self.desktop(Path("C:/Desktop"), Path("c:/Desktop"))
        traverse = Mock(side_effect=FileNotFoundError("Missing"))
        with self.assertRaises(FileNotFoundError):
            desktop.list_files(traverse)
        traverse.assert_called_once()

    def test_known_folder_failure_uses_qt_path(self):
        with patch("src.utils.desktop_paths.known_folder", return_value=None), \
                patch("src.utils.desktop_paths.QStandardPaths.writableLocation", return_value="D:/Redirected/Desktop"):
            self.assertEqual(DesktopPaths().primary, Path("D:/Redirected/Desktop"))

    def test_cloud_placeholder_metadata_does_not_read_shortcut_content(self):
        info = SimpleNamespace(st_mode=stat.S_IFREG, st_mtime=1, st_mtime_ns=1,
                               st_ctime_ns=1, st_size=100, st_file_attributes=0x400000)
        with patch("src.utils.file_listing.read_shortcut") as read:
            entry = describe_file(Path("C:/Desktop/Game.url"), info)
            self.assertTrue(entry.online_only)
            self.assertIn("shortcuts", entry.kinds)
            read.assert_not_called()

    def test_file_stat_error_is_preserved_for_reporting(self):
        with patch.object(Path, "stat", side_effect=PermissionError("Access denied")):
            entry = describe_file(Path("C:/Desktop/Protected.exe"))
        self.assertIn("Access denied", entry.error)


if __name__ == "__main__":
    unittest.main()
