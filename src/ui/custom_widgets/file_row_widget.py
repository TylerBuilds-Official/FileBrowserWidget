from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import QMimeData, QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QDrag


class FileRowWidget(QWidget):
    clicked = pyqtSignal()
    middle_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.star_button = None
        self.icon_label = None
        self.path = None
        self.is_folder = False
        self.press_position = None
        self.middle_pressed = False

    def mousePressEvent(self, event):
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

    def refresh_star(self):
        """An unpinned star waits for its row, the way Explorer reveals its checkboxes."""
        if self.star_button is None:
            return
        pinned = self.star_button.property("pinned") == "true"
        active = self.underMouse() or self.hasFocus() or self.star_button.hasFocus()
        self.star_button.set_state(quiet=not (pinned or active))

    def enterEvent(self, event):
        super().enterEvent(event)
        self.refresh_star()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.press_position = None
        self.middle_pressed = False
        self.refresh_star()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.refresh_star()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.refresh_star()
