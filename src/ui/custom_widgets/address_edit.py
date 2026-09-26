from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QLineEdit


class AddressEdit(QLineEdit):
    """The folder's path as text, the way Explorer's address bar becomes one when clicked.

    Enter asks to go where it says; Esc or clicking away puts the breadcrumbs back. The panel
    binds Up, Down and Esc for its list, so the edit claims those keys while it has them.
    """

    submitted = pyqtSignal(str)
    cancelled = pyqtSignal()

    OWN_KEYS = (Qt.Key.Key_Up, Qt.Key.Key_Down, Qt.Key.Key_Escape)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("addressEdit")
        self.setAccessibleName("Address")
        self.returnPressed.connect(lambda: self.submitted.emit(self.text()))

    def event(self, event):
        # QLineEdit already claims its editing keys this way; these three it leaves to shortcuts.
        if (event.type() == QEvent.Type.ShortcutOverride and event.key() in self.OWN_KEYS
                and event.modifiers() == Qt.KeyboardModifier.NoModifier):
            event.accept()
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        elif event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            event.accept()  # Nothing to move to in one line of text.
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        # Its own right-click menu takes the focus for a moment; anything else is clicking away.
        if self.isVisible() and event.reason() != Qt.FocusReason.PopupFocusReason:
            self.cancelled.emit()
