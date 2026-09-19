import ctypes
import os
from ctypes import wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer


class GlobalHotkey(QAbstractNativeEventFilter):
    """Register Alt+B with Windows, including when this app has no focus."""

    HOTKEY_ID = 0xB001
    WM_HOTKEY = 0x0312
    MOD_ALT = 0x0001
    MOD_NOREPEAT = 0x4000

    def __init__(self, app, callback):
        super().__init__()
        self.app = app
        self.callback = callback
        self.registered = False
        self.error = ""
        self.user32 = None
        if os.name == "nt":
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                                  wintypes.UINT, wintypes.UINT]
            self.user32.RegisterHotKey.restype = wintypes.BOOL
            self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.UnregisterHotKey.restype = wintypes.BOOL
        self.app.aboutToQuit.connect(self.unregister)

    def register(self):
        if self.registered:
            return True
        if self.user32 is None:
            self.error = "Global Alt+B is only available on Windows."
            return False
        if not self.user32.RegisterHotKey(None, self.HOTKEY_ID,
                                         self.MOD_ALT | self.MOD_NOREPEAT, ord("B")):
            self.error = "Alt+B could not be registered. Another app may be using it."
            return False
        self.app.installNativeEventFilter(self)
        self.registered = True
        self.error = ""
        return True

    def unregister(self):
        if self.registered:
            self.user32.UnregisterHotKey(None, self.HOTKEY_ID)
            self.app.removeNativeEventFilter(self)
            self.registered = False

    def nativeEventFilter(self, event_type, message):
        if self.registered and event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            event = wintypes.MSG.from_address(int(message))
            if event.message == self.WM_HOTKEY and event.wParam == self.HOTKEY_ID:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0
