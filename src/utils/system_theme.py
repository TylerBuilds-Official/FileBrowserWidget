import os
from pathlib import Path
from string import Template

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPalette

from src.utils import window_effects
from src.utils.assets import asset, read_asset


# Fluent neutrals, as Windows 11 mixes them over its own flyout surfaces.
THEMES = {
    "light": dict(background="#f3f3f3", surface="#fbfbfb", text="#1b1b1b",
                  muted="#5d5d5d", border="#e5e5e5", edge="#d2d2d2", hover="#ededed",
                  pressed="#e5e5e5", selection="#e8e8e8", scrollbar="#8a8a8a"),
    "dark": dict(background="#202020", surface="#2b2b2b", text="#ffffff",
                 muted="#c5c5c5", border="#353535", edge="#1a1a1a", hover="#2d2d2d",
                 pressed="#282828", selection="#323232", scrollbar="#7e7e7e"),
}

ACCENT_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Accent"


def accent_shades():
    """The seven shades Windows keeps of the user's accent colour, lightest first."""
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, ACCENT_KEY) as key:
                blob = winreg.QueryValueEx(key, "AccentPalette")[0]
            return [QColor(blob[i * 4], blob[i * 4 + 1], blob[i * 4 + 2]) for i in range(7)]
        except (OSError, IndexError, TypeError):
            pass
    base = QColor("#0078d4")
    return ([base.lighter(160), base.lighter(140), base.lighter(120), base]
            + [base.darker(120), base.darker(140), base.darker(160)])


def luminance(color):
    channels = []
    for value in (color.redF(), color.greenF(), color.blueF()):
        channels.append(value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def contrast(first, second):
    lighter, darker = sorted((luminance(first), luminance(second)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def accent_colors(theme):
    """Windows fills with a set shade; text and focus rings need one the surface can carry."""
    shades = accent_shades()
    background = QColor(THEMES[theme]["background"])
    fill = shades[1] if theme == "dark" else shades[4]
    steps = (3, 2, 1, 0) if theme == "dark" else (3, 4, 5, 6)
    readable = next((shades[step] for step in steps
                     if contrast(shades[step], background) >= 3), shades[steps[-1]])
    on_fill = "#000000" if contrast(fill, QColor("#000000")) > contrast(fill, QColor("#ffffff")) else "#ffffff"
    return dict(accent=readable.name(), accent_fill=fill.name(), accent_text=on_fill)


class SystemTheme(QObject):
    """Apply Light/Dark/System and follow Qt's Windows theme notifications."""

    theme_changed = pyqtSignal(str)
    MODES = ("system", "light", "dark")

    def __init__(self, app, settings=None):
        super().__init__(app)
        self.app = app
        self.settings = settings
        self._applying = False
        self.mode = "system"
        self.effective_theme = "light"
        self._stylesheet = Template(read_asset("styles.qss"))
        self.app.styleHints().colorSchemeChanged.connect(self._system_changed)
        saved = settings.value("appearance/theme", "system") if settings is not None else "system"
        self.set_mode(saved if saved in self.MODES else "system")

    def set_mode(self, mode):
        if mode not in self.MODES:
            raise ValueError(f"Unknown theme mode: {mode}")
        self.mode = mode
        self._applying = True
        try:
            scheme = {"system": Qt.ColorScheme.Unknown,
                      "light": Qt.ColorScheme.Light,
                      "dark": Qt.ColorScheme.Dark}[mode]
            self.app.styleHints().setColorScheme(scheme)
            self._apply()
        finally:
            self._applying = False
        if self.settings is not None:
            self.settings.setValue("appearance/theme", mode)

    def _system_changed(self, scheme):
        if self.mode == "system" and not self._applying:
            # Qt updates its palette after emitting colorSchemeChanged.
            QTimer.singleShot(0, self._apply)

    def _apply(self):
        if self.mode == "system":
            dark = self.app.styleHints().colorScheme() == Qt.ColorScheme.Dark
            effective = "dark" if dark else "light"
        else:
            effective = self.mode
        colors = dict(THEMES[effective])
        colors.update(accent_colors(effective))
        colors["chevron"] = asset(f"icons/chevron-down-{effective}.svg")
        # checkmark-light.svg is the white glyph and sits on a dark accent fill, and the reverse.
        checkmark = "light" if colors["accent_text"] == "#ffffff" else "dark"
        colors["checkmark"] = asset(f"icons/checkmark-{checkmark}.svg")
        palette = QPalette()
        roles = {
            "Window": "background", "WindowText": "text", "Base": "surface",
            "AlternateBase": "hover", "Text": "text", "Button": "surface",
            "ButtonText": "text", "ToolTipBase": "surface", "ToolTipText": "text",
            "Highlight": "accent", "Link": "accent", "PlaceholderText": "muted",
        }
        for role, token in roles.items():
            palette.setColor(getattr(QPalette.ColorRole, role), QColor(colors[token]))
        palette.setColor(QPalette.ColorRole.HighlightedText,
                         QColor("#ffffff" if effective == "light" else "#1a1a1a"))
        for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText,
                     QPalette.ColorRole.ButtonText):
            palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(colors["muted"]))
        self.app.setPalette(palette)
        self.app.setStyleSheet(self._stylesheet.substitute(colors))
        window_effects.set_theme(effective == "dark", colors["edge"])
        for window in self.app.topLevelWidgets():
            if window.isVisible():
                window_effects.style_window(window)
        self.effective_theme = effective
        self.theme_changed.emit(effective)
