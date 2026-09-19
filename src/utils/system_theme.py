from pathlib import Path
from string import Template

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPalette


THEMES = {
    "light": dict(background="#f3f3f3", surface="#ffffff", text="#1a1a1a",
                  muted="#616161", border="#dedede", hover="#e9e9e9",
                  pressed="#dddddd", accent="#005fb8", selection="#e5f1fb",
                  scrollbar="#8a8a8a"),
    "dark": dict(background="#202020", surface="#2b2b2b", text="#f2f2f2",
                 muted="#b5b5b5", border="#404040", hover="#363636",
                 pressed="#414141", accent="#60cdff", selection="#233e4c",
                 scrollbar="#858585"),
}


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
        self._stylesheet = Template(
            (Path(__file__).resolve().parents[1] / "assets" / "styles.qss")
            .read_text(encoding="utf-8")
        )
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
        icons = Path(__file__).resolve().parents[1] / "assets" / "icons"
        colors["chevron"] = (icons / f"chevron-down-{effective}.svg").as_posix()
        colors["checkmark"] = (icons / f"checkmark-{effective}.svg").as_posix()
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
        self.effective_theme = effective
        self.theme_changed.emit(effective)
