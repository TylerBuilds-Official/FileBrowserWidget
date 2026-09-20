"""The parts of a Windows 11 flyout that the compositor draws, not the widget."""
import ctypes
import os
from ctypes import wintypes

USE_IMMERSIVE_DARK_MODE = 20
WINDOW_CORNER_PREFERENCE = 33
BORDER_COLOR = 34
SYSTEMBACKDROP_TYPE = 38
CORNER_ROUND = 2
BACKDROP_NONE = 1
BACKDROP_TRANSIENT = 3

PERSONALIZE_KEY = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"

_theme = {"dark": True, "border": "#1a1a1a"}


def transparency_enabled():
    """Windows only puts acrylic behind its own flyouts while the user leaves it switched on."""
    if os.name != "nt":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, PERSONALIZE_KEY) as key:
            return bool(winreg.QueryValueEx(key, "EnableTransparency")[0])
    except OSError:
        return True


def set_theme(dark, border):
    _theme.update(dark=dark, border=border)


def colorref(color):
    """DwmSetWindowAttribute takes 0x00BBGGRR, the reverse of a CSS colour."""
    value = color.lstrip("#")
    return int(value[4:6] + value[2:4] + value[0:2], 16)


def set_attribute(handle, attribute, value):
    data = wintypes.DWORD(value)
    return ctypes.WinDLL("dwmapi").DwmSetWindowAttribute(
        wintypes.HWND(handle), wintypes.DWORD(attribute), ctypes.byref(data), ctypes.sizeof(data))


def style_window(widget):
    """Round the corners and colour the frame; returns each call's HRESULT for checking."""
    if os.name != "nt":
        return {}
    handle = int(widget.winId())
    return {
        "corner": set_attribute(handle, WINDOW_CORNER_PREFERENCE, CORNER_ROUND),
        "dark": set_attribute(handle, USE_IMMERSIVE_DARK_MODE, int(_theme["dark"])),
        "border": set_attribute(handle, BORDER_COLOR, colorref(_theme["border"])),
        # The surfaces are opaque, so ask for a backdrop only when one would show.
        "backdrop": set_attribute(handle, SYSTEMBACKDROP_TYPE,
                                  BACKDROP_TRANSIENT if transparency_enabled() else BACKDROP_NONE),
    }
