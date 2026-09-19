import os
import shutil
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QColor, QIcon, QImage
from PyQt6.QtWidgets import QApplication

from src.utils.file_icons import FileIcons


class FileIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.root = Path(__file__).resolve().parent / f".icon-test-{uuid4().hex}"
        self.root.mkdir()
        self.addCleanup(self.remove_fixture)
        self.icon_file = self.root / "game icon.ico"
        image = QImage(32, 32, QImage.Format.Format_ARGB32)
        image.fill(QColor("#12ab34"))
        self.assertTrue(image.save(str(self.icon_file)))
        self.icons = FileIcons()
        self.fallback = QIcon(str(self.icon_file))
        self.icons.provider = Mock()
        self.icons.provider.icon.return_value = self.fallback

    def remove_fixture(self):
        root = self.root.resolve()
        assert root.parent == Path(__file__).resolve().parent
        assert root.name.startswith(".icon-test-")
        shutil.rmtree(root)

    def shortcut(self, content, encoding="utf-8"):
        file = self.root / "Game.URL"
        file.write_text(content, encoding=encoding)
        return file

    def test_explicit_icon_overrides_file_type_icon(self):
        file = self.shortcut(f"[InternetShortcut]\nURL=steam://rungameid/123\nIconFile={self.icon_file}\nIconIndex=0\n")
        icon = self.icons.icon(file)
        self.assertEqual(icon.pixmap(32, 32).toImage().pixelColor(10, 10).name(), "#12ab34")
        self.icons.provider.icon.assert_not_called()

    def test_quoted_relative_icon_and_unicode_encodings(self):
        for encoding in ("utf-8-sig", "utf-16", "cp1252"):
            with self.subTest(encoding=encoding):
                file = self.shortcut('[InternetShortcut]\nComment=Café\nIconFile="game icon.ico"\n', encoding)
                self.assertFalse(self.icons.icon(file).pixmap(16, 16).isNull())
        self.icons.provider.icon.assert_not_called()

    def test_environment_variables_are_expanded_without_ini_interpolation(self):
        with patch.dict(os.environ, {"GAME_ICON_DIR": str(self.root)}):
            file = self.shortcut('[InternetShortcut]\nIconFile=%GAME_ICON_DIR%/game icon.ico\n')
            self.assertFalse(self.icons.icon(file).pixmap(16, 16).isNull())
        self.icons.provider.icon.assert_not_called()

    def test_missing_malformed_and_remote_icons_fall_back(self):
        for content in ('not an ini file', '[InternetShortcut]\n',
                        '[InternetShortcut]\nIconFile=missing.ico\n',
                        '[InternetShortcut]\nIconFile=https://example.com/icon.ico\n'):
            with self.subTest(content=content):
                self.icons.provider.reset_mock()
                file = self.shortcut(content)
                self.assertIs(self.icons.icon(file), self.fallback)
                self.icons.provider.icon.assert_called_once()

    def test_unreadable_image_falls_back(self):
        self.icon_file.write_bytes(b"not an image")
        file = self.shortcut(f"[InternetShortcut]\nIconFile={self.icon_file}\n")
        self.assertIs(self.icons.icon(file), self.fallback)

    def test_embedded_resource_index_is_used(self):
        executable = self.root / "game.exe"
        executable.write_bytes(b"fixture")
        file = self.shortcut(f"[InternetShortcut]\nIconFile={executable}\nIconIndex=-7\n")
        with patch.object(self.icons, "resource_icon", return_value=self.fallback) as extract:
            self.assertIs(self.icons.icon(file), self.fallback)
            extract.assert_called_once_with(executable, -7)
        self.icons.provider.icon.assert_not_called()

    def test_regular_files_use_qt_provider(self):
        self.assertIs(self.icons.icon(self.root / "notes.txt"), self.fallback)
        self.assertIs(self.icons.icon(self.root / "shortcut.lnk"), self.fallback)
        self.assertEqual(self.icons.provider.icon.call_count, 2)

    @unittest.skipUnless(os.name == "nt", "Windows icon resources")
    def test_native_resource_extraction_and_missing_resource(self):
        dll = Path(os.environ["SystemRoot"]) / "System32" / "shell32.dll"
        self.assertFalse(self.icons.resource_icon(dll, 0).pixmap(16, 16).isNull())
        self.assertTrue(self.icons.resource_icon(self.root / "missing.dll", 0).isNull())


if __name__ == "__main__":
    unittest.main()
