from time import monotonic

from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from src.ui.custom_widgets.file_row_widget import FileRowWidget


class KeyboardHandler(QObject):
    """Browser shortcuts and file-row keyboard input, owned by the browser."""

    TYPE_SECONDS = 1.0

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.shortcuts = []
        self.typed = ""
        self.typed_at = 0.0
        browser.installEventFilter(self)  # Letters typed anywhere in the panel reach the list.
        for key, action in (
            ("Ctrl+F", browser.focus_search),
            ("Alt+Left", browser.go_back),
            ("Backspace", browser.go_back),
            ("Alt+Right", browser.go_forward),
            ("Alt+Up", browser.go_up),
            ("Alt+Home", browser.go_home),
            ("F5", browser.refresh_files),
            ("Ctrl+R", browser.refresh_files),
            ("Ctrl+C", browser.copy_focused),
            ("Delete", browser.delete_focused),
            ("Alt+Return", browser.properties_focused),
            ("Alt+Enter", browser.properties_focused),
            ("Right", lambda: browser.cascade.open_focused()),
            ("Left", lambda: browser.cascade.close()),
            ("Up", lambda: self.move_focus(-1)),
            ("Down", lambda: self.move_focus(1)),
            ("Home", lambda: self.move_focus(0, edge=True)),
            ("End", lambda: self.move_focus(-1, edge=True)),
        ):
            self.add_shortcut(key, browser.content, action)
        self.add_shortcut("Esc", browser, self.close_panel)

    def add_shortcut(self, key, parent, action):
        shortcut = QShortcut(QKeySequence(key), parent)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.setAutoRepeat(False)
        shortcut.activated.connect(action)
        self.shortcuts.append(shortcut)

    def register_row(self, row):
        row.installEventFilter(self)

    def rows(self) -> list[FileRowWidget]:
        layout = self.browser.file_list_layout

        return [layout.itemAt(i).widget() for i in range(layout.count())
                if isinstance(layout.itemAt(i).widget(), FileRowWidget)]

    def focus_row(self, row: FileRowWidget):
        row.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.browser.scroll_area.ensureWidgetVisible(row)

    def move_focus(self, step, edge=False):
        rows = self.rows()
        if not rows:
            return
        focused = self.browser.focusWidget()
        if edge:
            index = step
        elif focused in rows:
            index = max(0, min(len(rows) - 1, rows.index(focused) + step))
        else:
            index = 0 if step > 0 else len(rows) - 1
        self.focus_row(rows[index])

    def jump_to_typed(self, text: str) -> bool:
        """Typing a name's first letters moves focus to it, as Explorer does; search stays Ctrl+F.

        Letters typed within a second build a prefix. The same letter again steps through
        the names starting with it.
        """

        now = monotonic()
        if now - self.typed_at > self.TYPE_SECONDS:
            self.typed = ""
        self.typed_at = now
        letter = text.casefold()
        cycling = bool(self.typed) and self.typed == self.typed[0] * len(self.typed) and letter == self.typed[0]
        self.typed = self.typed + letter
        prefix = letter if cycling else self.typed
        rows = self.rows()
        if not rows:
            return False
        focused = self.browser.focusWidget()
        start = rows.index(focused) if focused in rows else -1
        # A single letter means the next such name, as in Explorer; a longer prefix may stay put.
        if cycling or len(prefix) == 1 or start < 0:
            start += 1
        for offset in range(len(rows)):
            row = rows[(start + offset) % len(rows)]
            if row.path.name.casefold().startswith(prefix):
                self.focus_row(row)
                return True

        return False

    def close_panel(self):
        if self.browser.settings_modal.isVisible():
            self.browser.settings_modal.hide_settings()
        elif self.browser.filter_menu.isVisible():
            self.browser.filter_menu.close()
        elif self.browser.search_edit.text():
            self.browser.search_edit.clear()
        else:
            self.browser.hide()

    def is_typing(self, event) -> bool:
        """A plain printable key, meant for the list rather than a control or a shortcut."""

        text = event.text()
        if not text or not text.isprintable() or text.isspace():
            return False
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            return False

        return not self.browser.settings_modal.isVisible()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(watched, FileRowWidget):
            if event.modifiers() == Qt.KeyboardModifier.NoModifier and event.key() in (
                Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space,
            ):
                if not event.isAutoRepeat():
                    watched.clicked.emit()
                return True
        elif event.type() == QEvent.Type.KeyPress and watched is self.browser and self.is_typing(event):
            self.jump_to_typed(event.text())
            return True
        return super().eventFilter(watched, event)
