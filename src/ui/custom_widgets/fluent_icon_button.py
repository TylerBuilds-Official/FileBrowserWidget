from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton


class FluentIconButton(QPushButton):
    """A command button drawn from Segoe Fluent Icons, the font Windows draws its own chrome with.

    The glyph is the button's text, so it follows the theme colour, the font size, and the
    display scale without any painting of our own.
    """

    GLYPHS = {
        "back": "",
        "forward": "",
        "up": "",
        "home": "",
        "settings": "",
        "filter": "",
        "star": "",
        "star-filled": "",
    }

    def __init__(self, glyph, label, parent=None):
        super().__init__(self.GLYPHS[glyph], parent)
        # The size lives in the stylesheet: a fixed size here fights its min-height and clips.
        self.setProperty("role", "iconButton")
        self.setAccessibleName(label)
        self.setToolTip(label)

    def set_glyph(self, glyph):
        self.setText(self.GLYPHS[glyph])

    def set_state(self, **states):
        """Restyle from a stylesheet property, which Qt only re-reads after a repolish."""
        changed = False
        for name, value in states.items():
            value = "true" if value else "false"
            if self.property(name) != value:
                self.setProperty(name, value)
                changed = True
        if changed:
            self.style().unpolish(self)
            self.style().polish(self)
