from PyQt6.QtCore import QObject, QEvent, Qt
from PyQt6.QtGui import QKeySequence, QShortcut

from src.ui.custom_widgets.file_row_widget import FileRowWidget


class KeyboardHandler(QObject):
    """Browser shortcuts and file-row keyboard input, owned by the browser."""

    def __init__(self, browser):
        super().__init__(browser)
        self.browser = browser
        self.shortcuts = []
        for key, action in (
            ("Ctrl+F", browser.focus_search),
            ("Alt+Left", browser.go_back),
            ("Backspace", browser.go_back),
            ("Alt+Right", browser.go_forward),
            ("Alt+Up", browser.go_up),
            ("F5", browser.refresh_files),
            ("Ctrl+R", browser.refresh_files),
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

    def move_focus(self, step, edge=False):
        layout = self.browser.file_list_layout
        rows = [layout.itemAt(i).widget() for i in range(layout.count())
                if isinstance(layout.itemAt(i).widget(), FileRowWidget)]
        if not rows:
            return
        focused = self.browser.focusWidget()
        if edge:
            index = step
        elif focused in rows:
            index = max(0, min(len(rows) - 1, rows.index(focused) + step))
        else:
            index = 0 if step > 0 else len(rows) - 1
        rows[index].setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.browser.scroll_area.ensureWidgetVisible(rows[index])

    def close_panel(self):
        if self.browser.settings_modal.isVisible():
            self.browser.settings_modal.hide_settings()
        elif self.browser.search_edit.text():
            self.browser.search_edit.clear()
        else:
            self.browser.hide()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.KeyPress and isinstance(watched, FileRowWidget):
            if event.modifiers() == Qt.KeyboardModifier.NoModifier and event.key() in (
                Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space,
            ):
                if not event.isAutoRepeat():
                    watched.clicked.emit()
                return True
        return super().eventFilter(watched, event)
