from PyQt6.QtWidgets import QWidget, QApplication
from PyQt6.QtCore import QMimeData, QUrl, pyqtSignal, Qt
from PyQt6.QtGui import QDrag


class FileRowWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.star_button = None
        self.icon_label = None
        self.path = None
        self.press_position = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Opening waits for the release: a press that turns into a drag must not launch.
            self.press_position = event.position().toPoint()
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
        self.refresh_star()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.refresh_star()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.refresh_star()
