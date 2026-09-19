import configparser
import ctypes
import os
from pathlib import Path

from PyQt6.QtCore import QFileInfo
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QFileIconProvider


class FileIcons:
    """Use a URL shortcut's own icon before asking Qt for a file-type icon."""

    def __init__(self):
        self.provider = QFileIconProvider()

    def icon(self, file: str | Path) -> QIcon:
        file = Path(file)
        if file.suffix.lower() == ".url":
            icon = self.shortcut_icon(file)
            if not icon.isNull():
                return icon
        return self.provider.icon(QFileInfo(str(file)))

    def shortcut_icon(self, file: Path) -> QIcon:
        try:
            data = file.read_bytes()
            if data.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = data.decode("utf-16")
            else:
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeDecodeError:
                    text = data.decode("mbcs" if os.name == "nt" else "cp1252")
            shortcut = configparser.ConfigParser(interpolation=None, strict=False)
            shortcut.read_string(text)
            location = shortcut.get("InternetShortcut", "IconFile", fallback="").strip().strip('"')
            if not location or "://" in location:
                return QIcon()
            icon_file = Path(os.path.expandvars(location))
            if not icon_file.is_absolute():
                icon_file = file.parent / icon_file
            if not icon_file.is_file():
                return QIcon()
            if icon_file.suffix.lower() in (".exe", ".dll", ".icl"):
                index = shortcut.getint("InternetShortcut", "IconIndex", fallback=0)
                return self.resource_icon(icon_file, index)
            # Check the pixmap too: QIcon can be non-null for an unreadable image.
            icon = QIcon(str(icon_file))
            return icon if not icon.pixmap(32, 32).isNull() else QIcon()
        except (OSError, UnicodeError, ValueError, configparser.Error):
            return QIcon()

    @staticmethod
    def resource_icon(file: Path, index: int) -> QIcon:
        """Extract an embedded Windows icon without loading/running the program."""
        if os.name != "nt":
            return QIcon()
        from ctypes import wintypes

        extract = ctypes.windll.shell32.ExtractIconExW
        extract.argtypes = [wintypes.LPCWSTR, ctypes.c_int,
                            ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON),
                            wintypes.UINT]
        extract.restype = wintypes.UINT
        destroy = ctypes.windll.user32.DestroyIcon
        destroy.argtypes = [wintypes.HICON]
        destroy.restype = wintypes.BOOL
        large, small = wintypes.HICON(), wintypes.HICON()
        icon = QIcon()
        try:
            extract(str(file), index, ctypes.byref(large), ctypes.byref(small), 1)
            for handle in (large, small):
                if handle.value:
                    image = QImage.fromHICON(handle.value)
                    if not image.isNull():
                        icon.addPixmap(QPixmap.fromImage(image))
        finally:
            for handle in (large, small):
                if handle.value:
                    destroy(handle)
        return icon
