"""The places the panel can jump to: the user's own folders, and the drives under This PC.

Listing them never touches a drive. Drive letters and their kinds come from the local drive
table, so a network drive whose server is asleep still lists at once. The parts that do ask a
drive, its label and its share, are read on a worker by read_names and filled in as they land.
"""
import ctypes
import os
from dataclasses import dataclass
from pathlib import Path

from src.utils.desktop_paths import known_folder

# The user's folders besides the Desktop, in the order Windows 11 pins them.
USER_FOLDERS = (
    ("Downloads", "374DE290-123F-4565-9164-39C4925E467B"),
    ("Documents", "FDD39AD0-238F-46AF-ADB4-6C85480369C7"),
    ("Pictures", "33E28130-4E1E-4676-835A-98395C3BC3BB"),
    ("Music", "4BD8D571-6D19-48D3-BE97-422220080E43"),
    ("Videos", "18989B1D-99B5-455B-841C-AB7C74E4DDFC"),
)

DRIVE_KINDS = {2: "removable", 3: "fixed", 4: "network", 5: "optical", 6: "ram"}
# What Explorer calls a drive with no label of its own.
DEFAULT_NAMES = {"removable": "USB Drive", "fixed": "Local Disk", "network": "Network Drive",
                 "optical": "DVD Drive", "ram": "RAM Disk"}

SEM_FAILCRITICALERRORS = 0x0001
ERROR_CONNECTION_UNAVAIL = 1201


@dataclass
class Drive:
    root: Path
    kind: str
    label: str = ""
    remote: str = ""  # \server\share, for a mapped network drive
    connected: bool = True

    @property
    def letter(self) -> str:
        return str(self.root)[:2]

    @property
    def name(self) -> str:
        """As Explorer names it: 'Boot (C:)', or 'Media (\\NAS) (M:)' for a mapped share."""

        if self.remote:
            parent, _, share = self.remote.rstrip("\\").rpartition("\\")
            return f"{share} ({parent}) ({self.letter})"

        return f"{self.label or DEFAULT_NAMES[self.kind]} ({self.letter})"


def user_folders() -> list[tuple[str, Path]]:
    """Each user folder wherever it has been moved to; one Windows cannot resolve is left out."""

    folders = []
    for name, folder_id in USER_FOLDERS:
        path = known_folder(folder_id)
        if path is not None:
            folders.append((name, path))

    return folders


def drive_kind(root: str) -> str | None:
    """The kind of drive a root such as 'C:\\' is, from the local drive table: the drive is not asked.

    Only ever pass a bare root. Given any deeper path, Windows opens it to find its volume.
    """

    from ctypes import wintypes

    get_type = ctypes.windll.kernel32.GetDriveTypeW
    get_type.argtypes = [wintypes.LPCWSTR]
    get_type.restype = wintypes.UINT

    return DRIVE_KINDS.get(get_type(root))


def list_drives() -> list[Drive]:
    """Every drive letter and its kind. Both come from the local drive table: no drive is asked."""

    if os.name != "nt":
        return []
    drives = []
    for root in os.listdrives():
        kind = drive_kind(root)
        if kind is not None:
            drives.append(Drive(Path(root), kind))

    return drives


def typed_path(text: str, base: Path) -> Path | None:
    """What someone typed or pasted as a place, as a path; None if there is nothing to go to.

    Windows' Copy as path wraps a path in quotes, a variable such as %USERPROFILE% is spelled
    out, a drive letter alone means its root, and anything relative is taken from `base`.
    """

    text = os.path.expandvars(text.strip().strip('"').strip())
    if not text:
        return None
    if len(text) == 2 and text[1] == ":":
        text += "\\"
    path = Path(text)
    if not path.is_absolute():
        path = base / path

    return Path(os.path.normpath(path))


def is_remote(path) -> bool:
    """Whether a path lives on another machine, told from its spelling and the drive table alone."""

    drive = Path(path).drive
    if drive.startswith("\\\\"):
        return True  # \\server\share

    return os.name == "nt" and len(drive) == 2 and drive_kind(drive + "\\") == "network"


def server_name(path) -> str | None:
    """The server a bare \\\\server path names, with no share chosen on it; None for any other path."""

    drive = Path(path).drive.rstrip("\\")
    if drive.startswith("\\\\") and drive.count("\\") == 2:
        return drive[2:]

    return None


def server_root(path) -> Path | None:
    """\\\\server for a path on one of its shares, \\\\server\\share\\...; None for a server alone or a local path."""

    drive = Path(path).drive.rstrip("\\")
    if drive.startswith("\\\\") and drive.count("\\") == 3:
        return Path(drive.rpartition("\\")[0])

    return None


STYPE_SPECIAL = 0x80000000  # An administrative share, such as C$.


def enumerate_shares(server: str) -> list[tuple[str, int]]:
    """Every share a server offers, with its kind, straight from the server: only ever on a worker."""

    from ctypes import wintypes

    class ShareInfo(ctypes.Structure):
        _fields_ = [("netname", wintypes.LPWSTR), ("type", wintypes.DWORD), ("remark", wintypes.LPWSTR)]

    api = ctypes.WinDLL("netapi32")
    enumerate = api.NetShareEnum
    enumerate.argtypes = [wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    enumerate.restype = wintypes.DWORD
    buffer, read, total, resume = ctypes.c_void_p(), wintypes.DWORD(), wintypes.DWORD(), wintypes.DWORD(0)
    status = enumerate(server, 1, ctypes.byref(buffer), 0xFFFFFFFF, ctypes.byref(read), ctypes.byref(total),
                       ctypes.byref(resume))
    if status != 0:
        raise ctypes.WinError(status)  # A server not there is a FileNotFoundError, as a missing folder is.
    try:
        shares = ctypes.cast(buffer, ctypes.POINTER(ShareInfo * read.value)).contents
        return [(share.netname, share.type) for share in shares]
    finally:
        api.NetApiBufferFree(buffer)


def list_shares(server: str) -> list[str]:
    """The folders a server shares, as Explorer lists them at \\\\server: disk shares, none ending in $.

    Asks the server, so only ever on a worker; one that is asleep or not there takes seconds to say.
    """

    return sorted((name for name, kind in enumerate_shares(server)
                   if kind & 0x0FFFFFFF == 0 and not kind & STYPE_SPECIAL and not name.endswith("$")),
                  key=str.casefold)


def quiet_drive_errors():
    """Have this thread's reads of an empty drive fail, rather than raise an "insert a disk" dialog.

    An empty card reader or disc drive otherwise answers with that dialog, and holds the read until
    someone dismisses it. The mode belongs to the thread, and every worker is a new thread, so
    each worker that may touch a drive sets it for itself.
    """

    if os.name == "nt":
        ctypes.WinDLL("kernel32").SetThreadErrorMode(SEM_FAILCRITICALERRORS, None)


def read_space(root: Path) -> tuple[int, int] | None:
    """How much of a drive is free, and how big it is, in bytes; None if the drive will not say.

    Run it on a worker: a sleeping server holds this for the whole SMB timeout.
    """

    if os.name != "nt":
        return None
    from ctypes import wintypes

    quiet_drive_errors()
    space = ctypes.WinDLL("kernel32").GetDiskFreeSpaceExW
    space.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_ulonglong),
                      ctypes.POINTER(ctypes.c_ulonglong), ctypes.POINTER(ctypes.c_ulonglong)]
    space.restype = wintypes.BOOL
    free, total = ctypes.c_ulonglong(), ctypes.c_ulonglong()
    if not space(str(root), ctypes.byref(free), ctypes.byref(total), None):
        return None

    return free.value, total.value


def size_text(size: int) -> str:
    """A size as Explorer shows one: '412 GB', '1.82 TB', '96.3 MB'."""

    for unit in ("bytes", "KB", "MB", "GB", "TB", "PB"):
        if size < 1000 or unit == "PB":
            break
        size /= 1024
    if unit == "bytes":
        return f"{size:.0f} {unit}"
    # Three figures, as Explorer shows them: 1.82 TB, 96.3 MB, 412 GB.
    digits = 2 if size < 10 else 1 if size < 100 else 0

    return f"{size:.{digits}f} {unit}"


def read_names(drives: list[Drive]) -> dict[Path, tuple[str, str, bool]]:
    """Each drive's label, its share if mapped, and whether that share is connected.

    Run it on a worker: a sleeping server can hold these calls for the whole SMB timeout. A
    network drive is named by its share, as Explorer names it, so its label is never asked for.
    """

    if os.name != "nt":
        return {}
    from ctypes import wintypes

    quiet_drive_errors()
    volume = ctypes.WinDLL("kernel32").GetVolumeInformationW
    volume.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD, wintypes.LPDWORD,
                       wintypes.LPDWORD, wintypes.LPDWORD, wintypes.LPWSTR, wintypes.DWORD]
    volume.restype = wintypes.BOOL
    connection = ctypes.WinDLL("mpr").WNetGetConnectionW
    connection.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.LPDWORD]
    connection.restype = wintypes.DWORD
    names = {}
    for drive in drives:
        if drive.kind == "network":
            remote = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(remote))
            status = connection(drive.letter, remote, ctypes.byref(size))
            if status in (0, ERROR_CONNECTION_UNAVAIL):
                # A remembered mapping still names its share while its server is away.
                names[drive.root] = ("", remote.value, status == 0)
            continue
        label = ctypes.create_unicode_buffer(261)
        if volume(str(drive.root), label, len(label), None, None, None, None, 0):
            names[drive.root] = (label.value, "", True)

    return names
