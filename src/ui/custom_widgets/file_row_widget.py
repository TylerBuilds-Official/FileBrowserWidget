from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal, Qt

class FileRowWidget(QWidget):
    clicked = pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
            self.clicked.emit()
        else:
            super().mousePressEvent(event)
