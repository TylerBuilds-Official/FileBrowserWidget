"""File actions Windows performs for us: the Recycle Bin and the properties dialog."""
import ctypes
import os
from ctypes import wintypes
from pathlib import Path

FO_DELETE = 3
FOF_ALLOWUNDO = 0x0040
DE_OPCANCELLED = 0x4C7
SEE_MASK_INVOKEIDLIST = 0x0000000C
SW_SHOW = 5


class FileOperation(ctypes.Structure):
    _fields_ = [("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", ctypes.c_uint16),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", ctypes.c_void_p),
                ("lpszProgressTitle", wintypes.LPCWSTR)]


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD),
                ("fMask", ctypes.c_ulong),
                ("hwnd", wintypes.HWND),
                ("lpVerb", wintypes.LPCWSTR),
                ("lpFile", wintypes.LPCWSTR),
                ("lpParameters", wintypes.LPCWSTR),
                ("lpDirectory", wintypes.LPCWSTR),
                ("nShow", ctypes.c_int),
                ("hInstApp", wintypes.HINSTANCE),
                ("lpIDList", ctypes.c_void_p),
                ("lpClass", wintypes.LPCWSTR),
                ("hkeyClass", wintypes.HKEY),
                ("dwHotKey", wintypes.DWORD),
                ("hIcon", wintypes.HANDLE),
                ("hProcess", wintypes.HANDLE)]


def recycle(file):
    """Send a file to the Recycle Bin, so Windows can undo it. Returns an error string, or ''."""
    if os.name != "nt":
        return "The Recycle Bin is only available on Windows."
    path = str(Path(file).absolute())
    if not Path(path).exists():
        return "That item no longer exists."
    operation = FileOperation(None, FO_DELETE, path + "\0\0", None, FOF_ALLOWUNDO, False, None, None)
    result = ctypes.WinDLL("shell32").SHFileOperationW(ctypes.byref(operation))
    if operation.fAnyOperationsAborted or result == DE_OPCANCELLED:
        return ""  # The user answered no to Windows' own confirmation; nothing to report.
    if result != 0:
        return f"Windows could not delete this item (error {result})."
    return ""


def show_properties(file):
    """Open the Windows properties dialog. Returns an error string, or ''."""
    if os.name != "nt":
        return "The properties dialog is only available on Windows."
    path = str(Path(file).absolute())
    info = ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = SEE_MASK_INVOKEIDLIST
    info.lpVerb = "properties"
    info.lpFile = path
    info.nShow = SW_SHOW
    if not ctypes.WinDLL("shell32").ShellExecuteExW(ctypes.byref(info)):
        return "Windows could not open the properties for this item."
    return ""
