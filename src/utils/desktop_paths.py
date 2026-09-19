import ctypes
import os
from pathlib import Path
from uuid import UUID

from PyQt6.QtCore import QStandardPaths


def known_folder(folder_id):
    """Ask Windows for the redirected path without requiring it to be online."""
    if os.name != "nt":
        return None
    from ctypes import wintypes
    guid = (ctypes.c_ubyte * 16).from_buffer_copy(UUID(folder_id).bytes_le)
    shell = ctypes.WinDLL("shell32")
    get_path = shell.SHGetKnownFolderPath
    get_path.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE,
                        ctypes.POINTER(ctypes.c_wchar_p)]
    get_path.restype = ctypes.c_long
    free = ctypes.WinDLL("ole32").CoTaskMemFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = None
    result = ctypes.c_wchar_p()
    try:
        # KF_FLAG_DONT_VERIFY avoids probing a disconnected redirected share.
        status = get_path(ctypes.byref(guid), 0x4000, None, ctypes.byref(result))
        return Path(result.value) if status == 0 and result.value else None
    finally:
        if result:
            free(ctypes.cast(result, ctypes.c_void_p))


class DesktopPaths:
    def __init__(self):
        self.primary = known_folder("B4BFCC3A-DB2C-424C-B029-7FE99A87C641")
        if self.primary is None:
            self.primary = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
                                or Path.home() / "Desktop")
        self.public = known_folder("C4AA340D-F20F-4863-AFEF-F87EF2E6BA25")
        if self.public is None and os.name == "nt" and os.environ.get("PUBLIC"):
            self.public = Path(os.environ["PUBLIC"]) / "Desktop"

    def sources(self):
        paths = [self.primary]
        if self.public is not None and self.public != self.primary:
            paths.append(self.public)
        return paths

    def list_files(self, traverse):
        files, errors = {}, []
        readable = False
        for folder in self.sources():
            try:
                children = traverse(folder)
                readable = True
                for file in children:
                    # The user's item takes precedence over a common item.
                    files.setdefault(file.name.casefold(), file)
            except OSError as error:
                errors.append((folder, error))
        if not readable and errors:
            raise errors[0][1]
        return list(files.values()), errors
