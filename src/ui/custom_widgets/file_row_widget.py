from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import QMimeData, QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QDrag


class FileRowWidget(QWidget):
    """One item of the list. What it needs from the panel it is told directly: an event filter
    on every row would put every event on every row through Python, most of them on a rebuild."""

    clicked = pyqtSignal()
    middle_clicked = pyqtSignal()
    pressed = pyqtSignal()  # Any button, before the row acts on it.

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.star_button = None
        self.icon_label = None
        self.cascade = None  # Told when the row goes, so a level fanned out from it can follow.
        self.path = None
        self.is_folder = False
        self.hovered = False
        self.press_position = None
        self.middle_pressed = False

    def keyPressEvent(self, event):
        # Enter or Space opens the row, as a click does; anything else is the panel's to handle.
        if event.modifiers() == Qt.KeyboardModifier.NoModifier and event.key() in (
            Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space,
        ):
            if not event.isAutoRepeat():
                self.clicked.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        self.pressed.emit()
        if event.button() == Qt.MouseButton.LeftButton:
            # Opening waits for the release: a press that turns into a drag must not launch.
            self.press_position = event.position().toPoint()
            event.accept()
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.middle_pressed = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.press_position is None or self.path is None:
            super().mouseMoveEvent(event)
            return
        moved = (event.position().toPoint() - self.press_position).manhattanLength()
        if moved < QApplication.startDragDistance():
            return
        self.press_position = None
        self.start_drag()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.press_position is not None:
            self.press_position = None
            self.clicked.emit()
        elif event.button() == Qt.MouseButton.MiddleButton and self.middle_pressed:
            self.middle_pressed = False
            self.middle_clicked.emit()
        else:
            super().mouseReleaseEvent(event)

    def start_drag(self):
        """Hand the file to whatever the pointer lands on, as a drag from Explorer would."""
        drag = QDrag(self)
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(str(self.path))])
        drag.setMimeData(data)
        if self.icon_label is not None and not self.icon_label.pixmap().isNull():
            drag.setPixmap(self.icon_label.pixmap())
        drag.exec(Qt.DropAction.CopyAction | Qt.DropAction.MoveAction | Qt.DropAction.LinkAction,
                  Qt.DropAction.CopyAction)

    def set_cascaded(self, cascaded: bool):
        """Stay lit while a cascade menu fans out from this row, as an open menu title does."""

        value = "true" if cascaded else "false"
        if self.property("cascaded") == value:
            return
        self.setProperty("cascaded", value)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_hovered(self, hovered: bool):
        """Lit while the pointer is over the row, as far as the panel knows.

        Qt's own :hover cannot carry this. While a cascade level is open the popup takes every
        mouse event, so the rows hear no Enter or Leave: the next row would never light, and
        the one the pointer left would stay lit. The cascade reports the pointer instead then.
        """

        if self.hovered == hovered:
            return
        self.hovered = hovered
        self.setProperty("hovered", "true" if hovered else "false")
        self.style().unpolish(self)
        self.style().polish(self)
        self.refresh_star()

    def refresh_star(self):
        """An unpinned star waits for its row, the way Explorer reveals its checkboxes."""
        if self.star_button is None:
            return
        pinned = self.star_button.property("pinned") == "true"
        active = self.hovered or self.hasFocus() or self.star_button.hasFocus()
        self.star_button.set_state(quiet=not (pinned or active))

    def enterEvent(self, event):
        super().enterEvent(event)
        self.set_hovered(True)

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.press_position = None
        self.middle_pressed = False
        self.set_hovered(False)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.set_hovered(False)  # A hidden row is under nothing, whatever Qt last told it.
        if self.cascade is not None:
            self.cascade.row_hidden(self)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.refresh_star()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.refresh_star()
