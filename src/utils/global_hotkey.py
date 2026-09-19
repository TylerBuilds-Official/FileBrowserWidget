import ctypes
import os
from ctypes import wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter, QTimer, Qt
from PyQt6.QtGui import QKeySequence


class GlobalHotkey(QAbstractNativeEventFilter):
    """Register a configurable shortcut with Windows, even without app focus."""

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
        self.sequence = "Alt+B"
        self._hotkey_id = self.HOTKEY_ID
        self.user32 = None
        if os.name == "nt":
            self.user32 = ctypes.WinDLL("user32", use_last_error=True)
            self.user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                                  wintypes.UINT, wintypes.UINT]
            self.user32.RegisterHotKey.restype = wintypes.BOOL
            self.user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            self.user32.UnregisterHotKey.restype = wintypes.BOOL
        self.app.aboutToQuit.connect(self.unregister)

    @staticmethod
    def key_codes(sequence):
        keys = QKeySequence(sequence)
        if keys.count() != 1:
            raise ValueError("Choose one key combination, such as Alt+B.")
        combination = keys[0]
        modifiers = combination.keyboardModifiers()
        allowed = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ShiftModifier
        if modifiers & ~allowed or not modifiers & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            raise ValueError("Include Ctrl or Alt, optionally with Shift.")
        key = combination.key()
        if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            virtual_key = int(key)
        elif Qt.Key.Key_F1 <= key <= Qt.Key.Key_F24 and key != Qt.Key.Key_F12:
            virtual_key = 0x70 + int(key) - int(Qt.Key.Key_F1)
        else:
            raise ValueError("Use a letter, number, or function key (except F12).")
        native_modifiers = GlobalHotkey.MOD_NOREPEAT
        for qt_modifier, native in ((Qt.KeyboardModifier.AltModifier, 1),
                                    (Qt.KeyboardModifier.ControlModifier, 2),
                                    (Qt.KeyboardModifier.ShiftModifier, 4)):
            if modifiers & qt_modifier:
                native_modifiers |= native
        return keys.toString(QKeySequence.SequenceFormat.PortableText), native_modifiers, virtual_key

    def register(self, sequence="Alt+B"):
        try:
            sequence, modifiers, key = self.key_codes(sequence)
        except ValueError as error:
            self.error = str(error)
            return False
        if self.registered and sequence == self.sequence:
            self.error = ""
            return True
        if self.user32 is None:
            self.error = "Global shortcuts are only available on Windows."
            return False
        # Register first so a conflict never disables the user's working shortcut.
        new_id = self.HOTKEY_ID
        if self.registered and self._hotkey_id == self.HOTKEY_ID:
            new_id += 1
        if not self.user32.RegisterHotKey(None, new_id, modifiers, key):
            self.error = f"{sequence} could not be registered. Another app may be using it."
            return False
        if self.registered:
            self.user32.UnregisterHotKey(None, self._hotkey_id)
        else:
            self.app.installNativeEventFilter(self)
        self._hotkey_id = new_id
        self.sequence = sequence
        self.registered = True
        self.error = ""
        return True

    def unregister(self):
        if self.registered:
            self.user32.UnregisterHotKey(None, self._hotkey_id)
            self.app.removeNativeEventFilter(self)
            self.registered = False

    def nativeEventFilter(self, event_type, message):
        if self.registered and event_type in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            event = wintypes.MSG.from_address(int(message))
            if event.message == self.WM_HOTKEY and event.wParam == self._hotkey_id:
                QTimer.singleShot(0, self.callback)
                return True, 0
        return False, 0
